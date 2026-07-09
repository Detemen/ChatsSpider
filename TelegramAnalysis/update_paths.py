"""
Оновлення шляхів у всіх файлах документації
"""
from pathlib import Path

# Файли для оновлення
FILES_TO_UPDATE = [
    "README.txt",
    "МІГРАЦІЯ_ЗАВЕРШЕНА.txt",
    "STATUS_AND_NEXT_STEPS.txt",
]

# Заміни
REPLACEMENTS = [
    ("f:\\PY\\TelegramAnalysis", "f:\\PY\\ChatsSpider\\TelegramAnalysis"),
    ("f:/PY/TelegramAnalysis", "f:/PY/ChatsSpider/TelegramAnalysis"),
]

def update_paths():
    """Оновлює шляхи у файлах"""
    base_dir = Path(__file__).parent

    print("=" * 80)
    print("  ОНОВЛЕННЯ ШЛЯХІВ У ДОКУМЕНТАЦІЇ")
    print("=" * 80 + "\n")

    for filename in FILES_TO_UPDATE:
        file_path = base_dir / filename

        if not file_path.exists():
            print(f"   -- Пропущено {filename} (не знайдено)")
            continue

        # Читаємо файл
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Робимо заміни
        modified = False
        for old_path, new_path in REPLACEMENTS:
            if old_path in content:
                content = content.replace(old_path, new_path)
                modified = True

        # Записуємо назад якщо були зміни
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"   OK Оновлено {filename}")
        else:
            print(f"   -- {filename} (без змін)")

    print("\n" + "=" * 80)
    print("  ЗАВЕРШЕНО")
    print("=" * 80)
    print(f"\nВсі шляхи оновлені на: f:\\PY\\ChatsSpider\\TelegramAnalysis\n")


if __name__ == "__main__":
    update_paths()
