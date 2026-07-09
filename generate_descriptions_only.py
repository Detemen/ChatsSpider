# generate_descriptions_only.py
# -*- coding: utf-8 -*-
"""
Генерація описів через ChatGPT з вже зібраних даних
Використовує дані з output/chat_analysis_data.txt
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict
import json

# Налаштування кодування для Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from playwright.async_api import async_playwright, Page, Browser


# ------------------ КОНФІГУРАЦІЯ ------------------
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
CHAT_DATA_FILE = OUTPUT_DIR / "chat_analysis_data.txt"
RESULT_FILE = OUTPUT_DIR / "chat_descriptions.txt"

CHATGPT_URL = os.getenv("CHATGPT_CONVERSATION_URL", "https://chatgpt.com/")
EDGE_CDP_PORT = 9222

# Затримки
WAIT_FOR_RESPONSE = 30
DELAY_BETWEEN_CHATS = 5  # Затримка між чатами (секунди)

# Режим роботи
PROCESS_MODE = "one_by_one"  # "one_by_one" = по одному з паузою, "batch" = всі підряд

# Файли для промптів
TEMP_PROMPT_DIR = SCRIPT_DIR / "temp_prompts"  # Папка для тимчасових промптів


# ------------------ ЧИТАННЯ ДАНИХ ------------------
def load_data_from_file() -> List[Dict]:
    """
    Читає дані з output/chat_analysis_data.txt
    """
    if not CHAT_DATA_FILE.exists():
        print(f"❌ Файл не знайдено: {CHAT_DATA_FILE}")
        return []

    data = []
    current_chat = None
    in_messages_section = False
    current_message = None

    with open(CHAT_DATA_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Початок нового чату
            if line_stripped.startswith("ЧАТ #"):
                if current_chat:
                    data.append(current_chat)
                current_chat = {
                    'title': '',
                    'about': '',
                    'username': '',
                    'members_count': 0,
                    'admins': [],
                    'pinned_message': '',
                    'linked_channel': None,
                    'url': '',
                    'recent_messages': []
                }
                in_messages_section = False

            elif current_chat:
                if line_stripped.startswith("URL:"):
                    url = line_stripped.replace("URL:", "").strip()
                    current_chat['url'] = url

                elif line_stripped.startswith("Username:"):
                    username = line_stripped.replace("Username:", "").strip().lstrip('@')
                    current_chat['username'] = username

                elif line_stripped.startswith("Назва:"):
                    current_chat['title'] = line_stripped.replace("Назва:", "").strip()

                elif line_stripped.startswith("Кількість учасників:"):
                    try:
                        count = line_stripped.replace("Кількість учасників:", "").strip()
                        current_chat['members_count'] = int(count)
                    except:
                        pass

                elif line_stripped.startswith("Опис чату:"):
                    # Читаємо багаторядковий опис
                    about_lines = []
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith(("Закріплене", "Пов'язаний", "Адміністратори", "Останні")):
                        if lines[j].strip():
                            about_lines.append(lines[j].strip())
                        j += 1
                    current_chat['about'] = ' '.join(about_lines)

                elif line_stripped.startswith("Закріплене повідомлення:"):
                    pinned_lines = []
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith(("Пов'язаний", "Адміністратори", "Останні")):
                        if lines[j].strip():
                            pinned_lines.append(lines[j].strip())
                        j += 1
                    current_chat['pinned_message'] = ' '.join(pinned_lines)

                elif line_stripped.startswith("Останні повідомлення ("):
                    in_messages_section = True

                elif in_messages_section:
                    # Формат: [2024-12-10 22:43] Sender:
                    if line_stripped.startswith("[") and "]" in line_stripped and ":" in line_stripped:
                        # Це нове повідомлення
                        if current_message:
                            current_chat['recent_messages'].append(current_message)

                        # Парсимо дату та відправника
                        date_end = line_stripped.index("]")
                        date = line_stripped[1:date_end]
                        sender = line_stripped[date_end+1:].strip().rstrip(":")

                        current_message = {
                            "date": date,
                            "sender": sender,
                            "text": ""
                        }
                    elif current_message and line_stripped and not line_stripped.startswith("-" * 40):
                        # Текст повідомлення
                        current_message['text'] += " " + line_stripped if current_message['text'] else line_stripped
                    elif line_stripped.startswith("-" * 40) or line_stripped.startswith("=" * 40):
                        # Кінець секції повідомлень
                        if current_message:
                            current_chat['recent_messages'].append(current_message)
                            current_message = None
                        in_messages_section = False

    # Додаємо останній чат
    if current_chat and current_chat.get('title'):
        data.append(current_chat)

    return data


# ------------------ PLAYWRIGHT: ChatGPT ------------------
async def connect_to_browser() -> tuple:
    """Returns (browser, page, playwright). All three must be cleaned up by the caller."""
    print("🌐 Підключення до браузера...")

    playwright = await async_playwright().start()

    try:
        browser = await playwright.chromium.connect_over_cdp(f"http://localhost:{EDGE_CDP_PORT}")

        contexts = browser.contexts
        if not contexts:
            print("❌ Немає відкритих вкладок в браузері")
            print(f"💡 Відкрийте {CHATGPT_URL} в браузері")
            await playwright.stop()
            return None, None, None

        context = contexts[0]
        pages = context.pages

        # Шукаємо вкладку з ChatGPT
        chatgpt_page = None
        _url = CHATGPT_URL
        target_chat_id = _url.split("/c/")[-1].split("?")[0] if "/c/" in _url else ""

        for page in pages:
            if target_chat_id in page.url or "chatgpt.com" in page.url or "chat.openai.com" in page.url:
                chatgpt_page = page
                print(f"✅ Знайдено вкладку ChatGPT: {page.url}")
                break

        if not chatgpt_page:
            if pages:
                chatgpt_page = pages[-1]
                print(f"⚠️ Не знайдено вкладку з ChatGPT")
                print(f"📄 Використовуємо активну вкладку: {chatgpt_page.url}")
            else:
                print("❌ Немає активних вкладок")
                await playwright.stop()
                return None, None, None

        # Переходимо на потрібний чат
        if target_chat_id not in chatgpt_page.url:
            print(f"🔄 Переходимо на чат: {CHATGPT_URL}")
            await chatgpt_page.goto(CHATGPT_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)
        else:
            print(f"✅ Вже в потрібному чаті")

        print(f"📄 Робоча вкладка: {chatgpt_page.url}\n")

        return browser, chatgpt_page, playwright

    except Exception as e:
        print(f"❌ Помилка підключення: {e}")
        print(f"\n💡 Переконайтесь що Chrome запущено з параметрами:")
        print(f'   & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port={EDGE_CDP_PORT}')
        await playwright.stop()
        return None, None, None


def create_prompt_file(chat_data: Dict, chat_index: int) -> Path:
    """
    Створює текстовий файл з ПОКРАЩЕНИМ промптом для ChatGPT
    Повертає шлях до файлу
    """
    # Створюємо папку для тимчасових промптів
    TEMP_PROMPT_DIR.mkdir(exist_ok=True)

    # Формуємо промпт
    prompt = """Ти експерт з аналізу Telegram спільнот. Проаналізуй чат і створи ТОЧНИЙ опис (2-3 речення).

