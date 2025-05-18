from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters.command import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from func.interactions import *
import asyncio
import traceback
import io
import base64
import sqlite3
bot = Bot(token=token)
dp = Dispatcher()
settings_kb = InlineKeyboardBuilder()

settings_kb.row(
    types.InlineKeyboardButton(text="🔄 Switch LLM", callback_data="switchllm"),
    types.InlineKeyboardButton(text="🗑️ Delete LLM", callback_data="delete_model"),
)
settings_kb.row(
    types.InlineKeyboardButton(text="📋 Select System Prompt", callback_data="select_prompt"),
    types.InlineKeyboardButton(text="🗑️ Delete System Prompt", callback_data="delete_prompt"), 
)
settings_kb.row(
    types.InlineKeyboardButton(text="📋 List Users and remove User", callback_data="list_users"),
)

# Команды для обычных пользователей
user_commands = [
    types.BotCommand(command="start", description="Start"),
    types.BotCommand(command="reset", description="Reset Chat"),
    types.BotCommand(command="history", description="Look through messages"),
    types.BotCommand(command="addprivateprompt", description="Add a private prompt"),
]

# Команды для администраторов
admin_commands = [
    types.BotCommand(command="start", description="Start"),
    types.BotCommand(command="reset", description="Reset Chat"),
    types.BotCommand(command="history", description="Look through messages"),
    types.BotCommand(command="addprivateprompt", description="Add a private prompt"),
    types.BotCommand(command="addglobalprompt", description="Add a global prompt"),
    types.BotCommand(command="pullmodel", description="Pull a model from Ollama"),
    types.BotCommand(command="approve", description="Approve user registration"),
    types.BotCommand(command="reject", description="Reject user registration"),
    types.BotCommand(command="users", description="Show all users"),
    types.BotCommand(command="remove", description="Remove user"),
]

ACTIVE_CHATS = {}
ACTIVE_CHATS_LOCK = contextLock()
modelname = os.getenv("INITMODEL")
mention = None
selected_prompt_id = None  # Variable to store the selected prompt ID
CHAT_TYPE_GROUP = "group"
CHAT_TYPE_SUPERGROUP = "supergroup"

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  role TEXT,
                  content TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS system_prompts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  prompt TEXT,
                  is_global BOOLEAN,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

def register_user(user_id, user_name):
    global allowed_ids
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", (user_id, user_name))
    conn.commit()
    conn.close()
    if user_id not in allowed_ids:
        allowed_ids.append(user_id)

def save_chat_message(user_id, role, content):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO chats (user_id, role, content) VALUES (?, ?, ?)",
              (user_id, role, content))
    conn.commit()
    conn.close()

def check_user_exists(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

async def notify_admin_about_new_user(user_id, user_name):
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🆕 Новый пользователь запросил доступ:\nID: {user_id}\nИмя: {user_name}\n\nИспользуйте команду /approve_{user_id} для одобрения"
            )
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_id}: {e}")

@dp.callback_query(lambda query: query.data == "register")
async def register_callback_handler(query: types.CallbackQuery):
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    
    if check_user_exists(user_id):
        await query.answer("Вы уже зарегистрированы!")
        return
        
    register_user(user_id, user_name)
    await notify_admin_about_new_user(user_id, user_name)
    await query.answer("Заявка на регистрацию отправлена администраторам. Ожидайте подтверждения.")
    await query.message.edit_text("Заявка на регистрацию отправлена администраторам. Ожидайте подтверждения.")

@dp.message(lambda message: message.text.startswith("/approve_"))
@perms_admins
async def approve_user_handler(message: Message):
    try:
        user_id = int(message.text.split("_")[1])
        if not check_user_exists(user_id):
            await message.answer("Пользователь не найден!")
            return
            
        # Устанавливаем команды для пользователя
        await set_commands_for_user(user_id)
            
        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=user_id,
                text="✅ Ваша регистрация одобрена! Теперь вы можете использовать бота."
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user_id}: {e}")
            
        await message.answer(f"Пользователь {user_id} успешно одобрен!")
        
    except (ValueError, IndexError):
        await message.answer("Неверный формат команды. Используйте: /approve_USER_ID")

