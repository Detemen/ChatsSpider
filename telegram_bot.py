# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH   = Path("output/spider.db")
SUBS_FILE = Path("output/subscribers.json")

# Якщо БД не оновлювалась довше цього — вважаємо спайдер завис
STALE_THRESHOLD_SEC = 15 * 60  # 15 хвилин
CHECK_INTERVAL_SEC  = 5 * 60   # перевіряємо кожні 5 хвилин

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("aiogram").setLevel(logging.WARNING)

router = Router()

# ── Стан алертів (in-memory) ─────────────────────────────────────────────────
_alert_state = {
    "stale_notified": False,   # вже відправили «спайдер завис»
}


# ── Subscribers ───────────────────────────────────────────────────────────────

def load_subscribers() -> set:
    if SUBS_FILE.exists():
        try:
            return set(json.loads(SUBS_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_subscribers(subs: set):
    SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBS_FILE.write_text(json.dumps(list(subs)))


def add_subscriber(chat_id: int):
    subs = load_subscribers()
    subs.add(chat_id)
    save_subscribers(subs)


def remove_subscriber(chat_id: int):
    subs = load_subscribers()
    subs.discard(chat_id)
    save_subscribers(subs)


# ── DB helpers ────────────────────────────────────────────────────────────────

def db_query(sql: str, params: tuple = ()) -> list:
    if not DB_PATH.exists():
        return []
    con = sqlite3.connect(str(DB_PATH))
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def get_last_seen_ts() -> int | None:
    row = db_query("SELECT MAX(last_seen_ts) FROM channels")
    return row[0][0] if row and row[0][0] else None


def get_stats() -> dict:
    channels = db_query("SELECT COUNT(*) FROM channels")[0][0]
    chats    = db_query("SELECT COUNT(*) FROM chats")[0][0]

    day_ago = int(datetime.now(timezone.utc).timestamp()) - 86400
    new_ch  = db_query("SELECT COUNT(*) FROM channels WHERE first_seen_ts > ?", (day_ago,))[0][0]
    new_ct  = db_query("SELECT COUNT(*) FROM chats WHERE first_seen_ts > ?", (day_ago,))[0][0]

    last_ts  = get_last_seen_ts()
    last_str = datetime.fromtimestamp(last_ts).strftime("%d.%m %H:%M") if last_ts else "—"

    staleness = int(datetime.now(timezone.utc).timestamp()) - last_ts if last_ts else None
    stale = staleness is not None and staleness > STALE_THRESHOLD_SEC

    return {
        "channels": channels, "chats": chats,
        "new_channels": new_ch, "new_chats": new_ct,
        "last_update": last_str, "stale": stale,
        "staleness_min": staleness // 60 if staleness else 0,
    }


def get_recent(table: str, limit: int = 10) -> list:
    if table == "channels":
        return db_query(
            "SELECT username, title FROM channels ORDER BY last_seen_ts DESC LIMIT ?", (limit,)
        )
    return db_query(
        "SELECT username, title, channel_username FROM chats ORDER BY last_seen_ts DESC LIMIT ?",
        (limit,)
    )


def get_category_stats() -> list:
    try:
        sys.path.insert(0, str(Path(__file__).parent / "TelegramAnalysis"))
        from categories_config import find_best_category_by_keywords
    except ImportError:
        return []
    rows = db_query("SELECT title, about FROM chats WHERE about IS NOT NULL AND about != ''")
    counts: dict = {}
    for title, about in rows:
        text = f"{title or ''} {about or ''}".lower()
        cat, _, _ = find_best_category_by_keywords(text)
        counts[cat] = counts.get(cat, 0) + 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)


# ── Keyboards ─────────────────────────────────────────────────────────────────

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика",  callback_data="stats"),
            InlineKeyboardButton(text="📡 Канали",      callback_data="channels"),
        ],
        [
            InlineKeyboardButton(text="💬 Чати",        callback_data="chats"),
            InlineKeyboardButton(text="🏷 Категорії",   callback_data="categories"),
        ],
        [
            InlineKeyboardButton(text="🔔 Сповіщення вкл/викл", callback_data="toggle_alerts"),
        ],
    ])


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.message(Command("start", "help"))
async def cmd_start(message: Message):
    add_subscriber(message.chat.id)
    await message.answer(
        "👋 <b>ChatsSpider Monitor</b>\n\n"
        "Моніторинг Telegram-спайдера в реальному часі.\n"
        "🔔 Сповіщення про проблеми з сесією <b>увімкнені</b>.\n\n"
        "Обери дію:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    remove_subscriber(message.chat.id)
    await message.answer("🔕 Сповіщення вимкнені. Надішли /start щоб увімкнути знову.")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await send_stats(message)

@router.message(Command("channels"))
async def cmd_channels(message: Message):
    await send_channels(message)

@router.message(Command("chats"))
async def cmd_chats(message: Message):
    await send_chats(message)

@router.message(Command("categories"))
async def cmd_categories(message: Message):
    await send_categories(message)


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "stats")
async def cb_stats(call: CallbackQuery):
    await call.answer()
    await send_stats(call.message)

@router.callback_query(lambda c: c.data == "channels")
async def cb_channels(call: CallbackQuery):
    await call.answer()
    await send_channels(call.message)

@router.callback_query(lambda c: c.data == "chats")
async def cb_chats(call: CallbackQuery):
    await call.answer()
    await send_chats(call.message)

