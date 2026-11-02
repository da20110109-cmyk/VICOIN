"""
VICOIN Telegram-бот
- Меню, команды, ответы
- Кнопка на личный аккаунт (подарки Stars)
- Админ: начисление VIC вручную после подарка
- Ссылка на Mini App

Установка:
  pip install aiogram==3.15.0 python-dotenv

.env:
  BOT_TOKEN=токен_от_BotFather
  ADMIN_IDS=123456789          # твой telegram id (можно несколько через запятую)
  OWNER_USERNAME=vife_kkin # без @ — личный аккаунт для подарков
  MINIAPP_URL=https://da20110109-cmyk.github.io/VICOIN/
"""

import asyncio
import json
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
)
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "vife_kkin").lstrip("@")
MINIAPP_URL = os.getenv(
    "MINIAPP_URL", "https://da20110109-cmyk.github.io/VICOIN/"
).rstrip("/")

DATA_FILE = Path(__file__).with_name("vicoin_data.json")

# ---------- хранилище (простой json) ----------
def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"users": {}, "pending": []}  # pending — заявки на зачисление


def save_data(data):
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ensure_user(data, user):
    uid = str(user.id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "id": user.id,
            "username": user.username or "",
            "name": (user.full_name or "")[:64],
            "vic": 0,
            "note": "",
        }
    else:
        data["users"][uid]["username"] = user.username or data["users"][uid].get(
            "username", ""
        )
        data["users"][uid]["name"] = (user.full_name or data["users"][uid].get("name", ""))[
            :64
        ]
    return data["users"][uid]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- клавиатуры ----------
def main_kb(is_adm: bool = False):
    rows = [
        [KeyboardButton(text="🎮 Играть"), KeyboardButton(text="⭐ Купить VIC")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="🎁 Сделать подарок")],
        [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📞 Поддержка")],
    ]
    if is_adm:
        rows.append([KeyboardButton(text="🛠 Админ")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def pay_inline():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Открыть мой аккаунт (подарок Stars)",
                    url=f"https://t.me/{OWNER_USERNAME}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 Открыть игру",
                    url=MINIAPP_URL if MINIAPP_URL.startswith("http") else f"https://t.me/{OWNER_USERNAME}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Я отправил подарок",
                    callback_data="gift_sent",
                )
            ],
        ]
    )


def support_inline():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Написать владельцу",
                    url=f"https://t.me/{OWNER_USERNAME}",
                )
            ],
            [
                InlineKeyboardButton(text="🎮 Играть", url=MINIAPP_URL),
            ],
        ]
    )


def admin_inline():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Заявки", callback_data="adm_pending"),
                InlineKeyboardButton(text="👥 Игроки", callback_data="adm_users"),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Начислить VIC", callback_data="adm_help_add"
                ),
            ],
        ]
    )


# ---------- тексты ----------
WELCOME = (
    "👋 <b>Добро пожаловать в VICOIN!</b>\n\n"
    "Это idle-игра: покупай бизнесы, тапай, копи VIC.\n\n"
    "🎮 <b>Играть</b> — открыть Mini App\n"
    "⭐ <b>Купить VIC</b> — пакеты за Telegram Stars (подарок)\n"
    "🎁 Можно отправить Stars <b>подарком</b> на аккаунт владельца — "
    "после проверки VIC начислят на баланс.\n\n"
    "Жми кнопки меню ниже 👇"
)

HELP = (
    "ℹ️ <b>Помощь VICOIN</b>\n\n"
    "<b>Команды:</b>\n"
    "/start — главное меню\n"
    "/game — ссылка на игру\n"
    "/pay — как купить VIC за Stars\n"
    "/profile — ваш профиль\n"
    "/help — эта справка\n"
    "/support — связь с владельцем\n\n"
    "<b>Покупка за Stars:</b>\n"
    "1. Выбери пакет в /pay или в игре\n"
    "2. Открой аккаунт владельца и отправь <b>подарок Stars</b>\n"
    "3. В боте нажми «Я отправил подарок»\n"
    "4. Владелец проверит и начислит VIC\n\n"
    f"Аккаунт для подарков: @{OWNER_USERNAME}\n"
    f"Игра: {MINIAPP_URL}"
)

PAY_TEXT = (
    "⭐ <b>Пакеты VIC за Telegram Stars</b>\n\n"
    "• 25 ★ → 50 000 VIC\n"
    "• 99 ★ → 250 000 VIC\n"
    "• 299 ★ → 1 000 000 VIC\n"
    "• 999 ★ → 5 000 000 VIC\n\n"
    "• 15 ★ → пропуск 1 ч\n"
    "• 49 ★ → пропуск 5 ч\n"
    "• 89 ★ → пропуск 10 ч\n\n"
    f"1️⃣ Открой аккаунт: @{OWNER_USERNAME}\n"
    "2️⃣ Отправь <b>подарок</b> на нужное число Stars\n"
    "3️⃣ Вернись и нажми «Я отправил подарок»\n"
    "4️⃣ Напиши в заявке: какой пакет и свой ник в игре\n\n"
    "После проверки VIC начислят вручную."
)

