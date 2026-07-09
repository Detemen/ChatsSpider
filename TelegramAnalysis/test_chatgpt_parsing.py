"""
Тест ChatGPT фази з даними які були зібрані
"""
import json
from pathlib import Path
import sys

# Додаємо шлях для імпорту
sys.path.insert(0, str(Path(__file__).parent))

from analyze_chats_playwright import parse_chatgpt_response, create_prompt_file


def test_parsing():
    print("=" * 80)
    print("  ТЕСТ ПАРСИНГУ CHATGPT ВІДПОВІДЕЙ")
    print("=" * 80 + "\n")

    # Тестові відповіді різних форматів
    test_responses = [
        # Формат 1: Правильна відповідь
        """CATEGORY: IT-сфера
LANGUAGE_CHECK: PASS - Более 90% сообщений на русском языке
PROHIBITED_CONTENT: PASS - Запрещенного контента не обнаружено
CATEGORY_FIT: PASS - Чат соответствует тематике IT-сферы
DESCRIPTION: Чат для IT-специалистов, обсуждают программирование, вакансии и технологии.""",

        # Формат 2: Відхилення через мову
        """CATEGORY: Інше
LANGUAGE_CHECK: FAIL - Менее 80% русского языка, много английского
PROHIBITED_CONTENT: PASS - Запрещенного контента нет
CATEGORY_FIT: FAIL - Не подходит ни под одну бизнес-категорию
DESCRIPTION: Чат для семей с детьми в Стокгольме, обсуждают детские вопросы и паспорта.""",

        # Формат 3: Відхилення через заборонений контент
        """CATEGORY: Фриланс/Самозанятые
LANGUAGE_CHECK: PASS - 85% русского языка
PROHIBITED_CONTENT: FAIL - Обнаружены упоминания ЗСУ (5 раз) и сбор средств на помощь
CATEGORY_FIT: PASS - Соответствует тематике фриланса
DESCRIPTION: Чат для фрилансеров, но содержит запрещенный контент.""",

        # Формат 4: Успішна валідація Crypto
        """CATEGORY: Crypto и GameFi
LANGUAGE_CHECK: PASS - 92% русского языка
PROHIBITED_CONTENT: PASS - Контент чистый
CATEGORY_FIT: PASS - Обсуждают криптовалюты, NFT и DeFi проекты
DESCRIPTION: Активное сообщество криптоэнтузиастов, обсуждают торговлю и новые проекты.""",
    ]

    print("📝 Тестування парсингу різних відповідей:\n")

    for i, response in enumerate(test_responses, 1):
        print(f"--- Тест {i} ---")
        result = parse_chatgpt_response(response)

        if result:
            print(f"   OK Категорія: {result.get('category', 'НЕ ЗНАЙДЕНО')}")
            print(f"   OK Мова: {result['language_check']['status']} - {result['language_check']['details'][:50]}...")
            print(f"   OK Заборонений контент: {result['prohibited_content']['status']} - {result['prohibited_content']['details'][:50]}...")
            print(f"   OK Відповідність категорії: {result['category_fit']['status']} - {result['category_fit']['details'][:50]}...")
            print(f"   OK Валідний: {result['is_valid']}")
            print(f"   OK Опис: {result['description'][:60]}...")
        else:
            print("   FAIL Помилка парсингу!")

        print()

    # Тест створення промпта
    print("\n" + "=" * 80)
    print("  ТЕСТ СТВОРЕННЯ ПРОМПТУ")
    print("=" * 80 + "\n")

    test_chat = {
        'url': 'https://t.me/testchat',
        'username': '@testchat',
        'title': 'Test Chat',
        'description': 'Test description',
        'members_count': 1000,
        'activity_level': 'HIGH',
        'avg_messages_per_day': 50.0,
        'messages_count': 350,
        'admins': [{'username': '@admin1', 'first_name': 'Admin', 'last_name': 'One', 'is_bot': False}],
        'pinned_message': 'Test pinned message',
        'messages': [
            {'date': '2025-12-20', 'sender': 'User 1', 'text': 'Test message 1'},
            {'date': '2025-12-20', 'sender': 'User 2', 'text': 'Test message 2'},
        ]
    }

    prompt_file = Path(__file__).parent / "test_prompt.txt"
    try:
        result_file = create_prompt_file(test_chat, 1)
        print(f"   OK Промпт створено: {result_file}")
        print(f"   OK Розмір: {result_file.stat().st_size} байтів\n")

        # Показуємо перші рядки промпту
        with open(result_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')[:20]
            print("   Перші 20 рядків промпту:")
            for line in lines:
                print(f"     {line}")

    except Exception as e:
        print(f"   FAIL Помилка створення промпту: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_parsing()
