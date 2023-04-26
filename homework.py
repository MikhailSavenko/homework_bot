import logging
import time
import requests
import os
from dotenv import load_dotenv
import telegram
import sys
from more_exceptions import UndocumentedStatus

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
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
    is_token = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

    if not all(is_token):
        error_message = 'Переменная окружения не задана'
        logging.critical(error_message)
        raise ValueError(error_message)
    return True


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

    if response_api.status_code != 200:
        logging.error('Ошибка при запросе API')
        raise Exception(f'Ошибка при запросе API: код ответа'
                        f'{response_api.status_code}')
    response = response_api.json()
    logging.info(type(response))
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
    if isinstance(d := response, list):
        raise TypeError('Ожидается словарь, получен список')
    if d.get('homeworks') is None:
        raise KeyError('Ключ словаря None')
    if not isinstance(response, dict):
        raise TypeError('В ответ от API ожидался тип данных словарь.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Ожидался тип данных список')
    homework = homeworks[0]
    return homework


def parse_status(homework):
    """Извлекает статус проверки работы из ответа API."""
    PREVIOUS_STATUS = None
    logging.info(type(homework))
    try:
        if not homework:
            raise ValueError('Пустой список')
        if 'status' not in homework:
            raise KeyError('Нет ключа "status"')
        status = homework.get('status')
        logging.info(status)
        if 'homework_name' not in homework:
            raise KeyError('Нет ключа "homeworks"')
        homework_name = homework.get('homework_name')
        current_status = status
        if current_status == PREVIOUS_STATUS:
            pass
        else:
            if status in HOMEWORK_VERDICTS:
                verdict = HOMEWORK_VERDICTS[status]
                PREVIOUS_STATUS = current_status
                return f'Изменился статус проверки работы "{homework_name}".'\
                       f'{verdict}'
            else:
                raise UndocumentedStatus('Неизвестный статус работы')
    except AttributeError:
        logging.error('Ошибка при попытке извлечения статуса работы из ответа'
                      'API.')
    return None


def main():
    """Основная логика работы бота."""
    # Проверяем переменные окружения
    check = check_tokens()
    if check is ValueError:
        sys.exit(1)
    logging.debug('Все переменные окружения доступны')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    period_time_seconds = PERIOD_TIME_DAYS * 24 * 60 * 60
    timestamp = int(time.time() - period_time_seconds)
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)

        except Exception as error:
            logging.error(f'Произошла ошибка: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, f'Произошла ошибка: {error}')
            # Устанавливаем задержку выполнения кода на определенный период.
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