🎯 ЗАВДАННЯ:
Опиши чат за структурою: [Цільова аудиторія] + [Основні теми] + [Тип активності]

📊 ПРІОРИТЕТ ІНФОРМАЦІЇ (від найважливішого):
1. ПОВІДОМЛЕННЯ - головне джерело правди про чат!
2. Закріплене повідомлення - ключова інформація
3. Опис чату (about)
4. Назва та метадані

✅ ПРИКЛАДИ ПРАВИЛЬНИХ ОПИСІВ:

Крипто:
"Чат для трейдеров криптовалют, обсуждение сигналов Bitcoin/Ethereum, анализ рынка и стратегии торговли. Активный обмен скриншотами сделок и прогнозами."

Фриланс:
"Сообщество дизайнеров и SMM-специалистов, поиск заказов и обсуждение цен на услуги. Постоянный обмен кейсами и портфолио."

Программирование:
"Чат Python-разработчиков, вопросы по Django/Flask, code review и обсуждение архитектуры проектов. Технические дискуссии и помощь новичкам."

Еда/Рестораны:
"Гастрономическое сообщество Киева, рекомендации ресторанов и кафе, обмен рецептами. Фото блюд и отзывы о заведениях."

Локальное сообщество:
"Чат родителей с детьми в Стокгольме, обсуждение детских садов, школ и досуга. Обмен советами по адаптации и организация встреч."

Бизнес/Стартапы:
"Сообщество founders и product managers, обсуждение метрик, fundraising и масштабирования. Обмен опытом запуска продуктов."

Арбитраж трафика:
"Чат арбитражников, кейсы по Facebook/Google Ads, обсуждение офферов и сливов. Анализ креативов и оптимизация ROI."

Инвестиции:
"Чат инвесторов и трейдеров, обсуждение акций, облигаций, ETF. Анализ компаний, дивидендные стратегии и управление портфелем."

Недвижимость:
"Сообщество риелторов и инвесторов в недвижимость, обсуждение сделок, ипотеки и аренды. Обмен объектами и рыночной аналитикой."

