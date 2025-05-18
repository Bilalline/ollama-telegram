<div align="center">
  <br>
  <a href="">
    <img src="res/github/ollama-telegram-readme.png" width="200" height="200">
  </a>
  <h1>🦙 Ollama Telegram Bot</h1>
  <p>
    <b>Chat with your LLM, using Telegram bot!</b><br>
    <b>Feel free to contribute!</b><br>
  </p>
  <br>
  <p align="center">
    <img src="https://img.shields.io/docker/pulls/ruecat/ollama-telegram?style=for-the-badge">
  </p>
  <br>
</div>

## Features
Here's features that you get out of the box:

- [x] Fully dockerized bot
- [x] Response streaming without ratelimit with **SentenceBySentence** method
- [x] Mention [@] bot in group to receive answer

## Roadmap
- [x] Docker config & automated tags by [StanleyOneG](https://github.com/StanleyOneG), [ShrirajHegde](https://github.com/ShrirajHegde)
- [x] History and `/reset` by [ShrirajHegde](https://github.com/ShrirajHegde)
- [ ] Add more API-related functions [System Prompt Editor, Ollama Version fetcher, etc.]
- [ ] Redis DB integration
- [ ] Update bot UI

## Prerequisites
- [Telegram-Bot Token](https://core.telegram.org/bots#6-botfather)

## Installation (Non-Docker)
+ Install latest [Python](https://python.org/downloads)
+ Clone Repository
    ```
    git clone https://github.com/ruecat/ollama-telegram
    ```
+ Install requirements from requirements.txt
    ```
    pip install -r requirements.txt
    ```
+ Enter all values in .env.example

+ Rename .env.example -> .env

+ Launch bot

    ```
    python3 run.py
    ```
## Installation (Docker Image)
The official image is available at dockerhub: [ruecat/ollama-telegram](https://hub.docker.com/r/ruecat/ollama-telegram)

+ Download [.env.example](https://github.com/ruecat/ollama-telegram/blob/main/.env.example) file, rename it to .env and populate the variables.
+ Create `docker-compose.yml` (optionally: uncomment GPU part of the file to enable Nvidia GPU)

    ```yml
    version: '3.8'
    services:
      ollama-telegram:
        image: ruecat/ollama-telegram
        container_name: ollama-telegram
        restart: on-failure
        env_file:
          - ./.env
      
      ollama-server:
        image: ollama/ollama:latest
        container_name: ollama-server
        volumes:
          - ./ollama:/root/.ollama
        
        # Uncomment to enable NVIDIA GPU
        # Otherwise runs on CPU only:
    
        # deploy:
        #   resources:
        #     reservations:
        #       devices:
        #         - driver: nvidia
        #           count: all
        #           capabilities: [gpu]
    
        restart: always
        ports:
          - '11434:11434'
    ```

+ Start the containers

    ```sh
    docker compose up -d
    ```


## Installation (Build your own Docker image)
+ Clone Repository
    ```
    git clone https://github.com/ruecat/ollama-telegram
    ```

+ Enter all values in .env.example

+ Rename .env.example -> .env

+ Run ONE of the following docker compose commands to start:
    1. To run ollama in docker container (optionally: uncomment GPU part of docker-compose.yml file to enable Nvidia GPU)
        ```
        docker compose up --build -d
        ```

    2. To run ollama from locally installed instance (mainly for **MacOS**, since docker image doesn't support Apple GPU acceleration yet):
        ```
        docker compose up --build -d ollama-tg
        ```

## Environment Configuration
|          Parameter          |                                                      Description                                                      | Required? | Default Value |                        Example                        |
|:---------------------------:|:---------------------------------------------------------------------------------------------------------------------:|:---------:|:-------------:|:-----------------------------------------------------:|
|           `TOKEN`           | Your **Telegram bot token**.<br/>[[How to get token?]](https://core.telegram.org/bots/tutorial#obtain-your-bot-token) |    Yes    |  `yourtoken`  |             MTA0M****.GY5L5F.****g*****5k             |
|         `ADMIN_IDS`         |                     Telegram user IDs of admins.<br/>These can change model and control the bot.                      |    Yes    |               | 1234567890<br/>**OR**<br/>1234567890,0987654321, etc. |
|         `USER_IDS`          |                       Telegram user IDs of regular users.<br/>These only can chat with the bot.                       |    Yes    |               | 1234567890<br/>**OR**<br/>1234567890,0987654321, etc. |
|         `INITMODEL`         |                                                      Default LLM                                                      |    No     |   `llama2`    |        mistral:latest<br/>mistral:7b-instruct         |
|      `OLLAMA_BASE_URL`      |                                                  Your OllamaAPI URL                                                   |    No     |               |          localhost<br/>host.docker.internal           |
|        `OLLAMA_PORT`        |                                                  Your OllamaAPI port                                                  |    No     |     11434     |                                                       |
|            `TIMEOUT`        |                                    The timeout in seconds for generating responses                                    |    No     |     3000      |                                                       |
| `ALLOW_ALL_USERS_IN_GROUPS` |                Allows all users in group chats interact with bot without adding them to USER_IDS list                 |    No     |       0       |                                                       |



## Credits
+ [Ollama](https://github.com/jmorganca/ollama)

## Libraries used
+ [Aiogram 3.x](https://github.com/aiogram/aiogram)

# Ollama Telegram Bot

Telegram бот для взаимодействия с Ollama API.

## Особенности

- Взаимодействие с языковыми моделями через Ollama API
- Система регистрации и управления пользователями
- Административные команды для управления ботом
- Поддержка групповых чатов
- Система промптов (глобальных и приватных)
- История сообщений
- Поддержка контекста в групповых чатах

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/ollama-telegram.git
cd ollama-telegram
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` с необходимыми переменными:
```env
BOT_TOKEN=your_telegram_bot_token
INITMODEL=llama2
```

4. Запустите бота:
```bash
python bot/run.py
```

## Команды

### Команды для пользователей
- `/start` - Начать работу с ботом
- `/reset` - Сбросить историю чата
- `/history` - Просмотреть историю сообщений
- `/addprivateprompt` - Добавить приватный промпт

### Команды для администраторов
- `/start` - Начать работу с ботом
- `/reset` - Сбросить историю чата
- `/history` - Просмотреть историю сообщений
- `/addprivateprompt` - Добавить приватный промпт
- `/addglobalprompt` - Добавить глобальный промпт
- `/pullmodel` - Загрузить модель из Ollama
- `/approve` - Одобрить регистрацию пользователя
- `/reject` - Отклонить регистрацию пользователя
- `/users` - Показать список пользователей
- `/remove` - Удалить пользователя

## Использование в группах

Бот может быть использован в групповых чатах следующими способами:
1. Упоминание бота в сообщении (например, "@bot_name прокомментируй это")
2. Ответ на сообщение бота
3. Ответ на сообщение другого пользователя с упоминанием бота

Бот будет анализировать контекст обсуждения и давать соответствующие комментарии.

## Система промптов

Бот поддерживает:
- Глобальные промпты (доступны всем пользователям)
- Приватные промпты (доступны только создателю)
- Управление промптами через интерфейс бота

## Требования

- Python 3.8+
- Ollama API
- Telegram Bot Token

## Лицензия

MIT License
