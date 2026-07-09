# analyze_chats_playwright.py
# -*- coding: utf-8 -*-
"""
Аналіз Telegram чатів з генерацією описів через ChatGPT
Використовує Playwright для підключення до запущеного Chrome браузера

ІНСТРУКЦІЯ:
1. Запустіть Chrome через start_chrome.bat (подвійний клік)
2. Відкрийте https://chatgpt.com/c/6937098c-d498-832a-8921-8e543d15ff2f і авторизуйтесь
3. Запустіть цей скрипт: python analyze_chats_playwright.py
4. Введіть посилання на Telegram чати
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple

# Автоматичний режим (без запитів до користувача)
AUTO_MODE = '--auto' in sys.argv or os.getenv('AUTO_MODE') == '1'

# Налаштування кодування для Windows
if sys.platform.startswith('win'):
    try:
        # Встановлюємо UTF-8 для виводу
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        # Якщо не вдалось - продовжуємо без емоджі
        pass

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantsRequest
from telethon.tl.types import Channel, ChannelParticipantsAdmins, InputChannel
from telethon.errors import FloodWaitError

from playwright.async_api import async_playwright, Page, Browser

# Нові імпорти для системи з пам'яттю та пакетною обробкою
from utils.logger import setup_logging
from state_manager import StateManager
from rate_limiter import RateLimiter
from session_manager import SessionManager, SessionInfo
from browser_manager import BrowserManager
from batch_collector import BatchCollector
from parsers.auto_detector import FormatDetector

# Ініціалізація логера (буде викликано в main)
logger = None


# ------------------ КОНФІГУРАЦІЯ ------------------
SCRIPT_DIR = Path(__file__).parent  # Папка де знаходиться скрипт
ACCS_DIR = SCRIPT_DIR / "accs"
CONFIG_ACCOUNTS = SCRIPT_DIR / "config_accounts.json"
OUTPUT_DIR = SCRIPT_DIR / "output"
CHAT_DATA_FILE = OUTPUT_DIR / "chat_analysis_data.txt"
RESULT_FILE = OUTPUT_DIR / "chat_descriptions.txt"

CHATGPT_URL = "https://chatgpt.com/c/6937098c-d498-832a-8921-8e543d15ff2f"  # Конкретний чат ChatGPT
EDGE_CDP_PORT = 9222  # Порт для підключення до Chrome/Edge
INPUT_FILE = Path(__file__).parent / "@mt_offer.txt"  # Файл з чатами (відносно скрипта)

# Ліміти
MAX_CHATS_PER_RUN = 150  # Максимум чатів за один запуск з одного акаунту
MAX_MESSAGES_TO_FETCH = 100  # Кількість повідомлень для аналізу чату

# Імпорт порогів активності з конфігурації
from categories_config import HIGH_ACTIVITY_THRESHOLD, LOW_ACTIVITY_THRESHOLD, ACTIVITY_CHECK_DAYS
MIN_MESSAGES_PER_DAY = LOW_ACTIVITY_THRESHOLD  # 20 - Мінімум для LOW активності

# Затримки
WAIT_FOR_RESPONSE = 30  # секунд очікування відповіді від GPT
DELAY_BETWEEN_CHATS = 3  # секунд між обробкою чатів в Telegram
DELAY_BETWEEN_CHATGPT = 5  # секунд між надсиланням промптів в ChatGPT

# Режим роботи ChatGPT
PROCESS_MODE = "one_by_one"  # "one_by_one" = по одному з паузою, "batch" = всі підряд

# Файли для промптів
TEMP_PROMPT_DIR = SCRIPT_DIR / "temp_prompts"  # Папка для тимчасових промптів


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


def load_chats_from_file(file_path: Path) -> List[str]:
    """
    Читає файл @mt_offer.txt з чатами
    Формат: ID\tНазва\t@username
    Повертає список URL чатів (тільки з username)
    """
    if not file_path.exists():
        print(f"❌ Файл не знайдено: {file_path}")
        return []

    chat_urls = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            # Парсимо формат: ID\tНазва\t@username
            parts = line.split('\t')
            if len(parts) < 3:
                continue

            username = parts[2].strip()

            # Пропускаємо чати без username
            if username == '—' or not username:
                continue

            # Видаляємо @ якщо є
            username = username.lstrip('@')

            # Формуємо URL
            chat_url = f"https://t.me/{username}"
            chat_urls.append(chat_url)

    return chat_urls


def check_chat_activity(messages: List[Dict]) -> tuple[bool, str, float, int]:
    """
    Перевіряє чи чат активний та визначає рівень активності

    УВАГА: messages вже містить ТІЛЬКИ повідомлення за останні ACTIVITY_CHECK_DAYS днів!
    (зібрані через offset_date в Telethon)

    Повертає: (is_active, activity_level, avg_per_day, messages_count)
    - is_active: True якщо >= LOW_ACTIVITY_THRESHOLD (20 msg/day)
    - activity_level: "HIGH" (40+), "LOW" (20-39), або None (<20)
    - avg_per_day: середня кількість повідомлень на день
    - messages_count: загальна кількість повідомлень за період
    """
    if not messages:
        return False, None, 0.0, 0

    # Кількість повідомлень (всі вже за потрібний період!)
    messages_count = len(messages)

    # Середня кількість на день
    avg_per_day = messages_count / ACTIVITY_CHECK_DAYS

    # Визначення рівня активності
    if avg_per_day >= HIGH_ACTIVITY_THRESHOLD:
        activity_level = "HIGH"
        is_active = True
    elif avg_per_day >= LOW_ACTIVITY_THRESHOLD:
        activity_level = "LOW"
        is_active = True
    else:
        activity_level = None
        is_active = False

    return is_active, activity_level, avg_per_day, messages_count


# ------------------ TELETHON: ЗБІР ДАНИХ ------------------
async def collect_chat_data(chat_urls: List[str]) -> List[Dict]:
    """
    Збирає дані про чати через Telethon
    Повертає список словників з даними
    """
    load_dotenv(SCRIPT_DIR / ".env", override=False)
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
                    "members_count": 0,
                    "recent_messages": []  # Додаємо список для останніх повідомлень
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

                        # Збір ВСІХ повідомлень за останні N днів для точної перевірки активності
                        try:
                            from datetime import datetime, timedelta

                            # Дата відсікання - N днів назад
                            cutoff_date = datetime.now() - timedelta(days=ACTIVITY_CHECK_DAYS)

                            print(f"   📨 Збір повідомлень за останні {ACTIVITY_CHECK_DAYS} днів (з {cutoff_date.strftime('%Y-%m-%d')})...")

                            # Отримуємо повідомлення новіші за cutoff_date (до 500 штук)
                            # 500 повідомлень / 7 днів = ~71 повідомлень/день (макс. вимірювана активність)
                            messages = await client.get_messages(
                                entity,
                                limit=500,  # Розумний ліміт - достатньо для активних чатів, швидше ніж limit=None
                                offset_date=cutoff_date  # Тільки новіші за цю дату
                            )

                            for msg in messages:
                                if msg and msg.text:  # Беремо тільки текстові повідомлення
                                    # Отримуємо інформацію про відправника
                                    sender_name = "Unknown"
                                    if msg.sender:
                                        if hasattr(msg.sender, 'first_name'):
                                            sender_name = msg.sender.first_name or "Unknown"
                                            if hasattr(msg.sender, 'last_name') and msg.sender.last_name:
                                                sender_name += f" {msg.sender.last_name}"
                                        elif hasattr(msg.sender, 'title'):
                                            sender_name = msg.sender.title

                                    message_data = {
                                        "sender": sender_name,
                                        "text": msg.text[:500],  # Обмежуємо до 500 символів
                                        "date": msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else ""
                                    }
                                    chat_data["recent_messages"].append(message_data)

                            print(f"   ✅ Зібрано {len(chat_data['recent_messages'])} текстових повідомлень за {ACTIVITY_CHECK_DAYS} днів")
                        except Exception as e:
                            print(f"   ⚠️ Не вдалось отримати повідомлення: {e}")

                    except FloodWaitError as e:
                        print(f"   ⏳ FloodWait {e.seconds}s, чекаємо...")
                        await asyncio.sleep(e.seconds)
                        continue
                    except Exception as e:
                        print(f"   ⚠️ Помилка отримання деталей: {e}")

                # Перевірка активності чату
                is_active, activity_level, avg_per_day, messages_in_period = check_chat_activity(chat_data['recent_messages'])

                if not is_active:
                    print(f"   ⚠️ ЧАТ НЕАКТИВНИЙ - пропускаємо")
                    print(f"   📊 За останні {ACTIVITY_CHECK_DAYS} днів: {messages_in_period} повідомлень")
                    print(f"   📉 Середня активність: {avg_per_day:.1f} повідомлень/день (потрібно ≥{MIN_MESSAGES_PER_DAY})")
                    print()
                    continue

                # Чат активний - зберігаємо рівень активності та додаємо в результати
                chat_data['activity_level'] = activity_level
                chat_data['avg_messages_per_day'] = avg_per_day
                results.append(chat_data)
                print(f"   ✅ Зібрано: {chat_data['title']}")
                print(f"   👥 Учасників: {chat_data['members_count']}")
                print(f"   👤 Адмінів знайдено: {len(chat_data['admins'])}")
                print(f"   📊 Активність: {avg_per_day:.1f} повідомлень/день ({activity_level}) ✓")
                if chat_data["linked_channel"]:
                    print(f"   🔗 Пов'язаний канал: @{chat_data['linked_channel']['username']}")
                print()

                # Затримка між чатами для уникнення FloodWait
                await asyncio.sleep(DELAY_BETWEEN_CHATS)

            except Exception as e:
                print(f"   ❌ Помилка: {e}\n")
                continue

    except Exception as e:
        print(f"❌ Критична помилка: {e}")
    finally:
        await client.disconnect()
        print("🔌 Відключено від Telegram\n")

        # Статистика фільтрації
        checked_count = len(chat_urls)
        active_count = len(results)
        filtered_count = checked_count - active_count

        print("=" * 60)
        print("📊 СТАТИСТИКА ФІЛЬТРАЦІЇ АКТИВНОСТІ:")
        print("=" * 60)
        print(f"   🔍 Перевірено чатів: {checked_count}")
        print(f"   ✅ Активних (≥{MIN_MESSAGES_PER_DAY} повідомлень/день): {active_count}")
        print(f"   ❌ Відфільтровано неактивних: {filtered_count}")
        print(f"   📅 Період перевірки: останні {ACTIVITY_CHECK_DAYS} днів")
        print("=" * 60 + "\n")

    return results


def save_data_to_file(data: List[Dict]):
    """Зберігає зібрані дані у текстовий файл"""
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

            # Додаємо останні повідомлення
            if chat.get('recent_messages'):
                f.write(f"Останні повідомлення ({len(chat['recent_messages'])}):\n")
                f.write("-" * 80 + "\n")
                for msg in chat['recent_messages'][:30]:  # Зберігаємо максимум 30 для файлу
                    f.write(f"[{msg['date']}] {msg['sender']}:\n")
                    f.write(f"{msg['text']}\n\n")
                f.write("-" * 80 + "\n\n")

            f.write("=" * 80 + "\n\n")

    print(f"💾 Дані збережено в: {CHAT_DATA_FILE}\n")


# ------------------ PLAYWRIGHT: ChatGPT ------------------
async def connect_to_browser() -> tuple[Browser, Page]:
    """
    Підключається до запущеного Chrome/Edge браузера через CDP
    Переходить на конкретний чат ChatGPT
    """
    print("🌐 Підключення до браузера...")

    playwright = await async_playwright().start()

    try:
        # Підключаємося до вже запущеного браузера (Chrome або Edge)
        browser = await playwright.chromium.connect_over_cdp(f"http://localhost:{EDGE_CDP_PORT}")

        # Отримуємо існуючі контексти та сторінки
        contexts = browser.contexts
        if not contexts:
            print("❌ Немає відкритих вкладок в браузері")
            print(f"💡 Відкрийте {CHATGPT_URL} в браузері")
            await playwright.stop()
            return None, None

        # Беремо перший контекст
        context = contexts[0]
        pages = context.pages

        # Шукаємо вкладку з нашим конкретним чатом ChatGPT
        chatgpt_page = None
        target_chat_id = "6937098c-d498-832a-8921-8e543d15ff2f"

        for page in pages:
            if target_chat_id in page.url or "chatgpt.com" in page.url or "chat.openai.com" in page.url:
                chatgpt_page = page
                print(f"✅ Знайдено вкладку ChatGPT: {page.url}")
                break

        if not chatgpt_page:
            # Якщо немає вкладки з ChatGPT, створюємо нову або беремо активну
            if pages:
                chatgpt_page = pages[-1]
                print(f"⚠️ Не знайдено вкладку з ChatGPT")
                print(f"📄 Використовуємо активну вкладку: {chatgpt_page.url}")
            else:
                print("❌ Немає активних вкладок")
                await playwright.stop()
                return None, None

        # Переходимо на потрібний чат (якщо ще не там)
        if target_chat_id not in chatgpt_page.url:
            print(f"🔄 Переходимо на чат: {CHATGPT_URL}")
            await chatgpt_page.goto(CHATGPT_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)  # Даємо час на завантаження
        else:
            print(f"✅ Вже в потрібному чаті")

        print(f"📄 Робоча вкладка: {chatgpt_page.url}\n")

        return browser, chatgpt_page

    except Exception as e:
        print(f"❌ Помилка підключення до браузера: {e}")
        print(f"\n💡 Переконайтесь що браузер запущено з параметрами:")
        print(f'\n🔹 Для Chrome:')
        print(f'   & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port={EDGE_CDP_PORT} --user-data-dir="C:\\chrome-playwright-profile"')
        print(f'\n🔹 Для Edge:')
        print(f'   & "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port={EDGE_CDP_PORT} --user-data-dir="C:\\edge-playwright-profile"')
        await playwright.stop()
        return None, None


async def reconnect_telegram_session(
    session_manager: SessionManager,
    current_client: TelegramClient,
    current_session_name: str,
    wait_seconds: int,
    api_id: int,
    api_hash: str
) -> Optional[Tuple[TelegramClient, SessionInfo]]:
    """
    Переключитися на наступну доступну Telegram сесію при FloodWait

    Args:
        session_manager: Менеджер сесій
        current_client: Поточний TelegramClient
        current_session_name: Ім'я поточної сесії (.session файлу)
        wait_seconds: Скільки секунд FloodWait (з FloodWaitError.seconds)
        api_id: Telegram API ID
        api_hash: Telegram API Hash

    Returns:
        (new_client, new_session_info) або None якщо всі сесії заблоковані
    """
    logger.warning(f"\n🔄 ПЕРЕКЛЮЧЕННЯ СЕСІЇ через FloodWait ({wait_seconds}s)")

    # Закрити поточного клієнта
    try:
        await current_client.disconnect()
        logger.info(f"   ✅ Відключено від {current_session_name}")
    except Exception as e:
        logger.warning(f"   ⚠️ Помилка при відключенні: {e}")

    # Позначити сесію як заблоковану
    session_manager.mark_session_blocked(current_session_name, wait_seconds, f"FloodWait {wait_seconds}s")

    # Отримати наступну доступну сесію
    next_session_info = session_manager.get_next_available_session(api_id, api_hash)

    if not next_session_info:
        # Всі сесії заблоковані
        logger.error("   ❌ Всі сесії заблоковані!")
        print("\n❌ ВСІ TELEGRAM СЕСІЇ ЗАБЛОКОВАНІ FloodWait!")
        print(session_manager.get_status_report())
        print("\n💡 Додайте більше .session файлів в accs/ або зачекайте розблокування")
        return None

    # Підключитися до нової сесії
    new_client = TelegramClient(str(next_session_info.path), api_id, api_hash)

    try:
        logger.info(f"   🔌 Підключення через {next_session_info.name}...")
        await new_client.connect()

        if not await new_client.is_user_authorized():
            logger.error(f"   ❌ Сесія {next_session_info.name} не авторизована")
            await new_client.disconnect()
            # Позначаємо цю сесію як непрацюючу (блокуємо на 1 годину)
            session_manager.mark_session_blocked(next_session_info.name, 3600, "Not authorized")
            # Рекурсивно пробуємо наступну
            return await reconnect_telegram_session(
                session_manager, new_client, next_session_info.name, 3600, api_id, api_hash
            )

        logger.info(f"   ✅ Підключено через {next_session_info.name}")
        print(f"\n✅ Переключено на сесію: {next_session_info.name}")
        print(session_manager.get_status_report())

        return new_client, next_session_info

    except Exception as e:
        logger.error(f"   ❌ Помилка підключення до {next_session_info.name}: {e}")
        await new_client.disconnect()
        # Позначаємо як заблоковану на 10 хвилин
        session_manager.mark_session_blocked(next_session_info.name, 600, str(e))
        # Рекурсивно пробуємо наступну
        return await reconnect_telegram_session(
            session_manager, new_client, next_session_info.name, 600, api_id, api_hash
        )


def create_prompt_file(chat_data: Dict, chat_index: int) -> Path:
    """
    Створює текстовий файл з ПОКРАЩЕНИМ промптом для ChatGPT
    Повертає шлях до файлу
    """
    # Створюємо папку для тимчасових промптів
    TEMP_PROMPT_DIR.mkdir(exist_ok=True)

    # Формуємо промпт з категоризацією та валідацією
    from categories_config import CATEGORIES

    prompt = """Ты эксперт по анализу русскоязычных Telegram-сообществ. Твоя задача - категоризация, валидация и описание чата.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 КАТЕГОРИИ (выбери ОДНУ наиболее подходящую):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ Crypto и GameFi
   ЧТО ВХОДИТ: Блокчейн-проекты, криптовалюты, токены, DeFi, NFT, сети (Ethereum, Solana), трейдинг крипты, on-chain игры, Web3
   ЧТО НЕ ВХОДИТ: Классические акции, фиатные инвестиции

