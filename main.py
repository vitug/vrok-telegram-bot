# -*- coding: utf-8 -*-
import asyncio
import logging
import os
from telebot.async_telebot import AsyncTeleBot
from utils import (manage_config, init_db, load_context, save_context, clear_context,
                  get_user_translate_enabled, set_user_translate_enabled,
                  get_ai_translate_enabled, set_ai_translate_enabled,
                  get_memory, set_memory, generate_response_async, split_message,
                  get_character_name, set_character_name, translate_text, is_english,
                  get_user_character_name, set_user_character_name, get_avg_response_time, temp_message_livetime,
                  save_context_to_file, add_system_prompt, remove_system_prompt)

# При ошибке SSL: CERTIFICATE_VERIFY_FAILED certificate verify failed: unable to get local issuer certificate (_ssl.c:1129)')
# pip install pip-system-certs

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
        try:
            init_db()  # Проверяет структуру или создаёт базу
        except SystemExit as e:
            logger.error(f"Программа завершена из-за ошибки в базе данных: {e}")
            return  # Завершает main(), бот не запускается
        bot = AsyncTeleBot(config["telegram_token"])
        logger.info("Бот инициализирован с токеном")

        # Добавляем обработчик исключений для polling с перезапуском при TimeoutError
        async def polling_with_logging():
            while True:  # Бесконечный цикл для перезапуска polling
                try:
                    logger.info("Начинаем polling")
                    await bot.polling(none_stop=True, timeout=60)  # Уменьшаем timeout до 60 секунд
                except asyncio.TimeoutError as te:
                    logger.error(f"TimeoutError в polling: {te}. Перезапуск через 5 секунд...")
                    await asyncio.sleep(5)  # Задержка перед перезапуском
                except Exception as e:
                    logger.error(f"Неизвестная ошибка в polling: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Задержка перед перезапуском при других ошибках
                    raise  # Повторно выбрасываем исключение для обработки выше

        @bot.message_handler(commands=['start'])
        async def handle_start(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /start от chat_id: {chat_id}, username: {username}")
            context = load_context(chat_id)
            if not context:
                context = add_system_prompt(config["system_prompt"])
                save_context(chat_id, context)
            await bot.reply_to(message, "Привет! Я Врок, весёлый ИИ. Напиши что-нибудь, и я отвечу с юмором!\n"
                                       "Для списка команд используй /help.")
            logger.info(f"Отправлено приветственное сообщение в chat_id: {chat_id}")

        @bot.message_handler(commands=['help'])
        async def handle_help(message):
            chat_id = message.chat.id
            logger.info(f"Получена команда /help от chat_id: {chat_id}")
            help_text = (
                "Вот список доступных команд:\n"
                "/start — Запустить бота и получить приветствие.\n"
                "/help — Показать это сообщение со списком команд.\n"
                "/clear — Очистить контекст разговора.\n"
                "/continue — Продолжить текущую историю без нового ввода.\n"
                "/usertranslate — Включить/выключить перевод ваших сообщений на английский перед отправкой ИИ.\n"
                "/aitranslate — Включить/выключить перевод ответов ИИ на русский.\n"
                "/memory [текст] — Задать или посмотреть memory для ИИ (инструкцию о его поведении).\n"
                "/character [имя] — Задать или посмотреть имя персонажа (по умолчанию 'Person').\n"
                "/usercharacter [имя] — Задать или посмотреть имя пользователя (по умолчанию 'User'). Пробел и двоеточие добавляются автоматически.\n"
                "/getcontext — Получить текущий контекст разговора в виде текстового файла.\n"
                "Просто текст — Отправить сообщение ИИ, он ответит с учётом текущих настроек.\n"
                "... — Продолжить историю без явного ввода."
            )
            await bot.reply_to(message, help_text)
            logger.info(f"Отправлен текст помощи в chat_id: {chat_id}")

        @bot.message_handler(commands=['clear'])
        async def handle_clear(message):
            chat_id = message.chat.id
            logger.info(f"Получена команда /clear от chat_id: {chat_id}")
            status_message = await bot.reply_to(message, "Очищаю контекст...")
            clear_context(chat_id)
            await bot.edit_message_text(
                text="Контекст успешно очищен! Можете начать новый разговор.",
                chat_id=message.chat.id,
                message_id=status_message.message_id
            )
            logger.info(f"Контекст очищен и сообщение обновлено для chat_id: {chat_id}")

        @bot.message_handler(commands=['usertranslate'])
        async def handle_user_translate(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /usertranslate от chat_id: {chat_id}, username: {username}")
            current_state = get_user_translate_enabled(chat_id)
            new_state = not current_state
            set_user_translate_enabled(chat_id, new_state)
            state_text = "включён" if new_state else "выключен"
            await bot.reply_to(message, f"Перевод сообщений пользователя на английский теперь {state_text}.")
            logger.info(f"Перевод сообщений пользователя {state_text} для chat_id: {chat_id}")

        @bot.message_handler(commands=['aitranslate'])
        async def handle_ai_translate(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /aitranslate от chat_id: {chat_id}, username: {username}")
            current_state = get_ai_translate_enabled(chat_id)
            new_state = not current_state
            set_ai_translate_enabled(chat_id, new_state)
            state_text = "включён" if new_state else "выключен"
            await bot.reply_to(message, f"Перевод ответов ИИ на русский теперь {state_text}.")
            logger.info(f"Перевод ответов ИИ {state_text} для chat_id: {chat_id}")

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
                    current_memory = "You are a cheerful AI named Grok, always responding with a bit of humor."
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
                # Проверяем, включён ли перевод запросов
                user_translate_enabled = get_user_translate_enabled(chat_id)
                if user_translate_enabled and not is_english(character_input):
                    # Переводим имя персонажа на английский, если оно не на английском
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
                # Проверяем, включён ли перевод запросов
                user_translate_enabled = get_user_translate_enabled(chat_id)
                if user_translate_enabled and not is_english(user_character_input):
                    # Переводим имя пользователя на английский, если оно не на английском
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

        @bot.message_handler(commands=['getcontext'])
        async def handle_get_context(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /getcontext от chat_id: {chat_id}, username: {username}")
            
            # Получаем путь к файлу с контекстом, передаём config
            file_path = save_context_to_file(chat_id, config)
            
            if file_path is None:
                await bot.reply_to(message, "Контекст пуст или содержит только системный промпт. Начните разговор, чтобы создать контекст!")
                logger.info(f"Контекст пуст для chat_id: {chat_id}")
                return
            
            try:
                # Отправляем файл пользователю
                with open(file_path, 'rb') as file:
                    await bot.send_document(chat_id=chat_id, document=file, caption="Ваш текущий контекст")
                logger.info(f"Файл контекста отправлен в chat_id: {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке файла: {e}", exc_info=True)
                await bot.reply_to(message, "Произошла ошибка при отправке файла контекста.")
            finally:
                # Удаляем временный файл
                try:
                    os.remove(file_path)
                    logger.info(f"Временный файл удалён: {file_path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {file_path}: {e}")

        @bot.message_handler(commands=['continue'])
        async def handle_continue(message):
            chat_id = message.chat.id
            logger.info(f"Получена команда /continue от chat_id: {chat_id}")
            context = load_context(chat_id)
            logger.info(f"Загружен контекст: {context[:100]}...")
            if not context:
                context = add_system_prompt(config["system_prompt"])
                logger.info("Используется системный промпт как контекст с разделителями")

            # Получаем среднее время генерации
            avg_time, count = get_avg_response_time(chat_id)
            status_text = "Продолжаю историю, пожалуйста, подождите..."
            if avg_time:
                status_text += f"\nСреднее время ответа: {avg_time:.2f} сек (на основе {count} предыдущих ответов)"

            status_message = await bot.reply_to(message, status_text)
            logger.info(f"Отправлено сообщение о статусе в chat_id: {chat_id}, message_id: {status_message.message_id}")
            ai_response, text_en, response_en, character_name, character_prompt, response_time = await generate_response_async(
                "", config, chat_id, context, get_user_translate_enabled(chat_id), get_ai_translate_enabled(chat_id), continue_only=True
            )
            logger.info(f"Сгенерирован ответ: {ai_response[:100]}...")

            # Контекст обновляется в generate_response_async, здесь только отправляем ответ
            message_parts = split_message(ai_response)
            logger.info(f"Сообщение разбито на {len(message_parts)} частей: {message_parts[0][:50]}...")
            await bot.edit_message_text(
                text=message_parts[0],
                chat_id=message.chat.id,
                message_id=status_message.message_id
            )
            logger.info(f"Сообщение статуса отредактировано для chat_id: {chat_id}")
            for part in message_parts[1:]:
                await bot.send_message(chat_id=message.chat.id, text=part)
                logger.info(f"Отправлена дополнительная часть в chat_id: {chat_id}")

            # Отправляем временное сообщение о завершении генерации
            temp_message = await bot.send_message(
                chat_id=message.chat.id,
                text=f"Генерация завершена за {response_time:.2f} сек"
            )
            logger.info(f"Отправлено временное сообщение о завершении в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            
            # Удаляем сообщение через temp_message_livetime секунд
            await asyncio.sleep(temp_message_livetime(config))
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=temp_message.message_id)
                logger.info(f"Временное сообщение удалено в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временное сообщение: {e}")

        @bot.message_handler(content_types=['text'])
        async def handle_message(message):
            chat_id = message.chat.id
            user_message = message.text
            logger.info(f"Получено текстовое сообщение от chat_id: {chat_id}: {user_message[:50]}...")
            if user_message.startswith('/'):
                logger.info("Пропуск сообщения, похожего на команду")
                return

            context = load_context(chat_id)
            if not context:
                context = add_system_prompt(config["system_prompt"])
                logger.info("Используется системный промпт как контекст с разделителями")
            else:
                logger.info(f"Загружен контекст: {context[:100]}...")

            # Получаем среднее время генерации
            avg_time, count = get_avg_response_time(chat_id)
            status_text = "Генерирую ответ, пожалуйста, подождите..."
            if avg_time:
                status_text += f"\nСреднее время ответа: {avg_time:.2f} сек (на основе {count} предыдущих ответов)"

            status_message = await bot.reply_to(message, status_text)
            logger.info(f"Отправлено сообщение о статусе в chat_id: {chat_id}, message_id: {status_message.message_id}")
            
            ai_response, text_en, response_en, character_name, character_prompt, response_time = await generate_response_async(
                user_message, config, chat_id, context, get_user_translate_enabled(chat_id), get_ai_translate_enabled(chat_id)
            )
            logger.info(f"Сгенерирован ответ: {ai_response[:100]}...")

            # Отправляем основной ответ
            message_parts = split_message(ai_response)
            logger.info(f"Сообщение разбито на {len(message_parts)} частей: {message_parts[0][:50]}...")
            await bot.edit_message_text(
                text=message_parts[0],
                chat_id=message.chat.id,
                message_id=status_message.message_id
            )
            logger.info(f"Сообщение статуса отредактировано для chat_id: {chat_id}")
            for part in message_parts[1:]:
                await bot.send_message(chat_id=message.chat.id, text=part)
                logger.info(f"Отправлена дополнительная часть в chat_id: {chat_id}")

            # Отправляем временное сообщение о завершении генерации
            temp_message = await bot.send_message(
                chat_id=message.chat.id,
                text=f"Генерация завершена за {response_time:.2f} сек"
            )
            logger.info(f"Отправлено временное сообщение о завершении в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            
            # Удаляем сообщение через temp_message_livetime секунд
            await asyncio.sleep(temp_message_livetime(config))
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=temp_message.message_id)
                logger.info(f"Временное сообщение удалено в chat_id: {chat_id}, message_id: {temp_message.message_id}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временное сообщение: {e}")

        # (Остальной код остаётся без изменений)

        logger.info("Запуск polling")
        await polling_with_logging()

    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    logger.info("Запуск бота с явным циклом событий")
    loop.run_until_complete(main())