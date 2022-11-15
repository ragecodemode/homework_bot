import logging
import os
import requests
import time
import telegram

from http import HTTPStatus

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)

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
    try:
        logging.info('Отправка сообщения в телеграмм чат')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.info(f'Собщение {message} было отправлено')
    except Exception as error:
        logging.error(f'Сообщение {message} об ошибки: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Сбой при запросе к эндпоинту: {error}'
        logger.error(message)
        raise ValueError(message)
    status_code = homework.status_code
    if status_code != HTTPStatus.OK:
        message = f'Код ошибки: {status_code}'
        logger.error(message)
        raise ValueError(message)
    try:
        homework_json = homework.json()
    except Exception as error:
        message = f'Сбой формата json: {error}'
        logger.error(message)
        raise ValueError(message)
    return homework_json


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) == list:
        response = response[0]
    if type(response) != dict:
        response_type = type(response)
        message = f'Ответ пришёл в неверном формате: {response_type}'
        logging.error(message)
        raise ValueError(message)
    if 'current_date' and 'homeworks' not in response:
        message = 'Не найдено верных ключей'
        logging.error(message)
        raise ValueError(message)
    homework = response.get('homeworks')
    if type(homework) != list:
        message = 'Неккоректное значение в ответе у домашней работы'
        logger.error(message)
        raise ValueError(message)
    return homework


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        message = 'Недокументированный статус домашней работы'
        logger.error(message)
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
            message = f'Переменные окружения не найдены {token}'
            logging.critical(message)
            return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            for homworks in homework:
                if homworks:
                    logging.info('Собщение об изменение статуса отправлена')
                    send_message(bot, parse_status(homework))
            logging.info('Статутс работы изменён')
            time.sleep(RETRY_TIME)
            current_timestamp = response.get('current_date')
            response = get_api_answer(current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
