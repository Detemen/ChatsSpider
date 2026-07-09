# filter_active_chats.py
# -*- coding: utf-8 -*-
# [UKRAINIAN] Всі повідомлення українською мовою
"""
Фільтрація активних Telegram чатів з генерацією описів

Процес:
1. Читає файл @mt_offer.txt (ID, назва, @username)
2. Перевіряє активність (>15 повідомлень/тиждень) через Telethon
3. Збирає дані про активні чати (title, about, admins, pinned message)
4. Генерує теги/опис через ChatGPT
5. Форматує результат:
   Теги через кому
   https://t.me/username
   @admin
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import Channel, InputChannel
from telethon.errors import FloodWaitError, ChatAdminRequiredError

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


# ------------------ КОНФІГУРАЦІЯ ------------------
ACCS_DIR = Path("accs")
CONFIG_ACCOUNTS = Path("config_accounts.json")
INPUT_FILE = Path("@mt_offer.txt")
OUTPUT_DIR = Path("output")
RESULT_FILE = OUTPUT_DIR / "active_chats_formatted.txt"
DATA_FILE = OUTPUT_DIR / "active_chats_data.txt"
PROGRESS_FILE = OUTPUT_DIR / "progress.json"  # Файл прогресу

MIN_MESSAGES_PER_DAY = 15  # Мінімум повідомлень за день (в середньому за тиждень)
CHATGPT_URL = "https://chat.openai.com/"

# Затримки для уникнення банів
DELAY_BETWEEN_CHATS = 3  # секунд між обробкою чатів
DELAY_AFTER_HISTORY = 2  # секунд після отримання історії


# ------------------ ПРОГРЕС ------------------
def load_progress() -> Dict:
    """Завантажує збережений прогрес"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'processed_usernames': [],  # Оброблені username
        'active_chats': [],  # Знайдені активні чати
        'stage': 'collection'  # collection або chatgpt
    }


