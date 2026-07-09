"""
Тест ChatGPT аналізу з одним чатом
"""
import asyncio
import json
from pathlib import Path

# Імпортуємо функції з головного скрипта
import sys
sys.path.insert(0, str(Path(__file__).parent))

from analyze_chats_playwright import (
    create_prompt_file,
    send_prompt_file_to_chatgpt,
    parse_chatgpt_response
)
from playwright.async_api import async_playwright


async def test_one_chat():
    """Тестує ChatGPT аналіз з одним чатом"""
    print("=" * 80)
    print("  ТЕСТ CHATGPT З ОДНИМ ЧАТОМ")
    print("=" * 80 + "\n")

    # Тестовий чат (IT-тематика, має бути прийнятий)
    test_chat = {
        'url': 'https://t.me/gamedevmeets',
        'username': '@gamedevmeets',
        'title': 'Game dev в Польше',
        'description': 'Чат для розробників ігор в Польщі',
        'members_count': 500,
        'activity_level': 'HIGH',
        'avg_messages_per_day': 45.0,
        'messages_count': 315,
        'admins': [
            {'username': '@admin1', 'first_name': 'Admin', 'last_name': 'One', 'is_bot': False}
        ],
        'pinned_message': 'Обговорюємо розробку ігор',
        'messages': [
            {'date': '2025-12-20', 'sender': 'User 1', 'text': 'Хто працює з Unity?'},
            {'date': '2025-12-20', 'sender': 'User 2', 'text': 'Я на Unreal Engine'},
            {'date': '2025-12-20', 'sender': 'User 3', 'text': 'Шукаю художника для інді-проекту'},
        ] * 100  # Повторюємо щоб було багато повідомлень
    }

    # 1. Створюємо промпт файл
    print("1. Створення промпт файлу...")
    try:
        prompt_file = create_prompt_file(test_chat, 1)
        print(f"   OK Створено: {prompt_file}")
        print(f"   OK Розмір: {prompt_file.stat().st_size} bytes\n")
    except Exception as e:
        print(f"   FAIL Помилка: {e}\n")
        return

    # 2. Підключаємось до ChatGPT через браузер
    print("2. Підключення до ChatGPT...")
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
        contexts = browser.contexts

        if not contexts:
            print("   FAIL Браузер не запущений з режимом відладки")
            print("   Запустіть Chrome:")
            print('   chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\\chrome-playwright-profile\n')
            await playwright.stop()
            return

        # Шукаємо вкладку ChatGPT
        chatgpt_page = None
        for context in contexts:
            for page in context.pages:
                if "chatgpt.com" in page.url:
                    chatgpt_page = page
                    break
            if chatgpt_page:
                break

        if not chatgpt_page:
            print("   FAIL ChatGPT вкладка не знайдена")
            print("   Відкрийте https://chatgpt.com в Chrome\n")
            await playwright.stop()
            return

        print(f"   OK Підключено до: {chatgpt_page.url}\n")

        # 3. Відправляємо промпт
        print("3. Відправка промпту в ChatGPT...")
        response = await send_prompt_file_to_chatgpt(chatgpt_page, prompt_file)

        if response:
            print(f"   OK Отримано відповідь ({len(response)} символів)")
            print("\n   Перші 500 символів відповіді:")
            print("   " + "-" * 76)
            print("   " + response[:500].replace("\n", "\n   "))
            print("   " + "-" * 76 + "\n")
        else:
            print("   FAIL Не отримано відповіді від ChatGPT\n")
            await playwright.stop()
            return

        # 4. Парсимо відповідь
        print("4. Парсинг відповіді...")
        result = parse_chatgpt_response(response)

        if result:
            print("   OK Відповідь розпарсена успішно\n")
            print("   Результати:")
            print(f"      Категорія: {result.get('category', 'НЕ ЗНАЙДЕНО')}")
            print(f"      Мова: {result['language_check']['status']} - {result['language_check']['details']}")
            print(f"      Заборонений контент: {result['prohibited_content']['status']} - {result['prohibited_content']['details']}")
            print(f"      Відповідність категорії: {result['category_fit']['status']} - {result['category_fit']['details']}")
            print(f"      Валідний: {result['is_valid']}")
            print(f"      Опис: {result['description']}\n")
        else:
            print("   FAIL Помилка парсингу\n")
            print("   Повна відповідь ChatGPT:")
            print("   " + "-" * 76)
            print("   " + response.replace("\n", "\n   "))
            print("   " + "-" * 76 + "\n")

        await playwright.stop()

    except Exception as e:
        print(f"   FAIL Помилка: {e}\n")
        import traceback
        traceback.print_exc()

    print("=" * 80)
    print("  ТЕСТ ЗАВЕРШЕНО")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_one_chat())