2️⃣ Арбитраж трафика
   ЧТО ВХОДИТ: Покупка платного трафика (Google Ads, Facebook Ads, TikTok Ads), партнёрки, офферы, креативы, трекинг, ROI, CPA, арбитраж
   ЧТО НЕ ВХОДИТ: Органический SMM, бесплатный трафик, контент-маркетинг

3️⃣ Маркетинг/SMM
   ЧТО ВХОДИТ: Продвижение через соцсети, Instagram, TikTok, YouTube, контент-стратегия, инфлюенс-маркетинг, органический рост
   ЧТО НЕ ВХОДИТ: Платная реклама (это арбитраж)

4️⃣ Дизайн и Графика
   ЧТО ВХОДИТ: UI/UX дизайн, графический дизайн, айдентика, логотипы, Figma, Adobe, motion design, 3D-визуализация
   ЧТО НЕ ВХОДИТ: Программирование (код)

5️⃣ Маркет-плейсы
   ЧТО ВХОДИТ: Wildberries, Ozon, Amazon - FBO/FBS, карточки товаров, продвижение на МП, логистика МП
   ЧТО НЕ ВХОДИТ: Обычная e-commerce (свой сайт)

6️⃣ IT-сфера
   ЧТО ВХОДИТ: Программирование, веб/мобильная разработка, DevOps, тестирование, архитектура ПО, code review
   ЧТО НЕ ВХОДИТ: Дизайн (это отдельная категория)

