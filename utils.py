# -*- coding: utf-8 -*-
import json
import logging
import os
import re
import sqlite3
import aiohttp
import requests
import certifi
import ssl
from deep_translator import GoogleTranslator
from telebot import apihelper
import time
import asyncio
import tempfile
import os

# Разделители для системного промпта
SYSTEM_PROMPT_START = "###SYSTEM_PROMPT_START###"
SYSTEM_PROMPT_END = "###SYSTEM_PROMPT_END###"

def clean_system_prompt_markers(text):
    """Удаляет маркеры системного промпта из текста."""
    original_text = text
    cleaned_text = text.replace(SYSTEM_PROMPT_START, "").replace(SYSTEM_PROMPT_END, "")
    if original_text != cleaned_text:
        logger.info(f"Удалены маркеры системного промпта: {original_text[:50]}... -> {cleaned_text[:50]}...")
    return cleaned_text

def add_system_prompt(prompt):
    """Добавляет системный промпт, окружённый разделителями."""
    return f"{SYSTEM_PROMPT_START}{prompt}{SYSTEM_PROMPT_END}"

def remove_system_prompt(context):
    """Удаляет системный промпт, окружённый разделителями, из контекста."""
    start_marker = SYSTEM_PROMPT_START
    end_marker = SYSTEM_PROMPT_END
    start_idx = context.find(start_marker)
    if start_idx != -1:
        end_idx = context.find(end_marker, start_idx + len(start_marker))
        if end_idx != -1:
            cleaned_context = context[:start_idx] + context[end_idx + len(end_marker):]
            logger.info(f"Удалён системный промпт из контекста: {context[start_idx:end_idx + len(end_marker)][:50]}...")
            return cleaned_context.strip()
    return context.strip()

# Основной логгер
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Новый логгер для детального логирования AI-ответов и контекста
ai_detail_logger = logging.getLogger('ai_details')
ai_detail_logger.setLevel(logging.INFO)
ai_detail_handler = logging.FileHandler("ai_details.log", encoding="utf-8")
ai_detail_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - \n%(message)s\n' + '-'*50))
ai_detail_logger.addHandler(ai_detail_handler)
ai_detail_logger.propagate = False

# Настройка SOCKS5-прокси
PROXY = "socks5://localhost:3128"
apihelper.proxy = {'https': PROXY}

translation_session = requests.Session()
translation_session.proxies = {"http": PROXY, "https": PROXY}
translation_session.verify = certifi.where()
requests.packages.urllib3.disable_warnings()

translator = GoogleTranslator(source='ru', target='en', session=translation_session)
translator_reverse = GoogleTranslator(source='en', target='ru', session=translation_session)

def temp_message_livetime(config=None):
    """Возвращает время жизни временных сообщений из конфига или значение по умолчанию."""
    if config and "temp_message_lifetime" in config:
        return config["temp_message_lifetime"]
    return 30

def is_english(text):
    """Проверяет, состоит ли текст только из английских символов."""
    logger.info(f"Проверка текста на английский: {text[:50]}...")
    return all(ord(char) < 128 for char in text)

def clean_text(text):
    """Очищает текст от лишних повторений и нежелательных суффиксов."""
    logger.info(f"Очистка текста: {text[:50]}...")
    text = re.sub(r'(.)\1{3,}', r'\1\1', text)
    text = re.sub(r'(\w+)(un|yu|anon)\b', r'\1', text)
    cleaned = text.strip()
    logger.info(f"Текст после очистки: {cleaned[:50]}...")
    return cleaned

def split_message(text, max_length=4096):
    """Разбивает длинный текст на части для отправки в Telegram."""
    logger.info(f"Разбиение текста, длина: {len(text)}")
    if len(text) <= max_length:
        logger.info("Текст короче лимита, возвращаем как есть")
        return [text]
    parts = []
    current_part = ""
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 <= max_length:
            current_part += line + "\n"
        else:
            parts.append(current_part.strip())
            current_part = line + "\n"
    if current_part:
        parts.append(current_part.strip())
    logger.info(f"Текст разбит на {len(parts)} частей")
    return parts

def get_default_character_name():
    """Возвращает имя персонажа по умолчанию."""
    return "Vrok"

