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

RETRY_PERIOD = 600
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
    if not isinstance(response['homeworks'], list):
        message = (
            f'Неккоректное значение в ответе домашней работы {type(response)}'
            f'ожидали: {list(response)}'
        )
        logging.info(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = f'Не найден верный ключ homeworks {response["homeworks"]}'
        logging.error(message)
        raise ValueError(message)
    homework = response.get('homeworks')
    return homework


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    try:
        homework_name = homework.get('homework_name')
    except Exception as error:
        message = f'Осутсвуют ожидаемые ключи: {error}'
        logging.error(message)
        raise KeyError(message)
    if homework_status not in HOMEWORK_STATUSES:
        message = (
            f'Не верный статус домашней работы {homework_status}'
            'Доступыне: approved, reviewing, rejected'
        )
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES[homework_status]
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
    load_dotenv()
    global logger

    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(funcName)s'
        )
    )
    logger = logging.getLogger(__name__)

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
