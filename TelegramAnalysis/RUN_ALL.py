"""
АВТОМАТИЧНИЙ ЗАПУСК АНАЛІЗУ ЧАТІВ
Запускає Chrome, перевіряє ChatGPT і запускає повний аналіз
"""
import subprocess
import time
import sys
import os
from pathlib import Path
import asyncio
from playwright.async_api import async_playwright

# Конфігурація
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CDP_PORT = 9222
CHATGPT_URL = "https://chatgpt.com/c/6937098c-d498-832a-8921-8e543d15ff2f"
CHROME_PROFILE = r"C:\chrome-playwright-profile"
EDGE_PROFILE = r"C:\edge-playwright-profile"

SCRIPT_DIR = Path(__file__).parent
ANALYZE_SCRIPT = SCRIPT_DIR / "analyze_chats_playwright.py"


def print_header(text):
    """Красивий заголовок"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def find_browser():
    """Знайти доступний браузер"""
    if os.path.exists(CHROME_PATH):
        return CHROME_PATH, CHROME_PROFILE, "Chrome"
    elif os.path.exists(EDGE_PATH):
        return EDGE_PATH, EDGE_PROFILE, "Edge"
    else:
        return None, None, None


def is_browser_running(port=9222):
    """Перевірити чи браузер вже запущений з CDP"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0


def launch_browser(browser_path, profile_dir, browser_name):
    """Запустити браузер з режимом відладки"""
    print(f"🚀 Запуск {browser_name}...")

    cmd = [
        browser_path,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={profile_dir}",
        CHATGPT_URL
    ]

    try:
        # Запускаємо браузер у фоні (без очікування завершення)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        print(f"✅ {browser_name} запущено")
        print(f"   URL: {CHATGPT_URL}")
        print(f"   Порт відладки: {CDP_PORT}")
        return True
    except Exception as e:
        print(f"❌ Помилка запуску {browser_name}: {e}")
        return False


async def check_chatgpt_ready():
    """Перевірити що ChatGPT доступний і користувач авторизований"""
    print("\n🔍 Перевірка ChatGPT...")

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")

        # Отримуємо всі контексти
        contexts = browser.contexts
        if not contexts:
            print("❌ Немає відкритих вкладок")
            await playwright.stop()
            return False

        # Шукаємо вкладку з ChatGPT
        chatgpt_page = None
        for context in contexts:
            for page in context.pages:
                if "chatgpt.com" in page.url:
                    chatgpt_page = page
                    break
            if chatgpt_page:
                break

        if not chatgpt_page:
            print("⚠️  Вкладка ChatGPT не знайдена")
            print("   Спроба відкрити...")
            # Відкриваємо нову вкладку
            page = await contexts[0].new_page()
            await page.goto(CHATGPT_URL)
            chatgpt_page = page
            time.sleep(3)

        # Перевіряємо чи авторизований
        print(f"✅ ChatGPT відкрито: {chatgpt_page.url}")

        # Перевіряємо наявність елементів для введення (означає що авторизований)
        try:
            input_field = await chatgpt_page.wait_for_selector('input[type="file"]', timeout=5000)
            if input_field:
                print("✅ Авторизація успішна (знайдено поле для файлів)")
                await playwright.stop()
                return True
        except:
            print("⚠️  ВАЖЛИВО: Можливо потрібна авторизація в ChatGPT!")
            print("   Перевірте браузер і увійдіть в акаунт якщо потрібно")
            print("   Натисніть Enter після авторизації...")
            input()

        await playwright.stop()
        return True

    except Exception as e:
        print(f"❌ Помилка перевірки ChatGPT: {e}")
        return False


def run_analysis():
    """Запустити аналіз чатів"""
    print_header("ЗАПУСК АНАЛІЗУ ЧАТІВ")

    if not ANALYZE_SCRIPT.exists():
        print(f"❌ Файл не знайдено: {ANALYZE_SCRIPT}")
        return False

    print("📊 Запуск analyze_chats_playwright.py...")
    print("   Режим: АВТОМАТИЧНИЙ (всі чати підряд)")
    print()

    # Запускаємо скрипт з прапорцем --auto для автоматичного режиму
    cmd = [sys.executable, str(ANALYZE_SCRIPT), '--auto']

    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            text=True
        )

        if result.returncode == 0:
            print("\n✅ Аналіз завершено успішно!")
            return True
        else:
            print(f"\n⚠️  Скрипт завершився з кодом: {result.returncode}")
            return False

    except Exception as e:
        print(f"❌ Помилка запуску аналізу: {e}")
        return False


async def main():
    """Головна функція"""
    print_header("🤖 АВТОМАТИЧНИЙ ЗАПУСК АНАЛІЗУ TELEGRAM ЧАТІВ")

    print("Цей скрипт автоматично:")
    print("  1️⃣  Запустить Chrome/Edge з режимом відладки")
    print("  2️⃣  Відкриє ChatGPT")
    print("  3️⃣  Перевірить що все готово")
    print("  4️⃣  Запустить повний аналіз чатів")
    print()

    # Крок 1: Перевірити чи браузер вже запущений
    if is_browser_running(CDP_PORT):
        print("✅ Браузер вже запущений з режимом відладки")
    else:
        # Знайти браузер
        browser_path, profile_dir, browser_name = find_browser()

        if not browser_path:
            print("❌ Не знайдено Chrome або Edge")
            print("\nВстановіть Chrome або Edge, або вкажіть правильний шлях у скрипті")
            return

        # Запустити браузер
        if not launch_browser(browser_path, profile_dir, browser_name):
            print("\n❌ Не вдалося запустити браузер")
            return

        # Почекати поки браузер запуститься
        print("\n⏳ Очікування запуску браузера...")
        time.sleep(5)

    # Крок 2: Перевірити ChatGPT
    if not await check_chatgpt_ready():
        print("\n❌ ChatGPT не готовий. Перевірте браузер вручну")
        print("   Переконайтесь що ви авторизовані на chatgpt.com")
        return

    print("\n" + "=" * 80)
    print("  ✅ ВСЕ ГОТОВО ДО АНАЛІЗУ!")
    print("=" * 80)
    print("\n⚠️  УВАГА: Зараз почнеться автоматичний аналіз ~93 чатів")
    print("   Це займе приблизно 5-10 хвилин")
    print("   НЕ ЗАКРИВАЙТЕ браузер під час роботи!")
    print("\nНатисніть Enter для початку або Ctrl+C для відміни...")

    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ Скасовано користувачем")
        return

    # Крок 3: Запустити аналіз
    run_analysis()

    # Показати де результати
    print_header("📁 РЕЗУЛЬТАТИ")
    print("Дивіться результати тут:")
    print(f"  📄 Founder (детально): {SCRIPT_DIR / 'output' / 'detailed' / 'founder_chats_detailed.txt'}")
    print(f"  📄 Founder (коротко):  {SCRIPT_DIR / 'output' / 'compact' / 'founder_chats_compact.txt'}")
    print(f"  📄 Manager (детально): {SCRIPT_DIR / 'output' / 'detailed' / 'manager_chats_detailed.txt'}")
    print(f"  📄 Manager (коротко):  {SCRIPT_DIR / 'output' / 'compact' / 'manager_chats_compact.txt'}")
    print(f"  📄 Відхилені:          {SCRIPT_DIR / 'output' / 'rejected' / 'rejected_chats.txt'}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Перервано користувачем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критична помилка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
