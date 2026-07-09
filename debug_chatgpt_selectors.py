# debug_chatgpt_selectors.py
"""
Скрипт для відладки - показує всі textarea на сторінці ChatGPT
"""
import asyncio
import sys

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

async def debug_selectors():
    playwright = await async_playwright().start()

    try:
        browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
        contexts = browser.contexts

        if not contexts:
            print("❌ Немає контекстів")
            return

        context = contexts[0]
        pages = context.pages

        if not pages:
            print("❌ Немає сторінок")
            return

        # Використовуємо активну сторінку
        page = pages[-1]
        print(f"📄 Сторінка: {page.url}\n")

        # Отримуємо інформацію про всі textarea
        print("🔍 Шукаємо всі textarea:")
        textareas = await page.query_selector_all('textarea')
        print(f"Знайдено {len(textareas)} textarea елементів\n")

        for i, textarea in enumerate(textareas, 1):
            print(f"Textarea #{i}:")

            # ID
            id_attr = await textarea.get_attribute('id')
            print(f"  id: {id_attr}")

            # Класи
            class_attr = await textarea.get_attribute('class')
            print(f"  class: {class_attr}")

            # Placeholder
            placeholder = await textarea.get_attribute('placeholder')
            print(f"  placeholder: {placeholder}")

            # data-* атрибути
            data_id = await textarea.get_attribute('data-id')
            if data_id:
                print(f"  data-id: {data_id}")

            # name
            name = await textarea.get_attribute('name')
            if name:
                print(f"  name: {name}")

            # Видимість
            is_visible = await textarea.is_visible()
            print(f"  visible: {is_visible}")

            print()

        # Шукаємо contenteditable елементи (ChatGPT може використовувати їх)
        print("\n🔍 Шукаємо contenteditable елементи:")
        contenteditable = await page.query_selector_all('[contenteditable="true"]')
        print(f"Знайдено {len(contenteditable)} contenteditable елементів\n")

        for i, elem in enumerate(contenteditable[:5], 1):
            print(f"Contenteditable #{i}:")

            # ID
            id_attr = await elem.get_attribute('id')
            print(f"  id: {id_attr}")

            # Класи
            class_attr = await elem.get_attribute('class')
            print(f"  class: {class_attr}")

            # role
            role = await elem.get_attribute('role')
            if role:
                print(f"  role: {role}")

            # Видимість
            is_visible = await elem.is_visible()
            print(f"  visible: {is_visible}")

            # Tag name
            tag = await elem.evaluate("el => el.tagName")
            print(f"  tag: {tag}")

            print()

        # Також шукаємо кнопки
        print("\n🔍 Шукаємо кнопки відправки:")
        buttons = await page.query_selector_all('button')
        print(f"Знайдено {len(buttons)} кнопок\n")

        # Показуємо перші 10
        for i, button in enumerate(buttons[:10], 1):
            aria_label = await button.get_attribute('aria-label')
            data_testid = await button.get_attribute('data-testid')
            text = await button.inner_text() if await button.is_visible() else ""

            if aria_label or data_testid or "send" in text.lower():
                print(f"Button #{i}:")
                if aria_label:
                    print(f"  aria-label: {aria_label}")
                if data_testid:
                    print(f"  data-testid: {data_testid}")
                if text:
                    print(f"  text: {text[:50]}")
                print()

    except Exception as e:
        print(f"❌ Помилка: {e}")
    finally:
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(debug_selectors())
