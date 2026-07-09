"""
Тест тільки ChatGPT фази з існуючими даними
"""
import asyncio
import json
import sys
from pathlib import Path

# Додаємо шлях
sys.path.insert(0, str(Path(__file__).parent))

from analyze_chats_playwright import generate_descriptions_with_chatgpt
from output_formatter import print_final_statistics

async def main():
    print("="*80)
    print("  ТЕСТ ChatGPT + КАТЕГОРИЗАЦІЯ")
    print("="*80)

    # Завантажуємо існуючі дані
    data_file = Path("output/chat_analysis_data.txt")

    if not data_file.exists():
        print("ERROR: chat_analysis_data.txt not found!")
        return

    # Читаємо chat_data (симуляція - берем з файлу що вже є)
    test_chat = {
        'url': 'https://t.me/familiesinstocholm',
        'username': 'familiesinstocholm',
        'title': 'Стокгольм с детьми',
        'members_count': 339,
        'activity_level': 'HIGH',
        'avg_messages_per_day': 70.4,
        'about': 'Привет! Группа для общения семей с детьми.',
        'admins': [{'username': 'AndreiUshakov', 'is_bot': False}],
        'recent_messages': []  # Вже є в промпті
    }

    print(f"\nТестуємо на чаті: {test_chat['title']}")
    print(f"Активність: {test_chat['activity_level']} ({test_chat['avg_messages_per_day']} msg/day)")
    print("\nЗапускаємо ChatGPT аналіз...")
    print("="*80)

    # Запускаємо ChatGPT
    results = await generate_descriptions_with_chatgpt([test_chat], mode="batch")

    print("\n" + "="*80)
    print("  РЕЗУЛЬТАТИ")
    print("="*80)

    for result in results:
        print(result)

    # Статистика
    print_final_statistics()

if __name__ == "__main__":
    asyncio.run(main())
