import os
from pathlib import Path
from dotenv import load_dotenv
from telethon.sync import TelegramClient

load_dotenv()

api_id = int(os.getenv("API_ID", "0"))
api_hash = os.getenv("API_HASH", "")

if not api_id or not api_hash:
    raise SystemExit("Помилка: API_ID та API_HASH мають бути вказані у файлі .env")

Path("accs").mkdir(exist_ok=True)
session_name = 'accs/my_account'

with TelegramClient(session_name, api_id, api_hash) as client:
    print("Сессия успешно создана. Файл:", session_name + ".session")
