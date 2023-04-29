import logging
import time
import requests
import os
from dotenv import load_dotenv
import telegram
import sys
from more_exceptions import UndocumentedStatus
from http import HTTPStatus


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='{asctime}, {levelname}, {message}, {name}',
    style='{',
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
PERIOD_TIME_DAYS = 30
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """
    Проверяет наличие необходимых переменных окружения.

    :raises Exception: Если одна из переменных окружения отсутствует.
    """
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


def send_message(bot, message):
    """
    Отправляет сообщение в чат.

    :param bot: Экземпляр объекта Bot из библиотеки python-telegram-bot.
    :type bot: telegram.Bot
    :param message: Текст сообщения.
    :type message: str
    :return: None
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено')
    except telegram.error.TelegramError:
        logging.error('Произошла ошибка отправки сообщения ботом')


def get_api_answer(timestamp):
    """
    Делает запрос к API и возвращает ответ в виде словаря.
    :param timestamp: Unix-время в формате int, начиная с которого нужно
    получить данные.
    :type timestamp: int
    :return: Словарь с ответом от API.
    :rtype: dict
    :raises Exception: В случае ошибки при запросе API (код ответа не равен
    200).
    """
    try:
        params = {'from_date': timestamp}
        response_api = requests.get(url=ENDPOINT, params=params,
                                    headers=HEADERS)
    except requests.RequestException as e:
        logging.error(f'Ошибка при запросе API: {e}')

    if response_api.status_code != HTTPStatus.OK:
        raise Exception(f'Ошибка при запросе API: код ответа'
                        f'{response_api.status_code}')
    response = response_api.json()
    return response


def check_response(response):
    """
    Проверяет ответ от API на наличие ожидаемых данных и их тип.
    Аргументы:
    - response: dict - Ответ от API в виде словаря.
    Возвращает:
    - list - Список значений, соответствующих ключу 'homeworks' в ответе от
    API.
    Исключения:
    - TypeError: Если тип данных аргумента response не является словарем или
    'homeworks' в response не является списком.
    - KeyError: Если в response отсутствует ключ 'homeworks'.
    """
    if not isinstance(response, dict):
        raise TypeError('В ответ от API ожидался тип данных словарь')
    if (homeworks := response.get('homeworks')) is None:
        raise KeyError('В словаре отсутствует ключ "homeworks"')
    if not isinstance(homeworks, list):
        raise TypeError('Значение ключа "homeworks" должно  быть списком')
    return response


def parse_status(homework):
    """Извлекает статус проверки работы из ответа API."""
    try:
        if (status := homework.get('status')) is None:
            raise KeyError('В словаре отсутствует ключ "status"')
        if status not in HOMEWORK_VERDICTS:
            raise UndocumentedStatus('Неизвестный статус работы')
        if (homework_name := homework.get('homework_name')) is None:
            raise KeyError('В словаре отсутствует ключ "homework_name"')
        verdict = HOMEWORK_VERDICTS[status]
        return (f'Изменился статус проверки работы "{homework_name}".'
                f'{verdict}')
    except (KeyError, UndocumentedStatus) as e:
        logging.error((f'Ошибка при попытке извлечения статуса работы из'
                       f'ответа API: {e}'))
        raise e from None


def main():
    """Основная логика работы бота."""
    # Проверяем переменные окружения
    check = check_tokens()
    if check is False:
        error_message = 'Переменная окружения не задана'
        logging.critical(error_message)
        sys.exit(1)
    logging.debug('Все переменные окружения доступны')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    period_time_seconds = PERIOD_TIME_DAYS * 24 * 60 * 60
    timestamp = int(time.time() - period_time_seconds)
    while True:
        try:
            response = get_api_answer(timestamp)
            validated_response = check_response(response)
            homework_list = validated_response['homeworks']
            if not homework_list:
                logging.warning('Список домашних работ пуст')
                continue
            if len(homework_list) > 0:
                homework = homework_list[-1]
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            logging.error(f'Произошла ошибка: {error}')
            message = f'Сбой в работе программы: {error}'
            # Устанавливаем задержку выполнения кода на определенный период.
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
