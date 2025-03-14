# -*- coding: utf-8 -*-
import json
import logging
import os
import re
import sqlite3
import aiohttp
import requests
import certifi
from deep_translator import GoogleTranslator
from telebot import apihelper
import time
import asyncio

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
    if config and "temp_message_lifetime" in config:
        return config["temp_message_lifetime"]
    return 30

def manage_config(config_file="config.json"):
    logger.info(f"Управление конфигурацией: {config_file}")
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
        "temp_message_lifetime": 30
    }
    if not os.path.exists(config_file):
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        logger.info(f"Создан новый файл конфигурации: {config_file}")
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    for key, value in default_config.items():
        if key not in config:
            config[key] = value
    if config.get("proxy"):
        apihelper.proxy = {'https': config["proxy"]}
        translation_session.proxies = {"http": config["proxy"], "https": config["proxy"]}
    logger.info(f"Конфигурация загружена: {json.dumps(config, indent=2)[:50]}...")
    return config

def get_default_character_name():
    """Возвращает имя персонажа по умолчанию."""
    return "Vrok"

def init_db(db_file="context.db"):
    logger.info(f"Инициализация базы данных: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(user_context)")
    if not cursor.fetchall():
        cursor.execute('''
            CREATE TABLE user_context (
                chat_id INTEGER PRIMARY KEY,
                context TEXT NOT NULL
            )
        ''')
        logger.info("Создана таблица user_context")

    cursor.execute("PRAGMA table_info(chat_settings)")
    columns = [col[1] for col in cursor.fetchall()]
    if not columns:
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
    else:
        if "character_name" not in columns:
            cursor.execute(f"ALTER TABLE chat_settings ADD COLUMN character_name TEXT DEFAULT '{get_default_character_name()}'")
            logger.info("Добавлен столбец character_name")
        if "user_character_name" not in columns:
            cursor.execute("ALTER TABLE chat_settings ADD COLUMN user_character_name TEXT DEFAULT 'User'")
            logger.info("Добавлен столбец user_character_name")

    cursor.execute("PRAGMA table_info(response_times)")
    if not cursor.fetchall():
        cursor.execute('''
            CREATE TABLE response_times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                response_time REAL NOT NULL,
                timestamp INTEGER NOT NULL
            )
        ''')
        logger.info("Создана таблица response_times")

    conn.commit()
    conn.close()
    logger.info(f"База данных готова: {db_file}")

def save_context(chat_id, context, db_file="context.db"):
    logger.info(f"Сохранение контекста для chat_id: {chat_id}, контекст: {context[:50]}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_context (chat_id, context) VALUES (?, ?)', (chat_id, context))
    conn.commit()
    conn.close()
    logger.info(f"Контекст сохранён для chat_id: {chat_id}")

def load_context(chat_id, db_file="context.db"):
    logger.info(f"Загрузка контекста для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT context FROM user_context WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    context = result[0] if result else ""
    logger.info(f"Контекст загружен: {context[:50]}...")
    return context

def clear_context(chat_id, db_file="context.db"):
    logger.info(f"Очистка контекста для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_context WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()
    logger.info(f"Контекст очищен для chat_id: {chat_id}")

def get_user_translate_enabled(chat_id, db_file="context.db"):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT user_translate_enabled FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    enabled = result[0] if result else 1
    logger.info(f"User translate enabled для chat_id {chat_id}: {enabled}")
    return bool(enabled)

def set_user_translate_enabled(chat_id, enabled, db_file="context.db"):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, user_translate_enabled) VALUES (?, ?)',
                   (chat_id, int(enabled)))
    conn.commit()
    conn.close()
    logger.info(f"User translate установлен в {enabled} для chat_id: {chat_id}")

def get_ai_translate_enabled(chat_id, db_file="context.db"):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT ai_translate_enabled FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    enabled = result[0] if result else 1
    logger.info(f"AI translate enabled для chat_id {chat_id}: {enabled}")
    return bool(enabled)

def set_ai_translate_enabled(chat_id, enabled, db_file="context.db"):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, ai_translate_enabled) VALUES (?, ?)',
                   (chat_id, int(enabled)))
    conn.commit()
    conn.close()
    logger.info(f"AI translate установлен в {enabled} для chat_id: {chat_id}")