def init_db(db_file="context.db"):
    """Инициализирует базу данных, проверяя структуру таблиц. Завершает выполнение при несоответствии."""
    logger.info(f"Инициализация базы данных: {db_file}")
    
    # Проверяем, существует ли файл базы данных
    if not os.path.exists(db_file):
        logger.info("База данных не существует, создаём таблицы")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Создаём таблицу user_context
        cursor.execute('''
            CREATE TABLE user_context (
                chat_id INTEGER PRIMARY KEY,
                context TEXT NOT NULL
            )
        ''')
        logger.info("Создана таблица user_context")

        # Создаём таблицу chat_settings
        cursor.execute(f'''
            CREATE TABLE chat_settings (
                chat_id INTEGER PRIMARY KEY,
                user_translate_enabled INTEGER NOT NULL DEFAULT 1,
                ai_translate_enabled INTEGER NOT NULL DEFAULT 1,
                memory TEXT DEFAULT '',
                character_name TEXT DEFAULT '{get_default_character_name()}',
                user_character_name TEXT DEFAULT 'User'
            )
        ''')
        logger.info("Создана таблица chat_settings")

        # Создаём таблицу response_times
        cursor.execute('''
            CREATE TABLE response_times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                response_time REAL NOT NULL,
                timestamp INTEGER NOT NULL
            )
        ''')
        logger.info("Создана таблица response_times для статистики времени генерации")

        conn.commit()
        conn.close()
        logger.info(f"База данных создана и готова: {db_file}")
        return

    # Если база существует, проверяем структуру
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Ожидаемая структура таблиц
    expected_tables = {
        "user_context": [
            ("chat_id", "INTEGER", 1),  # имя, тип, primary key
            ("context", "TEXT", 0)
        ],
        "chat_settings": [
            ("chat_id", "INTEGER", 1),
            ("user_translate_enabled", "INTEGER", 0),
            ("ai_translate_enabled", "INTEGER", 0),
            ("memory", "TEXT", 0),
            ("character_name", "TEXT", 0),
            ("user_character_name", "TEXT", 0)
        ],
        "response_times": [
            ("id", "INTEGER", 1),
            ("chat_id", "INTEGER", 0),
            ("response_time", "REAL", 0),
            ("timestamp", "INTEGER", 0)
        ]
    }

    # Проверяем наличие и структуру каждой таблицы
    for table_name, expected_columns in expected_tables.items():
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        if not columns:
            logger.error(f"Таблица {table_name} отсутствует в базе данных!")
            conn.close()
            raise SystemExit(f"Ошибка: таблица {table_name} отсутствует в базе данных. Проверьте структуру базы.")

        # Проверяем количество и имена столбцов
        actual_columns = [(col[1], col[2], 1 if col[5] else 0) for col in columns]  # имя, тип, primary key
        if len(actual_columns) != len(expected_columns):
            logger.error(f"Несоответствие структуры таблицы {table_name}: ожидалось {len(expected_columns)} столбцов, найдено {len(actual_columns)}")
            conn.close()
            raise SystemExit(f"Ошибка: несоответствие структуры таблицы {table_name}. Проверьте базу данных.")

        # Проверяем каждый столбец
        for expected, actual in zip(expected_columns, actual_columns):
            exp_name, exp_type, exp_pk = expected
            act_name, act_type, act_pk = actual
            if exp_name != act_name or exp_type != act_type or exp_pk != act_pk:
                logger.error(f"Несоответствие в таблице {table_name}: ожидался столбец {exp_name} ({exp_type}, PK={exp_pk}), найден {act_name} ({act_type}, PK={act_pk})")
                conn.close()
                raise SystemExit(f"Ошибка: неверная структура таблицы {table_name}. Проверьте базу данных.")

        logger.info(f"Структура таблицы {table_name} соответствует ожидаемой")

    # Завершение работы с базой данных
    conn.close()
    logger.info(f"База данных готова: {db_file}")

