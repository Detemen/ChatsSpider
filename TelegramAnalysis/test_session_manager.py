# -*- coding: utf-8 -*-
"""
Simple test для SessionManager
Перевіряє базову функціональність управління сесіями
"""

import sys
from pathlib import Path

# Тест 1: Імпорт SessionManager
print("\n1. Тестування імпорту SessionManager...")
try:
    from session_manager import SessionManager, SessionInfo
    print("   OK Імпорт успішний")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Тест 2: Створення екземпляру
print("\n2. Створення SessionManager...")
try:
    # Використовуємо тестовий DB path
    manager = SessionManager(db_path="state/chats.db", accs_dir="accs")
    print(f"   OK SessionManager створено")
    print(f"   OK Знайдено {manager.get_total_count()} сесій")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Тест 3: Перевірка методів
print("\n3. Тестування методів SessionManager...")
try:
    total = manager.get_total_count()
    available = manager.get_available_count()
    print(f"   OK get_total_count(): {total}")
    print(f"   OK get_available_count(): {available}")

    # Статус репорт
    report = manager.get_status_report()
    print(f"   OK get_status_report() працює")

except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Тест 4: Блокування сесії (якщо є хоча б одна)
if manager.get_total_count() > 0:
    print("\n4. Тестування блокування сесії...")
    try:
        test_session = manager.sessions[0]
        session_name = test_session.name

        # Заблокувати на 60 секунд
        manager.mark_session_blocked(session_name, 60, "Test FloodWait")
        print(f"   OK Сесія {session_name} заблокована на 60s")

        # Перевірити статус
        available_after = manager.get_available_count()
        print(f"   OK Доступних сесій після блокування: {available_after}")

        # Розблокувати (через force-видалення з DB)
        import sqlite3
        conn = sqlite3.connect("state/chats.db")
        conn.execute("DELETE FROM session_blocks WHERE session_name = ?", (session_name,))
        conn.commit()
        conn.close()
        print(f"   OK Блокування видалено з DB")

    except Exception as e:
        print(f"   ERROR: {e}")
        sys.exit(1)
else:
    print("\n4. Пропуск тесту блокування (немає сесій)")

# Тест 5: Перевірка інтеграції з analyze_chats_playwright.py
print("\n5. Перевірка імпорту в analyze_chats_playwright.py...")
try:
    import analyze_chats_playwright
    print("   OK analyze_chats_playwright імпортується без помилок")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("OK ВСІ ТЕСТИ ПРОЙДЕНО!")
print("="*60)
print("\nSessionManager готовий до використання:")
print(f"  - Всього сесій: {manager.get_total_count()}")
print(f"  - Доступних: {manager.get_available_count()}")
print("\nСтатус:")
print(manager.get_status_report())