Путешествия:
"Чат путешественников, обмен маршрутами, советы по визам и билетам. Фото из поездок и рекомендации отелей."

❌ НЕПРАВИЛЬНЫЕ ПРИМЕРЫ (НЕ делай так):
"Чат для общения" - слишком общо!
"Маркетинг и реклама" - нет конкретики!
"Группа любителей технологий" - расплывчато!

⚠️ ВАЖНО:
- ВСЕГДА пиши описание на РУССКОМ языке (даже если сообщения на другом языке)
- Базируйся на РЕАЛЬНОМ содержании сообщений, НЕ на названии чата
- Указывай КОНКРЕТНЫЕ темы из сообщений (не общие фразы)
- Если видишь профессиональные термины/сленг - используй их
- Если есть регион/город - обязательно укажи

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ДАННЫЕ О ЧАТЕ:

"""

    # 1. БАЗОВА ІНФОРМАЦІЯ
    prompt += f"📌 Название: {chat_data['title']}\n"
    prompt += f"👥 Участников: {chat_data.get('members_count', 0)}\n"

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

🎯 ТЕПЕРЬ СОЗДАЙ ОПИСАНИЕ:

На основе СООБЩЕНИЙ выше (это самое важное!), напиши 2-3 предложения:
- Кто целевая аудитория?
- Какие КОНКРЕТНЫЕ темы обсуждаются? (не общие фразы!)
- Какой характер общения? (обмен кейсами, вопросы-ответы, новости, торговля)

Помни: описание должно отражать РЕАЛЬНОЕ содержание сообщений, а не название чата!

ОТВЕТ НА РУССКОМ ЯЗЫКЕ (2-3 предложения):"""

    # Зберігаємо в файл
    filename = f"prompt_chat_{chat_index}.txt"
    file_path = TEMP_PROMPT_DIR / filename

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(prompt)

    return file_path


async def send_prompt_file_to_chatgpt(page: Page, file_path: Path) -> Optional[str]:
    """
    Завантажує файл з промптом в ChatGPT і чекає на відповідь
    """
    try:
        print(f"   📎 Завантаження файлу: {file_path.name}")

        # Знаходимо кнопку прикріплення файлу
        # ChatGPT має input для файлів (прихований)
        file_input = await page.query_selector('input[type="file"]')

        if not file_input:
            print("   ❌ Не знайдено input для файлів")
            return None

        # Завантажуємо файл
        await file_input.set_input_files(str(file_path.absolute()))
        await asyncio.sleep(2)  # Даємо час на завантаження

        print("   ✅ Файл завантажено")

        # Відправляємо (натискаємо Enter або кнопку Send)
        # Спробуємо знайти кнопку Send
        send_button = None
        send_selectors = [
            'button[data-testid="send-button"]',
            'button:has-text("Send")',
            '[aria-label="Send message"]',
        ]

        for selector in send_selectors:
            try:
                send_button = await page.wait_for_selector(selector, timeout=2000, state="visible")
                if send_button:
                    break
            except:
                continue

        if send_button:
            await send_button.click()
            print("   📤 Промпт надіслано")
        else:
            # Якщо кнопку не знайдено, пробуємо Enter
            await page.keyboard.press("Enter")
            print("   📤 Промпт надіслано (Enter)")

        print("   ⏳ Чекаємо відповідь від ChatGPT...")

        # Даємо час на початок генерації
        await asyncio.sleep(3)

        # Чекаємо поки GPT не закінчить друкувати (кнопка "Stop generating" зникне)
        try:
            # Спочатку чекаємо появи кнопки Stop
            await page.wait_for_selector('button:has-text("Stop")', timeout=5000)
            # Потім чекаємо поки вона зникне (GPT закінчив)
            await page.wait_for_selector('button:has-text("Stop")', state="hidden", timeout=WAIT_FOR_RESPONSE * 1000)
        except:
            # Якщо кнопки немає - GPT відповів дуже швидко або є помилка
            await asyncio.sleep(2)

        # Отримуємо останню відповідь асистента
        messages = await page.query_selector_all('[data-message-author-role="assistant"]')

        if messages:
            last_message = messages[-1]
            response_text = await last_message.inner_text()
            return response_text.strip()
        else:
            print("   ⚠️ Не знайдено відповіді від ChatGPT")
            return None

    except Exception as e:
        print(f"   ❌ Помилка при роботі з ChatGPT: {e}")
        return None


