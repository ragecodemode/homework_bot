import logging
import os
import time
from http import HTTPStatus

import telegram
import requests
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='error.log',
    format=(
        '%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(funcName)s'
    )
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message: str) -> None:
    """отправляет сообщение в Telegram чат."""
    logging.info('Отправка сообщения в телеграмм чат')
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except Exception as error:
        logger.error(f'Сообщение {message} об ошибки: {error}')
    else:
        logging.debug(f'Собщение {message} было отправлено')

def get_api_answer(current_timestamp: int) -> int:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework.status_code != HTTPStatus.OK:
            logger.error(
                f'код ошибки: {homework.status_code}'
                f'заголовок: {HEADERS}, параметр {params}'
            )
            raise ValueError(f'Ендпоинт {ENDPOINT} недоступен.')
        return homework.json()
    except Exception as error:
        message = f'Сбой при запросе к серверу {ENDPOINT}: {error}'
        raise ConnectionAbortedError(message)


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')
    if 'current_date' and 'homeworks' not in response:
        message = 'В ответе отсутствуют необходимые ключи'
        logger.error(message)
        raise ValueError(message)
    if not isinstance(response["homeworks"], list):
        message = (
            f'Неккоректное значение в ответе домашней работы {type(response)}'
            f'ожидали: {list(response)}'
        )
        logger.error(message)
        raise TypeError(message)
    homework = response.get('homeworks')
    if not isinstance(response["homeworks"], list):
        message = (
            f'Неккоректное значение в ответе домашней работы {type(response)}'
            f'ожидали: {list(response)}'
        )
        logger.error(message)
        raise TypeError(message)
    return homework


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if homework.get('homework_name') is None:
        message = f'Отсутствует имя домашней работы {homework_name}'
        logger.error(message)
        raise KeyError(message)
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        message = (
            f'Не верный статус домашней работы {homework_status}'
            f'Доступыне: approved, reviewing, rejected'
        )
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
        TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
        TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID'
    }
    all_tokens = True

    for token in tokens:
        if token is None:
            logging.critical(
                f'Отсутствует переменная окружения {tokens.get(token)}.'
            )
            all_tokens = False
        else:
            logging.info(
                f'Переменная окружения есть {tokens.get(token)}.'
            )
    return all_tokens


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствует обязательная переменная окружения'
        logger.critical(message)
        raise ValueError(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Бот начал работу')
    current_timestamp = int(time.time())
    previous_status = None
    last_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            for homworks in homework:
                if homworks:
                    logging.info('Собщение об изменение статуса отправлена')
                    hw_status = homework[0].get('status')
                    if hw_status != previous_status:
                        previous_status = hw_status
                        message = parse_status(homework[0])
                        send_message(bot, message)
                else:
                    logging.debug('Нет новых статусов')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if str(error) != str(last_error):
                send_message(bot, message)
                last_error = error
                logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
