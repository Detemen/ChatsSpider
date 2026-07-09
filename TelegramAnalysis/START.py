"""
АВТОМАТИЧНИЙ ЗАПУСК АНАЛІЗУ TELEGRAM ЧАТІВ
Запускає RUN_ALL.py з віртуального середовища
"""
import subprocess
import sys
from pathlib import Path

def main():
    """Запуск аналізу"""
    print("=" * 80)
    print("  ЗАПУСК АНАЛІЗУ TELEGRAM ЧАТІВ")
    print("=" * 80 + "\n")

    # Шлях до поточної папки
    script_dir = Path(__file__).parent

    # Шлях до Python у віртуальному середовищі
    if sys.platform == "win32":
        python_exe = script_dir / "venv" / "Scripts" / "python.exe"
    else:
        python_exe = script_dir / "venv" / "bin" / "python"

    # Шлях до RUN_ALL.py
    run_all_script = script_dir / "RUN_ALL.py"

    # Перевірка наявності файлів
    if not python_exe.exists():
        print(f"ПОМИЛКА: Віртуальне середовище не знайдено!")
        print(f"Очікувався: {python_exe}")
        print("\nСтворіть віртуальне середовище:")
        print("  python -m venv venv")
        print("  venv\\Scripts\\activate")
        print("  pip install -r requirements.txt")
        print("  playwright install")
        return 1

    if not run_all_script.exists():
        print(f"ПОМИЛКА: RUN_ALL.py не знайдено!")
        print(f"Очікувався: {run_all_script}")
        return 1

    # Запуск RUN_ALL.py
    print(f"Запуск: {python_exe} {run_all_script}\n")

    try:
        result = subprocess.run(
            [str(python_exe), str(run_all_script)],
            cwd=str(script_dir)
        )
        return result.returncode

    except KeyboardInterrupt:
        print("\n\nПерервано користувачем (Ctrl+C)")
        return 130

    except Exception as e:
        print(f"\n\nПОМИЛКА: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()

    # Пауза перед закриттям (якщо запущено подвійним кліком)
    if sys.platform == "win32":
        input("\nНатисніть Enter для виходу...")

    sys.exit(exit_code)