@dp.message(lambda message: message.text.startswith("/reject_"))
@perms_admins
async def reject_user_handler(message: Message):
    try:
        user_id = int(message.text.split("_")[1])
        if not check_user_exists(user_id):
            await message.answer("Пользователь не найден!")
            return
            
        # Удаляем пользователя из базы
        remove_user_from_db(user_id)
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=user_id,
                text="❌ Ваша заявка на регистрацию отклонена."
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user_id}: {e}")
            
        await message.answer(f"Пользователь {user_id} отклонен и удален из базы!")
        
    except (ValueError, IndexError):
        await message.answer("Неверный формат команды. Используйте: /reject_USER_ID")

async def get_bot_info():
    global mention
    if mention is None:
        get = await bot.get_me()
        mention = f"@{get.username}"
    return mention

# Функция для установки команд в зависимости от прав пользователя
async def set_commands_for_user(user_id: int):
    try:
        if user_id in admin_ids:
            await bot.set_my_commands(admin_commands, scope=types.BotCommandScopeChat(chat_id=user_id))
            logging.info(f"Установлены команды администратора для пользователя {user_id}")
        else:
            await bot.set_my_commands(user_commands, scope=types.BotCommandScopeChat(chat_id=user_id))
            logging.info(f"Установлены команды пользователя для {user_id}")
    except Exception as e:
        logging.error(f"Ошибка при установке команд для пользователя {user_id}: {e}")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    
    # Проверяем, зарегистрирован ли пользователь
    if not check_user_exists(user_id):
        # Создаем клавиатуру с кнопкой регистрации
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Зарегистрироваться", callback_data="register")]
        ])
        
        await message.answer(
            "👋 Добро пожаловать в Ollama Telegram Bot!\n\n"
            "🤖 Я - умный бот, который поможет вам взаимодействовать с языковыми моделями через Ollama API.\n\n"
            "✨ Мои возможности:\n"
            "• Умные промпты\n"
            "• История сообщений\n"
            "• Работа в группах\n\n"
            "📝 Для начала работы, пожалуйста, зарегистрируйтесь:",
            reply_markup=keyboard
        )
        return
    
    # Если пользователь уже зарегистрирован, показываем основное меню
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
        [types.InlineKeyboardButton(text="🔄 Сбросить историю", callback_data="reset_history")]
    ])
    
    await message.answer(
        f"👋 Привет, {user_name}!\n\n"
        "🤖 Я - ваш умный ассистент на базе Ollama API.\n\n"
        "✨ Что я умею:\n"
        "• Общаться на разные темы\n"
        "• Помогать с задачами\n"
        "• Работать в группах\n\n"
        "💡 Просто напишите мне сообщение!",
        reply_markup=keyboard
    )

@dp.message(Command("reset"))
async def command_reset_handler(message: Message) -> None:
    if message.from_user.id in allowed_ids:
        if message.from_user.id in ACTIVE_CHATS:
            async with ACTIVE_CHATS_LOCK:
                ACTIVE_CHATS.pop(message.from_user.id)
            logging.info(f"Chat has been reset for {message.from_user.first_name}")
            await bot.send_message(
                chat_id=message.chat.id,
                text="Chat has been reset",
            )