# ---------- бот ----------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    data = load_data()
    ensure_user(data, message.from_user)
    save_data(data)

    payload = (command.args or "").strip()
    extra = ""
    if payload.startswith("stars_"):
        extra = (
            f"\n\n⭐ Ты пришёл за пакетом <code>{payload}</code>.\n"
            "Жми «Купить VIC» или кнопку ниже."
        )

    await message.answer(
        WELCOME + extra,
        parse_mode=ParseMode.HTML,
        reply_markup=main_kb(is_admin(message.from_user.id)),
    )
    if payload.startswith("stars_"):
        await message.answer(
            PAY_TEXT, parse_mode=ParseMode.HTML, reply_markup=pay_inline()
        )


@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    await message.answer(HELP, parse_mode=ParseMode.HTML, reply_markup=support_inline())


@dp.message(Command("game"))
@dp.message(F.text == "🎮 Играть")
async def cmd_game(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть VICOIN", url=MINIAPP_URL)],
        ]
    )
    await message.answer(
        f"🎮 <b>Mini App VICOIN</b>\n\n{MINIAPP_URL}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@dp.message(Command("pay"))
@dp.message(F.text.in_({"⭐ Купить VIC", "🎁 Сделать подарок"}))
async def cmd_pay(message: Message):
    await message.answer(PAY_TEXT, parse_mode=ParseMode.HTML, reply_markup=pay_inline())


@dp.message(Command("profile"))
@dp.message(F.text == "👤 Мой профиль")
async def cmd_profile(message: Message):
    data = load_data()
    u = ensure_user(data, message.from_user)
    save_data(data)
    uname = f"@{u['username']}" if u.get("username") else "—"
    await message.answer(
        "👤 <b>Профиль</b>\n\n"
        f"ID: <code>{u['id']}</code>\n"
        f"Имя: {u.get('name') or '—'}\n"
        f"Username: {uname}\n"
        f"VIC (учёт бота): <b>{u.get('vic', 0):,}</b>\n\n"
        "<i>Баланс в Mini App хранится на устройстве. "
        "После подарка владелец начислит VIC в учёте бота и/или подскажет, что сделать в игре.</i>",
        parse_mode=ParseMode.HTML,
    )


@dp.message(Command("support"))
@dp.message(F.text == "📞 Поддержка")
async def cmd_support(message: Message):
    await message.answer(
        "📞 <b>Поддержка</b>\n\n"
        "Вопросы по игре, оплате и начислению — пиши владельцу.\n"
        f"Аккаунт: @{OWNER_USERNAME}",
        parse_mode=ParseMode.HTML,
        reply_markup=support_inline(),
    )


@dp.callback_query(F.data == "gift_sent")
async def cb_gift_sent(call: CallbackQuery):
    data = load_data()
    u = ensure_user(data, call.from_user)
    req = {
        "user_id": call.from_user.id,
        "username": call.from_user.username or "",
        "name": call.from_user.full_name or "",
        "status": "new",
    }
    data.setdefault("pending", []).append(req)
    save_data(data)

    await call.answer("Заявка отправлена")
    await call.message.answer(
        "✅ Заявка принята.\n"
        "Напиши сюда одним сообщением:\n"
        "• какой пакет (например 99★ → 250k VIC)\n"
        "• когда отправил подарок\n\n"
        "Владелец проверит и ответит."
    )

    # уведомить админов
    text = (
        "🔔 <b>Новая заявка на начисление</b>\n"
        f"ID: <code>{call.from_user.id}</code>\n"
        f"Имя: {call.from_user.full_name}\n"
        f"Username: @{call.from_user.username or '—'}\n\n"
        f"Начислить: <code>/addvic {call.from_user.id} 250000</code>"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, parse_mode=ParseMode.HTML)
        except Exception:
            pass


# ---------- админ ----------
@dp.message(F.text == "🛠 Админ")
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\n"
        "Команды:\n"
        "<code>/addvic USER_ID AMOUNT</code> — начислить VIC\n"
        "<code>/setvic USER_ID AMOUNT</code> — установить баланс\n"
        "<code>/find USERNAME_OR_ID</code> — найти игрока\n"
        "<code>/pending</code> — заявки\n"
        "<code>/broadcast текст</code> — рассылка (осторожно)",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_inline(),
    )


