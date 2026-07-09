# analyze_chats.py
# -*- coding: utf-8 -*-
"""
Аналіз Telegram чатів з генерацією описів через ChatGPT

Процес:
1. Telethon збирає дані про чат (title, about, pinned message, admins)
2. Зберігає в текстовий файл
3. Selenium відкриває ChatGPT Web
4. Вставляє дані та отримує опис
5. Зберігає результат у форматі:
   "Детальний опис чату (https://t.me/chat) (@admin_username)"
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Dict

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantsRequest
from telethon.tl.types import Channel, ChannelParticipantsAdmins, InputChannel
from telethon.errors import FloodWaitError

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


# ------------------ КОНФІГУРАЦІЯ ------------------
ACCS_DIR = Path("accs")
CONFIG_ACCOUNTS = Path("config_accounts.json")
OUTPUT_DIR = Path("output")
CHAT_DATA_FILE = OUTPUT_DIR / "chat_analysis_data.txt"
RESULT_FILE = OUTPUT_DIR / "chat_descriptions.txt"

CHATGPT_URL = "https://chat.openai.com/"
CHROME_PROFILE_PATH = None  # Якщо хочете використати свій профіль Chrome, вкажіть шлях


# ------------------ УТИЛИТЫ ------------------
def load_api_from_config(session_name: str) -> Optional[tuple]:
    """Завантажити API креди з config_accounts.json"""
    if CONFIG_ACCOUNTS.exists():
        try:
            cfg = json.loads(CONFIG_ACCOUNTS.read_text(encoding="utf-8"))
            e = cfg.get(session_name) or cfg.get("default")
            if e and "api_id" in e and "api_hash" in e:
                return int(e["api_id"]), str(e["api_hash"])
        except Exception as e:
            print(f"⚠️ Помилка читання {CONFIG_ACCOUNTS}: {e}")
    return None


def load_api_from_env() -> Optional[tuple]:
    """Завантажити API креди з .env"""
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    if api_id and api_hash:
        try:
            return int(api_id), str(api_hash)
        except Exception:
            pass
    return None


def resolve_api_creds(session_file: Path) -> Optional[tuple]:
    """Отримати API креди"""
    c = load_api_from_config(session_file.name)
    if c:
        return c
    e = load_api_from_env()
    if e:
        return e
    return None


def get_first_session() -> Optional[Path]:
    """Знайти першу .session файл в папці accs/"""
    if not ACCS_DIR.exists():
        print("❌ Папка accs/ не знайдена")
        return None
    sessions = [p for p in ACCS_DIR.iterdir() if p.is_file() and p.suffix == ".session"]
    if not sessions:
        print("❌ Немає .session файлів в accs/")
        return None
    return sessions[0]


# ------------------ TELETHON: ЗБІР ДАНИХ ------------------
async def collect_chat_data(chat_urls: List[str]) -> List[Dict]:
    """
    Збирає дані про чати через Telethon
    Повертає список словників з даними
    """
    load_dotenv(override=False)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Знаходимо сесію
    session_path = get_first_session()
    if not session_path:
        print("❌ Не знайдено session файлів")
        return []

    # API креди
    creds = resolve_api_creds(session_path)
    if not creds:
        print(f"❌ Не знайдено API_ID та API_HASH")
        print("Додайте їх в .env або config_accounts.json")
        return []

    api_id, api_hash = creds
    client = TelegramClient(str(session_path), api_id, api_hash)

    print(f"🔌 Підключення через {session_path.name}...")

    results = []

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Сесія не авторизована")
            await client.disconnect()
            return []

        print("✅ Авторизація успішна\n")

        for url in chat_urls:
            print(f"📥 Обробка: {url}")

            # Витягаємо username з URL
            username = url.strip().replace("https://t.me/", "").replace("@", "")

            try:
                # Отримуємо entity
                entity = await client.get_entity(username)

                chat_data = {
                    "url": f"https://t.me/{username}",
                    "username": username,
                    "title": "",
                    "about": "",
                    "pinned_message": "",
                    "admins": [],
                    "linked_channel": None,
                    "members_count": 0
                }

                # Базова інформація
                if hasattr(entity, "title"):
                    chat_data["title"] = entity.title

                # Детальна інформація
                if isinstance(entity, Channel):
                    try:
                        full = await client(GetFullChannelRequest(
                            channel=InputChannel(entity.id, entity.access_hash)
                        ))

                        # About
                        if hasattr(full.full_chat, "about"):
                            chat_data["about"] = full.full_chat.about or ""

                        # Members count
                        if hasattr(full.full_chat, "participants_count"):
                            chat_data["members_count"] = full.full_chat.participants_count

                        # Linked channel (якщо чат від каналу)
                        if hasattr(full.full_chat, "linked_chat_id") and full.full_chat.linked_chat_id:
                            try:
                                from telethon.tl.types import PeerChannel
                                linked_entity = await client.get_entity(PeerChannel(full.full_chat.linked_chat_id))
                                if hasattr(linked_entity, "username") and linked_entity.username:
                                    chat_data["linked_channel"] = {
                                        "username": linked_entity.username,
                                        "title": getattr(linked_entity, "title", "")
                                    }
                            except Exception as e:
                                print(f"   ⚠️ Не вдалось отримати linked channel: {e}")

                        # Pinned message
                        try:
                            pinned = full.full_chat.pinned_msg_id
                            if pinned:
                                msg = await client.get_messages(entity, ids=pinned)
                                if msg and msg.text:
                                    chat_data["pinned_message"] = msg.text[:500]  # Перші 500 символів
                        except Exception:
                            pass

                        # Адміни
                        try:
                            admins = await client(GetParticipantsRequest(
                                channel=InputChannel(entity.id, entity.access_hash),
                                filter=ChannelParticipantsAdmins(),
                                offset=0,
                                limit=10,
                                hash=0
                            ))

                            for user in admins.users:
                                if hasattr(user, "username") and user.username:
                                    admin_info = {
                                        "username": user.username,
                                        "first_name": getattr(user, "first_name", ""),
                                        "last_name": getattr(user, "last_name", ""),
                                        "is_bot": getattr(user, "bot", False)
                                    }
                                    chat_data["admins"].append(admin_info)

                        except Exception as e:
                            print(f"   ⚠️ Не вдалось отримати адмінів: {e}")

                    except FloodWaitError as e:
                        print(f"   ⏳ FloodWait {e.seconds}s, чекаємо...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"   ⚠️ Помилка отримання деталей: {e}")

                results.append(chat_data)
                print(f"   ✅ Зібрано: {chat_data['title']}")
                print(f"   👥 Учасників: {chat_data['members_count']}")
                print(f"   👤 Адмінів знайдено: {len(chat_data['admins'])}")
                if chat_data["linked_channel"]:
                    print(f"   🔗 Пов'язаний канал: @{chat_data['linked_channel']['username']}")
                print()

                # Невелика затримка між запитами
                await asyncio.sleep(2)

            except Exception as e:
                print(f"   ❌ Помилка: {e}\n")
                continue

    except Exception as e:
        print(f"❌ Критична помилка: {e}")
    finally:
        await client.disconnect()
        print("🔌 Відключено від Telegram\n")

    return results


def save_data_to_file(data: List[Dict]):
    """Зберігає зібрані дані у текстовий файл для ChatGPT"""
    with open(CHAT_DATA_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ДАНІ ПРО TELEGRAM ЧАТИ ДЛЯ АНАЛІЗУ\n")
        f.write("=" * 80 + "\n\n")

        for idx, chat in enumerate(data, 1):
            f.write(f"ЧАТ #{idx}\n")
            f.write("-" * 80 + "\n")
            f.write(f"URL: {chat['url']}\n")
            f.write(f"Username: @{chat['username']}\n")
            f.write(f"Назва: {chat['title']}\n")
            f.write(f"Кількість учасників: {chat['members_count']}\n\n")

            f.write(f"Опис чату:\n{chat['about']}\n\n")

            if chat['pinned_message']:
                f.write(f"Закріплене повідомлення:\n{chat['pinned_message']}\n\n")

            if chat['linked_channel']:
                f.write(f"Пов'язаний канал:\n")
                f.write(f"  @{chat['linked_channel']['username']} - {chat['linked_channel']['title']}\n\n")

            if chat['admins']:
                f.write(f"Адміністратори ({len(chat['admins'])}):\n")
                for admin in chat['admins']:
                    name = f"{admin['first_name']} {admin['last_name']}".strip()
                    f.write(f"  @{admin['username']} - {name}")
                    if admin['is_bot']:
                        f.write(" [BOT]")
                    f.write("\n")
                f.write("\n")

            f.write("=" * 80 + "\n\n")

    print(f"💾 Дані збережено в: {CHAT_DATA_FILE}\n")


# ------------------ SELENIUM: ChatGPT ------------------
def generate_descriptions_with_chatgpt(data: List[Dict]) -> List[str]:
    """
    Відкриває ChatGPT через Selenium та генерує описи
    """
    print("🤖 Запуск Selenium для ChatGPT...\n")

    # Налаштування Chrome
    chrome_options = Options()
    if CHROME_PROFILE_PATH:
        chrome_options.add_argument(f"user-data-dir={CHROME_PROFILE_PATH}")
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--headless")  # Розкоментуйте для фонового режиму

    driver = webdriver.Chrome(options=chrome_options)
    results = []

    try:
        # Відкриваємо ChatGPT
        driver.get(CHATGPT_URL)
        print("🌐 Відкрито ChatGPT Web")
        print("⏳ Зачекайте 10 секунд на завантаження сторінки...")
        time.sleep(10)

        # Промпт для ChatGPT
        base_prompt = """Проаналізуй інформацію про Telegram чат і створи ОДИН детальний опис у форматі:
