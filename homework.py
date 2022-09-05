import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

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

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[logging.StreamHandler(stream=sys.stdout)])


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        raise exceptions.SendError(f'Бот не отправил сообщение! - {error}')


def get_api_answer(current_timestamp):
    """Запрос к API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code != HTTPStatus.OK:
        raise exceptions.ApiError('Сбой запроса к API-сервиса')
    else:
        return homework_statuses.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if not (isinstance(response, dict)):
        raise TypeError('Ответ сервера не является словарем!')
    homeworks = response.get('homeworks')

    if homeworks is None:
        raise exceptions.ExceptionResponseError('Ошибка ответа')

    if not isinstance(homeworks, list):
        raise TypeError('Работа с сервера не является списком!')

    if not homeworks:
        raise exceptions.ExceptionListEmpty('Список домашних работ пуст!')
    return homeworks


def parse_status(homework):
    """Извлечение информации о конкретной домашней работе."""
    homework_name = homework['homework_name']
    if 'homework_name' not in homework:
        raise KeyError(f'Ключ {homework_name} отсутствует в ответе сервера')

    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует в ответе сервера')

    homework_status = homework.get('status')

    if homework.get('status') not in HOMEWORK_STATUSES:
        raise KeyError(f'Ключ {homework_status} отсутствует в списке')

    verdict = HOMEWORK_STATUSES[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия переменных окружения."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if check_tokens():
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                for homework in homeworks:
                    last_homework = {
                        homework['homework_name']: homework['status']
                    }
                    message = parse_status(homework)
                    if last_homework != homework['status']:
                        send_message(bot, message)
                        logging.info('Сообщение было отправлено')
                    else:
                        logging.debug('Статус не изменился')
            except Exception as error:
                logging.error(f'Сбой в работе программы: {error}')
                message = f'Сбой в работе программы: {error}'
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            finally:
                time.sleep(RETRY_TIME)
    else:
        logging.critical('Отсутствуют обязательные переменные окружения')


if __name__ == '__main__':
    main()
