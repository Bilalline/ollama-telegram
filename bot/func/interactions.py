# >> interactions
import logging
import os
import aiohttp
import json
import sqlite3
from aiogram import types
from aiohttp import ClientTimeout
from asyncio import Lock
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
token = os.getenv("TOKEN")
allowed_ids = list(map(int, os.getenv("USER_IDS", "").split(",")))
admin_ids = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
ollama_port = os.getenv("OLLAMA_PORT", "11434")
log_level_str = os.getenv("LOG_LEVEL", "INFO")
allow_all_users_in_groups = bool(int(os.getenv("ALLOW_ALL_USERS_IN_GROUPS", "0")))
log_levels = list(logging._levelToName.values())
timeout = os.getenv("TIMEOUT", "3000")
if log_level_str not in log_levels:
    log_level = logging.DEBUG
else:
    log_level = logging.getLevelName(log_level_str)
logging.basicConfig(level=log_level)

async def manage_model(action: str, model_name: str):
    async with aiohttp.ClientSession() as session:
        url = f"http://{ollama_base_url}:{ollama_port}/api/{action}"
        
        if action == "pull":
            # Use the exact payload structure from the curl example
            data = json.dumps({"name": model_name})
            headers = {
                'Content-Type': 'application/json'
            }
            logging.info(f"Pulling model: {model_name}")
            logging.info(f"Request URL: {url}")
            logging.info(f"Request Payload: {data}")
            
            async with session.post(url, data=data, headers=headers) as response:
                logging.info(f"Pull model response status: {response.status}")
                response_text = await response.text()
                logging.info(f"Pull model response text: {response_text}")
                return response
        elif action == "delete":
            data = json.dumps({"name": model_name})
            headers = {
                'Content-Type': 'application/json'
            }
            async with session.delete(url, data=data, headers=headers) as response:
                return response
        else:
            logging.error(f"Unsupported model management action: {action}")
            return None

def add_system_prompt(user_id, prompt, is_global):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO system_prompts (user_id, prompt, is_global) VALUES (?, ?, ?)",
              (user_id, prompt, is_global))
    conn.commit()
    conn.close()

def get_system_prompts(user_id=None, is_global=None):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    query = "SELECT * FROM system_prompts WHERE 1=1"
    params = []
    
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    
    if is_global is not None:
        query += " AND is_global = ?"
        params.append(is_global)
    
    c.execute(query, params)
    prompts = c.fetchall()
    conn.close()
    return prompts

def delete_system_prompt(prompt_id):
    conn = sqlite3.connect('prompts.db')
    c = conn.cursor()
    c.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
    conn.commit()
    conn.close()

async def model_list():
    async with aiohttp.ClientSession() as session:
        url = f"http://{ollama_base_url}:{ollama_port}/api/tags"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data["models"]
            else:
                return []
                
async def generate(prompt, modelname):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{ollama_base_url}:{ollama_port}/api/generate",
                json={"model": modelname, "prompt": prompt, "stream": False}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"Ошибка Ollama API: {error_text}")
                    raise Exception(f"Ошибка Ollama API: {error_text}")
                
                result = await response.json()
                return result.get("response", "Ошибка: нет ответа от модели")
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка подключения к Ollama API: {e}")
        raise Exception(f"Ошибка подключения к Ollama API: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при генерации ответа: {e}")
        raise Exception(f"Неожиданная ошибка при генерации ответа: {e}")

def load_allowed_ids_from_db():
    global allowed_ids
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users")
    user_ids = [row[0] for row in c.fetchall()]
    print(f"users_ids: {user_ids}")
    conn.close()
    allowed_ids = user_ids
    return user_ids


def get_all_users_from_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM users")
    users = c.fetchall()
    conn.close()
    return users

def remove_user_from_db(user_id):
    global allowed_ids
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    removed = c.rowcount > 0
    conn.commit()
    conn.close()
    if removed:
        allowed_ids = [id for id in allowed_ids if id != user_id]
    return removed

def perms_allowed(func):
    @wraps(func)
    async def wrapper(message: types.Message = None, query: types.CallbackQuery = None):
        if message is None and query is None:
            raise ValueError("Должно быть передано либо message, либо query")
            
        user_id = message.from_user.id if message else query.from_user.id
        
        # Проверяем, является ли пользователь админом или разрешенным пользователем
        if user_id in admin_ids or user_id in allowed_ids:
            if message:
                return await func(message)
            elif query:
                return await func(query=query)
        else:
            # Для групповых чатов
            if message and message.chat.type in ["supergroup", "group"]:
                if allow_all_users_in_groups:
                    return await func(message)
                return
            
            # Для личных сообщений
            if message:
                await message.answer("Доступ запрещен. Пожалуйста, зарегистрируйтесь, нажав кнопку 'Register'.")
            elif query:
                await query.answer("Доступ запрещен. Пожалуйста, зарегистрируйтесь, нажав кнопку 'Register'.")
                logging.info(f"Пользователь {user_id} пытался получить доступ без регистрации")

    return wrapper


def perms_admins(func):
    @wraps(func)
    async def wrapper(message: types.Message = None, query: types.CallbackQuery = None):
        user_id = message.from_user.id if message else query.from_user.id
        if user_id in admin_ids:
            if message:
                return await func(message)
            elif query:
                return await func(query=query)
        else:
            if message:
                if message and message.chat.type in ["supergroup", "group"]:
                    return
                await message.answer("Access Denied")
                logging.info(
                    f"[MSG] {message.from_user.first_name} {message.from_user.last_name}({message.from_user.id}) is not allowed to use this bot."
                )
            elif query:
                if message and message.chat.type in ["supergroup", "group"]:
                    return
                await query.answer("Access Denied")
                logging.info(
                    f"[QUERY] {message.from_user.first_name} {message.from_user.last_name}({message.from_user.id}) is not allowed to use this bot."
                )

    return wrapper
class contextLock:
    lock = Lock()

    async def __aenter__(self):
        await self.lock.acquire()

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        self.lock.release()