def save_progress(progress: Dict):
    """Зберігає прогрес"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# ------------------ УТИЛІТИ ------------------
def load_api_from_config(session_name: str) -> Optional[tuple]:
    if CONFIG_ACCOUNTS.exists():
        try:
            cfg = json.loads(CONFIG_ACCOUNTS.read_text(encoding="utf-8"))
            e = cfg.get(session_name) or cfg.get("default")
            if e and "api_id" in e and "api_hash" in e:
                return int(e["api_id"]), str(e["api_hash"])
        except Exception:
            pass
    return None


def load_api_from_env() -> Optional[tuple]:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    if api_id and api_hash:
        try:
            return int(api_id), str(api_hash)
        except Exception:
            pass
    return None


def resolve_api_creds(session_file: Path) -> Optional[tuple]:
    c = load_api_from_config(session_file.name)
    if c:
        return c
    e = load_api_from_env()
    if e:
        return e
    return None


def get_first_session() -> Optional[Path]:
    if not ACCS_DIR.exists():
        return None
    sessions = [p for p in ACCS_DIR.iterdir() if p.is_file() and p.suffix == ".session"]
    if not sessions:
        return None
    return sessions[0]


def parse_input_file(file_path: Path) -> List[Dict]:
    """
    Парсить файл формату:
    ID   Назва   @username

    Повертає список словників з полями: id, title, username
    """
    if not file_path.exists():
        print(f"❌ Файл не знайдено: {file_path}")
        return []

    chats = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Парсимо формат: ID\tНазва\t@username
            parts = line.split('\t')
            if len(parts) < 3:
                continue

            chat_id = parts[0].strip()
            title = parts[1].strip()
            username = parts[2].strip()

            # Пропускаємо чати без username
            if username == '—' or not username.startswith('@'):
                continue

            chats.append({
                'id': chat_id,
                'title': title,
                'username': username.lstrip('@')
            })

    return chats


# ------------------ TELETHON: ПЕРЕВІРКА АКТИВНОСТІ ------------------
async def check_activity_and_collect_data(chats: List[Dict], progress: Dict) -> List[Dict]:
    """
    Перевіряє активність чатів та збирає дані про активні
    """
    load_dotenv(override=False)
    OUTPUT_DIR.mkdir(exist_ok=True)

    session_path = get_first_session()
    if not session_path:
        print("❌ Не знайдено session файлів")
        return []

    creds = resolve_api_creds(session_path)
    if not creds:
        print("❌ Не знайдено API_ID та API_HASH")
        return []

    api_id, api_hash = creds
    client = TelegramClient(str(session_path), api_id, api_hash)

    print(f"🔌 Підключення через {session_path.name}...")

    active_chats = progress.get('active_chats', [])
    processed = set(progress.get('processed_usernames', []))
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Сесія не авторизована")
            await client.disconnect()
            return active_chats

        print("✅ Авторизація успішна\n")

        # Фільтруємо тільки необроблені чати
        remaining_chats = [c for c in chats if c['username'] not in processed]

        print(f"📊 Всього чатів: {len(chats)}")
        print(f"✅ Вже оброблено: {len(processed)}")
        print(f"⏳ Залишилось: {len(remaining_chats)}")
        print(f"💚 Знайдено активних: {len(active_chats)}\n")
        print("="*80)

        for idx, chat_info in enumerate(remaining_chats, 1):
            username = chat_info['username']
            title = chat_info['title']

            print(f"[{idx}/{len(remaining_chats)}] Перевірка: {title} (@{username})")

            try:
                # Отримуємо entity
                entity = await client.get_entity(username)

                if not isinstance(entity, Channel):
                    print(f"  ⚠️  Не канал/чат, пропускаємо\n")
                    processed.add(username)
                    progress['processed_usernames'] = list(processed)
                    save_progress(progress)
                    await asyncio.sleep(DELAY_BETWEEN_CHATS)
                    continue

                # Отримуємо історію повідомлень за тиждень
                try:
                    # ВАЖЛИВО: Беремо достатньо повідомлень для підрахунку
                    # Якщо чат дуже активний (100+ повідомлень/день), може не вистачити
                    # Але 500 - розумний ліміт щоб не перевантажувати API
                    messages = await client(GetHistoryRequest(
                        peer=entity,
                        limit=500,  # Достатньо для дуже активних чатів
                        offset_date=None,
                        offset_id=0,
                        max_id=0,
                        min_id=0,
                        add_offset=0,
                        hash=0
                    ))

                    # Рахуємо повідомлення за останній тиждень
                    messages_this_week = 0
                    oldest_msg_date = None

                    for msg in messages.messages:
                        if msg.date:
                            if msg.date >= week_ago:
                                messages_this_week += 1
                            # Запам'ятовуємо найстаріше повідомлення
                            if oldest_msg_date is None or msg.date < oldest_msg_date:
                                oldest_msg_date = msg.date

                    # Рахуємо скільки днів реально охопили
                    if oldest_msg_date and oldest_msg_date < week_ago:
                        # Маємо повний тиждень даних
                        days_covered = 7.0
                    elif oldest_msg_date:
                        # Маємо неповний тиждень (новий чат або мало повідомлень)
                        days_covered = max(1, (datetime.now(timezone.utc) - oldest_msg_date).days)
                    else:
                        days_covered = 7.0

                    # Рахуємо середнє на день
                    avg_per_day = messages_this_week / days_covered if days_covered > 0 else 0

                    print(f"  📨 Повідомлень за останні {int(days_covered)} днів: {messages_this_week}")
                    print(f"  📊 В середньому на день: {avg_per_day:.1f}")

                    # Якщо менше ніж мінімум - пропускаємо
                    if avg_per_day < MIN_MESSAGES_PER_DAY:
                        print(f"  ⚠️  Недостатньо активний (< {MIN_MESSAGES_PER_DAY} повідомлень/день), пропускаємо\n")
                        processed.add(username)
                        progress['processed_usernames'] = list(processed)
                        save_progress(progress)
                        await asyncio.sleep(DELAY_AFTER_HISTORY)
                        continue

                    print(f"  ✅ АКТИВНИЙ! Збираю дані...")

                except ChatAdminRequiredError:
                    print(f"  ⚠️  Немає доступу до історії, пропускаємо\n")
                    processed.add(username)
                    progress['processed_usernames'] = list(processed)
                    save_progress(progress)
                    await asyncio.sleep(DELAY_BETWEEN_CHATS)
                    continue

                # Збираємо детальні дані
                chat_data = {
                    'username': username,
                    'title': title,
                    'about': '',
                    'members_count': 0,
                    'messages_per_week': messages_this_week,
                    'admins': [],
                    'pinned_message': '',
                    'linked_channel': None
                }

                # Детальна інформація
                try:
                    full = await client(GetFullChannelRequest(
                        channel=InputChannel(entity.id, entity.access_hash)
                    ))

                    if hasattr(full.full_chat, 'about'):
                        chat_data['about'] = full.full_chat.about or ''

                    if hasattr(full.full_chat, 'participants_count'):
                        chat_data['members_count'] = full.full_chat.participants_count

                    # Pinned message
                    try:
                        pinned = full.full_chat.pinned_msg_id
                        if pinned:
                            msg = await client.get_messages(entity, ids=pinned)
                            if msg and msg.text:
                                chat_data['pinned_message'] = msg.text[:300]
                    except Exception:
                        pass

                    # Linked channel
                    if hasattr(full.full_chat, 'linked_chat_id') and full.full_chat.linked_chat_id:
                        try:
                            from telethon.tl.types import PeerChannel
                            linked = await client.get_entity(PeerChannel(full.full_chat.linked_chat_id))
                            if hasattr(linked, 'username') and linked.username:
                                chat_data['linked_channel'] = {
                                    'username': linked.username,
                                    'title': getattr(linked, 'title', '')
                                }
                        except Exception:
                            pass

                    # Адміни
                    try:
                        from telethon.tl.functions.channels import GetParticipantsRequest
                        from telethon.tl.types import ChannelParticipantsAdmins

                        admins = await client(GetParticipantsRequest(
                            channel=InputChannel(entity.id, entity.access_hash),
                            filter=ChannelParticipantsAdmins(),
                            offset=0,
                            limit=10,
                            hash=0
                        ))

                        for user in admins.users:
                            if hasattr(user, 'username') and user.username:
                                admin_info = {
                                    'username': user.username,
                                    'first_name': getattr(user, 'first_name', ''),
                                    'is_bot': getattr(user, 'bot', False)
                                }
                                chat_data['admins'].append(admin_info)

                    except Exception as e:
                        print(f"  ⚠️  Не вдалось отримати адмінів: {e}")

                except FloodWaitError as e:
                    print(f"  ⏳ FloodWait {e.seconds}s, зберігаю прогрес і чекаю...")
                    # Зберігаємо прогрес перед очікуванням
                    progress['processed_usernames'] = list(processed)
                    progress['active_chats'] = active_chats
                    save_progress(progress)

                    print(f"\n⚠️⚠️⚠️ БАН НА {e.seconds} СЕКУНД ⚠️⚠️⚠️")
                    print(f"Прогрес збережено в: {PROGRESS_FILE}")
                    print(f"Ви можете безпечно зупинити скрипт (Ctrl+C)")
                    print(f"При наступному запуску продовжимо з цього місця\n")

                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    print(f"  ⚠️  Помилка: {e}")

                active_chats.append(chat_data)
                processed.add(username)

                # Зберігаємо прогрес після кожного активного чату
                progress['active_chats'] = active_chats
                progress['processed_usernames'] = list(processed)
                save_progress(progress)

                print(f"  👥 Учасників: {chat_data['members_count']}")
                print(f"  👤 Адмінів знайдено: {len(chat_data['admins'])}")
                print(f"  💾 Прогрес збережено\n")

            except FloodWaitError as e:
                print(f"  ⏳ FloodWait {e.seconds}s при get_entity")

                # Зберігаємо прогрес
                progress['processed_usernames'] = list(processed)
                progress['active_chats'] = active_chats
                save_progress(progress)

                print(f"\n⚠️⚠️⚠️ БАН НА {e.seconds} СЕКУНД ⚠️⚠️⚠️")
                print(f"Прогрес збережено в: {PROGRESS_FILE}")
                print(f"Оброблено: {len(processed)}/{len(chats)}")
                print(f"Знайдено активних: {len(active_chats)}\n")

                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                print(f"  ❌ Помилка: {e}\n")
                processed.add(username)
                progress['processed_usernames'] = list(processed)
                save_progress(progress)
                continue

            # Затримка між чатами
            await asyncio.sleep(DELAY_BETWEEN_CHATS)

        print("="*80)
        print(f"\n✅ Знайдено активних чатів: {len(active_chats)}\n")

        # Фінальне збереження
        progress['active_chats'] = active_chats
        progress['processed_usernames'] = list(processed)
        progress['stage'] = 'chatgpt'
        save_progress(progress)

    except KeyboardInterrupt:
        print("\n\n⚠️  Переривання користувачем")
        print(f"💾 Зберігаю прогрес...")
        progress['active_chats'] = active_chats
        progress['processed_usernames'] = list(processed)
        save_progress(progress)
        print(f"✅ Прогрес збережено в: {PROGRESS_FILE}")
        print(f"📊 Оброблено: {len(processed)}/{len(chats)}")
        print(f"💚 Знайдено активних: {len(active_chats)}")
        raise
    except Exception as e:
        print(f"❌ Критична помилка: {e}")
    finally:
        await client.disconnect()

    return active_chats


def save_collected_data(data: List[Dict]):
    """Зберігає зібрані дані у файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("ДАНІ ПРО АКТИВНІ TELEGRAM ЧАТИ\n")
        f.write("="*80 + "\n\n")

        for idx, chat in enumerate(data, 1):
            f.write(f"ЧАТ #{idx}\n")
            f.write("-"*80 + "\n")
            f.write(f"Username: @{chat['username']}\n")
            f.write(f"Назва: {chat['title']}\n")
            f.write(f"Кількість учасників: {chat['members_count']}\n")
            f.write(f"Повідомлень за тиждень: {chat['messages_per_week']}\n\n")

            f.write(f"Опис чату:\n{chat['about']}\n\n")

            if chat['pinned_message']:
                f.write(f"Закріплене повідомлення:\n{chat['pinned_message']}\n\n")

            if chat['linked_channel']:
                f.write(f"Пов'язаний канал: @{chat['linked_channel']['username']}\n\n")

            if chat['admins']:
                f.write(f"Адміністратори:\n")
                for admin in chat['admins']:
                    f.write(f"  @{admin['username']}")
                    if admin['is_bot']:
                        f.write(" [BOT]")
                    f.write("\n")
                f.write("\n")

            f.write("="*80 + "\n\n")

    print(f"💾 Дані збережено в: {DATA_FILE}\n")


