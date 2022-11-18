import logging
import os
import time
from http import HTTPStatus

import telegram
import requests
from dotenv import load_dotenv

from logging.handlers import RotatingFileHandler


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
TOKENS = [
    PRACTICUM_TOKEN,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID
]


def send_message(bot, message: str) -> None:
    """отправляет сообщение в Telegram чат."""
    logger.info('Отправка сообщения в телеграмм чат')
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except Exception as error:
        logger.error(f'Сообщение {message} об ошибки: {error}')
    else:
        logger.info(f'Собщение {message} было отправлено')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
    homework_json = homework.json()
    if homework.status_code != HTTPStatus.OK:
        logger.error(f'Эндпоинт {ENDPOINT} недоступен, код ошибки: {homework.status_code}'
                     f'заголовок: {HEADERS}, параметр {params}')
        raise ValueError(f'Сервер {ENDPOINT} недоступен.')
    return homework_json


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response['homeworks'], list):
        message ='Неккоректное значение в ответе у домашней работы'
        logging.info(message)
        raise ValueError(message)
    if type(response) != dict:
        response_type = type(response)
        message = f'Ответ пришёл в неверном формате: {response_type}'
        logger.error(message)
        raise ValueError(message)
    if 'current_date' and 'homeworks' not in response:
        message = 'Не найдено верных ключей'
        logging.error(message)
        raise ValueError(message)
    homework = response.get('homeworks')
    return homework


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        message = 'Не верный статус домашней работы'
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    return tokens


def main():
    """Основная логика работы бота."""
    load_dotenv()
    global logger

    logging.basicConfig(
        level=logging.DEBUG,
        filename='program.log',
        filemode='a',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(funcName)s'
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        'my_logger.log',
        maxBytes=50000000,
        backupCount=5
    ),
    logger.addHandler(handler)

    if not check_tokens():
        message = 'Отсутствует обязательная переменная окружения'
        logger.critical(message)
        raise ValueError(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Бот начал работу')
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            for homworks in homework:
                if homworks:
                    logging.info('Собщение об изменение статуса отправлена')
                    send_message(bot, parse_status(homework[0]))
                else:
                    logging.debug('Нет новых статусов')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
