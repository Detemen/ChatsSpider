"""
Тест тільки Telegram колекції (перші 5 чатів)
"""
import asyncio
import sys
from pathlib import Path

# Додаємо шлях для імпорту
sys.path.insert(0, str(Path(__file__).parent))

from analyze_chats_playwright import collect_chat_data, load_chats_from_file, save_data_to_file


async def main():
    print("=" * 80)
    print("  ТЕСТ TELEGRAM КОЛЕКЦІЇ (ПЕРШІ 5 ЧАТІВ)")
    print("=" * 80 + "\n")

    # Завантажуємо всі чати
    INPUT_FILE = Path(__file__).parent / "@mt_offer.txt"
    all_chat_urls = load_chats_from_file(INPUT_FILE)

    print(f"✅ Завантажено {len(all_chat_urls)} чатів з @username\n")

    # Беремо тільки перші 5 для тесту
    test_urls = all_chat_urls[:5]

    print("📋 Чати для тесту:")
    for i, url in enumerate(test_urls, 1):
        print(f"   {i}. {url}")
    print()

    print("🔄 Початок збору даних через Telethon...")
    print("   (це може зайняти 1-2 хвилини)\n")

    # Збираємо дані
    try:
        data = await collect_chat_data(test_urls)

        print(f"\n✅ Збір даних завершено!")
        print(f"   Оброблено чатів: {len(test_urls)}")
        print(f"   Активних чатів (20+ повідомлень/день): {len(data)}")

        if data:
            print("\n📊 Активні чати:")
            for i, chat in enumerate(data, 1):
                print(f"   {i}. {chat['title']} - {chat['avg_messages_per_day']:.1f} повідомлень/день")

            # Зберігаємо результат
            output_file = Path(__file__).parent / "output" / "test_collection_result.txt"
            save_data_to_file(data, output_file)
            print(f"\n💾 Результат збережено: {output_file}")
        else:
            print("\n⚠️  Жоден з чатів не є активним (менше 20 повідомлень/день)")

    except KeyboardInterrupt:
        print("\n\n❌ Зупинено користувачем (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
