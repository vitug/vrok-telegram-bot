# -*- coding: utf-8 -*-
import asyncio
import logging
from telebot.async_telebot import AsyncTeleBot
from utils import (manage_config, init_db, load_context, save_context, clear_context,
                  get_user_translate_enabled, set_user_translate_enabled,
                  get_ai_translate_enabled, set_ai_translate_enabled,
                  get_memory, set_memory, generate_response_async, split_message,
                  get_character_name, set_character_name, translate_text, is_english,
                  get_user_character_name, set_user_character_name, get_avg_response_time, temp_message_livetime)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("Запуск инициализации бота")
        config = manage_config()
        init_db()
        bot = AsyncTeleBot(config["telegram_token"])
        logger.info("Бот инициализирован с токеном")

        async def polling_with_logging():
            try:
                await bot.polling(none_stop=True)
            except Exception as e:
                logger.error(f"Ошибка в polling: {e}", exc_info=True)
                await asyncio.sleep(5)
                await polling_with_logging()

        @bot.message_handler(commands=['start'])
        async def handle_start(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /start от chat_id: {chat_id}, username: {username}")
            await bot.reply_to(message, "Привет! Я Vrok, твой ИИ-ассистент. Используй команды или просто пиши мне.")
            logger.info(f"Отправлен ответ на /start для chat_id: {chat_id}")

        @bot.message_handler(commands=['help'])
        async def handle_help(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /help от chat_id: {chat_id}, username: {username}")
            help_text = (
                "Команды:\n"
                "/start - Начать работу\n"
                "/help - Показать помощь\n"
                "/clear - Очистить контекст\n"
                "/usertranslate - Вкл/выкл перевод запросов\n"
                "/aitranslate - Вкл/выкл перевод ответов\n"
                "/memory - Установить/показать memory\n"
                "/character - Установить/показать имя персонажа\n"
                "/usercharacter - Установить/показать имя пользователя\n"
                "/continue - Продолжить последний контекст\n"
                "/stats - Показать среднее время ответа\n"
                "Добавь 'мдXXX' или 'mlXXX' (XXX - трёхзначное число до 512) в конец запроса для задания длины ответа."
            )
            await bot.reply_to(message, help_text)
            logger.info(f"Отправлен ответ на /help для chat_id: {chat_id}")

        @bot.message_handler(commands=['clear'])
        async def handle_clear(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /clear от chat_id: {chat_id}, username: {username}")
            clear_context(chat_id)
            await bot.reply_to(message, "Контекст очищен.")
            logger.info(f"Контекст очищен для chat_id: {chat_id}")

        @bot.message_handler(commands=['usertranslate'])
        async def handle_usertranslate(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /usertranslate от chat_id: {chat_id}, username: {username}")
            current_state = get_user_translate_enabled(chat_id)
            new_state = not current_state
            set_user_translate_enabled(chat_id, new_state)
            state_text = "включён" if new_state else "выключен"
            await bot.reply_to(message, f"Перевод запросов {state_text}.")
            logger.info(f"Перевод запросов установлен в {state_text} для chat_id: {chat_id}")

        @bot.message_handler(commands=['aitranslate'])
        async def handle_aitranslate(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /aitranslate от chat_id: {chat_id}, username: {username}")
            current_state = get_ai_translate_enabled(chat_id)
            new_state = not current_state
            set_ai_translate_enabled(chat_id, new_state)
            state_text = "включён" if new_state else "выключен"
            await bot.reply_to(message, f"Перевод ответов {state_text}.")
            logger.info(f"Перевод ответов установлен в {state_text} для chat_id: {chat_id}")

        @bot.message_handler(commands=['memory'])
        async def handle_memory(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /memory от chat_id: {chat_id}, username: {username}")
            command_text = message.text.strip()

            memory_input = command_text[len("/memory"):].strip()
            if memory_input:
                user_translate_enabled = get_user_translate_enabled(chat_id)
                if user_translate_enabled and not is_english(memory_input):
                    memory_en = translate_text(memory_input, to_english=True)
                else:
                    memory_en = memory_input
                set_memory(chat_id, memory_en)
                await bot.reply_to(message, f"Установлено новое memory: {memory_en}")
                logger.info(f"Установлено новое memory: {memory_en[:50]}... для chat_id: {chat_id}")
            else:
                current_memory = get_memory(chat_id)
                if not current_memory:
                    current_memory = "You are a cheerful AI, always responding with a bit of humor."
                await bot.reply_to(message, f"Текущее memory: {current_memory}")
                logger.info(f"Отправлено текущее memory: {current_memory[:50]}... для chat_id: {chat_id}")

        @bot.message_handler(commands=['character'])
        async def handle_character(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /character от chat_id: {chat_id}, username: {username}")
            command_text = message.text.strip()

            character_input = command_text[len("/character"):].strip()
            if character_input:
                user_translate_enabled = get_user_translate_enabled(chat_id)
                if user_translate_enabled and not is_english(character_input):
                    character_name_en = translate_text(character_input, to_english=True)
                    logger.info(f"Имя персонажа переведено на английский: {character_name_en}")
                else:
                    character_name_en = character_input
                set_character_name(chat_id, character_name_en)
                await bot.reply_to(message, f"Установлено новое имя персонажа: {character_name_en}")
                logger.info(f"Установлено имя персонажа: {character_name_en} для chat_id: {chat_id}")
            else:
                current_character = get_character_name(chat_id)
                await bot.reply_to(message, f"Текущее имя персонажа: {current_character}")
                logger.info(f"Отправлено текущее имя персонажа: {current_character} для chat_id: {chat_id}")

        @bot.message_handler(commands=['usercharacter'])
        async def handle_user_character(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /usercharacter от chat_id: {chat_id}, username: {username}")
            command_text = message.text.strip()

            user_character_input = command_text[len("/usercharacter"):].strip()
            if user_character_input:
                user_translate_enabled = get_user_translate_enabled(chat_id)
                if user_translate_enabled and not is_english(user_character_input):
                    user_character_name_en = translate_text(user_character_input, to_english=True)
                    logger.info(f"Имя пользователя переведено на английский: {user_character_name_en}")
                else:
                    user_character_name_en = user_character_input
                set_user_character_name(chat_id, user_character_name_en)
                await bot.reply_to(message, f"Установлено новое имя пользователя: {user_character_name_en}: ")
                logger.info(f"Установлено имя пользователя: {user_character_name_en} для chat_id: {chat_id}")
            else:
                current_user_character = get_user_character_name(chat_id)
                await bot.reply_to(message, f"Текущее имя пользователя: {current_user_character}: ")
                logger.info(f"Отправлено текущее имя пользователя: {current_user_character} для chat_id: {chat_id}")

        @bot.message_handler(commands=['continue'])
        async def handle_continue(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /continue от chat_id: {chat_id}, username: {username}")
            context = load_context(chat_id)
            if not context:
                await bot.reply_to(message, "Контекст пуст. Начните с обычного сообщения.")
                logger.info(f"Контекст пуст для chat_id: {chat_id}")
                return

            response, _, _, _, _, response_time = await generate_response_async(
                "...", config, chat_id, context=context,
                user_translate_enabled=get_user_translate_enabled(chat_id),
                ai_translate_enabled=get_ai_translate_enabled(chat_id),
                continue_only=True
            )
            for part in split_message(response):
                await bot.reply_to(message, part)
            logger.info(f"Отправлен ответ на /continue для chat_id: {chat_id}")
            temp_message = await bot.send_message(
                chat_id=message.chat.id,
                text=f"Генерация завершена за {response_time:.2f} сек"
            )
            logger.info(f"Отправлено временное сообщение о завершении в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            await asyncio.sleep(temp_message_livetime(config))
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=temp_message.message_id)
                logger.info(f"Временное сообщение удалено в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временное сообщение: {e}")

        @bot.message_handler(commands=['stats'])
        async def handle_stats(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /stats от chat_id: {chat_id}, username: {username}")
            avg_time = get_avg_response_time(chat_id)
            if avg_time is None:
                await bot.reply_to(message, "Нет данных о времени ответа.")
            else:
                await bot.reply_to(message, f"Среднее время ответа: {avg_time:.2f} сек")
            logger.info(f"Отправлена статистика для chat_id: {chat_id}")

        @bot.message_handler(func=lambda message: True)
        async def handle_message(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получено сообщение от chat_id: {chat_id}, username: {username}, текст: {message.text[:50]}...")
            context = load_context(chat_id)
            response, _, _, _, _, response_time = await generate_response_async(
                message.text, config, chat_id, context=context,
                user_translate_enabled=get_user_translate_enabled(chat_id),
                ai_translate_enabled=get_ai_translate_enabled(chat_id)
            )
            for part in split_message(response):
                await bot.reply_to(message, part)
            logger.info(f"Отправлен ответ для chat_id: {chat_id}")
            temp_message = await bot.send_message(
                chat_id=message.chat.id,
                text=f"Генерация завершена за {response_time:.2f} сек"
            )
            logger.info(f"Отправлено временное сообщение о завершении в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            await asyncio.sleep(temp_message_livetime(config))
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=temp_message.message_id)
                logger.info(f"Временное сообщение удалено в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временное сообщение: {e}")

        logger.info("Запуск polling")
        await polling_with_logging()

    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    logger.info("Запуск бота с явным циклом событий")
    loop.run_until_complete(main())