@router.callback_query(lambda c: c.data == "categories")
async def cb_categories(call: CallbackQuery):
    await call.answer()
    await send_categories(call.message)

@router.callback_query(lambda c: c.data == "toggle_alerts")
async def cb_toggle(call: CallbackQuery):
    await call.answer()
    subs = load_subscribers()
    if call.message.chat.id in subs:
        remove_subscriber(call.message.chat.id)
        await call.message.answer("🔕 Сповіщення вимкнені. /start — увімкнути.")
    else:
        add_subscriber(call.message.chat.id)
        await call.message.answer("🔔 Сповіщення увімкнені.")


# ── Senders ───────────────────────────────────────────────────────────────────

async def send_stats(target: Message):
    s = get_stats()
    stale_warn = f"\n\n⚠️ <b>Спайдер не оновлює БД вже {s['staleness_min']} хв!</b>" if s["stale"] else ""
    text = (
        "📊 <b>Статистика бази даних</b>\n\n"
        f"📡 Канали:  <b>{s['channels']:,}</b>  <i>(+{s['new_channels']} за добу)</i>\n"
        f"💬 Чати:    <b>{s['chats']:,}</b>  <i>(+{s['new_chats']} за добу)</i>\n\n"
        f"🕐 Останнє оновлення: <b>{s['last_update']}</b>"
        f"{stale_warn}"
    )
    await target.answer(text, reply_markup=main_keyboard(), parse_mode="HTML")


async def send_channels(target: Message):
    rows = get_recent("channels", 15)
    if not rows:
        await target.answer("База каналів порожня.", reply_markup=main_keyboard())
        return
    lines = [f"📡 <b>Останні {len(rows)} каналів</b>\n"]
    for username, title in rows:
        lines.append(f"• <a href='https://t.me/{username}'>{title or username}</a>")
    await target.answer(
        "\n".join(lines), reply_markup=main_keyboard(),
        parse_mode="HTML", disable_web_page_preview=True,
    )


async def send_chats(target: Message):
    rows = get_recent("chats", 15)
    if not rows:
        await target.answer("База чатів порожня.", reply_markup=main_keyboard())
        return
    lines = [f"💬 <b>Останні {len(rows)} чатів</b>\n"]
    for username, title, src in rows:
        src_str = f" <i>(з @{src})</i>" if src else ""
        lines.append(f"• <a href='https://t.me/{username}'>{title or username}</a>{src_str}")
    await target.answer(
        "\n".join(lines), reply_markup=main_keyboard(),
        parse_mode="HTML", disable_web_page_preview=True,
    )


async def send_categories(target: Message):
    cats = get_category_stats()
    if not cats:
        await target.answer(
            "🏷 Немає чатів з описом для класифікації.",
            reply_markup=main_keyboard(),
        )
        return
    total = sum(c for _, c in cats)
    lines = [f"🏷 <b>Розподіл чатів по категоріям</b>  (всього: {total})\n"]
    for name, count in cats:
        pct = count / total * 100
        lines.append(f"• {name}: <b>{count}</b> ({pct:.0f}%)")
    await target.answer("\n".join(lines), reply_markup=main_keyboard(), parse_mode="HTML")


# ── Monitor task ──────────────────────────────────────────────────────────────

async def monitor_loop(bot: Bot):
    """Фоновий цикл: перевіряє стан спайдера кожні 5 хвилин."""
    await asyncio.sleep(30)  # дати час спайдеру стартувати після перезапуску

    while True:
        try:
            last_ts = get_last_seen_ts()
            now     = int(datetime.now(timezone.utc).timestamp())
            staleness = now - last_ts if last_ts else None

            is_stale = staleness is not None and staleness > STALE_THRESHOLD_SEC

            subs = load_subscribers()
            if not subs:
                pass

            elif is_stale and not _alert_state["stale_notified"]:
                # Перший раз помітили що спайдер завис
                _alert_state["stale_notified"] = True
                mins = staleness // 60
                text = (
                    "🚨 <b>Спайдер зупинився!</b>\n\n"
                    f"БД не оновлювалась <b>{mins} хвилин</b>.\n"
                    "Можливі причини:\n"
                    "• Сесія @mt_offer розлогінена / заблокована\n"
                    "• FloodWait без відновлення\n"
                    "• Контейнер впав\n\n"
                    "Перевір: <code>docker logs chatsspider --tail 30</code>"
                )
                for chat_id in subs:
                    try:
                        await bot.send_message(chat_id, text, parse_mode="HTML")
                    except Exception as e:
                        logging.warning(f"Alert send failed to {chat_id}: {e}")

            elif not is_stale and _alert_state["stale_notified"]:
                # Спайдер відновився
                _alert_state["stale_notified"] = False
                text = "✅ <b>Спайдер відновив роботу!</b>\nБД знову оновлюється."
                for chat_id in subs:
                    try:
                        await bot.send_message(chat_id, text, parse_mode="HTML")
                    except Exception as e:
                        logging.warning(f"Recovery send failed to {chat_id}: {e}")

        except Exception as e:
            logging.error(f"monitor_loop error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SEC)


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не знайдено у .env")

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher()
    dp.include_router(router)

    asyncio.create_task(monitor_loop(bot))

    logging.info("Бот запущено (моніторинг сесії активний)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
