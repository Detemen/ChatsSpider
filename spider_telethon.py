# spider_telethon.py
# -*- coding: utf-8 -*-
"""
Мульти-аккаунтный «паук» на Telethon с SQLite.

Фичи:
- .session из ./accs (1 прокси = 1 аккаунт из proxy.txt)
- Креды берём из config_accounts.json (per-file или "default") ИЛИ .env (API_ID, API_HASH)
- Каналы-доноры и обсуждения (только публичные username) пишем в SQLite (output/spider.db)
  * channels(username, title, about, ...)
  * chats(username, title, about, channel_username, ...)
- Похожие каналы: GetChannelRecommendationsRequest
- Обсуждения: GetFullChannelRequest -> linked_chat_id -> entity.username (только публичные)
- Игнорируем internal_chat_id (никаких приватных ID в БД)
- Консоль: одна цветная таблица
    session.session | донор-каналы | найдено за сессию | всего чатов в БД | статус
- Явные логи о вылетах/лимитах (FloodWait, неавторизованные, сетевые)
"""

import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from colorama import init as colorama_init, Fore, Style

from telethon import TelegramClient, errors
from telethon.errors.rpcerrorlist import FloodWaitError
from telethon.tl.functions.channels import GetFullChannelRequest, GetChannelRecommendationsRequest
from telethon.tl.types import InputChannel, PeerChannel, Channel

from database import Database

# ------------------ ПАРАМЕТРЫ ------------------
ACCS_DIR = Path("accs")
PROXY_FILE = Path("proxy.txt")
CHANNELS_BASE = Path("channelsdb.txt")
CONFIG_ACCOUNTS = Path("config_accounts.json")
OUT_DIR = Path("output")

CONCURRENT_ACCOUNTS = 20
STATUS_REFRESH_SEC = 2.0

# ------------------ ЛОГИ ------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("telethon.network").setLevel(logging.ERROR)
colorama_init(autoreset=True)

# ── АДАПТИВНІ ЗАТРИМКИ ────────────────────────────────────────────────────────