def save_context(chat_id, context, db_file="context.db"):
    """Сохраняет контекст разговора для указанного chat_id."""
    logger.info(f"Сохранение контекста для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_context (chat_id, context) VALUES (?, ?)', (chat_id, context))
    conn.commit()
    conn.close()
    logger.info(f"Контекст сохранён: {context[:50]}...")

def load_context(chat_id, db_file="context.db"):
    """Загружает контекст разговора для указанного chat_id."""
    logger.info(f"Загрузка контекста для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT context FROM user_context WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    context = result[0] if result else ""
    logger.info(f"Загружен контекст: {context[:50]}...")
    return context

def clear_context(chat_id, db_file="context.db"):
    """Очищает контекст разговора для указанного chat_id."""
    logger.info(f"Очистка контекста для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_context WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()
    logger.info("Контекст очищен")

# Функции для работы с настройками (без изменений)
def set_user_translate_enabled(chat_id, enabled, db_file="context.db"):
    """Устанавливает настройку перевода сообщений пользователя."""
    logger.info(f"Установка user_translate_enabled для chat_id: {chat_id} на {enabled}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, user_translate_enabled, ai_translate_enabled, memory, character_name, user_character_name) VALUES (?, ?, COALESCE((SELECT ai_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), COALESCE((SELECT memory FROM chat_settings WHERE chat_id = ?), ""), COALESCE((SELECT character_name FROM chat_settings WHERE chat_id = ?), "Person"), COALESCE((SELECT user_character_name FROM chat_settings WHERE chat_id = ?), "User"))', (chat_id, 1 if enabled else 0, chat_id, chat_id, chat_id, chat_id))
    conn.commit()
    conn.close()
    logger.info("Настройка сохранена")

def set_ai_translate_enabled(chat_id, enabled, db_file="context.db"):
    """Устанавливает настройку перевода ответов ИИ."""
    logger.info(f"Установка ai_translate_enabled для chat_id: {chat_id} на {enabled}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, user_translate_enabled, ai_translate_enabled, memory, character_name, user_character_name) VALUES (?, COALESCE((SELECT user_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), ?, COALESCE((SELECT memory FROM chat_settings WHERE chat_id = ?), ""), COALESCE((SELECT character_name FROM chat_settings WHERE chat_id = ?), "Person"), COALESCE((SELECT user_character_name FROM chat_settings WHERE chat_id = ?), "User"))', (chat_id, chat_id, 1 if enabled else 0, chat_id, chat_id, chat_id))
    conn.commit()
    conn.close()
    logger.info("Настройка сохранена")

def set_memory(chat_id, memory, db_file="context.db"):
    """Устанавливает memory для ИИ."""
    logger.info(f"Установка memory для chat_id: {chat_id}: {memory[:50]}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, user_translate_enabled, ai_translate_enabled, memory, character_name, user_character_name) VALUES (?, COALESCE((SELECT user_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), COALESCE((SELECT ai_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), ?, COALESCE((SELECT character_name FROM chat_settings WHERE chat_id = ?), "Person"), COALESCE((SELECT user_character_name FROM chat_settings WHERE chat_id = ?), "User"))', (chat_id, chat_id, chat_id, memory, chat_id, chat_id))
    conn.commit()
    conn.close()
    logger.info("Memory установлено")

def set_character_name(chat_id, character_name, db_file="context.db"):
    """Устанавливает имя персонажа."""
    logger.info(f"Установка character_name для chat_id: {chat_id}: {character_name}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, user_translate_enabled, ai_translate_enabled, memory, character_name, user_character_name) VALUES (?, COALESCE((SELECT user_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), COALESCE((SELECT ai_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), COALESCE((SELECT memory FROM chat_settings WHERE chat_id = ?), ""), ?, COALESCE((SELECT user_character_name FROM chat_settings WHERE chat_id = ?), "User"))', (chat_id, chat_id, chat_id, chat_id, character_name, chat_id))
    conn.commit()
    conn.close()
    logger.info("Имя персонажа установлено")

def set_user_character_name(chat_id, user_character_name, db_file="context.db"):
    """Устанавливает имя пользователя."""
    logger.info(f"Установка user_character_name для chat_id: {chat_id}: {user_character_name}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, user_translate_enabled, ai_translate_enabled, memory, character_name, user_character_name) VALUES (?, COALESCE((SELECT user_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), COALESCE((SELECT ai_translate_enabled FROM chat_settings WHERE chat_id = ?), 1), COALESCE((SELECT memory FROM chat_settings WHERE chat_id = ?), ""), COALESCE((SELECT character_name FROM chat_settings WHERE chat_id = ?), "Person"), ?)', (chat_id, chat_id, chat_id, chat_id, chat_id, user_character_name))
    conn.commit()
    conn.close()
    logger.info("Имя пользователя установлено")

def get_memory(chat_id, db_file="context.db"):
    """Получает memory для ИИ."""
    logger.info(f"Получение memory для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT memory FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    memory = result[0] if result else ""
    logger.info(f"Memory: {memory[:50]}...")
    return memory

def get_user_translate_enabled(chat_id, db_file="context.db"):
    """Получает настройку перевода сообщений пользователя."""
    logger.info(f"Получение user_translate_enabled для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT user_translate_enabled FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    enabled = result[0] if result is not None else 1
    logger.info(f"User translate enabled: {enabled}")
    return enabled

def get_ai_translate_enabled(chat_id, db_file="context.db"):
    """Получает настройку перевода ответов ИИ."""
    logger.info(f"Получение ai_translate_enabled для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT ai_translate_enabled FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    enabled = result[0] if result is not None else 1
    logger.info(f"AI translate enabled: {enabled}")
    return enabled

def get_character_name(chat_id, db_file="context.db"):
    """Получает имя персонажа."""
    logger.info(f"Получение character_name для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT character_name FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    name = result[0] if result else get_default_character_name()  # Используем функцию
    logger.info(f"Character name: {name}")
    return name

def get_user_character_name(chat_id, db_file="context.db"):
    """Получает имя пользователя."""
    logger.info(f"Получение user_character_name для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT user_character_name FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    name = result[0] if result else "User"
    logger.info(f"User character name: {name}")
    return name

# Новые функции для работы со статистикой времени генерации
def save_response_time(chat_id, response_time, db_file="context.db"):
    """Сохраняет время генерации ответа, ограничивая до 5 записей на чат."""
    logger.info(f"Сохранение времени генерации {response_time:.2f} сек для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    timestamp = int(time.time())
    cursor.execute('INSERT INTO response_times (chat_id, response_time, timestamp) VALUES (?, ?, ?)', 
                   (chat_id, response_time, timestamp))
    
    # Удаляем старые записи, оставляя только последние 5
    cursor.execute('DELETE FROM response_times WHERE chat_id = ? AND id NOT IN '
                   '(SELECT id FROM response_times WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 5)', 
                   (chat_id, chat_id))
    conn.commit()
    conn.close()
    logger.info(f"Время генерации сохранено для chat_id: {chat_id}")

def get_avg_response_time(chat_id, db_file="context.db"):
    """Возвращает среднее время генерации на основе последних 5 ответов."""
    logger.info(f"Получение среднего времени генерации для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT response_time FROM response_times WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 5', 
                   (chat_id,))
    times = cursor.fetchall()
    conn.close()
    if len(times) > 1:  # Нужно больше одного ответа для статистики
        avg_time = sum(t[0] for t in times) / len(times)
        logger.info(f"Среднее время генерации: {avg_time:.2f} сек, на основе {len(times)} записей")
        return avg_time, len(times)
    logger.info("Недостаточно данных для расчёта среднего времени")
    return None, len(times)

def manage_config(config_file="config.json"):
    """Управляет конфигурацией бота, загружает или создаёт файл config.json."""
    logger.info(f"Управление конфигурацией: {config_file}")

def manage_config(config_file="config.json"):
    """Управляет конфигурацией бота, загружает или создаёт файл config.json."""
    default_config = {
        "telegram_token": "YOUR_TELEGRAM_BOT_TOKEN",
        "kobold_api_url": "http://127.0.0.1:5001/api/v1/generate",
        "max_new_tokens": 512,
        "max_length": 200,
        "temperature": 0.8,
        "top_p": 0.9,
        "proxy": None,
        "timeout": 300,
        "system_prompt": "You are Vrok, a humorous AI assistant created by vitug. Respond with wit and a touch of sarcasm.",
        "log_ai_details": False,
        "temp_message_lifetime": 30  # Новая опция
    }

    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Проверяем наличие всех ключей
        updated = False
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
                updated = True
        if updated:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            logger.info(f"Обновлён файл конфигурации: {config_file}")
        logger.info(f"Конфигурация загружена из {config_file}")
    else:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        config = default_config
        logger.warning(f"Конфигурация создана с значениями по умолчанию: {config_file}")

    required_fields = ["telegram_token", "kobold_api_url"]
    for field in required_fields:
        if field not in config or not config[field]:
            logger.error(f"Отсутствует обязательное поле {field}")
            raise KeyError(f"Отсутствует обязательное поле {field}")
        if field == "telegram_token" and config[field] == "YOUR_TELEGRAM_TOKEN_HERE":
            logger.error("Токен Telegram не настроен!")
            raise ValueError("Токен Telegram не настроен!")

    config.setdefault("max_new_tokens", 512)
    config.setdefault("max_length", 200)
    config.setdefault("temperature", 0.8)
    config.setdefault("top_p", 0.9)
    config.setdefault("proxy", PROXY)
    config.setdefault("timeout", 120)
    config.setdefault("system_prompt", "You are Grok, a humorous AI assistant created by xAI. Respond with wit and a touch of sarcasm.")

    apihelper.proxy = {'https': config["proxy"]}
    logger.info(f"Прокси для Telegram: {config['proxy']}")
    return config

def translate_text(text, to_english=True):
    """Переводит текст на английский или русский в зависимости от параметра."""
    logger.info(f"Перевод текста: {text[:50]}..., на английский: {to_english}")
    try:
        if to_english:
            translated = translator.translate(text)
            logger.info(f"Переведено на английский: {translated[:50]}...")
            return translated
        else:
            translated = translator_reverse.translate(text)
            logger.info(f"Переведено на русский: {translated[:50]}...")
            return translated
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        return text

async def check_kobold_api(url):
    """Проверяет доступность Kobold API."""
    logger.info(f"Проверка Kobold API: {url}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info("Kobold API доступен")
                    return True
                else:
                    logger.error(f"Kobold API вернул статус {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Ошибка подключения к Kobold API: {e}")
            return False

def get_default_memory():
    """Возвращает значение memory по умолчанию."""
    return "You are a cheerful AI, always responding with a bit of humor."

def save_context_to_file(chat_id, config, db_file="context.db"):
    """Сохраняет текущий контекст и memory в временный текстовый файл, исключая системный промпт, и возвращает путь к файлу."""
    logger.info(f"Сохранение контекста в файл для chat_id: {chat_id}")
    
    # Загружаем memory для данного chat_id
    memory = get_memory(chat_id, db_file)
    if not memory:
        memory = get_default_memory() # Используем значение по умолчанию
        logger.info(f"Memory не задано, используется значение по умолчанию: {memory[:50]}...")
    
    # Загружаем контекст
    context = load_context(chat_id, db_file)
    if not context:
        logger.info("Контекст пуст, возвращаем None")
        return None
    
    # Удаляем системный промпт из начала контекста, если он там есть
    cleaned_context = remove_system_prompt(context)
    if not cleaned_context:
        logger.info("Контекст после удаления системного промпта пуст, возвращаем None")
        return None
    
    # Создаём временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as temp_file:
        # Записываем memory в начало файла
        temp_file.write(f"Memory:\n{memory}\n\n")
        # Записываем очищенный контекст после memory
        temp_file.write(f"Context:\n{cleaned_context}")
        file_path = temp_file.name
    
    logger.info(f"Контекст и memory сохранены в файл: {file_path}")
    return file_path

def remove_last_word(text):
    """Удаляет только последнее слово из текста, сохраняя знаки препинания и кавычки."""
    # Учитываем текст в кавычках и знаки препинания в конце
    pattern = r'(\s+)(\w+)(\W*)$'
    match = re.search(pattern, text)
    if match:
        # Группа 1: пробел перед последним словом
        # Группа 2: последнее слово
        # Группа 3: знаки препинания и кавычки после слова
        return text[:match.start()] + match.group(1) + match.group(3)
    return text

async def generate_response_async(text, config, chat_id, context="", user_translate_enabled=True, ai_translate_enabled=True, continue_only=False):
    """Генерирует ответ от Kobold API асинхронно."""
    logger.info(f"Генерация ответа для chat_id: {chat_id}, текст: {text[:50]}..., continue_only: {continue_only}")
    start_time = time.time()  # Запускаем замер времени выполнения

    # Проверяем доступность Kobold API
    if not await check_kobold_api(config["kobold_api_url"].replace("/api/v1/generate", "")):
        logger.error(f"Kobold API недоступен: {config['kobold_api_url']}")
        return f"Ошибка: Kobold API недоступен по адресу {config['kobold_api_url']}", text, "", get_default_character_name(), f"Roleplay character {get_default_character_name()}'s answer: ", 0.0

    # Проверяем наличие специальных символов "мдXXX", "mlXXX" или "mdXXX" в конце текста
    max_length = config["max_length"]  # Значение по умолчанию из конфига
    pattern = r'(мд|ml|md)(\d{3})$'  # Регулярное выражение для "мд300", "ml300" или "md300"
    match = re.search(pattern, text.strip())
    if match:
        length_value = int(match.group(2))  # Извлекаем число (например, 300)
        if length_value > 512:
            max_length = 512  # Ограничиваем до 512
            logger.info(f"Заданное значение max_length ({length_value}) превышает 512, установлено 512")
        else:
            max_length = length_value  # Используем заданное пользователем значение
            logger.info(f"Установлено max_length из запроса: {max_length}")
        # Удаляем специальные символы из текста
        text = re.sub(pattern, '', text).strip()
        logger.info(f"Текст после удаления специальных символов: {text[:50]}...")

    if user_translate_enabled and not is_english(text) and text != "...":
        text_en = translate_text(text, to_english=True)
        logger.info(f"Текст переведён на английский: {text_en[:50]}...")
    else:
        text_en = text
        logger.info(f"Текст используется как есть: {text_en[:50]}...")

    context_en = context if context else add_system_prompt(config["system_prompt"])
    logger.info(f"Контекст: {context_en[:50]}...")
    character_name = get_character_name(chat_id)
    user_character_name = get_user_character_name(chat_id)
    formatted_user_character_name = f"{user_character_name}: "
    character_prompt = f"Roleplay character {character_name}'s answer: "
    if continue_only or text_en == "...":
        prompt = context_en
        logger.info(f"Продолжение с контекстом: {prompt[:50]}...")
    else:
        prompt = f"{context_en}\n{formatted_user_character_name}{text_en}\n{character_prompt}"
        text_en_context = f"\n{formatted_user_character_name}{text_en}\n{character_prompt}"
        logger.info(f"Полный промпт: {prompt[:50]}...")

    memory = get_memory(chat_id)
    if not memory:
        memory = get_default_memory()
        logger.info(f"Memory по умолчанию: {memory[:50]}...")
    else:
        logger.info(f"Пользовательский memory: {memory[:50]}...")
    
	# Очищаем ответ от маркеров системного промпта
    prompt = clean_system_prompt_markers(prompt)
    # Формируем payload с динамическим max_length
    payload = {
        "prompt": prompt,
        "memory": memory,
        "max_length": max_length,  # Используем либо значение из запроса, либо из конфига
        "max_new_tokens": config["max_new_tokens"],
        "max_tokens": 512,
        "temperature": config["temperature"],
        "top_p": config["top_p"],
        "typical_p": 1,
        "typical": 1,
        "sampler_seed": -1,
        "min_p": 0,
        "repetition_penalty": 1.22,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "top_k": 0,
        "skew": 0,
        "min_tokens": 0,
        "add_bos_token": True,
        "smoothing_factor": 0,
        "smoothing_curve": 1,
        "dry_allowed_length": 2,
        "dry_multiplier": 0,
        "dry_base": 1.75,
        "dry_sequence_breakers": ["\\n", ":", "\\\"", "*"],
        "dry_penalty_last_n": 0,
        "max_tokens_second": 0,
        "stopping_strings": [f"\n{user_character_name}:", "\n***"],
        "stop": [f"\n{user_character_name}:", "\n***"],
        "truncation_length": 8192,
        "ban_eos_token": False,
        "skip_special_tokens": True,
        "top_a": 0,
        "tfs": 1,
        "mirostat_mode": 0,
        "mirostat_tau": 5,
        "mirostat_eta": 0.1,
        "custom_token_bans": "",
        "banned_strings": [],
        "sampler_order": [6, 0, 1, 3, 4, 2, 5],
        "xtc_threshold": 0.1,
        "xtc_probability": 0,
        "nsigma": 0,
        "grammar": "",
        "trim_stop": True,
        "rep_pen": 1.22,
        "rep_pen_range": 0,
        "repetition_penalty_range": 0,
        "seed": -1,
        "guidance_scale": 1,
        "negative_prompt": "",
        "grammar_string": "",
        "repeat_penalty": 1.22,
        "tfs_z": 1,
        "repeat_last_n": 0,
        "n_predict": 512,
        "num_predict": 512,
        "num_ctx": 8192,
        "mirostat": 0,
        "ignore_eos": False,
        "rep_pen_slope": 1
    }
    logger.info(f"Отправка запроса к Kobold API с промптом: {prompt[:50]}...")

    # Отправляем запрос к Kobold API через HTTP без шифрования
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                config["kobold_api_url"],
                json=payload,
                timeout=aiohttp.ClientTimeout(total=config.get("timeout", 300))
            ) as response:

                # Проверяем статус ответа
                if response.status != 200:
                    logger.error(f"Kobold API вернул статус {response.status}")
                    return f"Ошибка: Kobold API вернул статус {response.status}", text, "", character_name, character_prompt, 0.0

                # Получаем текстовый ответ от API
                # Читаем ответ как байты, чтобы избежать ContentLengthError
                response_bytes = await response.read()
                if not response_bytes:
                    raise ValueError("Пустой ответ от Kobold API")

                # Декодируем вручную с обработкой ошибок
                try:
                    response_text = response_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    logger.error("Не удалось декодировать ответ от Kobold API")
                    return "Ошибка: не удалось декодировать ответ от Kobold API", text, "", character_name, character_prompt, 0.0

                logger.info(f"Ответ Kobold API: {response_text[:50]}...")

                # Проверка, является ли ответ валидным JSON
                if not response_text.strip().startswith('{'):
                    logger.error(f"Получен невалидный JSON от Kobold API: {response_text[:100]}...")
                    return (
                        f"Ошибка: Kobold API вернул невалидный JSON: {response_text[:100]}...",
                        text, "", character_name, character_prompt, 0.0
                    )

                # Парсим JSON-ответ
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON от Kobold API: {str(e)}, текст ответа: {response_text[:100]}...")
                    return (
                        f"Ошибка: не удалось распарсить ответ от Kobold API ({str(e)})",
                        text, "", character_name, character_prompt, 0.0
                    )

                # Логируем полный JSON-ответ в ai_details.log, если включено
                if config.get("log_ai_details", False):
                    ai_detail_logger.info(f"JSON-ответ от Kobold API для chat_id {chat_id}: {json.dumps(result, indent=2)}")
                logger.info(f"JSON ответ: {json.dumps(result)[:50]}...")
                
                # Проверяем корректность формата ответа
                if "results" not in result or not result["results"]:
                    raise ValueError("Некорректный формат ответа")
                response_en = result["results"][0]["text"]
                if not response_en:
                    raise ValueError("Пустой текст в ответе")

                # Удаляем последнее слово из ответа для плавного продолжения
                response_en_cleaned = remove_last_word(response_en)
                if not response_en_cleaned.strip():
                    response_en_cleaned = response_en  # Если результат пустой, возвращаем оригинал
                logger.info(f"Ответ после удаления последнего слова: {response_en_cleaned[:50]}...")

                # Извлекаем последнее предложение из контекста, если оно оборвано (нет точки)
                last_sentence = ""
                if continue_only and context_en:
                    if not context_en.strip().endswith('.'):
                        lines = context_en.split('\n')
                        last_line = ""
                        for line in reversed(lines):
                            if line.strip():
                                last_line = line.strip()
                                break
                        if last_line:
                            sentences = last_line.split('.')
                            for sentence in reversed(sentences):
                                if sentence.strip():
                                    last_sentence = sentence.strip()
                                    break
                        logger.info(f"Последнее предложение из контекста (без точки в конце): {last_sentence[:50]}...")
                    else:
                        logger.info("Контекст заканчивается точкой, последнее предложение не извлекается")

                # Объединяем последнее предложение с новым ответом, если оно было извлечено
                combined_response_en = f"{last_sentence} {response_en_cleaned}".strip() if last_sentence else response_en_cleaned
                logger.info(f"Объединённый ответ: {combined_response_en[:50]}...")

                # Обновляем контекст для следующего вызова
                updated_context = f"{context}{text_en_context if not continue_only else ''}{response_en_cleaned}"
                save_context(chat_id, updated_context)
                # Логируем обновлённый контекст в ai_details.log, если включено
                if config.get("log_ai_details", False):
                    ai_detail_logger.info(f"Обновлённый контекст для chat_id {chat_id}: {updated_context}")
                logger.info(f"Обновлённый контекст сохранён: {updated_context[:50]}...")

                # Убираем character_prompt из текста для вывода пользователю
                display_response_en = combined_response_en.replace(character_prompt, "")
                logger.info(f"Ответ для вывода пользователю: {display_response_en[:50]}...")

                # Формируем окончательный ответ с учётом настроек перевода
                if ai_translate_enabled and is_english(display_response_en):
                    response_ru = translate_text(display_response_en, to_english=False)
                    if continue_only or text_en == "...":
                        full_response = (
                            f"Ответ ИИ (на английском): {display_response_en}\n"
                            f"---\n"
                            f"Перевод на русский: {response_ru}"
                        )
                    else:
                        if user_translate_enabled:
                            full_response = (
                                f"Перевод текста для ИИ на английский: {text_en}\n"
                                f"Ответ ИИ (на английском): {display_response_en}\n"
                                f"---\n"
                                f"Перевод на русский: {response_ru}"
                            )
                        else:
                            full_response = (
                                f"Текст для ИИ: {text_en}\n"
                                f"Ответ ИИ (на английском): {display_response_en}\n"
                                f"---\n"
                                f"Перевод на русский: {response_ru}"
                            )
                else:
                    # Определяем префикс в зависимости от языка ответа
                    response_prefix = "Ответ ИИ (на английском):" if is_english(display_response_en) else "Ответ ИИ:"
                    
                    if continue_only or text_en == "...":
                        full_response = f"{response_prefix} {display_response_en}"
                    else:
                        if user_translate_enabled:
                            full_response = (
                                f"Перевод текста для ИИ на английский: {text_en}\n"
                                f"{response_prefix} {display_response_en}"
                            )
                        else:
                            full_response = (
                                f"Текст для ИИ: {text_en}\n"
                                f"{response_prefix} {display_response_en}"
                            )
                            
                logger.info(f"Итоговый ответ: {full_response[:50]}...")

                # Завершаем замер времени и сохраняем его
                end_time = time.time()
                response_time = end_time - start_time
                save_response_time(chat_id, response_time)
                logger.info(f"Генерация завершена за {response_time:.2f} сек")

                # Возвращаем кортеж с ответом и метаданными
                return full_response, text_en, response_en_cleaned, character_name, character_prompt, response_time

        # Обрабатываем возможные ошибки
        except aiohttp.ClientPayloadError as e:
            logger.error(f"Ошибка полезной нагрузки от Kobold API: {e}", exc_info=True)
            return (
                "Ошибка: ответ от Kobold API был получен не полностью. "
                "Попробуйте снова или обратитесь к администратору."
            ), text, "", character_name, character_prompt, 0.0
        except asyncio.TimeoutError:
            logger.error("Превышено время ожидания ответа от Kobold API")
            default_character_name = get_default_character_name()  # Используем функцию
            return (
                f"Ошибка: превышено время ожидания ({config.get('timeout', 300)} сек). "
                "Попробуйте снова или упростите запрос."
            ), text, "", default_character_name, f"Roleplay character {default_character_name}'s answer: ", 0.0
        except (aiohttp.ClientError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ошибка при запросе к Kobold API: {e}", exc_info=True)
            default_character_name = get_default_character_name()  # Используем функцию
            return f"Ошибка: не удалось получить ответ от модели ({str(e)})", text, "", default_character_name, f"Roleplay character {default_character_name}'s answer: ", 0.0
        except Exception as e:
            logger.error(f"Неизвестная ошибка при запросе к Kobold API: {e}", exc_info=True)
            default_character_name = get_default_character_name()  # Используем функцию
            return f"Ошибка: неизвестная проблема ({str(e)})", text, "", default_character_name, f"Roleplay character {default_character_name}'s answer: ", 0.0