@dp.message(Command("addvic"))
async def cmd_addvic(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    parts = (command.args or "").split()
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].lstrip("-").isdigit():
        await message.answer("Формат: <code>/addvic USER_ID AMOUNT</code>", parse_mode=ParseMode.HTML)
        return
    uid, amount = parts[0], int(parts[1])
    data = load_data()
    if uid not in data["users"]:
        data["users"][uid] = {
            "id": int(uid),
            "username": "",
            "name": "",
            "vic": 0,
            "note": "",
        }
    data["users"][uid]["vic"] = int(data["users"][uid].get("vic", 0)) + amount
    save_data(data)
    await message.answer(
        f"✅ Начислено <b>{amount:,}</b> VIC → <code>{uid}</code>\n"
        f"Итого: <b>{data['users'][uid]['vic']:,}</b>",
        parse_mode=ParseMode.HTML,
    )
    try:
        await bot.send_message(
            int(uid),
            f"✅ Вам начислено <b>{amount:,} VIC</b> (учёт бота).\n"
            "Если нужно отразить в Mini App — напишите в поддержку.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


@dp.message(Command("setvic"))
async def cmd_setvic(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    parts = (command.args or "").split()
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].lstrip("-").isdigit():
        await message.answer("Формат: <code>/setvic USER_ID AMOUNT</code>", parse_mode=ParseMode.HTML)
        return
    uid, amount = parts[0], int(parts[1])
    data = load_data()
    if uid not in data["users"]:
        data["users"][uid] = {"id": int(uid), "username": "", "name": "", "vic": 0, "note": ""}
    data["users"][uid]["vic"] = amount
    save_data(data)
    await message.answer(f"Баланс <code>{uid}</code> = <b>{amount:,}</b> VIC", parse_mode=ParseMode.HTML)


@dp.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    q = (command.args or "").strip().lstrip("@").lower()
    if not q:
        await message.answer("Формат: /find username или id")
        return
    data = load_data()
    found = []
    for uid, u in data["users"].items():
        if q == uid or q == (u.get("username") or "").lower() or q in (u.get("name") or "").lower():
            found.append(u)
    if not found:
        await message.answer("Не найдено.")
        return
    lines = []
    for u in found[:20]:
        lines.append(
            f"<code>{u['id']}</code> @{u.get('username') or '—'} — {u.get('vic', 0):,} VIC"
        )
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@dp.message(Command("pending"))
@dp.callback_query(F.data == "adm_pending")
async def cmd_pending(event: Message | CallbackQuery):
    uid = event.from_user.id
    if not is_admin(uid):
        return
    data = load_data()
    pending = data.get("pending") or []
    text = "📋 <b>Заявки</b>\n\n"
    if not pending:
        text += "Пусто."
    else:
        for i, r in enumerate(pending[-30:], 1):
            text += (
                f"{i}. <code>{r.get('user_id')}</code> "
                f"@{r.get('username') or '—'} ({r.get('name')})\n"
            )
        text += "\nНачисление: <code>/addvic ID SUMMA</code>"
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(text, parse_mode=ParseMode.HTML)
    else:
        await event.answer(text, parse_mode=ParseMode.HTML)


@dp.callback_query(F.data == "adm_users")
async def cb_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    data = load_data()
    users = list(data.get("users", {}).values())
    users.sort(key=lambda x: x.get("vic", 0), reverse=True)
    lines = [f"👥 Игроков: {len(users)}\n"]
    for u in users[:40]:
        lines.append(
            f"<code>{u['id']}</code> @{u.get('username') or '—'} — {u.get('vic', 0):,}"
        )
    await call.answer()
    await call.message.answer("\n".join(lines) or "Пусто", parse_mode=ParseMode.HTML)


@dp.callback_query(F.data == "adm_help_add")
async def cb_help_add(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await call.message.answer(
        "Пример:\n<code>/addvic 123456789 250000</code>\n"
        "99★ пакет = 250000 VIC",
        parse_mode=ParseMode.HTML,
    )


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    text = (command.args or "").strip()
    if not text:
        await message.answer("Формат: /broadcast текст")
        return
    data = load_data()
    ok = fail = 0
    for uid in list(data.get("users", {}).keys()):
        try:
            await bot.send_message(int(uid), text, parse_mode=ParseMode.HTML)
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await message.answer(f"Рассылка: ok={ok}, fail={fail}")


# ---------- обычный текст ----------
@dp.message(F.text)
async def on_text(message: Message):
    t = (message.text or "").strip().lower()

    # частые вопросы
    if any(w in t for w in ("привет", "здравствуй", "хай", "хеллоу")):
        await message.answer(
            "Привет! Жми «🎮 Играть» или /help",
            reply_markup=main_kb(is_admin(message.from_user.id)),
        )
        return
    if any(w in t for w in ("как купить", "звезды", "stars", "донат", "оплат")):
        await cmd_pay(message)
        return
    if any(w in t for w in ("игра", "мини", "mini", "app")):
        await cmd_game(message)
        return

    data = load_data()
    ensure_user(data, message.from_user)
    save_data(data)

    await message.answer(
        "Не понял команду 🤔\n"
        "Используй меню внизу или /help",
        reply_markup=main_kb(is_admin(message.from_user.id)),
    )


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Укажи BOT_TOKEN в .env")
    print("VICOIN bot starting...")
    print(f"Owner for gifts: @{OWNER_USERNAME}")
    print(f"Mini App: {MINIAPP_URL}")
    print(f"Admins: {ADMIN_IDS or 'не заданы'}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

