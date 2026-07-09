import os
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv
load_dotenv()
api_id = int(os.getenv("API_ID", "0"))
api_hash = os.getenv("API_HASH", "")
if not api_id or not api_hash:
    raise SystemExit("Помилка: API_ID та API_HASH мають бути вказані у файлі .env")

phone = input('Phone (+...): ').strip()

client = TelegramClient('my_account', api_id, api_hash)
client.connect()
print('Connected:', client.is_connected())

if client.is_user_authorized():
    print('Already authorized. Session exists: my_account.session')
    client.disconnect()
    raise SystemExit

try:
    result = client.send_code_request(phone)
    print('Code request sent. Type:', type(result).__name__)
except Exception as e:
    print('send_code_request error:', repr(e))
    client.disconnect()
    raise SystemExit

code = input('Enter code from Telegram: ').strip()
try:
    client.sign_in(phone=phone, code=code)
except SessionPasswordNeededError:
    pwd = input('Enter 2FA password: ').strip()
    client.sign_in(password=pwd)
except Exception as e:
    print('sign_in error:', repr(e))
    client.disconnect()
    raise SystemExit

print('Session created: my_account.session')
client.disconnect()
