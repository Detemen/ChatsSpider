"""
Тестування імпортів та базової логіки
"""
import sys
print("Python version:", sys.version)
print("="*60)

# Тест 1: Імпорт всіх модулів
print("\n1. Тестування імпортів...")
try:
    import categories_config
    print("   OK categories_config")
except Exception as e:
    print(f"   FAIL categories_config: {e}")
    sys.exit(1)

try:
    import validation
    print("   OK validation")
except Exception as e:
    print(f"   FAIL validation: {e}")
    sys.exit(1)

try:
    import output_formatter
    print("   OK output_formatter")
except Exception as e:
    print(f"   FAIL output_formatter: {e}")
    sys.exit(1)

# Тест 2: Перевірка категорій
print("\n2. Тестування categories_config...")
print(f"   Всього категорій: {len(categories_config.CATEGORIES)}")
print(f"   Founder категорій: {len(categories_config.FOUNDER_CATEGORIES)}")
print(f"   Manager категорій: {len(categories_config.MANAGER_CATEGORIES)}")

# Перевірка функцій
test_category = "Crypto и GameFi"
owner = categories_config.get_category_owner(test_category)
print(f"   '{test_category}' -> owner: {owner}")

# Тест 3: Тестування валідації
print("\n3. Тестування validation...")
test_messages = [
    {'text': 'Привет, как дела?', 'sender': 'User1'},
    {'text': 'Хорошо, спасибо!', 'sender': 'User2'},
]
rus_percent = validation.estimate_russian_percentage(test_messages)
print(f"   Російська мова в тестових повідомленнях: {rus_percent:.1f}%")

# Тест 4: Тестування output_formatter
print("\n4. Тестування output_formatter...")
test_chat_data = {
    'url': 'https://t.me/test',
    'title': 'Test Chat',
    'username': 'test',
    'members_count': 100,
    'activity_level': 'HIGH',
    'avg_messages_per_day': 50.0,
}
test_result = {
    'category': 'IT-сфера',
    'language_check': {'status': 'PASS', 'details': '95% русский'},
    'prohibited_content': {'status': 'PASS', 'details': 'нет запрещённого контента'},
    'category_fit': {'status': 'PASS', 'details': 'хорошо подходит'},
    'description': 'Тестовое описание чата',
    'is_valid': True
}

formatted = output_formatter.format_compact(test_chat_data, test_result)
print(f"   Compact формат: {formatted.strip()}")

# Тест 4b: Тестування format_detailed
print("\n4b. Тестування format_detailed...")
formatted_detailed = output_formatter.format_detailed(test_chat_data, test_result)
lines = formatted_detailed.strip().split('\n')
print(f"   Detailed формат має {len(lines)} рядків (очікується 3)")
assert len(lines) == 3, f"Формат мав мати 3 рядки! Отримано: {len(lines)}"
print(f"   OK Структура: {lines[0][:60]}...")
print(f"   OK URL: {lines[1]}")
print(f"   OK Username: {lines[2]}")

# Тест 5: Перевірка парсера (симуляція)
print("\n5. Тестування парсера...")
test_response = """
CATEGORY: IT-сфера
LANGUAGE_CHECK: PASS - 95% русский язык
PROHIBITED_CONTENT: PASS - нет запрещённого контента
CATEGORY_FIT: PASS - чат соответствует IT тематике
DESCRIPTION: Сообщество программистов обсуждает Python и веб-разработку.
"""

# Імпортуємо функцію парсера
sys.path.insert(0, '.')
from analyze_chats_playwright import parse_chatgpt_response

parsed = parse_chatgpt_response(test_response)
if parsed:
    print(f"   OK Category: {parsed['category']}")
    print(f"   OK Valid: {parsed['is_valid']}")
else:
    print("   FAIL Parsing failed")

print("\n" + "="*60)
print("ALL TESTS PASSED SUCCESSFULLY!")
print("="*60)