class AdaptiveDelays:
    """
    ×2 при FloodWait, ×0.8 після 24г без банів — шукає мінімально допустиму затримку.
    Стан зберігається в output/delay_state.json (переживає перезапуск контейнера).
    """
    _STATE = Path("output/delay_state.json")
    FLOOR = (3.0, 6.0, 60, 120)           # мінімально можливі затримки
    CEIL  = (120.0, 240.0, 3600, 7200)    # максимально можливі затримки
    INIT  = (15.0, 30.0, 300, 600)        # стартові значення
    STABLE_SEC = 86400                     # 24 год без бану → зменшуємо
    BACKOFF    = 2.0                       # множник при бані
    RECOVERY   = 0.80                      # множник відновлення

    def __init__(self):
        self.delay_min, self.delay_max, self.pass_min, self.pass_max = self.INIT
        self.last_floodwait_ts: float | None = None
        self.stable_since_ts:   float | None = None
        self.total_bans: int = 0
        self._load()

    def _load(self):
        if self._STATE.exists():
            try:
                d = json.loads(self._STATE.read_text())
                self.delay_min = float(d.get("delay_min", self.INIT[0]))
                self.delay_max = float(d.get("delay_max", self.INIT[1]))
                self.pass_min  = int(d.get("pass_min",   self.INIT[2]))
                self.pass_max  = int(d.get("pass_max",   self.INIT[3]))
                self.last_floodwait_ts = d.get("last_floodwait_ts")
                self.stable_since_ts   = d.get("stable_since_ts")
                self.total_bans = int(d.get("total_bans", 0))
                logging.info(
                    f"[Delays] delay={self.delay_min:.0f}-{self.delay_max:.0f}s "
                    f"pass={self.pass_min//60}-{self.pass_max//60}min  банів={self.total_bans}"
                )
            except Exception as e:
                logging.warning(f"[Delays] не вдалось зчитати стан: {e}")

    def save(self):
        self._STATE.parent.mkdir(exist_ok=True)
        self._STATE.write_text(json.dumps({
            "delay_min": self.delay_min,
            "delay_max": self.delay_max,
            "pass_min":  self.pass_min,
            "pass_max":  self.pass_max,
            "last_floodwait_ts": self.last_floodwait_ts,
            "stable_since_ts":   self.stable_since_ts,
            "total_bans": self.total_bans,
        }, indent=2))

    def on_floodwait(self):
        """Викликати коли отримали FloodWait (не під час очікування, а в момент отримання)."""
        d0 = (self.delay_min, self.delay_max, self.pass_min, self.pass_max)
        self.delay_min = min(self.delay_min * self.BACKOFF, self.CEIL[0])
        self.delay_max = min(self.delay_max * self.BACKOFF, self.CEIL[1])
        self.pass_min  = min(int(self.pass_min  * self.BACKOFF), self.CEIL[2])
        self.pass_max  = min(int(self.pass_max  * self.BACKOFF), self.CEIL[3])
        self.last_floodwait_ts = time.time()
        self.stable_since_ts   = None
        self.total_bans += 1
        self.save()
        logging.warning(
            f"[Delays] FloodWait #{self.total_bans}! "
            f"delay {d0[0]:.0f}-{d0[1]:.0f}→{self.delay_min:.0f}-{self.delay_max:.0f}s  "
            f"pass {d0[2]//60}-{d0[3]//60}→{self.pass_min//60}-{self.pass_max//60}min"
        )

    def on_success(self):
        """Викликати після успішної обробки каналу."""
        now = time.time()
        if self.stable_since_ts is None:
            self.stable_since_ts = now
            self.save()
            return
        if now - self.stable_since_ts < self.STABLE_SEC:
            return
        d0 = (self.delay_min, self.delay_max, self.pass_min, self.pass_max)
        self.delay_min = max(self.delay_min * self.RECOVERY, self.FLOOR[0])
        self.delay_max = max(self.delay_max * self.RECOVERY, self.FLOOR[1])
        self.pass_min  = max(int(self.pass_min  * self.RECOVERY), self.FLOOR[2])
        self.pass_max  = max(int(self.pass_max  * self.RECOVERY), self.FLOOR[3])
        self.stable_since_ts = now
        self.save()
        logging.info(
            f"[Delays] 24г стабільності → зменшуємо: "
            f"delay {d0[0]:.0f}-{d0[1]:.0f}→{self.delay_min:.0f}-{self.delay_max:.0f}s  "
            f"pass {d0[2]//60}-{d0[3]//60}→{self.pass_min//60}-{self.pass_max//60}min"
        )

    def status_str(self) -> str:
        stable_h = (time.time() - self.stable_since_ts) / 3600 if self.stable_since_ts else 0
        return (
            f"delay={self.delay_min:.0f}-{self.delay_max:.0f}s  "
            f"pass={self.pass_min//60}-{self.pass_max//60}min  "
            f"стабільно={stable_h:.1f}г  банів={self.total_bans}"
        )


# ------------------ ГЛОБАЛЬНОЕ СОСТОЯНИЕ ------------------
DB = Database()
DELAYS = AdaptiveDelays()
STATUS: Dict[str, Dict] = {}     # session_name -> {assigned, found_session, total_chats, last_error, running}
STATUS_LOCK = asyncio.Lock()

# ------------------ УТИЛИТЫ ------------------
def ensure_out_dir():
    OUT_DIR.mkdir(exist_ok=True)

def load_text_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [x.strip() for x in path.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]