async def generate_descriptions_with_chatgpt(data: List[Dict], mode: str = "one_by_one") -> List[str]:
    """
    Генерує описи через ChatGPT
    mode: "one_by_one" - по одному з паузою, "batch" - всі підряд
    """
    print("🤖 Запуск Playwright для ChatGPT...\n")

    browser, page, pw = await connect_to_browser()

    if not browser or not page:
        return []

    results = []

    try:
        print(f"💬 Працюємо в чаті: {CHATGPT_URL}\n")

        if mode == "one_by_one":
            print(f"📌 Режим: ПО ОДНОМУ чату з паузою після кожного\n")
        else:
            print(f"📌 Режим: ВСІ ПІДРЯД з затримкою {DELAY_BETWEEN_CHATS} сек\n")

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
                print(f"\n   ✅ ОТРИМАНО ВІДПОВІДЬ:")
                print(f"   {'-'*56}")
                print(f"   {response}")
                print(f"   {'-'*56}\n")
                results.append(response)
            else:
                print(f"   ❌ Не вдалося отримати опис")
                results.append(f"[ПОМИЛКА] {chat['title']} ({chat['url']})")

            # Режим роботи
            if mode == "one_by_one" and idx < len(data):
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
                    print(f"\n⏳ Затримка {DELAY_BETWEEN_CHATS} секунд перед наступним чатом...")
                    await asyncio.sleep(DELAY_BETWEEN_CHATS)

    except Exception as e:
        print(f"❌ Помилка: {e}")
    finally:
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass

        # Очищаємо тимчасові файли
        try:
            import shutil
            if TEMP_PROMPT_DIR.exists():
                shutil.rmtree(TEMP_PROMPT_DIR)
                print("\n🗑️ Очищено тимчасові файли")
        except:
            pass

        print("\n✅ ChatGPT обробка завершена")
        # НЕ закриваємо браузер - він має залишитись відкритим

    return results


def save_results(results: List[str]):
    """Зберігає результати"""
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(result + "\n\n")

    print(f"💾 Результати збережено в: {RESULT_FILE}")


# ------------------ MAIN ------------------
async def main():
    print("=" * 80)
    print("🤖 ГЕНЕРАЦІЯ ОПИСІВ ЧЕРЕЗ ChatGPT")
    print("=" * 80 + "\n")

    # 1. Читаємо дані з файлу
    print(f"📂 Читання даних з: {CHAT_DATA_FILE}")
    data = load_data_from_file()

    if not data:
        print("❌ Не знайдено даних для обробки")
        print(f"💡 Спочатку запустіть збір даних через Telethon")
        return

    print(f"✅ Завантажено {len(data)} чатів\n")

    # Показуємо перші 5
    print(f"📋 Перші {min(5, len(data))} чатів:")
    for i, chat in enumerate(data[:5], 1):
        print(f"   {i}. {chat['title']} (@{chat.get('username', 'N/A')})")
    if len(data) > 5:
        print(f"   ... та ще {len(data) - 5} чатів")
    print()

    # 2. Вибір режиму роботи
    print("⚠️ ВАЖЛИВО:")
    print(f"   - Chrome має бути запущено на порту {EDGE_CDP_PORT}")
    print(f"   - Ви маєте бути авторизовані в ChatGPT")
    print(f"   - Чат відкритий: {CHATGPT_URL}\n")

    print("🔧 Оберіть режим роботи:")
    print("   1. ПО ОДНОМУ - обробити чат, зупинитись, запитати чи продовжувати")
    print("   2. ВСІ ПІДРЯД - обробити всі чати з затримкою між ними")
    print(f"\nВаш вибір (1/2, за замовчуванням 1): ", end="")

    mode_choice = input().strip()
    if mode_choice == '2':
        mode = "batch"
        print("✅ Вибрано: ВСІ ПІДРЯД")
    else:
        mode = "one_by_one"
        print("✅ Вибрано: ПО ОДНОМУ")

    print("\nПродовжити? (y/n): ", end="")
    choice = input().strip().lower()
    if choice != 'y':
        print("❌ Скасовано")
        return

    # 3. Генерація описів
    print("\n" + "=" * 80)
    print("ГЕНЕРАЦІЯ ОПИСІВ")
    print("=" * 80 + "\n")

    results = await generate_descriptions_with_chatgpt(data, mode=mode)

    # 4. Збереження
    if results:
        save_results(results)

        print("\n" + "=" * 80)
        print("✅ ГОТОВО!")
        print("=" * 80 + "\n")
        print(f"📁 Результати: {RESULT_FILE}")
        print(f"📊 Оброблено: {len(results)} чатів\n")

        print("Перші результати:")
        for result in results[:3]:
            print(f"  • {result}")
        if len(results) > 3:
            print(f"  ... та ще {len(results) - 3} описів")
    else:
        print("\n❌ Не вдалося згенерувати описи")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    asyncio.run(main())