def get_memory(chat_id, db_file="context.db"):
    logger.info(f"Получение memory для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT memory FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    memory = result[0] if result else ""
    logger.info(f"Memory: {memory[:50]}...")
    return memory

def set_memory(chat_id, memory, db_file="context.db"):
    logger.info(f"Установка memory для chat_id: {chat_id}: {memory[:50]}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, memory) VALUES (?, ?)', (chat_id, memory))
    conn.commit()
    conn.close()
    logger.info(f"Memory установлено для chat_id: {chat_id}")

def get_character_name(chat_id, db_file="context.db"):
    logger.info(f"Получение character_name для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT character_name FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    name = result[0] if result else get_default_character_name()
    logger.info(f"Character name: {name}")
    return name

def set_character_name(chat_id, name, db_file="context.db"):
    logger.info(f"Установка character_name для chat_id: {chat_id}: {name}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, character_name) VALUES (?, ?)', (chat_id, name))
    conn.commit()
    conn.close()
    logger.info(f"Character name установлено для chat_id: {chat_id}")

def get_user_character_name(chat_id, db_file="context.db"):
    logger.info(f"Получение user_character_name для chat_id: {chat_id}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT user_character_name FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    name = result[0] if result else "User"
    logger.info(f"User character name: {name}")
    return name

def set_user_character_name(chat_id, name, db_file="context.db"):
    logger.info(f"Установка user_character_name для chat_id: {chat_id}: {name}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_settings (chat_id, user_character_name) VALUES (?, ?)', (chat_id, name))
    conn.commit()
    conn.close()
    logger.info(f"User character name установлено для chat_id: {chat_id}")

def save_response_time(chat_id, response_time, db_file="context.db"):
    logger.info(f"Сохранение времени ответа для chat_id: {chat_id}: {response_time}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO response_times (chat_id, response_time, timestamp) VALUES (?, ?, ?)',
                   (chat_id, response_time, int(time.time())))
    conn.commit()
    conn.close()

def get_avg_response_time(chat_id, db_file="context.db"):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT AVG(response_time) FROM response_times WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    avg_time = result[0] if result and result[0] is not None else None
    logger.info(f"Среднее время ответа для chat_id {chat_id}: {avg_time}")
    return avg_time

def translate_text(text, to_english=True):
    try:
        if to_english:
            return translator.translate(text)
        return translator_reverse.translate(text)
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        return text

def is_english(text):
    return all(ord(char) < 128 for char in text)

def split_message(message, max_length=4096):
    if len(message) <= max_length:
        return [message]
    parts = []
    current_part = ""
    for line in message.split('\n'):
        if len(current_part) + len(line) + 1 <= max_length:
            current_part += line + "\n"
        else:
            parts.append(current_part.strip())
            current_part = line + "\n"
    if current_part:
        parts.append(current_part.strip())
    return parts

async def check_kobold_api(url):
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

def remove_last_word(text):
    """Удаляет только последнее слово из текста, сохраняя знаки препинания и кавычки."""
    pattern = r'(\s+)(\w+)(\W*)$'
    match = re.search(pattern, text)
    if match:
        return text[:match.start()] + match.group(1) + match.group(3)
    return text

async def generate_response_async(text, config, chat_id, context="", user_translate_enabled=True, ai_translate_enabled=True, continue_only=False):
    logger.info(f"Генерация ответа для chat_id: {chat_id}, текст: {text[:50]}..., continue_only: {continue_only}")
    start_time = time.time()  # Запускаем замер времени выполнения

    if not await check_kobold_api(config["kobold_api_url"].replace("/api/v1/generate", "")):
        logger.error(f"Kobold API недоступен: {config['kobold_api_url']}")
        return f"Ошибка: Kobold API недоступен по адресу {config['kobold_api_url']}", text, "", get_default_character_name(), f"Roleplay character {get_default_character_name()}'s answer: ", 0.0

    # Проверяем наличие специальных символов "мдXXX", "mlXXX" или "mdXXX" в конце текста
    max_length = config["max_length"]
    pattern = r'(мд|ml|md)(\d{3})$'
    match = re.search(pattern, text.strip())
    if match:
        length_value = int(match.group(2))
        if length_value > 512:
            max_length = 512
            logger.info(f"Заданное значение max_length ({length_value}) превышает 512, установлено 512")
        else:
            max_length = length_value
            logger.info(f"Установлено max_length из запроса: {max_length}")
        text = re.sub(pattern, '', text).strip()
        logger.info(f"Текст после удаления специальных символов: {text[:50]}...")

    if user_translate_enabled and not is_english(text) and text != "...":
        text_en = translate_text(text, to_english=True)
        logger.info(f"Текст переведён на английский: {text_en[:50]}...")
    else:
        text_en = text
        logger.info(f"Текст используется как есть: {text_en[:50]}...")

    context_en = context if context else config["system_prompt"]
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
        memory = "You are a cheerful AI, always responding with a bit of humor."
        logger.info(f"Memory по умолчанию: {memory[:50]}...")
    else:
        logger.info(f"Пользовательский memory: {memory[:50]}...")

    payload = {
        "prompt": prompt,
        "memory": memory,
        "max_length": max_length,
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

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                config["kobold_api_url"],
                json=payload,
                timeout=aiohttp.ClientTimeout(total=config.get("timeout", 300))
            ) as response:
                response_text = await response.text()
                logger.info(f"Ответ Kobold API: {response_text[:50]}...")
                if not response_text:
                    raise ValueError("Пустой ответ от Kobold API")
                result = json.loads(response_text)
                if config.get("log_ai_details", False):
                    ai_detail_logger.info(f"JSON-ответ от Kobold API для chat_id {chat_id}: {json.dumps(result, indent=2)}")
                logger.info(f"JSON ответ: {json.dumps(result)[:50]}...")
                if "results" not in result or not result["results"]:
                    raise ValueError("Некорректный формат ответа")
                response_en = result["results"][0]["text"]
                if not response_en:
                    raise ValueError("Пустой текст в ответе")

                response_en_cleaned = remove_last_word(response_en)
                if not response_en_cleaned.strip():
                    response_en_cleaned = response_en
                logger.info(f"Ответ после удаления последнего слова: {response_en_cleaned[:50]}...")

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

                combined_response_en = f"{last_sentence} {response_en_cleaned}".strip() if last_sentence else response_en_cleaned
                logger.info(f"Объединённый ответ: {combined_response_en[:50]}...")

                updated_context = f"{context}{text_en_context if not continue_only else ''}{response_en_cleaned}"
                save_context(chat_id, updated_context)
                if config.get("log_ai_details", False):
                    ai_detail_logger.info(f"Обновлённый контекст для chat_id {chat_id}: {updated_context}")
                logger.info(f"Обновлённый контекст сохранён: {updated_context[:50]}...")

                display_response_en = combined_response_en.replace(character_prompt, "")
                logger.info(f"Ответ для вывода пользователю: {display_response_en[:50]}...")

                if ai_translate_enabled and is_english(display_response_en):
                    response_ru = translate_text(display_response_en, to_english=False)
                    if continue_only or text_en == "...":
                        full_response = (
                            f"Ответ ИИ (на английском): {display_response_en}\n"
                            f"---\n"
                            f"Перевод на русский: {response_ru}"
                        )
                    else:
                        full_response = (
                            f"Перевод текста для ИИ на английский: {text_en}\n"
                            f"Ответ ИИ (на английском): {display_response_en}\n"
                            f"---\n"
                            f"Перевод на русский: {response_ru}"
                        )
                else:
                    if continue_only or text_en == "...":
                        full_response = f"Ответ ИИ (на английском): {display_response_en}"
                    else:
                        full_response = (
                            f"Перевод текста для ИИ на английский: {text_en}\n"
                            f"Ответ ИИ (на английском): {display_response_en}"
                        )
                logger.info(f"Итоговый ответ: {full_response[:50]}...")

                end_time = time.time()
                response_time = end_time - start_time
                save_response_time(chat_id, response_time)
                logger.info(f"Генерация завершена за {response_time:.2f} сек")

                return full_response, text_en, response_en_cleaned, character_name, character_prompt, response_time

        except asyncio.TimeoutError:
            logger.error("Превышено время ожидания ответа от Kobold API")
            return (
                f"Ошибка: превышено время ожидания ({config.get('timeout', 300)} сек). "
                "Попробуйте снова или упростите запрос."
            ), text, "", character_name, character_prompt, 0.0
        except (aiohttp.ClientError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ошибка при запросе к Kobold API: {e}", exc_info=True)
            return f"Ошибка: не удалось получить ответ от модели ({str(e)})", text, "", character_name, character_prompt, 0.0
        except Exception as e:
            logger.error(f"Неизвестная ошибка при запросе к Kobold API: {e}", exc_info=True)
            return f"Ошибка: неизвестная проблема ({str(e)})", text, "", character_name, character_prompt, 0.0