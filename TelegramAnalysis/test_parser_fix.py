"""
Тест виправленого парсера з реальною відповіддю ChatGPT
"""
from analyze_chats_playwright import parse_chatgpt_response

# Реальна відповідь ChatGPT (з скріншоту користувача)
test_response = """CATEGORY: Фриланс/Самозанятые

LANGUAGE_CHECK: PASS — ~100% сообщений на русском языке

PROHIBITED_CONTENT: FAIL — в ленте массово присутствует навязчивый финансовый спам «Дам в долг от 10 тысяч», что относится к рискованным/нелегальным финансовым услугам и засоряет чат

CATEGORY_FIT: PASS — по назначению чат ориентирован на самозанятых специалистов бьюти-сферы (косметологи): купля-продажа косметики, оборудования и расходников, объявления с ценами и контактами

DESCRIPTION: Чат косметологов, изначально предназначенный для купли-продажи профессиональной косметики, оборудования и расходников с указанием города, цены и контактов. По фактической активности последние сообщения почти полностью состоят из повторяющегося финансового спама «Дам в долг от 10 тысяч», из-за чего профильные объявления и обсуждения практически отсутствуют."""

print("=" * 80)
print("  ТЕСТ ВИПРАВЛЕНОГО ПАРСЕРА")
print("=" * 80 + "\n")

result = parse_chatgpt_response(test_response)

if result:
    print("OK Парсинг успішний!\n")
    print(f"Категорія: {result['category']}")
    print(f"\nМова:")
    print(f"  Статус: {result['language_check']['status']}")
    print(f"  Деталі: {result['language_check']['details']}")
    print(f"\nЗаборонений контент:")
    print(f"  Статус: {result['prohibited_content']['status']}")
    print(f"  Деталі: {result['prohibited_content']['details'][:100]}...")
    print(f"\nВідповідність категорії:")
    print(f"  Статус: {result['category_fit']['status']}")
    print(f"  Деталі: {result['category_fit']['details'][:100]}...")
    print(f"\nОпис: {result['description'][:150]}...")
    print(f"\nВалідний: {result['is_valid']}")

    print("\n" + "=" * 80)
    if result['is_valid']:
        print("РЕЗУЛЬТАТ: Чат буде ПРИЙНЯТО")
    else:
        print("РЕЗУЛЬТАТ: Чат буде ВІДХИЛЕНО")
        reasons = []
        if result['language_check']['status'] != 'PASS':
            reasons.append(f"Мова: {result['language_check']['details']}")
        if result['prohibited_content']['status'] != 'PASS':
            reasons.append(f"Заборонений контент: {result['prohibited_content']['details']}")
        if result['category_fit']['status'] != 'PASS':
            reasons.append(f"Не відповідає категорії: {result['category_fit']['details']}")
        print("Причини відхилення:")
        for reason in reasons:
            print(f"  - {reason[:100]}...")
    print("=" * 80)
else:
    print("FAIL Помилка парсингу!")