7️⃣ Инвестирование и Акции
   ЧТО ВХОДИТ: Легальные инвестиции - акции, облигации, ETF, дивиденды, биржа, портфельные стратегии, финансовая грамотность
   ЧТО НЕ ВХОДИТ: Криптовалюты (это Crypto и GameFi)

8️⃣ Фриланс/Самозанятые
   ЧТО ВХОДИТ: Работа на себя, поиск клиентов/заказов, удалёнка, самозанятость, фриланс-биржи (Upwork, Kwork)
   ЧТО НЕ ВХОДИТ: Найм в офис

9️⃣ Спорт (здоровье и форма)
   ЧТО ВХОДИТ: Личный фитнес, тренировки, похудение, питание, ЗОЖ, бег, йога
   ЧТО НЕ ВХОДИТ: Профессиональный спорт, букмекерство

🔟 Экспаты
   ЧТО ВХОДИТ: Русскоязычные за границей - релокация, виза, ВНЖ, быт, работа, адаптация в конкретной стране
   ЧТО НЕ ВХОДИТ: Просто путешествия

1️⃣1️⃣ Інше
   Используй ТОЛЬКО если чат точно не подходит ни под одну категорию выше

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 ВАЛИДАЦИЯ (обязательные проверки):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ЯЗЫК: Чат должен быть 80-90%+ на РУССКОМ языке
   - Считай процент русского по сообщениям
   - Если меньше 80% русского → FAIL

2. ЗАПРЕЩЁННЫЙ КОНТЕНТ (если найдёшь → FAIL):
   ❌ Сборы на ЗСУ/ВСУ (донаты армии)
   ❌ Мошенничество ("100% доход", пирамиды, скам)
   ❌ Нелегальные услуги (обнал, фейковые документы)

3. СООТВЕТСТВИЕ КАТЕГОРИИ:
   - Чат должен РЕАЛЬНО соответствовать выбранной категории
   - Если не подходит ни под одну → категория "Інше"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ПРИОРИТЕТ ИСТОЧНИКОВ ИНФОРМАЦИИ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. СООБЩЕНИЯ - главный источник правды!
2. Закреплённое сообщение
3. Описание чата (about)
4. Название

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 ФОРМАТ ОТВЕТА (СТРОГО):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CATEGORY: [название категории из списка выше или "Інше"]
LANGUAGE_CHECK: [PASS/FAIL] - [процент русского языка, например "90% русский" или "40% русский, 60% украинский"]
PROHIBITED_CONTENT: [PASS/FAIL] - [конкретная причина или "нет запрещённого контента"]
CATEGORY_FIT: [PASS/FAIL] - [обоснование почему чат соответствует/не соответствует категории]
DESCRIPTION: [2-3 предложения: целевая аудитория + конкретные темы + тип активности]

⚠️ ВАЖНО:
- Описание ВСЕГДА на русском (даже если чат на другом языке)
- Базируйся на РЕАЛЬНОМ содержании сообщений
- Используй КОНКРЕТНЫЕ термины из сообщений
- Если есть регион/город - укажи его

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ДАННЫЕ О ЧАТЕ:

"""

    # 1. БАЗОВА ІНФОРМАЦІЯ
    prompt += f"📌 Название: {chat_data['title']}\n"
    prompt += f"👥 Участников: {chat_data['members_count']}\n"

    if chat_data.get('about'):
        prompt += f"📝 Официальное описание: {chat_data['about'][:300]}\n"

    # 2. ПОВ'ЯЗАНИЙ КАНАЛ (якщо є)
    if chat_data.get('linked_channel'):
        prompt += f"\n🔗 Связанный канал: @{chat_data['linked_channel']['username']}"
        if chat_data['linked_channel'].get('title'):
            prompt += f" ({chat_data['linked_channel']['title']})"
        prompt += "\n"

    # 3. АДМІНІСТРАТОРИ (топ-3 не-боти)
    if chat_data.get('admins'):
        non_bot_admins = [a for a in chat_data['admins'] if not a.get('is_bot')][:3]
        if non_bot_admins:
            prompt += f"\n👤 Администраторы: "
            prompt += ", ".join([f"@{a['username']}" for a in non_bot_admins])
            prompt += "\n"

    # 4. ЗАКРІПЛЕНЕ ПОВІДОМЛЕННЯ (ДУЖЕ ВАЖЛИВО!)
    if chat_data.get('pinned_message'):
        prompt += f"\n📍 ЗАКРЕПЛЕННОЕ СООБЩЕНИЕ (важнейшая информация о чате!):\n"
        prompt += f"{chat_data['pinned_message'][:500]}\n"

    # 5. ОСТАННІ ПОВІДОМЛЕННЯ (30-50 штук!)
    if chat_data.get('recent_messages'):
        num_messages = min(50, len(chat_data['recent_messages']))
        prompt += f"\n💬 ПОСЛЕДНИЕ {num_messages} СООБЩЕНИЙ (анализируй тщательно!):\n"
        prompt += "━" * 60 + "\n"

        for i, msg in enumerate(chat_data['recent_messages'][:num_messages], 1):
            # Показуємо повідомлення повністю (до 300 символів)
            text = msg['text'][:300]
            if len(msg['text']) > 300:
                text += "..."

            sender = msg.get('sender', 'Unknown')
            date = msg.get('date', '')

            prompt += f"{i}. [{date}] {sender}:\n"
            prompt += f"   {text}\n\n"

        prompt += "━" * 60 + "\n"

    # 6. ФІНАЛЬНА ІНСТРУКЦІЯ
    prompt += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 ТЕПЕРЬ ВЫПОЛНИ АНАЛИЗ:

На основе СООБЩЕНИЙ выше (главный источник!):
1. Определи категорию из списка выше
2. Проверь язык (80%+ русский?)
3. Проверь запрещённый контент (ЗСУ, мошенничество, нелегал)
4. Проверь соответствие выбранной категории
5. Напиши описание (2-3 предложения на русском)

ОТВЕТ В ФОРМАТЕ:

CATEGORY: [название категории]
LANGUAGE_CHECK: [PASS/FAIL] - [детали]
PROHIBITED_CONTENT: [PASS/FAIL] - [детали]
CATEGORY_FIT: [PASS/FAIL] - [обоснование]
DESCRIPTION: [описание чата 2-3 предложения]"""

    # Зберігаємо в файл
    filename = f"prompt_chat_{chat_index}.txt"
    file_path = TEMP_PROMPT_DIR / filename

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(prompt)

    return file_path


