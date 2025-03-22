# -*- coding: utf-8 -*-
# main.py
import asyncio
import json
import logging
import os
import re
import tempfile
import locale
from telebot.async_telebot import AsyncTeleBot
from utils import (manage_config, init_db, load_context, save_context, clear_context,
                  get_user_translate_enabled, set_user_translate_enabled,
                  get_ai_translate_enabled, set_ai_translate_enabled,
                  get_memory, set_memory, generate_response_async, split_message,
                  get_character_name, set_character_name, translate_text, is_english,
                  get_user_character_name, set_user_character_name, get_avg_response_time, temp_message_livetime,
                  save_context_to_file, add_system_prompt, remove_system_prompt, get_selected_extension, set_selected_extension,
                  get_show_english, set_show_english)

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

# Создаём словарь для хранения блокировок по chat_id
generation_locks = {}

async def check_and_lock_generation(chat_id, message):
    """Проверяет, идёт ли генерация для chat_id, и устанавливает блокировку. Возвращает True, если можно продолжать."""
    if chat_id not in generation_locks:
        generation_locks[chat_id] = asyncio.Lock()
    
    if generation_locks[chat_id].locked():
        await bot.reply_to(message, "Генерация ответа уже идёт, подождите немного!")
        logger.info(f"Генерация для chat_id: {chat_id} заблокирована, уже выполняется")
        return False
    
    # Если генерация не идёт, возвращаем True и оставляем блокировку для использования в вызывающем коде
    return True

async def monitor_config(config_path, interval=10):
    """Периодически проверяет изменения в файле конфигурации и обновляет глобальный config."""
    global config
    last_mtime = os.path.getmtime(config_path)
    logger.info(f"Запущено сканирование файла конфигурации: {config_path} с интервалом {interval} сек")

    while True:
        try:
            current_mtime = os.path.getmtime(config_path)
            if current_mtime != last_mtime:
                logger.info(f"Обнаружено изменение файла конфигурации: {config_path}")
                with open(config_path, 'r', encoding='utf-8') as f:
                    new_config = json.load(f)
                config.update(new_config)  # Обновляем существующий config
                last_mtime = current_mtime
                logger.info("Конфигурация успешно обновлена")
            await asyncio.sleep(interval)
        except FileNotFoundError:
            logger.error(f"Файл конфигурации {config_path} не найден. Ожидание восстановления...")
            await asyncio.sleep(interval)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON в файле {config_path}: {str(e)}. Используется предыдущая конфигурация.")
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"Ошибка при сканировании конфига: {str(e)}")
            await asyncio.sleep(interval)
            
