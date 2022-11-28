import logging
import os
import time
from http import HTTPStatus
import telegram
import requests
from sys import stdout

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

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
    except Exception as error:
        raise ConnectionError(f'Ошибка:{error}, {ENDPOINT} недоступен.')
    if homework.status_code != HTTPStatus.OK:
        raise ValueError(
            f'Ожидали: {homework.status_code.HTTPStatus.OK}, пришёл: {homework.status_code}'
        )
    return homework.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API отличен от словаря, в ответ пришёл не верный тип данных: {type(response)}'
        )
    if 'current_date' and 'homeworks' not in response:
        raise KeyError('Не хватает нужных ключей: current_date и homeworks')
    homework = response["homeworks"]
    if not isinstance(homework, list):
        raise TypeError(
            f'Ответ API отличен от словаря, в ответ пришёл не верный тип данных: {type(homework)}'
        )
    return homework


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        raise KeyError('Не найдено имя домашней работы')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'Не верный статус домашней работы {homework_status}'
            f'Доступыне: {HOMEWORK_VERDICTS}'
        )
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    all_tokens = True

    for key, value in tokens.items():
        if value is None:
            logging.critical(
                f'Отсутствует переменная окружения {tokens.get(key)}'
            )
            all_tokens = False
        else:
            logging.info(
                f'Переменная окружения есть {tokens.get(key)}'
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
                    logging.debug('Нет новых статусов')
                    current_timestamp = int(time.time())
        except Exception as error:
            if str(error) != str(last_error):
                send_message(bot, message)
                last_error = error
                logger.error(
                    f'Сбой в работе программы: {error},'
                    f'Ошибка эдпоинта: {ENDPOINT},'
                )
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(funcName)s'
        )
    )
    handler = logging.FileHandler(
        os.path.join(os.path.dirname(__file__), 'main.log'),
        mode='a'
    )
    logging.StreamHandler(stream=stdout)
    logger.addHandler(handler)
    main()