import logging
import os
import time
from http import HTTPStatus

import telegram
import requests
from dotenv import load_dotenv


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


def get_api_answer(current_timestamp: int) -> int:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as error:
        message = f'Сбой при запросе к эндпоинту {ENDPOINT}: {error}'
        logger.error(message)
        raise ValueError(message)
    if homework.status_code != HTTPStatus.OK:
        logger.error(
            f'код ошибки: {homework.status_code}'
            f'заголовок: {HEADERS}, параметр {params}'
        )
        raise ValueError(f'Сервер {ENDPOINT} недоступен.')
    try:
        homework_json = homework.json()
    except Exception as error:
        message = f'Сбой при переводе в формат json: {error}'
        logger.error(message)
        raise ValueError(message)
    return homework_json


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response['homeworks'], list):
        message = (
            f'Неккоректное значение в ответе домашней работы {type(response)}'
            f'ожидали: {list(response)}'
        )
        logging.info(message)
        raise ValueError(message)
    if type(response) != dict:
        response_type = type(response)
        message = f'Ответ пришёл в неверном формате: {response_type}'
        logger.error(message)
        raise KeyError(message)
    if 'homeworks' not in response:
        message = 'Не найдено верных ключей'
        logging.error(message)
        raise KeyError(message)
    homework = response.get('homeworks')
    return homework


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        message = f'Не верный статус домашней работы {homework_status}'
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]

    for token in tokens:
        if token is None:
            logging.critical(f'Отсутствует переменная окружения {token}.')
            return False
    return True


def main():
    """Основная логика работы бота."""
    load_dotenv()
    global logger

    logging.basicConfig()
    formatter = logging.Formatter(
        '%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(funcName)s'
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
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