# ------------------ SELENIUM: ChatGPT ------------------
def generate_tags_with_chatgpt(data: List[Dict]) -> List[Dict]:
    """
    Генерує теги/опис через ChatGPT для кожного чату
    """
    print("🤖 Запуск Selenium для ChatGPT...\n")

    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(CHATGPT_URL)
        print("🌐 Відкрито ChatGPT Web")
        print("⏳ Зачекайте 10 секунд...\n")
        time.sleep(10)

        # Оптимізований промпт для генерації тегів
        base_prompt = """Проаналізуй Telegram чат і створи КОРОТКИЙ опис у вигляді тегів через кому (3-6 тегів).

ДУЖЕ ВАЖЛИВО:
- Відповідь має містити ЛИШЕ теги через кому, БЕЗ НУМЕРАЦІЇ, БЕЗ ЗАЙВОГО ТЕКСТУ
- Теги мають бути короткі та конкретні (1-3 слова)
- Вкажи тематику, цільову аудиторію, регіон (якщо є)
- НЕ використовуй загальні слова типу "чат", "спільнота", "група"

ПРИКЛАДИ ПРАВИЛЬНИХ ВІДПОВІДЕЙ (копіюй цей стиль):
"DIY, електроніка, 3D-друк, IT, інструменти"
"Їжа, ресторани, гастрономія, Нові-Сад"
"Atlassian, мітапи, розробка, Москва"
"Python, веб-розробка, Django, Flask"
"Крипто, арбітраж трафіку, кейси, офери"

НЕПРАВИЛЬНІ ПРИКЛАДИ (НЕ роби так):
"1. Чат про DIY та електроніку" ❌
"Спільнота любителів їжі в Нові-Сад" ❌
"Група для розробників Python" ❌

Дані чату:
"""

        for idx, chat in enumerate(data, 1):
            print(f"[{idx}/{len(data)}] Генерація тегів: {chat['title']}")

            # Формуємо промпт
            prompt = base_prompt + f"""
Назва: {chat['title']}
Опис: {chat['about']}
Учасників: {chat['members_count']}
"""
            if chat['pinned_message']:
                prompt += f"Закріплене: {chat['pinned_message'][:200]}\n"

            if chat['linked_channel']:
                prompt += f"Канал: {chat['linked_channel']['title']}\n"

            try:
                # Поле вводу - пробуємо різні селектори
                textarea = None
                selectors = [
                    (By.TAG_NAME, "textarea"),
                    (By.ID, "prompt-textarea"),
                    (By.CSS_SELECTOR, "textarea[placeholder*='Message']"),
                    (By.CSS_SELECTOR, "textarea[data-id='root']"),
                    (By.XPATH, "//textarea")
                ]

                for selector_type, selector_value in selectors:
                    try:
                        textarea = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        print(f"  ✅ Знайдено поле вводу: {selector_value}")
                        break
                    except:
                        continue

                if not textarea:
                    print(f"  ❌ Не знайдено поле вводу!")
                    print(f"  💡 Перевірте що ви авторизовані в ChatGPT")
                    chat['tags'] = chat['title']
                    continue

                # Очищаємо і вводимо текст
                textarea.click()
                time.sleep(0.5)
                textarea.clear()
                textarea.send_keys(prompt)
                time.sleep(1)
                textarea.send_keys(Keys.RETURN)

                print(f"  ⏳ Чекаємо відповідь...")
                time.sleep(15)

                # Отримуємо відповідь
                response_elements = driver.find_elements(By.CSS_SELECTOR, "[data-message-author-role='assistant']")

                if response_elements:
                    tags = response_elements[-1].text.strip()

                    # Очищаємо від зайвого тексту
                    tags = tags.replace('"', '').replace("'", "")
                    # Якщо є нумерація - беремо тільки після неї
                    if '\n' in tags:
                        tags = tags.split('\n')[0]

                    print(f"  ✅ Теги: {tags}\n")
                    chat['tags'] = tags
                else:
                    print(f"  ⚠️  Помилка: не отримано відповідь\n")
                    chat['tags'] = chat['title']  # Fallback

            except Exception as e:
                print(f"  ❌ Помилка: {e}\n")
                chat['tags'] = chat['title']

            time.sleep(3)

        print("✅ Всі теги згенеровано!\n")

    except Exception as e:
        print(f"❌ Критична помилка Selenium: {e}")
    finally:
        print("⏳ Закриття браузера...\n")
        time.sleep(3)
        driver.quit()

    return data