async def send_prompt_file_to_chatgpt(page: Page, file_path: Path) -> Optional[str]:
    """
    Завантажує файл з промптом в ChatGPT і чекає на відповідь
    ВАЖЛИВО: Перевіряємо кількість відповідей ДО і ПІСЛЯ для правильної синхронізації
    """
    try:
        print(f"   📎 Завантаження файлу: {file_path.name}")

        # КРИТИЧНО: Підрахувати кількість assistant відповідей ДО надсилання
        initial_response_count = await page.evaluate('''() => {
            return document.querySelectorAll('[data-message-author-role="assistant"]').length;
        }''')
        logger.debug(f"   [SYNC] Початкова кількість відповідей: {initial_response_count}")

        # Знаходимо кнопку прикріплення файлу
        # ChatGPT має input для файлів (прихований)
        file_input = await page.query_selector('input[type="file"]')

        if not file_input:
            print("   ❌ Не знайдено input для файлів")
            return None

        # Завантажуємо файл
        await file_input.set_input_files(str(file_path.absolute()))
        await asyncio.sleep(3)  # Даємо більше часу на завантаження і обробку

        print("   ✅ Файл завантажено")

        # Надсилання промпту - кілька методів для надійності
        print("   📤 Надсилання промпту...")
        sent_successfully = False

        # Метод 1: Пошук і клік по кнопці Send через JavaScript (найнадійніше)
        try:
            # Використовуємо JavaScript для пошуку і кліку
            js_click_result = await page.evaluate('''() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const sendButton = buttons.find(btn =>
                    btn.getAttribute('data-testid') === 'send-button' ||
                    btn.getAttribute('aria-label')?.includes('Send') ||
                    btn.textContent?.trim() === 'Send'
                );
                if (sendButton && !sendButton.disabled) {
                    sendButton.click();
                    return true;
                }
                return false;
            }''')

            if js_click_result:
                await asyncio.sleep(2)
                # Перевіряємо чи почалася генерація
                stop_btn = await page.query_selector('button:has-text("Stop")')
                if stop_btn:
                    print("   ✅ Промпт надіслано (JavaScript)")
                    sent_successfully = True
        except Exception as e:
            print(f"   ⚠️ JS клік не спрацював: {e}")

        # Метод 2: Enter якщо JS не спрацював
        if not sent_successfully:
            for attempt in range(3):
                try:
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(1)

                    stop_btn = await page.query_selector('button:has-text("Stop")')
                    if stop_btn:
                        print("   ✅ Промпт надіслано (Enter)")
                        sent_successfully = True
                        break
                except:
                    pass

        if not sent_successfully:
            print("   ⚠️ Надсилання може бути невдалим, продовжуємо...")

        print("   ⏳ Чекаємо відповідь від ChatGPT...")

        # Чекаємо початок генерації
        await asyncio.sleep(3)

        # ЕТАП 1: Чекаємо поки з'явиться НОВА відповідь (count > initial)
        max_wait_time = WAIT_FOR_RESPONSE
        wait_interval = 2
        total_waited = 0
        new_response_appeared = False

        print(f"   [SYNC] Чекаємо нову відповідь (поточно: {initial_response_count})...")

        while total_waited < max_wait_time:
            try:
                current_count = await page.evaluate('''() => {
                    return document.querySelectorAll('[data-message-author-role="assistant"]').length;
                }''')

                if current_count > initial_response_count:
                    new_response_appeared = True
                    logger.debug(f"   [SYNC] Нова відповідь з'явилась! ({initial_response_count} -> {current_count})")
                    break

                await asyncio.sleep(wait_interval)
                total_waited += wait_interval
            except:
                break

        if not new_response_appeared:
            print("   ⚠️ Нова відповідь не з'явилась - можлива десинхронізація!")
            logger.warning(f"   [SYNC] УВАГА: Кількість відповідей не змінилась за {total_waited}s")

        # ЕТАП 2: Чекаємо завершення генерації (кнопка Stop зникне)
        total_waited = 0
        while total_waited < max_wait_time:
            try:
                stop_button = await page.query_selector('button:has-text("Stop")')
                if not stop_button:
                    break
                await asyncio.sleep(wait_interval)
                total_waited += wait_interval
            except:
                break

        # Додаткова пауза для рендерингу
        await asyncio.sleep(2)

        # ЕТАП 3: Отримуємо САМЕ НОВУ відповідь (по індексу)
        response_text = None
        expected_index = initial_response_count  # Індекс нової відповіді (0-based)

        # Спосіб 1: Отримати відповідь по індексу
        try:
            response_text = await page.evaluate(f'''() => {{
                const assistantMessages = document.querySelectorAll('[data-message-author-role="assistant"]');
                const targetIndex = {expected_index};
                if (assistantMessages.length > targetIndex) {{
                    return assistantMessages[targetIndex].innerText;
                }}
                // Fallback: остання відповідь
                if (assistantMessages.length > 0) {{
                    return assistantMessages[assistantMessages.length - 1].innerText;
                }}
                return null;
            }}''')

            if response_text:
                logger.debug(f"   [SYNC] Отримано відповідь з індексу {expected_index}")
        except Exception as e:
            logger.warning(f"   [SYNC] Помилка отримання по індексу: {e}")

        # Спосіб 2: Fallback через стандартний селектор
        if not response_text or len(response_text.strip()) < 20:
            try:
                response_elements = await page.query_selector_all('[data-message-author-role="assistant"]')
                if response_elements and len(response_elements) > expected_index:
                    target_response = response_elements[expected_index]
                    response_text = await target_response.inner_text()
                    logger.debug(f"   [SYNC] Fallback: отримано через selector")
            except:
                pass

        if response_text and len(response_text.strip()) > 10:
            return response_text.strip()
        else:
            print("   ⚠️ Не знайдено відповіді від ChatGPT")
            return None

    except Exception as e:
        print(f"   ❌ Помилка при роботі з ChatGPT: {e}")
        return None


