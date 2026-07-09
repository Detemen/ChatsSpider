"""
Реорганізація: переміщення TelegramAnalysis в ChatsSpider та очищення
"""
import shutil
from pathlib import Path

# Поточна папка
CURRENT_DIR = Path("f:/PY/TelegramAnalysis")
# Цільова папка
TARGET_DIR = Path("f:/PY/ChatsSpider/TelegramAnalysis")

def reorganize():
    """Переміщує папку та очищає зайві файли"""
    print("=" * 80)
    print("  РЕОРГАНІЗАЦІЯ ПРОЕКТУ")
    print("=" * 80 + "\n")

    print(f"Джерело: {CURRENT_DIR}")
    print(f"Призначення: {TARGET_DIR}\n")

    # Якщо цільова папка вже існує, видаляємо її
    if TARGET_DIR.exists():
        print(f"   Видалення старої папки {TARGET_DIR}...")
        shutil.rmtree(TARGET_DIR)
        print("   OK Видалено\n")

    # Переміщуємо всю папку
    print(f"   Переміщення {CURRENT_DIR} -> {TARGET_DIR}...")
    shutil.move(str(CURRENT_DIR), str(TARGET_DIR))
    print("   OK Переміщено\n")

    print("=" * 80)
    print("  ЗАВЕРШЕНО")
    print("=" * 80)
    print(f"\nНова локація проекту: {TARGET_DIR}")
    print("\nДля запуску:")
    print(f"   cd {TARGET_DIR}")
    print("   START.bat")
    print()


if __name__ == "__main__":
    try:
        reorganize()
    except Exception as e:
        print(f"\n❌ ПОМИЛКА: {e}")
        import traceback
        traceback.print_exc()