def format_and_save_results(data: List[Dict]):
    """
    Форматує та зберігає результати у потрібному форматі:
    Теги
    URL
    @admin
    """
    results = []

    for chat in data:
        # Теги
        tags = chat.get('tags', chat['title'])

        # URL
        url = f"https://t.me/{chat['username']}"

        # Адмін (перший не-бот)
        admin = ""
        if chat['admins']:
            for a in chat['admins']:
                if not a['is_bot']:
                    admin = f"@{a['username']}"
                    break
            # Якщо всі боти - беремо першого
            if not admin and chat['admins']:
                admin = f"@{chat['admins'][0]['username']}"

        # Якщо немає адміна - шукаємо з linked channel
        if not admin and chat.get('linked_channel'):
            admin = f"@{chat['linked_channel']['username']}"

        # Формуємо блок
        block = f"{tags}\n{url}\n{admin}\n"
        results.append(block)

    # Зберігаємо
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))

    print(f"💾 Результати збережено в: {RESULT_FILE}\n")

    # Виводимо результати
    print("="*80)
    print("📊 РЕЗУЛЬТАТИ:")
    print("="*80 + "\n")
    for result in results:
        print(result)


# ------------------ MAIN ------------------
async def main():
    print("="*80)
    print("🔍 ФІЛЬТРАЦІЯ АКТИВНИХ TELEGRAM ЧАТІВ")
    print("="*80 + "\n")

    # Завантажуємо прогрес
    progress = load_progress()

    print("📋 Статус прогресу:")
    print(f"   Оброблено чатів: {len(progress.get('processed_usernames', []))}")
    print(f"   Знайдено активних: {len(progress.get('active_chats', []))}")
    print(f"   Етап: {progress.get('stage', 'collection')}\n")

    # Якщо є будь-який прогрес - даємо можливість очистити
    if progress.get('processed_usernames') or progress.get('active_chats'):
        print("⚠️  Знайдено попередній прогрес!")
        print("\nОберіть дію:")
        print("1 - Продовжити збір чатів (якщо немає бану)")
        print("2 - Перейти до генерації тегів ChatGPT (з поточними результатами)")
        print("3 - Почати ЗАНОВО (видалити прогрес)")
        choice = input("\nВаш вибір (1/2/3): ").strip()

        if choice == '2':
            # Перехід до ChatGPT з поточними активними чатами
            if progress.get('active_chats'):
                active_chats = progress['active_chats']
                save_collected_data(active_chats)
                print(f"\n✅ Знайдено {len(active_chats)} активних чатів")
                print("Переходимо до генерації тегів...\n")

                print("="*80)
                print("КРОК 2: ГЕНЕРАЦІЯ ТЕГІВ ЧЕРЕЗ ChatGPT")
                print("="*80 + "\n")
                print("⚠️  Зараз відкриється браузер Chrome з ChatGPT")
                print("⚠️  Переконайтеся, що ви авторизовані в ChatGPT\n")
                print("Продовжити? (y/n): ", end="")

                if input().strip().lower() == 'y':
                    active_chats = generate_tags_with_chatgpt(active_chats)
                    format_and_save_results(active_chats)
                    # Очищаємо прогрес після успішного завершення
                    PROGRESS_FILE.unlink(missing_ok=True)
                    print("\n✅ ГОТОВО!")
                return
            else:
                print("❌ Немає активних чатів для обробки")
                return
        elif choice == '3':
            PROGRESS_FILE.unlink(missing_ok=True)
            progress = load_progress()
            print("✅ Прогрес очищено, починаємо спочатку\n")

    # Якщо є активні чати і етап - chatgpt
    if progress.get('active_chats') and progress.get('stage') == 'chatgpt':
        print("✅ Знайдено збережені активні чати!")
        print(f"   Кількість: {len(progress['active_chats'])}\n")
        print("Оберіть дію:")
        print("1 - Продовжити збір нових чатів")
        print("2 - Перейти до генерації тегів ChatGPT")
        print("3 - Почати спочатку (очистити прогрес)")
        choice = input("\nВаш вибір (1/2/3): ").strip()

        if choice == '2':
            active_chats = progress['active_chats']
            save_collected_data(active_chats)
            print("\n" + "="*80)
            print("КРОК 2: ГЕНЕРАЦІЯ ТЕГІВ ЧЕРЕЗ ChatGPT")
            print("="*80 + "\n")
            print("⚠️  Зараз відкриється браузер Chrome з ChatGPT")
            print("⚠️  Переконайтеся, що ви авторизовані в ChatGPT\n")
            print("Продовжити? (y/n): ", end="")
            if input().strip().lower() == 'y':
                active_chats = generate_tags_with_chatgpt(active_chats)
                format_and_save_results(active_chats)
                # Очищаємо прогрес після успішного завершення
                PROGRESS_FILE.unlink(missing_ok=True)
                print("\n✅ ГОТОВО!")
            return
        elif choice == '3':
            PROGRESS_FILE.unlink(missing_ok=True)
            progress = load_progress()
            print("✅ Прогрес очищено\n")

    # 1. Парсинг файлу
    print(f"📂 Читання файлу: {INPUT_FILE}")
    chats = parse_input_file(INPUT_FILE)

    if not chats:
        print("❌ Не знайдено чатів для обробки")
        return

    print(f"✅ Знайдено чатів з username: {len(chats)}\n")

    # 2. Перевірка активності
    print("="*80)
    print("КРОК 1: ПЕРЕВІРКА АКТИВНОСТІ ТА ЗБІР ДАНИХ")
    print("="*80 + "\n")
    print("💡 Підказка: Ви можете безпечно зупинити скрипт (Ctrl+C)")
    print("   Прогрес буде збережено і можна продовжити пізніше\n")

    try:
        active_chats = await check_activity_and_collect_data(chats, progress)
    except KeyboardInterrupt:
        print("\n\n⚠️  Роботу зупинено користувачем")
        print(f"💾 Прогрес збережено в: {PROGRESS_FILE}")
        print(f"📊 Оброблено: {len(progress.get('processed_usernames', []))}/{len(chats)}")
        print(f"💚 Знайдено активних чатів: {len(progress.get('active_chats', []))}\n")

        # Якщо є активні чати - пропонуємо перейти до ChatGPT
        if progress.get('active_chats'):
            print("Оберіть дію:")
            print("1 - Вийти (продовжити перевірку пізніше)")
            print("2 - Перейти до генерації тегів ChatGPT з поточними результатами")
            choice = input("\nВаш вибір (1/2): ").strip()

            if choice == '2':
                active_chats = progress['active_chats']
                # Оновлюємо етап
                progress['stage'] = 'chatgpt'
                save_progress(progress)
                print("\n✅ Переходимо до генерації тегів...\n")
            else:
                print("\n💡 Для продовження просто запустіть скрипт знову")
                return
        else:
            print("⚠️  Поки що не знайдено активних чатів")
            print("💡 Для продовження просто запустіть скрипт знову")
            return

    if not active_chats:
        print("❌ Не знайдено активних чатів")
        return

    # 3. Збереження даних
    save_collected_data(active_chats)

    # 4. Генерація тегів
    print("="*80)
    print("КРОК 2: ГЕНЕРАЦІЯ ТЕГІВ ЧЕРЕЗ ChatGPT")
    print("="*80 + "\n")
    print("⚠️  Зараз відкриється браузер Chrome з ChatGPT")
    print("⚠️  Переконайтеся, що ви авторизовані в ChatGPT\n")
    print("Продовжити? (y/n): ", end="")

    choice = input().strip().lower()
    if choice != 'y':
        print("\n⏸️  Зупинено")
        print(f"💾 Дані збережено в: {DATA_FILE}")
        print(f"📊 Активних чатів: {len(active_chats)}")
        print("\n💡 Для генерації тегів запустіть скрипт знову та оберіть опцію 2")
        return

    active_chats = generate_tags_with_chatgpt(active_chats)

    # 5. Форматування та збереження
    format_and_save_results(active_chats)

    # Очищаємо прогрес після успішного завершення
    PROGRESS_FILE.unlink(missing_ok=True)

    print("\n✅ ГОТОВО!")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    asyncio.run(main())