def normalize_username(s: str) -> str:
    s = s.strip()
    s = re.sub(r'^(https?://)?(www\.)?t\.me/', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(https?://)?(www\.)?telegram\.me/', '', s, flags=re.IGNORECASE)
    return s.lstrip('@')

def parse_proxy_line(line: str):
    """
    Поддержка:
      ip:port
      ip:port:user:pass
      socks5://ip:port
      http://user:pass@host:port
    Возвращает tuple для Telethon: (proto, host, port, rdns, user, pass) или None
    """
    line = line.strip()
    if not line:
        return None
    m = re.match(
        r'^(?:(http|socks5|socks5h)://)?'
        r'(?:(?P<user>[^:@/]+):(?P<pwd>[^@/]+)@)?'
        r'(?P<host>[^:/]+):(?P<port>\d+)$', line
    )
    if m:
        schema = (m.group(1) or 'socks5').lower()
        host = m.group('host'); port = int(m.group('port'))
        user = m.group('user'); pwd = m.group('pwd')
        rdns = True
        if "http" in schema:
            return ("http", host, port, False, user, pwd)
        return ("socks5", host, port, rdns, user, pwd)
    parts = line.split(":")
    if len(parts) == 2:
        host, port = parts
        return ("socks5", host, int(port), True, None, None)
    if len(parts) == 4:
        host, port, user, pwd = parts
        return ("socks5", host, int(port), True, user, pwd)
    return None

def load_proxies() -> List[Tuple]:
    return [p for p in (parse_proxy_line(x) for x in load_text_lines(PROXY_FILE)) if p]

def load_sessions() -> List[Path]:
    if not ACCS_DIR.exists():
        logging.error("Папка accs/ не найдена")
        return []
    sessions = sorted([p for p in ACCS_DIR.iterdir() if p.is_file() and p.suffix == ".session"])
    if not sessions:
        logging.error("В accs/ нет .session файлов")
    return sessions

def load_api_from_config(session_name: str) -> Optional[Tuple[int, str]]:
    """
    Сначала ищем точное имя '<file>.session', затем 'default'
    """
    if CONFIG_ACCOUNTS.exists():
        try:
            cfg = json.loads(CONFIG_ACCOUNTS.read_text(encoding="utf-8"))
            e = cfg.get(session_name) or cfg.get("default")
            if e and "api_id" in e and "api_hash" in e:
                return int(e["api_id"]), str(e["api_hash"])
        except Exception as e:
            logging.warning(f"Ошибка чтения {CONFIG_ACCOUNTS}: {e}")
    return None

def load_api_from_env() -> Optional[Tuple[int, str]]:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    if api_id and api_hash:
        try:
            return int(api_id), str(api_hash)
        except Exception:
            pass
    return None

def resolve_api_creds(session_file: Path) -> Optional[Tuple[int, str]]:
    c = load_api_from_config(session_file.name)
    if c:
        return c
    e = load_api_from_env()
    if e:
        return e
    return None

# ------------------ КРАСИВЫЙ ВЫВОД ------------------
def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

async def status_printer():
    """
    Периодически печатает сводную таблицу.
    """
    while True:
        await asyncio.sleep(STATUS_REFRESH_SEC)
        async with STATUS_LOCK:
            data = list(STATUS.items())
        total_chats = DB.count_chats()
        clear_console()
        print(Fore.CYAN + "Telegram Spider — статус аккаунтов\n" + Style.RESET_ALL)
        print(f"{'session':30} | {'доноры':6} | {'найдено/сес':12} | {'всего чатов в БД':16} | статус")
        print("-"*90)
        for sess, st in data:
            running = st.get("running", False)
            last_error = st.get("last_error")
            color = Fore.GREEN if running and not last_error else (Fore.YELLOW if running and last_error else Fore.RED)
            donors = st.get("assigned", 0)
            found = st.get("found_session", 0)
            status_text = "OK"
            if last_error:
                status_text = f"⚠ {last_error}"
            elif not running:
                status_text = "OFF"
            print(color + f"{sess:30} | {donors:6d} | {found:12d} | {total_chats:16d} | {status_text}" + Style.RESET_ALL)
        print(Fore.CYAN + f"⚙  {DELAYS.status_str()}" + Style.RESET_ALL)
        print(Fore.WHITE + time.strftime("%Y-%m-%d %H:%M:%S") + Style.RESET_ALL)

# ------------------ ПОМОЩНИКИ ДЛЯ TELETHON ------------------
async def get_title_about(client: TelegramClient, entity) -> Tuple[Optional[str], Optional[str]]:
    """
    Возвращает (title, about) для канала/супергруппы.
    title — из entity.title, about — из ChannelFull.about (через GetFullChannelRequest).
    """
    title = getattr(entity, "title", None)
    about = None
    try:
        if hasattr(entity, "id") and hasattr(entity, "access_hash"):
            full = await client(GetFullChannelRequest(channel=InputChannel(entity.id, entity.access_hash)))
            if getattr(full, "full_chat", None) and getattr(full.full_chat, "about", None):
                about = full.full_chat.about
    except FloodWaitError as e:
        DELAYS.on_floodwait()
        await asyncio.sleep(max(0, int(e.seconds)))
    except Exception:
        pass
    return title, about

# ------------------ ВОРКЕР АККАУНТА ------------------
async def account_worker(slot_index: int,
                         session_path: Path,
                         api_id: int,
                         api_hash: str,
                         proxy_tuple: Optional[Tuple],
                         assigned_channels: List[str]):
    """
    Основной цикл для одного .session
    """
    name = session_path.name
    session_found_chats: set = set()  # для счётчика "найдено за сессию"
    channel_fails: dict = {}   # {channel: consecutive_fail_count}
    consec_conn_errs = [0]     # mutable box — кількість поспіль ConnectionError
    async with STATUS_LOCK:
        STATUS[name] = {
            "assigned": len(assigned_channels),
            "found_session": 0,
            "last_error": None,
            "running": False,
        }

    client = TelegramClient(str(session_path), api_id, api_hash, proxy=proxy_tuple)

    # подключение
    try:
        await client.connect()
        if not await client.is_user_authorized():
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = "не авторизован"
                STATUS[name]["running"] = False
            logging.error(f"[{name}] Сессия не авторизована. Пропуск.")
            try:
                await client.disconnect()
            except Exception:
                pass
            return
        async with STATUS_LOCK:
            STATUS[name]["running"] = True
            STATUS[name]["last_error"] = None
    except Exception as e:
        async with STATUS_LOCK:
            STATUS[name]["last_error"] = f"connect: {type(e).__name__}"
            STATUS[name]["running"] = False
        logging.error(f"[{name}] Не удалось подключиться: {e}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return

    async def bump_found(chat_username: str):
        # Учитываем "найдено за сессию" только 1 раз на конкретный username
        nonlocal session_found_chats
        if chat_username not in session_found_chats:
            session_found_chats.add(chat_username)
            async with STATUS_LOCK:
                STATUS[name]["found_session"] = len(session_found_chats)

    async def process_channel(target_raw: str):
        target = normalize_username(target_raw)
        if not target:
            return
        # 1) entity канала-донор
        try:
            entity = await client.get_entity(target)
        except FloodWaitError as e:
            secs = max(0, int(e.seconds))
            DELAYS.on_floodwait()
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = f"FloodWait get_entity {secs}s"
            logging.warning(f"[{name}] FloodWait get_entity({target}) — ждём {secs}s")
            await asyncio.sleep(secs)
            return
        except Exception as e:
            err_type = type(e).__name__
            channel_fails[target] = channel_fails.get(target, 0) + 1
            fails = channel_fails[target]
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = f"get_entity: {err_type} (ch_fail#{fails})"
            logging.debug(f"[{name}] get_entity({target}) error #{fails}: {e}")
            if err_type == "ConnectionError":
                consec_conn_errs[0] += 1
                if consec_conn_errs[0] >= 5:
                    logging.warning(f"[{name}] {consec_conn_errs[0]} поспіль ConnectionError — перепідключення")
                    async with STATUS_LOCK:
                        STATUS[name]["last_error"] = "reconnecting..."
                    try:
                        await client.disconnect()
                        await asyncio.sleep(15)
                        await client.connect()
                        consec_conn_errs[0] = 0
                        logging.info(f"[{name}] Перепідключено успішно")
                    except Exception as re:
                        logging.error(f"[{name}] Перепідключення не вдалось: {re}")
            else:
                consec_conn_errs[0] = 0
            return

        if not isinstance(entity, Channel):
            return

        # 2) сохраняем ДОНАР канал (только публичный username)
        donor_username = getattr(entity, "username", None)
        if donor_username:
            ch_title, ch_about = await get_title_about(client, entity)
            DB.upsert_channel(donor_username, ch_title, ch_about, name)

        # 3) обсуждения (только публичные username)
        try:
            if hasattr(entity, "access_hash"):
                full = await client(GetFullChannelRequest(channel=InputChannel(entity.id, entity.access_hash)))
                linked_id = None
                try:
                    if getattr(full, "full_chat", None) and getattr(full.full_chat, "linked_chat_id", None):
                        linked_id = full.full_chat.linked_chat_id
                    elif getattr(full, "linked_chat_id", None):
                        linked_id = full.linked_chat_id
                except Exception:
                    linked_id = None
                if linked_id:
                    try:
                        peer = PeerChannel(linked_id)
                        d_ent = await client.get_entity(peer)
                        chat_username = getattr(d_ent, "username", None)
                        if chat_username:  # сохраняем только публичные
                            t, a = await get_title_about(client, d_ent)
                            DB.upsert_chat(chat_username, t, a, donor_username, name)
                            await bump_found(chat_username)
                    except FloodWaitError as e:
                        secs = max(0, int(e.seconds))
                        DELAYS.on_floodwait()
                        async with STATUS_LOCK:
                            STATUS[name]["last_error"] = f"FloodWait linked {secs}s"
                        logging.warning(f"[{name}] FloodWait resolve linked_chat — ждём {secs}s")
                        await asyncio.sleep(secs)
                    except Exception as e:
                        logging.debug(f"[{name}] resolve linked_chat_id error: {e}")
        except FloodWaitError as e:
            secs = max(0, int(e.seconds))
            DELAYS.on_floodwait()
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = f"FloodWait full {secs}s"
            logging.warning(f"[{name}] FloodWait GetFullChannelRequest — ждём {secs}s")
            await asyncio.sleep(secs)
        except errors.RPCError as e:
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = f"RPC full: {type(e).__name__}"
            logging.debug(f"[{name}] RPC GetFullChannelRequest: {e}")
        except Exception as e:
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = f"full: {type(e).__name__}"
            logging.debug(f"[{name}] GetFullChannelRequest error: {e}")

        # 4) похожие каналы (только с username)
        try:
            if hasattr(entity, "access_hash"):
                rec = await client(GetChannelRecommendationsRequest(channel=InputChannel(entity.id, entity.access_hash)))
                for ch in getattr(rec, "chats", []) or []:
                    uname = getattr(ch, "username", None)
                    if uname:
                        # метаданные рекомендаций тоже можем подтянуть (минимально: title)
                        DB.upsert_channel(uname, getattr(ch, "title", None), None, name)
        except FloodWaitError as e:
            secs = max(0, int(e.seconds))
            DELAYS.on_floodwait()
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = f"FloodWait rec {secs}s"
            logging.warning(f"[{name}] FloodWait Recommendations — ждём {secs}s")
            await asyncio.sleep(secs)
        except Exception as e:
            # рекомендации могут быть недоступны — не считаем за падение
            logging.debug(f"[{name}] Recommendations error: {e}")

        # успішно — скидаємо лічильники помилок для цього каналу
        consec_conn_errs[0] = 0
        channel_fails.pop(target, None)
        async with STATUS_LOCK:
            STATUS[name]["last_error"] = None
        DELAYS.on_success()

    # --- стартовые каналы ---
    for ch in assigned_channels:
        try:
            await process_channel(ch)
        except Exception as e:
            async with STATUS_LOCK:
                STATUS[name]["last_error"] = f"process: {type(e).__name__}"
            logging.debug(f"[{name}] process_channel error {ch}: {e}")
        await asyncio.sleep(random.uniform(DELAYS.delay_min, DELAYS.delay_max))

    # --- бесконечный цикл собственной базы (каналы мы добавляем в БД; читаем для обработки из таблицы channels) ---
    try:
        while True:
            # берём свежую "волну" каналов-доноров из БД (username != NULL)
            # Можно сделать выборку более умной, но для простоты берём все.
            # Чтобы не молотить повторно слишком часто — маленькая пауза по раундам.
            # (Если захочешь — добавлю флажки "последний обход".)
            batch = DB.get_all_channel_usernames(limit=200)
            random.shuffle(batch)
            skipped = 0
            for target in batch:
                if channel_fails.get(target, 0) >= 3:
                    skipped += 1
                    logging.debug(f"[{name}] skip bad channel {target} (fails={channel_fails[target]})")
                    continue
                try:
                    await process_channel(target)
                except Exception as e:
                    async with STATUS_LOCK:
                        STATUS[name]["last_error"] = f"loop: {type(e).__name__}"
                    logging.debug(f"[{name}] loop error {target}: {e}")
                await asyncio.sleep(random.uniform(DELAYS.delay_min, DELAYS.delay_max))
            if skipped:
                logging.info(f"[{name}] Pass done — skipped {skipped} bad channels, bad_list={len(channel_fails)}")
            # зменшуємо лічильники — канали отримують новий шанс у наступному проході
            for ch in list(channel_fails):
                channel_fails[ch] -= 1
                if channel_fails[ch] <= 0:
                    del channel_fails[ch]
            await asyncio.sleep(random.uniform(DELAYS.pass_min, DELAYS.pass_max))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        async with STATUS_LOCK:
            STATUS[name]["last_error"] = f"fatal: {type(e).__name__}"
        logging.error(f"[{name}] Фатальная ошибка воркера: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        async with STATUS_LOCK:
            STATUS[name]["running"] = False

# ------------------ MAIN ------------------
async def main():
    load_dotenv(override=False)
    ensure_out_dir()

    sessions = load_sessions()
    if not sessions:
        return

    proxies_all = load_proxies()
    proxies_map = [proxies_all[i % max(1, len(proxies_all))] if proxies_all else None for i in range(len(sessions))]

    base_list = load_text_lines(CHANNELS_BASE)
    assigned: List[List[str]] = [[] for _ in sessions]
    if base_list:
        for i, ch in enumerate(base_list):
            assigned[i % len(sessions)].append(ch)
    else:
        logging.warning(f"{CHANNELS_BASE.name} пуст — стартуем сразу с локальной БД.")

    # резолвим креды
    creds = []
    for p in sessions:
        c = resolve_api_creds(p)
        if not c:
            logging.error(f"[{p.name}] Нет api_id/api_hash — добавь в .env (API_ID, API_HASH) или config_accounts.json ('{p.name}' или 'default'). Пропуск.")
            creds.append(None)
        else:
            creds.append(c)

    # подготовим статус
    async with STATUS_LOCK:
        for idx, sess in enumerate(sessions):
            STATUS[sess.name] = {
                "assigned": len(assigned[idx]),
                "found_session": 0,
                "last_error": None,
                "running": False,
            }

    # запускаем принтер статуса
    printer_task = asyncio.create_task(status_printer())

    # запускаем воркеры
    tasks = []
    for idx, sess in enumerate(sessions, start=1):
        if not creds[idx - 1]:
            continue
        api_id, api_hash = creds[idx - 1]
        tasks.append(asyncio.create_task(
            account_worker(
                slot_index=idx,
                session_path=sess,
                api_id=api_id,
                api_hash=api_hash,
                proxy_tuple=proxies_map[idx - 1],
                assigned_channels=assigned[idx - 1],
            )
        ))

    if not tasks:
        logging.error("Нет рабочих задач (все аккаунты без API кредов?). Завершение.")
        printer_task.cancel()
        try:
            await printer_task
        except Exception:
            pass
        return

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Ctrl+C — останавливаю...")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        printer_task.cancel()
        try:
            await printer_task
        except BaseException:
            pass
        DB.close()

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore
        except Exception:
            pass
    asyncio.run(main())
