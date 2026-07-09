# -*- coding: utf-8 -*-
"""
Демонстрація нового формату виводу detailed файлів
"""

import sys
sys.path.insert(0, '.')

from output_formatter import format_detailed, format_compact

# Приклад 1: Crypto чат
chat1 = {
    'url': 'https://t.me/crypto_chat',
    'username': 'crypto_chat',
    'title': 'Крипто Комюніті',
    'members_count': 5000,
    'activity_level': 'HIGH',
    'avg_messages_per_day': 120.5,
}

result1 = {
    'category': 'Crypto и GameFi',
    'is_valid': True,
    'description': 'Обговорення крипто проектів',
}

# Приклад 2: Фріланс чат
chat2 = {
    'url': 'https://t.me/remote_work_ru',
    'username': 'remote_work_ru',
    'title': 'Удалёнка 1.0',
    'members_count': 18,
    'activity_level': 'HIGH',
    'avg_messages_per_day': 60.1,
}

result2 = {
    'category': 'Фриланс/Самозанятые',
    'is_valid': True,
    'description': 'Вакансії для фрілансерів',
}

# Приклад 3: Експати чат
chat3 = {
    'url': 'https://t.me/expat_community',
    'username': 'expat_community',
    'title': 'Експати в Європі',
    'members_count': 2500,
    'activity_level': 'LOW',
    'avg_messages_per_day': 15.0,
}

result3 = {
    'category': 'Экспаты',
    'is_valid': True,
    'description': 'Спільнота експатів',
}

print("=" * 80)
print("НОВИЙ DETAILED ФОРМАТ (4 рядки на чат)")
print("=" * 80)

print("\nПриклад 1:")
print(format_detailed(chat1, result1))

print("Приклад 2:")
print(format_detailed(chat2, result2))

print("Приклад 3:")
print(format_detailed(chat3, result3))

print("=" * 80)
print("COMPACT ФОРМАТ (БЕЗ ЗМІН - одна лінія)")
print("=" * 80)

print("\nПриклад 1:")
print(format_compact(chat1, result1))

print("Приклад 2:")
print(format_compact(chat2, result2))

print("Приклад 3:")
print(format_compact(chat3, result3))