async def main():
    global bot, config  # Делаем bot и config глобальными для использования в check_and_lock_generation
    config = {}
    try:
        logger.info("Запуск инициализации бота")
        
        # Путь к файлу конфигурации (предполагается, что это config.json)
        config_path = "config.json"  # Убедитесь, что путь соответствует вашему файлу
        config = manage_config(config_path)
        # Запускаем задачу мониторинга конфига
        asyncio.create_task(monitor_config(config_path, interval=10))
        
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
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /help от chat_id: {chat_id}, username: {username}")
            help_text = """
        Список команд бота:
        /help Показывает это сообщение со списком всех доступных команд.
        /continue Продолжает текущую историю без нового ввода, основываясь на сохранённом контексте.
        /clear Очищает текущий контекст разговора, позволяя начать общение с чистого листа.
        /memory [текст] Задаёт или показывает инструкцию (memory) о поведении ИИ. Без аргумента выводит текущее значение. Пример: /memory You are a friendly assistant — задаёт новое поведение.
        /character [имя] Задаёт или показывает имя персонажа ИИ (по умолчанию "Vrok"). Если перевод включён, имя переводится на английский. Пример: /character Alex — устанавливает имя "Alex".
        /usercharacter [имя] Задаёт или показывает ваше имя в диалоге (по умолчанию "User"). Добавляет ": " автоматически. Если перевод включён, имя переводится на английский. Пример: /usercharacter Анна — устанавливает "Anna: ".
        /getcontext Отправляет текущий контекст разговора и memory в виде текстового файла (без системного промпта).
        /extension [имя] Выбирает дополнение персонажа, влияющее на стиль общения. Без аргумента показывает список доступных дополнений (например, Humor, Wisdom, Sarcasm) и текущее активное. Пример: /extension Humor — активирует режим с юмором и остроумием.
        /usertranslate Включает или выключает перевод ваших текстовых сообщений на английский перед отправкой ИИ. По умолчанию включён.
        /aitranslate Включает или выключает перевод ответов ИИ на русский. По умолчанию включён.
        /showenglish Включает/выключает отображение английского текста (переведённого текста и ответа ИИ до перевода).
        /start Запускает бота и отправляет приветственное сообщение. Инициализирует контекст разговора с системным промптом.
        - Голосовые сообщения Отправьте голосовое сообщение, и бот преобразует его в текст с помощью утилиты, покажет распознанный текст, а затем сгенерирует ответ ИИ с учётом текущего дополнения.
        - Текстовые сообщения Отправьте текст, и бот ответит с учётом контекста, настроек перевода и выбранного дополнения. Используйте "..." для продолжения без ввода.
            """
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
            
            # Передаём config как есть, он нужен для других целей в save_context_to_file
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

        @bot.message_handler(commands=['extension'])
        async def handle_extension(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /extension от chat_id: {chat_id}, username: {username}")

            # Извлекаем аргумент команды
            args = message.text.split(maxsplit=1)[1:]  # Пропускаем "/extension"
            extensions = config.get("extensions", [])

            if not args:
                # Если аргументов нет, показываем только несекретные расширения
                visible_extensions = [ext for ext in extensions if not ext.get("hidden", False)]
                if not visible_extensions:
                    await bot.reply_to(message, "Нет видимых дополнений. Используйте /extension xxx для полного списка.")
                    logger.info(f"Нет видимых дополнений для chat_id: {chat_id}")
                    return
                
                # Формируем список видимых дополнений
                extension_list = "\n".join(
                    [f"- {ext['name']}: {ext.get('short_description', '')}" if ext.get('short_description') 
                     else f"- {ext['name']}" for ext in visible_extensions]
                )
                current_extension = get_selected_extension(chat_id)
                current_status = f"\n\nТекущее дополнение: {current_extension or 'не выбрано'}"
                await bot.reply_to(message, f"Доступные дополнения:\n{extension_list}{current_status}\n\nИспользуйте /extension <имя> для выбора.")
                logger.info(f"Показаны видимые дополнения для chat_id: {chat_id}")
                return

            # Проверяем, является ли аргумент "xxx" или "ххх" (независимо от регистра)
            arg = args[0].strip().lower()
            if arg in ["xxx", "ххх"]:
                # Если аргумент "xxx" или "ххх", показываем все дополнения
                if not extensions:
                    await bot.reply_to(message, "Список дополнений пуст. Добавьте их в config.json.")
                    return
                
                # Формируем полный список с указанием скрытых
                extension_list = "\n".join(
                    [f"- {ext['name']}: {ext.get('short_description', '')}{' (скрыто)' if ext.get('hidden', False) else ''}" 
                     if ext.get('short_description') else f"- {ext['name']}{' (скрыто)' if ext.get('hidden', False) else ''}" 
                     for ext in extensions]
                )
                current_extension = get_selected_extension(chat_id)
                current_status = f"\n\nТекущее дополнение: {current_extension or 'не выбрано'}"
                await bot.reply_to(message, f"Все доступные дополнения:\n{extension_list}{current_status}\n\nИспользуйте /extension <имя> для выбора.")
                logger.info(f"Показан полный список дополнений для chat_id: {chat_id}")
                return
            
            # Если аргумент не "xxx" и не "ххх", проверяем, указано ли существующее дополнение
            extension_name = arg
            selected_extension = next((ext for ext in extensions if ext["name"].lower() == extension_name.lower()), None)

            if not selected_extension:
                await bot.reply_to(message, f"Дополнение '{extension_name}' не найдено. Используйте /extension xxx для полного списка.")
                logger.info(f"Дополнение '{extension_name}' не найдено для chat_id: {chat_id}")
                return

            # Сохраняем выбранное расширение в базу данных
            current_extension = get_selected_extension(chat_id)
            if current_extension and current_extension.lower() == selected_extension["name"].lower():
                await bot.reply_to(message, f"Дополнение '{selected_extension['name']}' уже активно.")
                return

            set_selected_extension(chat_id, selected_extension["name"])
            logger.info(f"Выбрано дополнение '{selected_extension['name']}' для chat_id: {chat_id}")
            await bot.reply_to(message, f"Дополнение '{selected_extension['name']}' активировано.")
            
        @bot.message_handler(commands=['showenglish'])
        async def handle_show_english(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получена команда /showenglish от chat_id: {chat_id}, username: {username}")
            current_state = get_show_english(chat_id)
            new_state = not current_state
            set_show_english(chat_id, new_state)
            state_text = "включено" if new_state else "выключено"
            await bot.reply_to(message, f"Отображение английского текста теперь {state_text}.")
            logger.info(f"Show_english для chat_id: {chat_id} установлен в {new_state}")
    
        @bot.message_handler(commands=['continue'])
        async def handle_continue(message):
            chat_id = message.chat.id
            logger.info(f"Получена команда /continue от chat_id: {chat_id}")
            context = load_context(chat_id)
            logger.info(f"Загружен контекст: {context[:100]}...")
            if not context:
                context = add_system_prompt(config["system_prompt"])
                logger.info("Используется системный промпт как контекст с разделителями")

            # Проверяем блокировку
            if not await check_and_lock_generation(chat_id, message):
                return

            async with generation_locks[chat_id]:
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

            # Проверяем блокировку
            if not await check_and_lock_generation(chat_id, message):
                return

            async with generation_locks[chat_id]:
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

        @bot.message_handler(content_types=['voice'])
        async def handle_voice_message(message):
            chat_id = message.chat.id
            username = message.from_user.username or "Unknown"
            logger.info(f"Получено аудио-сообщение от chat_id: {chat_id}, username: {username}")

            # Проверяем блокировку
            if not await check_and_lock_generation(chat_id, message):
                return

            async with generation_locks[chat_id]:
                # Скачиваем аудио-файл
                file_info = await bot.get_file(message.voice.file_id)
                downloaded_file = await bot.download_file(file_info.file_path)

                # Создаём временный файл для аудио
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_audio:
                    temp_audio.write(downloaded_file)
                    audio_file_path = temp_audio.name
                logger.info(f"Аудио сохранено во временный файл: {audio_file_path}")

                # Создаём путь для текстового файла, убирая расширение .ogg
                text_file_path = os.path.splitext(audio_file_path)[0] + ".txt"
                logger.info(f"Ожидаемый путь к текстовому файлу: {text_file_path}")

                # Логируем путь к утилите перед её вызовом
                logger.info(f"Используется утилита преобразования аудио: {config['audio_to_text_tool']}")

                # Отправляем временное сообщение о преобразовании речи в текст
                transcribe_status = await bot.reply_to(message, "Преобразование речи в текст, подождите...")
                logger.info(f"Отправлено временное сообщение о преобразовании в chat_id: {chat_id}, message_id: {transcribe_status.message_id}")

                # Вызываем утилиту для преобразования аудио в текст
                try:
                    process = await asyncio.create_subprocess_exec(
                        config["audio_to_text_tool"], audio_file_path,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()

                    # Логируем вывод утилиты
                    try:
                        stdout_str = stdout.decode('cp866').strip() if stdout else "нет вывода"
                    except UnicodeDecodeError as e:
                        stdout_str = f"ошибка декодирования: {str(e)}"
                        logger.warning(f"Не удалось декодировать stdout утилиты {config['audio_to_text_tool']}: {stdout[:100]}...")
                    try:
                        stderr_str = stderr.decode('cp866').strip() if stderr else "нет ошибок"
                    except UnicodeDecodeError as e:
                        stderr_str = f"ошибка декодирования: {str(e)}"
                        logger.warning(f"Не удалось декодировать stderr утилиты {config['audio_to_text_tool']}: {stderr[:100]}...")

                    logger.info(f"Вывод утилиты (stdout): {stdout_str[:100]}...")
                    logger.info(f"Ошибки утилиты (stderr): {stderr_str[:100]}...")
                    logger.info(f"Код завершения утилиты: {process.returncode}")

                    # Проверяем код завершения и наличие ошибок в stderr
                    if process.returncode != 0 or (stderr and stderr_str != "нет ошибок"):
                        logger.error(f"Утилита завершилась с проблемой (returncode={process.returncode}): {stderr_str[:100]}...")
                        await bot.reply_to(message, "Ошибка: утилита преобразования аудио завершилась с ошибкой или не выполнила задачу.")
                        return

                    # Проверяем наличие выходного файла
                    if not os.path.exists(text_file_path):
                        logger.error(f"Утилита не создала выходной файл: {text_file_path}")
                        await bot.reply_to(message, "Ошибка: утилита не создала текстовый файл с распознанным текстом.")
                        return

                    logger.info("Аудио успешно преобразовано в текст")

                    # Читаем текст из выходного файла
                    try:
                        with open(text_file_path, 'r', encoding='utf-8') as text_file:
                            raw_text = text_file.read()
                        logger.info(f"Прочитан текст из файла: {raw_text[:50]}...")
                        clean_text = re.sub(r'\[\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}\.\d{3}\]\s*', '', raw_text).strip()
                        logger.info(f"Текст после очистки: {clean_text[:50]}...")
                        
                        # Удаляем временное сообщение о преобразовании
                        try:
                            await bot.delete_message(chat_id=message.chat.id, message_id=transcribe_status.message_id)
                            logger.info(f"Удалено временное сообщение о преобразовании в chat_id: {chat_id}, message_id: {transcribe_status.message_id}")
                        except Exception as e:
                            logger.warning(f"Не удалось удалить временное сообщение о преобразовании: {e}")

                        # Отправляем распознанный текст пользователю
                        await bot.reply_to(message, f"Распознанный текст:\n{clean_text}")
                    except FileNotFoundError:
                        logger.error(f"Выходной файл {text_file_path} не найден")
                        await bot.reply_to(message, "Ошибка: утилита не создала текстовый файл.")
                        return
                    except Exception as e:
                        logger.error(f"Ошибка при чтении текстового файла: {str(e)}")
                        await bot.reply_to(message, "Ошибка: не удалось прочитать текст из файла.")
                        return

                    # Загружаем контекст
                    context = load_context(chat_id)
                    if not context:
                        context = add_system_prompt(config["system_prompt"])
                        logger.info("Используется системный промпт как контекст с разделителями")

                    # Получаем среднее время генерации
                    avg_time, count = get_avg_response_time(chat_id)
                    status_text = "Генерация ответа, подождите..."
                    if avg_time:
                        status_text += f"\nСреднее время ответа: {avg_time:.2f} сек (на основе {count} ответов)"

                    status_message = await bot.reply_to(message, status_text)
                    logger.info(f"Отправлено сообщение о статусе в chat_id: {chat_id}, message_id: {status_message.message_id}")

                    # Генерируем ответ ИИ
                    ai_response, text_en, response_en, character_name, character_prompt, response_time = await generate_response_async(
                        clean_text, config, chat_id, context, get_user_translate_enabled(chat_id), get_ai_translate_enabled(chat_id)
                    )
                    logger.info(f"Сгенерирован ответ: {ai_response[:50]}...")

                    # Отправляем ответ
                    message_parts = split_message(ai_response)
                    await bot.edit_message_text(
                        text=message_parts[0],
                        chat_id=message.chat.id,
                        message_id=status_message.message_id
                    )
                    for part in message_parts[1:]:
                        await bot.send_message(chat_id=message.chat.id, text=part)

                    # Отправляем временное сообщение о завершении
                    temp_message = await bot.send_message(
                        chat_id=message.chat.id,
                        text=f"Генерация завершена за {response_time:.2f} сек"
                    )
                    await asyncio.sleep(temp_message_livetime(config))
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=temp_message.message_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить временное сообщение о завершении: {e}")

                except Exception as e:
                    logger.error(f"Ошибка при обработке аудио-сообщения: {str(e)}")
                    await bot.reply_to(message, "Произошла ошибка при обработке аудио-сообщения.")
                    return

                finally:
                    # Удаляем временные файлы
                    try:
                        os.remove(audio_file_path)
                        if os.path.exists(text_file_path):
                            os.remove(text_file_path)
                        logger.info(f"Удалены временные файлы: {audio_file_path}, {text_file_path}")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить временные файлы: {e}")
                
        logger.info("Запуск polling")
        await polling_with_logging()

    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    logger.info("Запуск бота с явным циклом событий")
    loop.run_until_complete(main())