@dp.message(Command("history"))
async def command_get_context_handler(message: Message) -> None:
    if message.from_user.id in allowed_ids:
        if message.from_user.id in ACTIVE_CHATS:
            messages = ACTIVE_CHATS.get(message.chat.id)["messages"]
            context = ""
            for msg in messages:
                context += f"*{msg['role'].capitalize()}*: {msg['content']}\n"
            await bot.send_message(
                chat_id=message.chat.id,
                text=context,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await bot.send_message(
                chat_id=message.chat.id,
                text="No chat history available for this user",
            )

@dp.message(Command("addglobalprompt"))
@perms_admins
async def add_global_prompt_handler(message: Message):
    prompt_text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None  # Get the prompt text from the command arguments
    if prompt_text:
        add_system_prompt(message.from_user.id, prompt_text, True)
        await message.answer("Global prompt added successfully.")
    else:
        await message.answer("Please provide a prompt text to add.")

@dp.message(Command("addprivateprompt"))
async def add_private_prompt_handler(message: Message):
    prompt_text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None  # Get the prompt text from the command arguments
    if prompt_text:
        add_system_prompt(message.from_user.id, prompt_text, False)
        await message.answer("Private prompt added successfully.")
    else:
        await message.answer("Please provide a prompt text to add.")

@dp.message(Command("pullmodel"))
async def pull_model_handler(message: Message) -> None:
    model_name = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None  # Get the model name from the command arguments
    logging.info(f"Downloading {model_name}")
    if model_name:
        response = await manage_model("pull", model_name)
        if response.status == 200:
            await message.answer(f"Model '{model_name}' is being pulled.")
        else:
            await message.answer(f"Failed to pull model '{model_name}': {response.reason}")
    else:
        await message.answer("Please provide a model name to pull.")

@dp.callback_query(lambda query: query.data == "settings")
@perms_admins
async def settings_callback_handler(query: types.CallbackQuery):
    await bot.send_message(
        chat_id=query.message.chat.id,
        text=f"Choose the right option.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=settings_kb.as_markup()
    )

@dp.callback_query(lambda query: query.data == "switchllm")
async def switchllm_callback_handler(query: types.CallbackQuery):
    models = await model_list()
    switchllm_builder = InlineKeyboardBuilder()
    for model in models:
        modelname = model["name"]
        modelfamilies = ""
        if model["details"]["families"]:
            modelicon = {"llama": "🦙", "clip": "📷"}
            try:
                modelfamilies = "".join(
                    [modelicon[family] for family in model["details"]["families"]]
                )
            except KeyError as e:
                modelfamilies = f"✨"
        switchllm_builder.row(
            types.InlineKeyboardButton(
                text=f"{modelname} {modelfamilies}", callback_data=f"model_{modelname}"
            )
        )
    await query.message.edit_text(
        f"{len(models)} models available.\n🦙 = Regular\n🦙📷 = Multimodal", reply_markup=switchllm_builder.as_markup(),
    )

@dp.callback_query(lambda query: query.data.startswith("model_"))
async def model_callback_handler(query: types.CallbackQuery):
    global modelname
    global modelfamily
    modelname = query.data.split("model_")[1]
    await query.answer(f"Chosen model: {modelname}")

@dp.callback_query(lambda query: query.data == "about")
@perms_admins
async def about_callback(query: types.CallbackQuery):
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    is_admin = user_id in admin_ids
    
    about_text = (
        "🤖 <b>О боте</b>\n\n"
        "Я - умный бот на базе Ollama API, который помогает взаимодействовать с языковыми моделями.\n\n"
        "✨ <b>Основные возможности:</b>\n"
        "• Умные промпты\n"
        "• История сообщений\n"
        "• Работа в группах\n\n"
        "📝 <b>Как использовать:</b>\n"
        "• В личных сообщениях: просто пишите мне\n"
        "• В группах: упомяните меня в сообщении\n"
        "• Для сброса истории: используйте /reset\n"
        "• Для просмотра истории: используйте /history\n\n"
    )
    
    if is_admin:
        about_text += (
            "👑 <b>Административные команды:</b>\n"
            "• /addglobalprompt - добавить глобальный промпт\n"
            "• /pullmodel - загрузить модель\n"
            "• /approve - одобрить пользователя\n"
            "• /reject - отклонить пользователя\n"
            "• /users - список пользователей\n"
            "• /remove - удалить пользователя\n\n"
        )
    
    about_text += (
        "🔧 <b>Техническая информация:</b>\n"
        "• Версия: 1.1.0\n"
        "• База: Ollama API\n"
        "• Поддержка: Python 3.8+\n\n"
        "📚 <b>Документация:</b>\n"
        "• GitHub: https://github.com/yourusername/ollama-telegram\n"
        "• Документация: https://github.com/yourusername/ollama-telegram/wiki"
    )
    
    await query.message.edit_text(about_text, parse_mode="HTML")

@dp.callback_query(lambda query: query.data == "list_users")
@perms_admins
async def list_users_callback_handler(query: types.CallbackQuery):
    users = get_all_users_from_db()
    user_kb = InlineKeyboardBuilder()
    for user_id, user_name in users:
        user_kb.row(types.InlineKeyboardButton(text=f"{user_name} ({user_id})", callback_data=f"remove_{user_id}"))
    user_kb.row(types.InlineKeyboardButton(text="Cancel", callback_data="cancel_remove"))
    await query.message.answer("Select a user to remove:", reply_markup=user_kb.as_markup())

@dp.callback_query(lambda query: query.data.startswith("remove_"))
@perms_admins
async def remove_user_from_list_handler(query: types.CallbackQuery):
    user_id = int(query.data.split("_")[1])
    if remove_user_from_db(user_id):
        await query.answer(f"User {user_id} has been removed.")
        await query.message.edit_text(f"User {user_id} has been removed.")
    else:
        await query.answer(f"User {user_id} not found.")

@dp.callback_query(lambda query: query.data == "cancel_remove")
@perms_admins
async def cancel_remove_handler(query: types.CallbackQuery):
    await query.message.edit_text("User removal cancelled.")

@dp.callback_query(lambda query: query.data == "select_prompt")
async def select_prompt_callback_handler(query: types.CallbackQuery):
    prompts = get_system_prompts(user_id=query.from_user.id)
    prompt_kb = InlineKeyboardBuilder()
    for prompt in prompts:
        prompt_id, _, prompt_text, _, _ = prompt
        prompt_kb.row(
            types.InlineKeyboardButton(
                text=prompt_text, callback_data=f"prompt_{prompt_id}"
            )
        )
    await query.message.edit_text(
        f"{len(prompts)} system prompts available.", reply_markup=prompt_kb.as_markup()
    )

@dp.callback_query(lambda query: query.data.startswith("prompt_"))
async def prompt_callback_handler(query: types.CallbackQuery):
    global selected_prompt_id
    selected_prompt_id = int(query.data.split("prompt_")[1])
    await query.answer(f"Selected prompt ID: {selected_prompt_id}")

@dp.callback_query(lambda query: query.data == "delete_prompt")
async def delete_prompt_callback_handler(query: types.CallbackQuery):
    prompts = get_system_prompts(user_id=query.from_user.id)
    delete_prompt_kb = InlineKeyboardBuilder()
    for prompt in prompts:
        prompt_id, _, prompt_text, _, _ = prompt
        delete_prompt_kb.row(
            types.InlineKeyboardButton(
                text=prompt_text, callback_data=f"delete_prompt_{prompt_id}"
            )
        )
    await query.message.edit_text(
        f"{len(prompts)} system prompts available for deletion.", reply_markup=delete_prompt_kb.as_markup()
    )

@dp.callback_query(lambda query: query.data.startswith("delete_prompt_"))
async def delete_prompt_confirm_handler(query: types.CallbackQuery):
    prompt_id = int(query.data.split("delete_prompt_")[1])
    delete_ystem_prompt(prompt_id)
    await query.answer(f"Deleted prompt ID: {prompt_id}")

@dp.callback_query(lambda query: query.data == "delete_model")
async def delete_model_callback_handler(query: types.CallbackQuery):
    models = await model_list()
    delete_model_kb = InlineKeyboardBuilder()
    for model in models:
        modelname = model["name"]
        delete_model_kb.row(
            types.InlineKeyboardButton(
                text=modelname, callback_data=f"delete_model_{modelname}"
            )
        )
    await query.message.edit_text(
        f"{len(models)} models available for deletion.", reply_markup=delete_model_kb.as_markup()
    )

@dp.callback_query(lambda query: query.data.startswith("delete_model_"))
async def delete_model_confirm_handler(query: types.CallbackQuery):
    modelname = query.data.split("delete_model_")[1]
    response = await manage_model("delete", modelname)
    if response.status == 200:
        await query.answer(f"Deleted model: {modelname}")
    else:
        await query.answer(f"Failed to delete model: {modelname}")

@dp.message(Command("users"))
@perms_admins
async def show_users_handler(message: Message):
    users = get_all_users_from_db()
    if not users:
        await message.answer("Нет зарегистрированных пользователей.")
        return
        
    user_list = "Список пользователей:\n\n"
    for user_id, user_name in users:
        user_list += f"ID: {user_id}\nИмя: {user_name}\n\n"
    
    await message.answer(user_list)

@dp.message(Command("remove"))
@perms_admins
async def remove_user_command_handler(message: Message):
    try:
        user_id = int(message.text.split()[1])
        if remove_user_from_db(user_id):
            await message.answer(f"Пользователь {user_id} успешно удален.")
        else:
            await message.answer(f"Пользователь {user_id} не найден.")
    except (ValueError, IndexError):
        await message.answer("Неверный формат команды. Используйте: /remove USER_ID")

@dp.message()
@perms_allowed
async def handle_message(message: types.Message):
    await get_bot_info()
    
    if message.chat.type == "private":
        await ollama_request(message)
        return

    if await is_mentioned_in_group_or_supergroup(message):
        # Получаем контекст сообщений
        thread = await collect_message_thread(message)
        
        # Форматируем промпт с учетом контекста
        prompt = format_thread_for_prompt(thread)
        
        # Добавляем оригинальное сообщение пользователя
        user_message = message.text or message.caption
        if user_message and user_message.startswith(mention):
            user_message = user_message[len(mention):].strip()
        
        if user_message:
            prompt += f"\n\nЗапрос пользователя: {user_message}"
        
        # Отправляем запрос к боту
        await ollama_request(message, prompt)

async def collect_message_thread(message: types.Message, thread=None):
    if thread is None:
        thread = []
    
    # Добавляем сообщение в начало списка
    thread.insert(0, {
        'message': message,
        'text': message.text or message.caption or "[Нет текста]",
        'user': message.from_user.full_name,
        'is_bot': message.from_user.id == bot.id
    })
    
    # Если есть ответ на сообщение, добавляем его в контекст
    if message.reply_to_message:
        await collect_message_thread(message.reply_to_message, thread)
    
    return thread

def format_thread_for_prompt(thread):
    prompt = "Контекст обсуждения:\n\n"
    
    # Добавляем все сообщения из треда
    for msg in thread:
        sender = "Бот" if msg['is_bot'] else msg['user']
        prompt += f"{sender}: {msg['text']}\n\n"
    
    # Добавляем инструкцию для бота
    prompt += "Пожалуйста, проанализируй контекст обсуждения и дай соответствующий комментарий."
    return prompt

async def is_mentioned_in_group_or_supergroup(message: types.Message):
    if message.chat.type not in ["group", "supergroup"]:
        return False
    
    # Проверяем, упомянут ли бот в сообщении
    is_mentioned = (
        (message.text and message.text.startswith(mention)) or
        (message.caption and message.caption.startswith(mention))
    )
    
    # Проверяем, является ли сообщение ответом на сообщение бота
    is_reply_to_bot = (
        message.reply_to_message and 
        message.reply_to_message.from_user.id == bot.id
    )
    
    # Проверяем, является ли сообщение ответом на другое сообщение
    is_reply_to_other = (
        message.reply_to_message and 
        message.reply_to_message.from_user.id != bot.id
    )
    
    return is_mentioned or is_reply_to_bot or is_reply_to_other

async def process_image(message):
    image_base64 = ""
    if message.content_type == "photo":
        image_buffer = io.BytesIO()
        await bot.download(message.photo[-1], destination=image_buffer)
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")
    return image_base64

async def add_prompt_to_active_chats(message, prompt, image_base64, modelname, system_prompt=None):
    async with ACTIVE_CHATS_LOCK:
        # Prepare the messages list
        messages = []
        
        # Add system prompt if provided and not already present
        if system_prompt:
            # Check if a system message already exists
            existing_system_messages = [msg for msg in ACTIVE_CHATS.get(message.from_user.id, {}).get('messages', []) if msg.get('role') == 'system']
            
            if not existing_system_messages:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
        
        # Add existing messages if the chat exists, excluding any existing system messages
        if ACTIVE_CHATS.get(message.from_user.id):
            messages.extend([msg for msg in ACTIVE_CHATS[message.from_user.id].get("messages", []) if msg.get('role') != 'system'])
        
        # Add the new user message
        messages.append({
            "role": "user",
            "content": prompt,
            "images": ([image_base64] if image_base64 else []),
        })
        
        # Update or create the active chat
        ACTIVE_CHATS[message.from_user.id] = {
            "model": modelname,
            "messages": messages,
            "stream": True,
        }

async def handle_response(message, response_data, full_response):
    full_response_stripped = full_response.strip()
    if full_response_stripped == "":
        return
    if response_data.get("done"):
        text = f"{full_response_stripped}\n\n⚙️ {modelname}\nGenerated in {response_data.get('total_duration') / 1e9:.2f}s."
        await send_response(message, text)
        async with ACTIVE_CHATS_LOCK:
            if ACTIVE_CHATS.get(message.from_user.id) is not None:
                ACTIVE_CHATS[message.from_user.id]["messages"].append(
                    {"role": "assistant", "content": full_response_stripped}
                )
        logging.info(
            f"[Response]: '{full_response_stripped}' for {message.from_user.first_name} {message.from_user.last_name}"
        )
        return True
    return False

async def send_response(message, text):
    # A negative message.chat.id is a group message
    if message.chat.id < 0 or message.chat.id == message.from_user.id:
        await bot.send_message(chat_id=message.chat.id, text=text,parse_mode=ParseMode.MARKDOWN)
    else:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )

async def ollama_request(message: types.Message, prompt: str = None):
    try:
        full_response = ""
        await bot.send_chat_action(message.chat.id, "typing")
        image_base64 = await process_image(message)
        
        # Determine the prompt
        if prompt is None:
            prompt = message.text or message.caption

        # Retrieve and prepare system prompt if selected
        system_prompt = None
        if selected_prompt_id is not None:
            system_prompts = get_system_prompts(user_id=message.from_user.id, is_global=None)
            if system_prompts:
                # Find the specific prompt by ID
                for sp in system_prompts:
                    if sp[0] == selected_prompt_id:
                        system_prompt = sp[2]
                        break
                
                if system_prompt is None:
                    logging.warning(f"Selected prompt ID {selected_prompt_id} not found for user {message.from_user.id}")

        # Save the user's message
        save_chat_message(message.from_user.id, "user", prompt)

        # Prepare the active chat with the system prompt
        await add_prompt_to_active_chats(message, prompt, image_base64, modelname, system_prompt)
        
        logging.info(
            f"[OllamaAPI]: Processing '{prompt}' for {message.from_user.first_name} {message.from_user.last_name}"
        )
        
        # Get the payload from active chats
        payload = ACTIVE_CHATS.get(message.from_user.id)
        
        # Generate response
        async for response_data in generate(payload, modelname, prompt):
            msg = response_data.get("message")
            if msg is None:
                continue
            chunk = msg.get("content", "")
            full_response += chunk

            if any([c in chunk for c in ".\n!?"]) or response_data.get("done"):
                if await handle_response(message, response_data, full_response):
                    save_chat_message(message.from_user.id, "assistant", full_response)
                    break

    except Exception as e:
        print(f"-----\n[OllamaAPI-ERR] CAUGHT FAULT!\n{traceback.format_exc()}\n-----")
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Something went wrong: {str(e)}",
            parse_mode=ParseMode.HTML,
        )

async def main():
    init_db()
    global allowed_ids
    allowed_ids = load_allowed_ids_from_db()
    print(f"allowed_ids: {allowed_ids}")
    await dp.start_polling(bot, skip_update=True)

if __name__ == "__main__":
    asyncio.run(main())