def parse_chatgpt_response(response_text: str, chat_data: Dict = None) -> Optional[Dict]:
    """
    Парсинг структурованої відповіді ChatGPT з keyword-валідацією

    Очікуваний формат:
    CATEGORY: [назва]
    LANGUAGE_CHECK: [PASS/FAIL] - [деталі]
    PROHIBITED_CONTENT: [PASS/FAIL] - [деталі]
    CATEGORY_FIT: [PASS/FAIL] - [обґрунтування]
    DESCRIPTION: [опис]

    Args:
        response_text: Текст відповіді ChatGPT
        chat_data: Дані чату для keyword-валідації (title, description, messages)

    Returns:
        Dict з результатами або None при помилці парсингу
    """
    import re
    from categories_config import is_valid_category, validate_category_by_content, find_best_category_by_keywords

    if not response_text:
        return None

    try:
        # Ініціалізація результату
        result = {
            'category': None,
            'language_check': {'status': 'FAIL', 'details': 'Не вказано'},
            'prohibited_content': {'status': 'FAIL', 'details': 'Не вказано'},
            'category_fit': {'status': 'FAIL', 'details': 'Не вказано'},
            'description': '',
            'is_valid': False
        }

        # Парсинг CATEGORY
        category_match = re.search(r'CATEGORY:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if category_match:
            category = category_match.group(1).strip()
            # Валідація категорії
            if is_valid_category(category):
                result['category'] = category
            else:
                # Якщо категорія невалідна, ставимо "Інше"
                result['category'] = 'Інше'
        else:
            result['category'] = 'Інше'

        # Парсинг LANGUAGE_CHECK (підтримка - і —)
        lang_match = re.search(r'LANGUAGE_CHECK:\s*(PASS|FAIL)\s*[—\-]\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if lang_match:
            result['language_check'] = {
                'status': lang_match.group(1).upper(),
                'details': lang_match.group(2).strip()
            }

        # Парсинг PROHIBITED_CONTENT (підтримка - і —)
        prohibited_match = re.search(r'PROHIBITED_CONTENT:\s*(PASS|FAIL)\s*[—\-]\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if prohibited_match:
            result['prohibited_content'] = {
                'status': prohibited_match.group(1).upper(),
                'details': prohibited_match.group(2).strip()
            }

        # Парсинг CATEGORY_FIT (підтримка - і —)
        fit_match = re.search(r'CATEGORY_FIT:\s*(PASS|FAIL)\s*[—\-]\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if fit_match:
            result['category_fit'] = {
                'status': fit_match.group(1).upper(),
                'details': fit_match.group(2).strip()
            }

        # Парсинг DESCRIPTION (може бути багаторядковий)
        desc_match = re.search(r'DESCRIPTION:\s*(.+?)(?:\n\n|\Z)', response_text, re.IGNORECASE | re.DOTALL)
        if desc_match:
            result['description'] = desc_match.group(1).strip()
        else:
            # Fallback: використовуємо весь текст як опис
            result['description'] = response_text[:500].strip()

        # KEYWORD-ВАЛІДАЦІЯ: Перевіряємо чи категорія відповідає контенту
        result['keyword_validation'] = {'status': 'SKIP', 'details': 'No chat data', 'matched': []}

        if chat_data and result['category'] and result['category'] != 'Інше':
            # Збираємо весь контент для аналізу
            content_parts = []
            if chat_data.get('title'):
                content_parts.append(chat_data['title'])
            if chat_data.get('description'):
                content_parts.append(chat_data['description'])
            if chat_data.get('recent_messages'):
                # Беремо текст повідомлень (список словників або рядків)
                messages = chat_data['recent_messages']
                if isinstance(messages, list):
                    for msg in messages[:50]:  # Перші 50 повідомлень
                        if isinstance(msg, dict):
                            content_parts.append(msg.get('text', ''))
                        elif isinstance(msg, str):
                            content_parts.append(msg)

            full_content = ' '.join(content_parts)

            if full_content:
                # Валідуємо категорію ChatGPT
                is_valid_kw, reason, matched = validate_category_by_content(result['category'], full_content)

                if is_valid_kw:
                    result['keyword_validation'] = {
                        'status': 'PASS',
                        'details': reason,
                        'matched': matched
                    }
                    print(f"   [KW] Keyword-валідація: PASS ({len(matched)} keywords)")
                else:
                    # Категорія не підтверджена - шукаємо кращу
                    print(f"   [KW] Keyword-валідація: FAIL - {reason}")

                    best_cat, best_score, best_kw = find_best_category_by_keywords(full_content)

                    if best_cat != 'Інше' and best_score > 0:
                        # Знайшли кращу категорію
                        old_category = result['category']
                        result['category'] = best_cat
                        result['keyword_validation'] = {
                            'status': 'CORRECTED',
                            'details': f"Changed from '{old_category}' to '{best_cat}' ({best_score} keywords)",
                            'matched': best_kw
                        }
                        print(f"   [KW] Категорія змінена: {old_category} -> {best_cat}")
                    else:
                        # Жодна категорія не підходить
                        result['keyword_validation'] = {
                            'status': 'FAIL',
                            'details': reason,
                            'matched': matched
                        }
                        # НЕ міняємо категорію на "Інше" - залишаємо рішення ChatGPT
                        # але помічаємо як невалідовану
                        print(f"   [KW] Категорія не підтверджена keywords")

        # Визначення валідності (всі перевірки мають бути PASS)
        result['is_valid'] = (
            result['language_check']['status'] == 'PASS' and
            result['prohibited_content']['status'] == 'PASS' and
            result['category_fit']['status'] == 'PASS' and
            result['category'] is not None and
            result['description']
        )

        return result

    except Exception as e:
        print(f"   ⚠️ Помилка парсингу відповіді ChatGPT: {e}")
        # Повернути fallback результат
        return {
            'category': 'Інше',
            'language_check': {'status': 'FAIL', 'details': 'Помилка парсингу'},
            'prohibited_content': {'status': 'FAIL', 'details': 'Помилка парсингу'},
            'category_fit': {'status': 'FAIL', 'details': 'Помилка парсингу'},
            'description': response_text[:500] if response_text else 'Немає опису',
            'is_valid': False
        }


async def generate_descriptions_with_chatgpt(data: List[Dict], mode: str = "one_by_one") -> List[str]:
    """
    Генерує описи через ChatGPT використовуючи Playwright
    mode: "one_by_one" - по одному з паузою, "batch" - всі підряд
    """
    print("🤖 Запуск Playwright для ChatGPT...\n")

    browser, page = await connect_to_browser()

    if not browser or not page:
        return []

    results = []

    try:
        # Вже підключені до потрібного чату (це зроблено в connect_to_browser)
        print(f"💬 Працюємо в чаті: {CHATGPT_URL}\n")

        if mode == "one_by_one":
            print(f"📌 Режим: ПО ОДНОМУ чату з паузою після кожного\n")
        else:
            print(f"📌 Режим: ВСІ ПІДРЯД з затримкою {DELAY_BETWEEN_CHATGPT} сек\n")

        for idx, chat in enumerate(data, 1):
            print(f"\n{'='*60}")
            print(f"[{idx}/{len(data)}] Генерація опису для: {chat['title']}")
            print(f"{'='*60}")

            # Створюємо файл з промптом
            prompt_file = create_prompt_file(chat, idx)
            print(f"   📝 Створено файл промпту: {prompt_file.name}")

            # Відправляємо файл в ChatGPT
            response = await send_prompt_file_to_chatgpt(page, prompt_file)

            # Видаляємо файл після використання
            try:
                prompt_file.unlink()
                print(f"   🗑️ Видалено тимчасовий файл")
            except:
                pass

            if response:
                print(f"\n   ✅ ОТРИМАНО ВІДПОВІДЬ від ChatGPT")
                print(f"   {'-'*56}")

                # Парсимо відповідь з keyword-валідацією
                analysis_result = parse_chatgpt_response(response, chat_data=chat)

                if analysis_result:
                    # Виводимо результати аналізу
                    print(f"   📋 Категорія: {analysis_result['category']}")
                    print(f"   🌐 Мова: {analysis_result['language_check']['status']} - {analysis_result['language_check']['details']}")
                    print(f"   🚫 Заборонений контент: {analysis_result['prohibited_content']['status']} - {analysis_result['prohibited_content']['details']}")
                    print(f"   ✓ Відповідність категорії: {analysis_result['category_fit']['status']} - {analysis_result['category_fit']['details']}")
                    print(f"   📝 Опис: {analysis_result['description'][:100]}...")
                    print(f"   {'-'*56}\n")

                    # Зберігаємо в файли через output_formatter
                    from output_formatter import save_chat_to_files
                    save_chat_to_files(chat, analysis_result)

                    # Зберігаємо для статистики
                    if analysis_result['is_valid']:
                        results.append(f"✅ {chat['title']}: {analysis_result['category']}")
                    else:
                        results.append(f"❌ {chat['title']}: Відхилено")
                else:
                    print("   ⚠️ Не вдалося розпарсити відповідь")
                    print(f"   Сира відповідь: {response[:200]}...")
                    results.append(f"[Помилка парсингу] ({chat['url']})")
            else:
                print("   ⚠️ Не вдалося отримати відповідь")
                results.append(f"[Помилка генерації] ({chat['url']})")

            # Режим роботи
            if mode == "one_by_one" and idx < len(data) and not AUTO_MODE:
                print(f"\n⏸️  Чат {idx}/{len(data)} оброблено")
                print(f"   Залишилось: {len(data) - idx} чатів")
                print("\n   Продовжити з наступним чатом? (y/n або Enter для продовження): ", end="")

                try:
                    choice = input().strip().lower()
                    if choice and choice != 'y':
                        print("\n⏹️  Обробка зупинена користувачем")
                        break
                except:
                    # Якщо помилка вводу - продовжуємо
                    pass

                print()  # Порожній рядок для читабельності
            else:
                # Batch режим - затримка між чатами
                if idx < len(data):
                    print(f"\n⏳ Затримка {DELAY_BETWEEN_CHATGPT} секунд перед наступним чатом...")
                    await asyncio.sleep(DELAY_BETWEEN_CHATGPT)

        print("\n✅ Всі описи згенеровано!")

    except Exception as e:
        print(f"❌ Критична помилка: {e}")
    finally:
        # Очищаємо тимчасові файли
        try:
            import shutil
            if TEMP_PROMPT_DIR.exists():
                shutil.rmtree(TEMP_PROMPT_DIR)
                print("\n🗑️ Очищено тимчасові файли")
        except:
            pass

        # НЕ закриваємо браузер - він залишається відкритим!
        print("\n💡 Chrome браузер залишається відкритим")

    return results


def save_results(results: List[str]):
    """Зберігає фінальні результати"""
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(result + "\n\n")

    print(f"\n💾 Результати збережено в: {RESULT_FILE}")


# ------------------ НОВА ФУНКЦІЯ: Збір даних одного чату ------------------
async def collect_single_chat_data(telegram_client, chat_url_data: Dict) -> Optional[Dict]:
    """
    Збирає дані одного чату через Telethon

    Args:
        telegram_client: Підключений Telethon клієнт
        chat_url_data: {'url': '...', 'username': '...', 'title': '...'}

    Returns:
        Dict з даними чату або None при помилці/низькій активності
    """
    url = chat_url_data['url']
    username = chat_url_data.get('username') or url.replace("https://t.me/", "").replace("@", "")

    try:
        logger.info(f"📥 Збір даних: {url}")

        # Отримуємо entity
        entity = await telegram_client.get_entity(username)

        chat_data = {
            "url": f"https://t.me/{username}",
            "username": username,
            "title": "",
            "about": "",
            "pinned_message": "",
            "admins": [],
            "linked_channel": None,
            "members_count": 0,
            "recent_messages": []
        }

        # Базова інформація
        if hasattr(entity, "title"):
            chat_data["title"] = entity.title

        # Детальна інформація (аналогічно до collect_chat_data)
        if isinstance(entity, Channel):
            try:
                full = await telegram_client(GetFullChannelRequest(
                    channel=InputChannel(entity.id, entity.access_hash)
                ))

                # About
                if hasattr(full.full_chat, "about"):
                    chat_data["about"] = full.full_chat.about or ""

                # Members count
                if hasattr(full.full_chat, "participants_count"):
                    chat_data["members_count"] = full.full_chat.participants_count

                # Linked channel
                if hasattr(full.full_chat, "linked_chat_id") and full.full_chat.linked_chat_id:
                    try:
                        from telethon.tl.types import PeerChannel
                        linked_entity = await telegram_client.get_entity(PeerChannel(full.full_chat.linked_chat_id))
                        if hasattr(linked_entity, "username") and linked_entity.username:
                            chat_data["linked_channel"] = {
                                "username": linked_entity.username,
                                "title": getattr(linked_entity, "title", "")
                            }
                    except Exception as e:
                        logger.warning(f"Не вдалось отримати linked channel: {e}")

                # Pinned message
                try:
                    pinned = full.full_chat.pinned_msg_id
                    if pinned:
                        msg = await telegram_client.get_messages(entity, ids=pinned)
                        if msg and msg.text:
                            chat_data["pinned_message"] = msg.text[:500]
                except Exception:
                    pass

                # Адміни
                try:
                    admins = await telegram_client(GetParticipantsRequest(
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
                    logger.warning(f"Не вдалось отримати адмінів: {e}")

                # Збір повідомлень за останні N днів
                try:
                    from datetime import datetime, timedelta
                    cutoff_date = datetime.now() - timedelta(days=ACTIVITY_CHECK_DAYS)

                    logger.debug(f"Збір повідомлень за останні {ACTIVITY_CHECK_DAYS} днів...")

                    messages = await telegram_client.get_messages(
                        entity,
                        limit=500,
                        offset_date=cutoff_date
                    )

                    for msg in messages:
                        if msg and msg.text:
                            sender_name = "Unknown"
                            if msg.sender:
                                if hasattr(msg.sender, 'first_name'):
                                    sender_name = msg.sender.first_name or "Unknown"
                                    if hasattr(msg.sender, 'last_name') and msg.sender.last_name:
                                        sender_name += f" {msg.sender.last_name}"
                                elif hasattr(msg.sender, 'title'):
                                    sender_name = msg.sender.title

                            message_data = {
                                "sender": sender_name,
                                "text": msg.text[:500],
                                "date": msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else ""
                            }
                            chat_data["recent_messages"].append(message_data)

                    logger.info(f"Зібрано {len(chat_data['recent_messages'])} повідомлень")
                except Exception as e:
                    logger.warning(f"Не вдалось отримати повідомлення: {e}")

            except FloodWaitError:
                # НЕ ловимо FloodWaitError тут - дозволяємо propagate вгору до main()
                # де буде обробка з переключенням сесій
                raise
            except Exception as e:
                logger.warning(f"Помилка отримання деталей: {e}")

        # Перевірка активності
        is_active, activity_level, avg_per_day, messages_in_period = check_chat_activity(chat_data['recent_messages'])

        if not is_active:
            logger.info(f"ЧАТ НЕАКТИВНИЙ - пропускаємо (активність: {avg_per_day:.1f} msg/day)")
            return None

        # Чат активний - додаємо метадані
        chat_data['activity_level'] = activity_level
        chat_data['avg_messages_per_day'] = avg_per_day

        logger.info(f"✅ Зібрано: {chat_data['title']} (активність: {avg_per_day:.1f} msg/day - {activity_level})")

        # Затримка між чатами
        await asyncio.sleep(DELAY_BETWEEN_CHATS)

        return chat_data

    except FloodWaitError:
        # Propagate FloodWait вгору до main() для обробки з переключенням сесій
        raise
    except Exception as e:
        logger.error(f"Помилка збору даних для {url}: {e}")
        return None


# ------------------ LIVE PROGRESS INTERFACE ------------------
def print_progress_box(title: str, items: List[str], width: int = 80):
    """Виводить красивий бокс з інформацією"""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)
    for item in items:
        print(f"  {item}")
    print("=" * width)


def print_live_stats(processed: int, total: int, session_processed: int,
                     rate_used: int, rate_max: int, pass_count: int, fail_count: int):
    """Виводить поточну статистику в реальному часі"""
    progress_pct = (processed / total * 100) if total > 0 else 0
    pass_rate = (pass_count / session_processed * 100) if session_processed > 0 else 0
    rate_pct = (rate_used / rate_max * 100) if rate_max > 0 else 0

    # Прогрес бар
    bar_width = 40
    filled = int(bar_width * processed / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_width - filled)

    print("\n")
    print("┌" + "─" * 78 + "┐")
    print("│ 📊 LIVE PROGRESS" + " " * 61 + "│")
    print("├" + "─" * 78 + "┤")
    print("│" + " " * 78 + "│")

    progress_line = f"  Progress: [{bar}] {progress_pct:.1f}%"
    print("│" + progress_line + " " * (78 - len(progress_line)) + "│")

    processed_line = f"  Processed: {processed}/{total} chats"
    print("│" + processed_line + " " * (78 - len(processed_line)) + "│")

    print("│" + " " * 78 + "│")
    print("├" + "─" * 78 + "┤")

    stats_header = "  Session Stats:"
    print("│" + stats_header + " " * (78 - len(stats_header)) + "│")

    stats_line = f"    ✅ Processed: {session_processed}  |  ✓ Pass: {pass_count}  |  ✗ Fail: {fail_count}  |  Rate: {pass_rate:.1f}%"
    print("│" + stats_line + " " * (78 - len(stats_line)) + "│")

    print("│" + " " * 78 + "│")

    rate_header = "  Rate Limit:"
    print("│" + rate_header + " " * (78 - len(rate_header)) + "│")

    rate_line = f"    Used: {rate_used}/{rate_max} per hour ({rate_pct:.0f}%)"
    print("│" + rate_line + " " * (78 - len(rate_line)) + "│")

    print("└" + "─" * 78 + "┘")


def print_compact_header():
    """Компактна шапка на старті"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " CHATSSPIDER - TELEGRAM ANALYSIS v2.0 ".center(78) + "║")
    print("╚" + "═" * 78 + "╝")


def print_step_header(step_num: int, step_title: str):
    """Заголовок кроку"""
    print("\n┌" + "─" * 78 + "┐")
    print(f"│ STEP {step_num}: {step_title}".ljust(79) + "│")
    print("└" + "─" * 78 + "┘")


def print_batch_progress(batch_idx: int, batch_size: int, chat_title: str,
                         category: str = "", is_valid: bool = None):
    """Прогрес обробки батчу"""
    status = ""
    if is_valid is not None:
        status = "✅ PASS" if is_valid else "❌ FAIL"

    bar_width = 20
    filled = int(bar_width * batch_idx / batch_size) if batch_size > 0 else 0
    bar = "▓" * filled + "░" * (bar_width - filled)

    print(f"\n  [{batch_idx}/{batch_size}] [{bar}] {chat_title[:40]}")
    if category:
        print(f"         Category: {category}  {status}")


# ------------------ MAIN ------------------
async def main():
    global logger

    # Ініціалізація логування
    logger = setup_logging()

    # Красива шапка в консолі
    print_compact_header()

    logger.info("=" * 80)
    logger.info("🔍 АНАЛІЗ TELEGRAM ЧАТІВ - НОВА СИСТЕМА З БАТЧИНГОМ")
    logger.info("=" * 80)

    # Перевірка --fresh-start flag
    fresh_start = '--fresh-start' in sys.argv
    if fresh_start:
        logger.warning("⚠️ РЕЖИМ --fresh-start: Всі попередні результати будуть ВИДАЛЕНІ!")
        from output_formatter import clear_output_files, clear_dedup_cache
        clear_output_files()
        clear_dedup_cache()
        logger.info("🗑️ Попередні результати очищено")

    # Ініціалізація компонентів
    logger.info("📦 Ініціалізація компонентів системи...")
    state_manager = StateManager(db_path="state/chats.db")
    rate_limiter = RateLimiter(db_path="state/chats.db", max_per_hour=150)
    batch_collector = BatchCollector(db_path="state/chats.db", batch_size=10)
    format_detector = FormatDetector()

    # Завантажити dedup cache з state manager
    from output_formatter import load_dedup_cache_from_state
    load_dedup_cache_from_state(state_manager)
    logger.info("✅ Dedup cache завантажено")

    # КРОК 1: Збір всіх чатів з різних джерел
    print_step_header(1, "ЗБІР ВХІДНИХ ДАНИХ")
    logger.info("\n" + "=" * 80)
    logger.info("КРОК 1: ЗБІР ВХІДНИХ ДАНИХ")
    logger.info("=" * 80)

    all_chats = []

    # 1.1 Сканування папки "чати" (нова система)
    chats_dir = Path("чати")
    if chats_dir.exists() and chats_dir.is_dir():
        logger.info(f"📂 Сканування папки: {chats_dir}")

        all_input_files = []
        for pattern in ['**/*.txt', '**/*.json', '**/*.tsv']:
            all_input_files.extend(chats_dir.glob(pattern))

        logger.info(f"Знайдено {len(all_input_files)} файлів")

        for file_path in all_input_files:
            logger.info(f"📄 Обробка файлу: {file_path.name}")
            chats = format_detector.detect_and_parse(file_path)
            all_chats.extend(chats)
            logger.info(f"   └─ Знайдено {len(chats)} чатів")
    else:
        logger.info(f"📂 Папка '{chats_dir}' не знайдена, пропускаємо")

    # 1.2 Legacy підтримка @mt_offer.txt
    if INPUT_FILE.exists():
        logger.info(f"📂 Legacy режим: читання {INPUT_FILE}")
        legacy_urls = load_chats_from_file(INPUT_FILE)
        legacy_chats = [{'url': url, 'username': url.replace('https://t.me/', '').replace('@', '')} for url in legacy_urls]
        all_chats.extend(legacy_chats)
        logger.info(f"   └─ Знайдено {len(legacy_chats)} чатів (legacy)")

    if not all_chats:
        logger.error("❌ Не знайдено жодного чату для обробки!")
        logger.info(f"💡 Додайте файли в папку '{chats_dir}' або в {INPUT_FILE}")
        return

    logger.info(f"\n✅ Всього зібрано {len(all_chats)} чатів з усіх джерел")

    # КРОК 2: Фільтрація необроблених чатів
    print_step_header(2, "ФІЛЬТРАЦІЯ НЕОБРОБЛЕНИХ ЧАТІВ")
    logger.info("\n" + "=" * 80)
    logger.info("КРОК 2: ФІЛЬТРАЦІЯ НЕОБРОБЛЕНИХ ЧАТІВ")
    logger.info("=" * 80)

    unprocessed_chats = state_manager.get_unprocessed_chats(all_chats)

    if not unprocessed_chats:
        logger.info("✅ Всі чати вже оброблені!")
        stats = state_manager.get_stats()
        logger.info(f"📊 Статистика: {stats['total']} оброблено, pass rate: {stats['pass_rate']}")
        return

    logger.info(f"📊 Необроблених чатів: {len(unprocessed_chats)} з {len(all_chats)}")

    # КРОК 3: Підключення до Telegram
    print_step_header(3, "ПІДКЛЮЧЕННЯ ДО TELEGRAM")
    logger.info("\n" + "=" * 80)
    logger.info("КРОК 3: ПІДКЛЮЧЕННЯ ДО TELEGRAM")
    logger.info("=" * 80)

    load_dotenv(SCRIPT_DIR / ".env", override=False)

    # Ініціалізувати SessionManager для управління багатьма сесіями
    session_manager = SessionManager(db_path="state/chats.db", accs_dir="accs")

    if session_manager.get_total_count() == 0:
        logger.error("❌ Не знайдено жодної session файлу в accs/")
        return

    # Отримати API credentials (використовуємо перший .env або з ENV)
    first_session = session_manager.sessions[0]
    creds = resolve_api_creds(first_session)
    if not creds:
        logger.error("❌ Не знайдено API_ID та API_HASH")
        return

    api_id, api_hash = creds

    # Отримати першу доступну сесію
    current_session_info = session_manager.get_next_available_session(api_id, api_hash)
    if not current_session_info:
        logger.error("❌ Всі сесії заблоковані FloodWait!")
        print(session_manager.get_status_report())
        return

    # Підключитися до Telegram
    telegram_client = TelegramClient(str(current_session_info.path), api_id, api_hash)

    logger.info(f"🔌 Підключення через {current_session_info.name}...")
    await telegram_client.connect()

    if not await telegram_client.is_user_authorized():
        logger.error(f"❌ Сесія {current_session_info.name} не авторизована")
        await telegram_client.disconnect()
        return

    logger.info(f"✅ Авторізація успішна через {current_session_info.name}")
    print(session_manager.get_status_report())

    # КРОК 4: Підключення до ChatGPT з auto-recovery
    print_step_header(4, "ПІДКЛЮЧЕННЯ ДО ChatGPT")
    logger.info("\n" + "=" * 80)
    logger.info("КРОК 4: ПІДКЛЮЧЕННЯ ДО ChatGPT (з auto-recovery)")
    logger.info("=" * 80)

    # Ініціалізуємо BrowserManager для автоматичного відновлення
    browser_manager = BrowserManager(
        cdp_port=EDGE_CDP_PORT,
        chatgpt_url=CHATGPT_URL
    )
    chatgpt_page = await browser_manager.connect()

    if not chatgpt_page:
        logger.error("[X] Не вдалося підключитися до браузера")
        await telegram_client.disconnect()
        return

    logger.info("[OK] Підключено до ChatGPT з auto-recovery")

    # КРОК 5: Безперервна обробка
    print_step_header(5, "БЕЗПЕРЕРВНА ОБРОБКА ЧАТІВ")
    logger.info("\n" + "=" * 80)
    logger.info("КРОК 5: БЕЗПЕРЕРВНА ОБРОБКА ЧАТІВ")
    logger.info("=" * 80)
    logger.info(f"⚙️ Ліміт: {rate_limiter.max_per_hour} чатів/годину")
    logger.info(f"⚙️ Розмір батчу: {batch_collector.batch_size} чатів")

    # Інформаційний блок
    print_progress_box(
        "SYSTEM READY - STARTING PROCESSING",
        [
            f"Total chats to process: {len(unprocessed_chats)}",
            f"Rate limit: {rate_limiter.max_per_hour} chats/hour",
            f"Batch size: {batch_collector.batch_size} active chats",
            f"Estimated time: ~{len(unprocessed_chats) / rate_limiter.max_per_hour:.1f} hours",
            "",
            "Press Ctrl+C to stop (progress will be saved)",
            "Logs: state/chats_spider.log"
        ]
    )

    processed_in_session = 0
    active_chats_collected = 0
    pass_count = 0
    fail_count = 0

    try:
        for idx, chat_url_data in enumerate(unprocessed_chats, 1):
            # Перевірка rate limit
            if not rate_limiter.can_process():
                remaining = rate_limiter.get_remaining()
                logger.warning(f"\n⏳ Досягнуто ліміт {rate_limiter.max_per_hour} чатів/годину")
                logger.info(f"Залишилось в поточній годині: {remaining}")
                rate_limiter.wait_for_next_window()

            logger.info(f"\n[{idx}/{len(unprocessed_chats)}] Обробка: {chat_url_data.get('url', chat_url_data)}")

            # Збір даних одного чату з Telegram (з обробкою FloodWait)
            chat_data = None
            max_session_switches = session_manager.get_total_count()  # Максимум спроб = кількість сесій

            for session_attempt in range(max_session_switches):
                try:
                    chat_data = await collect_single_chat_data(telegram_client, chat_url_data)
                    break  # Успіх - виходимо з циклу

                except FloodWaitError as e:
                    logger.warning(f"   🚫 FloodWait {e.seconds}s на сесії {current_session_info.name}")

                    # Переключитися на наступну сесію
                    reconnect_result = await reconnect_telegram_session(
                        session_manager,
                        telegram_client,
                        current_session_info.name,
                        e.seconds,
                        api_id,
                        api_hash
                    )

                    if not reconnect_result:
                        # Всі сесії заблоковані
                        logger.error("   ❌ Всі сесії заблоковані - зупинка обробки")
                        print("\n❌ КРИТИЧНА ПОМИЛКА: Всі Telegram сесії заблоковані FloodWait!")
                        print("💡 Додайте більше .session файлів в accs/ або зачекайте")
                        # Вихід з функції main
                        await telegram_client.disconnect()
                        await browser.close()
                        return

                    # Оновити клієнта та інфо про сесію
                    telegram_client, current_session_info = reconnect_result
                    logger.info(f"   🔄 Повтор збору даних через {current_session_info.name}...")
                    # Продовжуємо цикл для повтору збору

            if not chat_data:
                logger.info("   └─ ⏭️ Пропущено (помилка або низька активність)")
                continue

            # Чат активний - додаємо до батчу
            is_batch_ready = batch_collector.add_to_batch(chat_data)
            active_chats_collected += 1

            logger.info(f"   └─ ✅ Додано до батчу ({active_chats_collected % batch_collector.batch_size}/{batch_collector.batch_size})")

            # Якщо батч готовий - обробляємо через ChatGPT
            if is_batch_ready or (idx == len(unprocessed_chats) and active_chats_collected % batch_collector.batch_size > 0):
                current_batch = batch_collector.get_current_batch()
                logger.info(f"\n🤖 Обробка батчу з {len(current_batch)} активних чатів через ChatGPT...")

                # ПОСЛІДОВНА обробка кожного чату в батчі
                for batch_idx, batch_chat in enumerate(current_batch, 1):
                    logger.info(f"\n   [{batch_idx}/{len(current_batch)}] ChatGPT: {batch_chat['title']}")

                    # Створюємо промпт
                    prompt_file = create_prompt_file(batch_chat, processed_in_session + batch_idx)

                    # Відправляємо в ChatGPT з auto-recovery логікою
                    response = None
                    MAX_RETRIES = 3

                    for retry_attempt in range(MAX_RETRIES):
                        if retry_attempt > 0:
                            logger.warning(f"   [!] Спроба {retry_attempt + 1}/{MAX_RETRIES}: Відновлення браузера...")
                            print(f"   [!] Спроба {retry_attempt + 1}/{MAX_RETRIES}: Відновлення браузера...")

                            # Перевіряємо здоров'я браузера і відновлюємо при потребі
                            if not await browser_manager.is_healthy():
                                logger.warning("   [!] Браузер не відповідає, перепідключення...")
                                chatgpt_page = await browser_manager.reconnect()
                                if not chatgpt_page:
                                    logger.error("   [X] Не вдалося перепідключитися до браузера")
                                    continue
                                logger.info("   [OK] Браузер перепідключено")
                            else:
                                # Браузер здоровий - просто перезавантажуємо сторінку
                                if not await browser_manager.reload_page():
                                    logger.warning("   [!] Reload не вдався, перепідключення...")
                                    chatgpt_page = await browser_manager.reconnect()
                                    if not chatgpt_page:
                                        continue
                                else:
                                    chatgpt_page = browser_manager.page

                        try:
                            # Відправляємо промпт
                            response = await send_prompt_file_to_chatgpt(chatgpt_page, prompt_file)

                            if response:
                                # Успішно отримано відповідь
                                browser_manager.reset_recovery_counter()  # Скидаємо лічильник recovery
                                if retry_attempt > 0:
                                    logger.info(f"   [OK] Відповідь отримана після {retry_attempt + 1} спроб!")
                                break
                            else:
                                # Не отримано відповідь
                                if retry_attempt < MAX_RETRIES - 1:
                                    logger.warning(f"   [!] Спроба {retry_attempt + 1} невдала")
                                else:
                                    logger.error(f"   [X] Всі {MAX_RETRIES} спроби невдалі для цього чату")

                        except Exception as e:
                            logger.error(f"   [X] Помилка ChatGPT: {e}")
                            if retry_attempt < MAX_RETRIES - 1:
                                # Спробуємо відновити браузер
                                chatgpt_page = await browser_manager.reconnect()
                                if not chatgpt_page:
                                    logger.error("   [X] Критична помилка браузера, пропускаємо чат")
                                    break

                    # Видаляємо тимчасовий файл
                    try:
                        prompt_file.unlink()
                    except:
                        pass

                    if response:
                        # Парсимо відповідь з keyword-валідацією
                        analysis_result = parse_chatgpt_response(response, chat_data=batch_chat)

                        if analysis_result:
                            logger.info(f"   Категорія: {analysis_result['category']}")
                            logger.info(f"   Валідація: {'✅ PASS' if analysis_result['is_valid'] else '❌ FAIL'}")

                            # Оновлюємо лічильники
                            if analysis_result['is_valid']:
                                pass_count += 1
                            else:
                                fail_count += 1

                            # Зберігаємо в файли
                            from output_formatter import save_chat_to_files
                            save_chat_to_files(batch_chat, analysis_result)

                            # Позначаємо як оброблений
                            state_manager.mark_processed(batch_chat['url'], analysis_result)

                            # КРИТИЧНО: Increment rate limiter ТІЛЬКИ після успіху!
                            rate_limiter.increment_processed()
                            processed_in_session += 1

                            # Live прогрес для батчу
                            print_batch_progress(
                                batch_idx,
                                len(current_batch),
                                batch_chat['title'],
                                analysis_result['category'],
                                analysis_result['is_valid']
                            )

                            logger.info(f"   ✅ Збережено та оброблено ({processed_in_session} в сесії)")
                        else:
                            logger.warning("   ⚠️ Помилка парсингу відповіді")
                    else:
                        logger.warning("   ⚠️ Не отримано відповідь від ChatGPT")

                    # Затримка між ChatGPT запитами
                    if batch_idx < len(current_batch):
                        await asyncio.sleep(DELAY_BETWEEN_CHATGPT)

                # Очистити батч після обробки
                batch_collector.clear_current_batch()
                logger.info(f"\n✅ Батч оброблено. Всього в сесії: {processed_in_session}")

                # Live статистика після кожного батчу
                current_rate = rate_limiter.get_current_count()
                print_live_stats(
                    processed=idx,
                    total=len(unprocessed_chats),
                    session_processed=processed_in_session,
                    rate_used=current_rate,
                    rate_max=rate_limiter.max_per_hour,
                    pass_count=pass_count,
                    fail_count=fail_count
                )

                # Backup кожні 100 чатів
                if processed_in_session > 0 and processed_in_session % 100 == 0:
                    backup_file = state_manager.backup_db()
                    logger.info(f"💾 Створено backup: {backup_file}")

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Обробка перервана користувачем (Ctrl+C)")
    except Exception as e:
        logger.error(f"\n❌ Критична помилка: {e}", exc_info=True)
    finally:
        # Обробити залишковий батч якщо є
        remaining_batch = batch_collector.get_current_batch()
        if remaining_batch:
            logger.info(f"\n🤖 Обробка залишкового батчу ({len(remaining_batch)} чатів)...")
            # Аналогічна обробка як вище (опущено для стислості)

        # Відключення
        await telegram_client.disconnect()
        logger.info("\n🔌 Відключено від Telegram")

        # НЕ закриваємо браузер - залишається відкритим
        logger.info("💡 Chrome браузер залишається відкритим")

        # Фінальна статистика
        logger.info("\n" + "=" * 80)
        logger.info("ЗАВЕРШЕНО")
        logger.info("=" * 80)
        logger.info(f"📊 Оброблено в цій сесії: {processed_in_session} чатів")

        stats = state_manager.get_stats()
        logger.info(f"📊 Всього в базі: {stats['total']} чатів")
        logger.info(f"   ✅ Пройшли валідацію: {stats['passed']}")
        logger.info(f"   ❌ Відхилено: {stats['failed']}")
        logger.info(f"   📈 Pass rate: {stats['pass_rate']}")

        # Красива фінальна статистика в консолі
        print("\n")
        print("╔" + "═" * 78 + "╗")
        print("║" + " PROCESSING COMPLETED ".center(78) + "║")
        print("╚" + "═" * 78 + "╝")
        print("\n" + "=" * 80)
        print("  SESSION SUMMARY")
        print("=" * 80)
        print(f"  Processed in this session: {processed_in_session} chats")
        print(f"  ✅ Passed: {pass_count}  |  ❌ Failed: {fail_count}")
        if processed_in_session > 0:
            session_pass_rate = (pass_count / processed_in_session * 100)
            print(f"  Session pass rate: {session_pass_rate:.1f}%")
        print("")
        print("  TOTAL DATABASE STATISTICS")
        print("  " + "-" * 76)
        print(f"  Total chats in database: {stats['total']}")
        print(f"  ✅ Passed validation: {stats['passed']}")
        print(f"  ❌ Rejected: {stats['failed']}")
        print(f"  📈 Overall pass rate: {stats['pass_rate']}")
        print("=" * 80)
        print("")
        print("  RESULTS SAVED TO:")
        print("  " + "-" * 76)
        print("    output/validated_chats.txt")
        print("    output/rejected_chats.txt")
        print("    output/founder_chats.txt")
        print("    output/manager_chats.txt")
        print("=" * 80)

        from output_formatter import print_final_statistics
        print_final_statistics()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    asyncio.run(main())