"[Детальний опис чату для кого він, що там обговорюють, яка тематика]"

Важливо:
- Опис має бути конкретним та інформативним (НЕ загальні фрази типу "Маркетинг чат")
- Вкажи для кого цей чат (цільова аудиторія)
- Що саме обговорюють
- Приклади правильних описів:
  * "Фриланс чат для дизайнерів та SMM-спеціалістів"
  * "Чат по арбітражу трафіку, кейси, офери, поради"
  * "Спільнота розробників на Python, обговорення бібліотек та проектів"

Дані чату:
"""

        for idx, chat in enumerate(data, 1):
            print(f"\n📝 Генерація опису для: {chat['title']}")

            # Формуємо повідомлення для ChatGPT
            prompt = base_prompt + f"""
Назва: {chat['title']}
Опис: {chat['about']}
Кількість учасників: {chat['members_count']}
"""
            if chat['pinned_message']:
                prompt += f"Закріплене повідомлення: {chat['pinned_message'][:300]}\n"

            if chat['linked_channel']:
                prompt += f"Пов'язаний канал: {chat['linked_channel']['title']}\n"

            try:
                # Знаходимо поле вводу
                textarea = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "textarea"))
                )

                # Вводимо промпт
                textarea.clear()
                textarea.send_keys(prompt)
                time.sleep(1)

                # Відправляємо
                textarea.send_keys(Keys.RETURN)
                print("   ⏳ Чекаємо відповідь від ChatGPT...")

                # Чекаємо на відповідь (максимум 60 секунд)
                time.sleep(15)  # Базова затримка на генерацію

                # Отримуємо останню відповідь
                # ChatGPT відповіді зазвичай у <div> з класами, що містять "markdown"
                response_elements = driver.find_elements(By.CSS_SELECTOR, "[data-message-author-role='assistant']")

                if response_elements:
                    last_response = response_elements[-1].text
                    print(f"   ✅ Отримано опис: {last_response[:100]}...")

                    # Формуємо фінальний результат
                    admin_str = ""
                    if chat['admins']:
                        # Беремо першого адміна (не бота)
                        for admin in chat['admins']:
                            if not admin['is_bot']:
                                admin_str = f"@{admin['username']}"
                                break
                        if not admin_str and chat['admins']:  # Якщо всі боти, беремо першого
                            admin_str = f"@{chat['admins'][0]['username']}"

                    final = f"{last_response.strip()} ({chat['url']}) ({admin_str})"
                    results.append(final)
                else:
                    print("   ⚠️ Не вдалося отримати відповідь")
                    results.append(f"[Помилка генерації] ({chat['url']})")

            except Exception as e:
                print(f"   ❌ Помилка: {e}")
                results.append(f"[Помилка: {str(e)}] ({chat['url']})")

            # Затримка між запитами
            time.sleep(3)

        print("\n✅ Всі описи згенеровано!")

    except Exception as e:
        print(f"❌ Критична помилка Selenium: {e}")
    finally:
        print("\n⏳ Закриття браузера через 5 секунд...")
        time.sleep(5)
        driver.quit()

    return results


def save_results(results: List[str]):
    """Зберігає фінальні результати"""
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(result + "\n\n")

    print(f"\n💾 Результати збережено в: {RESULT_FILE}")


# ------------------ MAIN ------------------
async def main():
    print("=" * 80)
    print("🔍 АНАЛІЗ TELEGRAM ЧАТІВ З ChatGPT")
    print("=" * 80 + "\n")

    # Введення URL чатів
    print("Введіть посилання на Telegram чати (по одному на рядок):")
    print("Після останнього посилання натисніть Enter двічі\n")

    chat_urls = []
    while True:
        line = input().strip()
        if not line:
            break
        chat_urls.append(line)

    if not chat_urls:
        print("❌ Не введено жодного посилання")
        return

    print(f"\n📋 Буде оброблено {len(chat_urls)} чатів\n")

    # 1. Збір даних через Telethon
    print("=" * 80)
    print("КРОК 1: ЗБІР ДАНИХ ЧЕРЕЗ TELETHON")
    print("=" * 80 + "\n")

    data = await collect_chat_data(chat_urls)

    if not data:
        print("❌ Не вдалося зібрати дані")
        return

    # 2. Збереження в файл
    save_data_to_file(data)

    # 3. Запит користувача перед ChatGPT
    print("=" * 80)
    print("КРОК 2: ГЕНЕРАЦІЯ ОПИСІВ ЧЕРЕЗ ChatGPT")
    print("=" * 80 + "\n")
    print("⚠️ Зараз відкриється браузер Chrome з ChatGPT")
    print("⚠️ Переконайтеся, що ви авторизовані в ChatGPT")
    print("\nПродовжити? (y/n): ", end="")

    choice = input().strip().lower()
    if choice != 'y':
        print("❌ Скасовано користувачем")
        return

    # 4. Генерація описів
    results = generate_descriptions_with_chatgpt(data)

    # 5. Збереження результатів
    if results:
        save_results(results)

        print("\n" + "=" * 80)
        print("📊 РЕЗУЛЬТАТИ:")
        print("=" * 80 + "\n")
        for result in results:
            print(result)
            print()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    asyncio.run(main())
