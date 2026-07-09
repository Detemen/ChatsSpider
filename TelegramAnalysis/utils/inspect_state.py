# -*- coding: utf-8 -*-
"""
State Inspector для ChatsSpider
CLI інструмент для інспекції стану SQLite бази даних

Використання:
    python utils/inspect_state.py              # Загальна статистика
    python utils/inspect_state.py --detailed   # Детальна інформація
    python utils/inspect_state.py --rate-limit # Стан rate limiter
    python utils/inspect_state.py --recent 10  # Останні 10 оброблених чатів
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Додати батьківську папку до sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from state_manager import StateManager
from rate_limiter import RateLimiter
from batch_collector import BatchCollector


class StateInspector:
    """Інспектор стану SQLite бази даних"""

    def __init__(self, db_path: str = "state/chats.db"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            print(f"❌ База даних не знайдена: {self.db_path}")
            print(f"💡 Запустіть analyze_chats_playwright.py спочатку")
            sys.exit(1)

    def get_general_stats(self) -> Dict:
        """Загальна статистика"""
        conn = sqlite3.connect(self.db_path)

        # Processed chats statistics
        total = conn.execute('SELECT COUNT(*) FROM processed_chats').fetchone()[0]
        passed = conn.execute(
            'SELECT COUNT(*) FROM processed_chats WHERE validation_result = "PASS"'
        ).fetchone()[0]
        failed = conn.execute(
            'SELECT COUNT(*) FROM processed_chats WHERE validation_result = "FAIL"'
        ).fetchone()[0]

        # Category distribution
        categories = conn.execute('''
            SELECT category, COUNT(*) as count
            FROM processed_chats
            WHERE validation_result = "PASS"
            GROUP BY category
            ORDER BY count DESC
        ''').fetchall()

        # Owner distribution
        owners = conn.execute('''
            SELECT owner, COUNT(*) as count
            FROM processed_chats
            WHERE validation_result = "PASS"
            GROUP BY owner
            ORDER BY count DESC
        ''').fetchall()

        # Recent activity (last 24 hours)
        recent_count = conn.execute('''
            SELECT COUNT(*) FROM processed_chats
            WHERE datetime(processed_at) >= datetime('now', '-1 day')
        ''').fetchone()[0]

        conn.close()

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            'categories': categories,
            'owners': owners,
            'recent_24h': recent_count
        }

    def get_rate_limit_status(self) -> Dict:
        """Статус rate limiter"""
        rate_limiter = RateLimiter(db_path=str(self.db_path))

        current_window = rate_limiter._get_current_hour_window()
        current_count = rate_limiter.get_current_count()
        remaining = rate_limiter.get_remaining()

        conn = sqlite3.connect(self.db_path)

        # Останні 5 годинних вікон
        recent_windows = conn.execute('''
            SELECT hour_window, chats_processed, last_update
            FROM rate_limit
            ORDER BY hour_window DESC
            LIMIT 5
        ''').fetchall()

        conn.close()

        return {
            'current_window': current_window,
            'current_count': current_count,
            'max_per_hour': rate_limiter.max_per_hour,
            'remaining': remaining,
            'recent_windows': recent_windows
        }

    def get_batch_status(self) -> Dict:
        """Статус поточного батчу"""
        batch_collector = BatchCollector(db_path=str(self.db_path))

        current_batch = batch_collector.get_current_batch()
        batch_num = batch_collector._get_current_batch_number()

        return {
            'current_batch_number': batch_num,
            'chats_in_batch': len(current_batch),
            'batch_size': batch_collector.batch_size,
            'batch_ready': len(current_batch) >= batch_collector.batch_size,
            'chats': [chat['url'] for chat in current_batch]
        }

    def get_recent_chats(self, limit: int = 10) -> List[Dict]:
        """Останні оброблені чати"""
        conn = sqlite3.connect(self.db_path)

        chats = conn.execute(f'''
            SELECT url, processed_at, validation_result, category, owner, rejection_reason
            FROM processed_chats
            ORDER BY processed_at DESC
            LIMIT {limit}
        ''').fetchall()

        conn.close()

        return [
            {
                'url': chat[0],
                'processed_at': chat[1],
                'validation_result': chat[2],
                'category': chat[3],
                'owner': chat[4],
                'rejection_reason': chat[5]
            }
            for chat in chats
        ]

    def get_failed_chats(self, limit: int = 20) -> List[Dict]:
        """Відхилені чати з причинами"""
        conn = sqlite3.connect(self.db_path)

        chats = conn.execute(f'''
            SELECT url, category, rejection_reason, processed_at
            FROM processed_chats
            WHERE validation_result = "FAIL"
            ORDER BY processed_at DESC
            LIMIT {limit}
        ''').fetchall()

        conn.close()

        return [
            {
                'url': chat[0],
                'category': chat[1],
                'rejection_reason': chat[2],
                'processed_at': chat[3]
            }
            for chat in chats
        ]

    def print_general_stats(self):
        """Вивести загальну статистику"""
        stats = self.get_general_stats()

        print("\n" + "=" * 80)
        print("📊 ЗАГАЛЬНА СТАТИСТИКА")
        print("=" * 80)
        print(f"Всього оброблено чатів: {stats['total']}")
        print(f"✅ Пройшли валідацію: {stats['passed']}")
        print(f"❌ Відхилено: {stats['failed']}")
        print(f"📈 Pass rate: {stats['pass_rate']}")
        print(f"🕐 За останні 24 години: {stats['recent_24h']} чатів")

        if stats['categories']:
            print("\n📂 Розподіл по категоріях (PASS):")
            for category, count in stats['categories']:
                percentage = count / stats['passed'] * 100 if stats['passed'] > 0 else 0
                print(f"   {category}: {count} чатів ({percentage:.1f}%)")

        if stats['owners']:
            print("\n👤 Розподіл по власникам (PASS):")
            for owner, count in stats['owners']:
                percentage = count / stats['passed'] * 100 if stats['passed'] > 0 else 0
                print(f"   {owner}: {count} чатів ({percentage:.1f}%)")

    def print_rate_limit_status(self):
        """Вивести статус rate limiter"""
        status = self.get_rate_limit_status()

        print("\n" + "=" * 80)
        print("⏱️ СТАТУС RATE LIMITER")
        print("=" * 80)
        print(f"Поточне вікно: {status['current_window']}")
        print(f"Оброблено в цю годину: {status['current_count']}/{status['max_per_hour']}")
        print(f"Залишилось в цю годину: {status['remaining']}")

        if status['remaining'] == 0:
            print("\n⚠️ ЛІМІТ ДОСЯГНУТО! Очікування наступного вікна...")
        else:
            percentage = status['current_count'] / status['max_per_hour'] * 100
            print(f"Використано: {percentage:.1f}%")

        if status['recent_windows']:
            print("\n📅 Останні 5 годинних вікон:")
            for window, count, last_update in status['recent_windows']:
                dt = datetime.fromisoformat(window)
                print(f"   {dt.strftime('%Y-%m-%d %H:00')}: {count} чатів (оновлено: {last_update})")

    def print_batch_status(self):
        """Вивести статус поточного батчу"""
        status = self.get_batch_status()

        print("\n" + "=" * 80)
        print("📦 СТАТУС ПОТОЧНОГО БАТЧУ")
        print("=" * 80)
        print(f"Номер батчу: {status['current_batch_number']}")
        print(f"Чатів в батчі: {status['chats_in_batch']}/{status['batch_size']}")
        print(f"Батч готовий: {'✅ ТАК' if status['batch_ready'] else '❌ НІ'}")

        if status['chats']:
            print(f"\nЧати в поточному батчі:")
            for i, url in enumerate(status['chats'], 1):
                print(f"   {i}. {url}")
        else:
            print("\nБатч порожній")

    def print_recent_chats(self, limit: int = 10):
        """Вивести останні оброблені чати"""
        chats = self.get_recent_chats(limit)

        print("\n" + "=" * 80)
        print(f"🕐 ОСТАННІ {limit} ОБРОБЛЕНИХ ЧАТІВ")
        print("=" * 80)

        if not chats:
            print("Немає оброблених чатів")
            return

        for i, chat in enumerate(chats, 1):
            status_icon = "✅" if chat['validation_result'] == "PASS" else "❌"
            dt = datetime.fromisoformat(chat['processed_at'])
            time_str = dt.strftime('%Y-%m-%d %H:%M')

            print(f"\n{i}. {status_icon} {chat['url']}")
            print(f"   Час: {time_str}")
            print(f"   Категорія: {chat['category']}")

            if chat['validation_result'] == "PASS":
                print(f"   Власник: {chat['owner']}")
            else:
                print(f"   Причина відхилення: {chat['rejection_reason']}")

    def print_failed_chats(self, limit: int = 20):
        """Вивести відхилені чати"""
        chats = self.get_failed_chats(limit)

        print("\n" + "=" * 80)
        print(f"❌ ОСТАННІ {limit} ВІДХИЛЕНИХ ЧАТІВ")
        print("=" * 80)

        if not chats:
            print("Немає відхилених чатів")
            return

        for i, chat in enumerate(chats, 1):
            dt = datetime.fromisoformat(chat['processed_at'])
            time_str = dt.strftime('%Y-%m-%d %H:%M')

            print(f"\n{i}. {chat['url']}")
            print(f"   Час: {time_str}")
            print(f"   Категорія: {chat['category']}")
            print(f"   Причина: {chat['rejection_reason']}")


def main():
    """Main CLI interface"""
    inspector = StateInspector()

    # Parse command line arguments
    if len(sys.argv) == 1:
        # Default: загальна статистика
        inspector.print_general_stats()
        inspector.print_rate_limit_status()
        inspector.print_batch_status()

    elif '--detailed' in sys.argv:
        # Детальна інформація
        inspector.print_general_stats()
        inspector.print_rate_limit_status()
        inspector.print_batch_status()
        inspector.print_recent_chats(limit=20)

    elif '--rate-limit' in sys.argv:
        # Тільки rate limiter
        inspector.print_rate_limit_status()

    elif '--batch' in sys.argv:
        # Тільки статус батчу
        inspector.print_batch_status()

    elif '--recent' in sys.argv:
        # Останні N чатів
        try:
            idx = sys.argv.index('--recent')
            limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 10
            inspector.print_recent_chats(limit=limit)
        except (ValueError, IndexError):
            print("❌ Використання: --recent <кількість>")
            sys.exit(1)

    elif '--failed' in sys.argv:
        # Відхилені чати
        try:
            idx = sys.argv.index('--failed')
            limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 20
            inspector.print_failed_chats(limit=limit)
        except (ValueError, IndexError):
            print("❌ Використання: --failed <кількість>")
            sys.exit(1)

    elif '--help' in sys.argv or '-h' in sys.argv:
        # Допомога
        print("\n📖 STATE INSPECTOR - Інспектор стану ChatsSpider")
        print("\nВикористання:")
        print("  python utils/inspect_state.py                 # Загальна статистика")
        print("  python utils/inspect_state.py --detailed      # Детальна інформація")
        print("  python utils/inspect_state.py --rate-limit    # Стан rate limiter")
        print("  python utils/inspect_state.py --batch         # Статус поточного батчу")
        print("  python utils/inspect_state.py --recent 10     # Останні 10 чатів")
        print("  python utils/inspect_state.py --failed 20     # Останні 20 відхилених")
        print("  python utils/inspect_state.py --help          # Ця допомога")
        print()

    else:
        print("❌ Невідома команда. Використайте --help для допомоги")
        sys.exit(1)

    print("\n" + "=" * 80)
    print()


if __name__ == "__main__":
    main()
