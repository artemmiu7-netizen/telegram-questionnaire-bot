import asyncio
import html
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ============================================================
# НАСТРОЙКИ
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

UNIVERSITY_URL = "https://mi.university/"
UNIVERSITY_ADDRESS = "Ленинградский проспект, д. 17"
MANAGER_NAME = "Артем"
MANAGER_USERNAME = "artemMIU"
MANAGER_URL = f"https://t.me/{MANAGER_USERNAME}"
MAP_URL = "https://www.google.com/maps/search/?api=1&query=Leningradsky+Prospekt+17+Moscow"
SITE_PHOTO = "university_site.png"
OPEN_DAY_PHOTO = "open_day.png"
CONSENT_TEXT = "Я даю согласие на обработку персональных данных."
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DB_PATH = "/data/bot.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения.")

if not ADMIN_ID_RAW:
    raise RuntimeError("ADMIN_ID не задан в переменных окружения.")

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError as exc:
    raise RuntimeError("ADMIN_ID должен быть числом.") from exc


# ============================================================
# СПРАВОЧНИКИ
# ============================================================
EXAMS = [
    "Обществознание",
    "Математика (профиль)",
    "История",
    "Иностранный язык",
    "Литература",
    "Информатика",
    "География",
    "Физика",
    "Химия",
    "Биология",
]

CAREERS = [
    "Продажи",
    "IT, телеком",
    "Финансы",
    "Туризм, рестораны",
    "Юриспруденция",
    "Искусство, медиа",
    "Госслужба",
]

WEEKDAYS = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]
WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ============================================================
# БАЗА ДАННЫХ ДЛЯ ЗАПИСЕЙ И НАПОМИНАНИЙ
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                reminder_day_sent INTEGER NOT NULL DEFAULT 0,
                reminder_morning_sent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_active_booking(user_id: int):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM bookings WHERE user_id = ? AND active = 1",
            (user_id,),
        ).fetchone()


def save_booking(user, phone: str, selected_date: str, selected_time: str):
    now = datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")
    username = f"@{user.username}" if user.username else "не указан"
    full_name = " ".join(
        x for x in [user.first_name, user.last_name] if x
    ) or "не указано"

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO bookings (
                user_id, username, full_name, phone, date, time,
                active, reminder_day_sent, reminder_morning_sent,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                phone = excluded.phone,
                date = excluded.date,
                time = excluded.time,
                active = 1,
                reminder_day_sent = 0,
                reminder_morning_sent = 0,
                updated_at = excluded.updated_at
            """,
            (
                user.id,
                username,
                full_name,
                phone,
                selected_date,
                selected_time,
                now,
                now,
            ),
        )
        conn.commit()


def cancel_booking(user_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE bookings SET active = 0, updated_at = ? WHERE user_id = ? AND active = 1",
            (datetime.now(MOSCOW_TZ).isoformat(timespec="seconds"), user_id),
        )
        conn.commit()


def mark_day_reminder_sent(booking_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE bookings SET reminder_day_sent = 1 WHERE id = ?",
            (booking_id,),
        )
        conn.commit()


def mark_morning_reminder_sent(booking_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE bookings SET reminder_morning_sent = 1 WHERE id = ?",
            (booking_id,),
        )
        conn.commit()


# ============================================================
# СОСТОЯНИЯ
# ============================================================
class Form(StatesGroup):
    consent = State()
    contact = State()
    school = State()
    class_number = State()
    surname = State()
    name = State()
    patronymic = State()
    student_phone = State()
    exams = State()
    career = State()
    other_career = State()
    summary = State()
    open_day_offer = State()
    open_day_date = State()
    open_day_time = State()


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def esc(value) -> str:
    return html.escape(str(value or ""))


def format_booking(booking) -> str:
    selected = datetime.fromisoformat(booking["date"]).date()
    return (
        f"{WEEKDAYS[selected.weekday()]}, "
        f"{selected.strftime('%d.%m.%Y')} в {booking['time']}"
    )


def user_name(user) -> str:
    return " ".join(
        x for x in [user.first_name, user.last_name] if x
    ) or "не указано"


# ============================================================
# КЛАВИАТУРЫ
# ============================================================
def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Дать согласие", callback_data="consent_yes")],
            [InlineKeyboardButton(text="❌ Не согласен(на)", callback_data="consent_no")],
        ]
    )


def phone_share_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером Telegram", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ]
    )


def class_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="9", callback_data="class:9"),
                InlineKeyboardButton(text="10", callback_data="class:10"),
                InlineKeyboardButton(text="11", callback_data="class:11"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
        ]
    )


def exams_keyboard(selected=None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if item in selected else '⬜'} {item}",
            callback_data=f"exam:{item}",
        )]
        for item in EXAMS
    ]
    rows += [
        [InlineKeyboardButton(text="✅ Готово", callback_data="exam_done")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def careers_keyboard(selected=None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if item in selected else '⬜'} {item}",
            callback_data=f"career:{item}",
        )]
        for item in CAREERS
    ]
    rows += [
        [InlineKeyboardButton(text="✏️ Другое", callback_data="career_other")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="career_done")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏫 Изменить школу", callback_data="edit:school")],
            [InlineKeyboardButton(text="🎓 Изменить класс", callback_data="edit:class")],
            [InlineKeyboardButton(text="👤 Изменить ФИО", callback_data="edit:name")],
            [InlineKeyboardButton(text="📱 Изменить телефон", callback_data="edit:phones")],
            [InlineKeyboardButton(text="📝 Изменить ЕГЭ", callback_data="edit:exams")],
            [InlineKeyboardButton(text="💼 Изменить карьеру", callback_data="edit:career")],
            [InlineKeyboardButton(text="✅ Отправить анкету", callback_data="submit_form")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_form")],
        ]
    )


def open_day_offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Записаться", callback_data="open_start")],
            [InlineKeyboardButton(text="⏭️ Не записываться", callback_data="open_skip")],
        ]
    )


def booking_manage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Изменить запись", callback_data="booking_change")],
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data="booking_cancel")],
            [InlineKeyboardButton(text="💬 Написать Артему", url=MANAGER_URL)],
        ]
    )


def admin_booking_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Открыть профиль", url=f"tg://user?id={user_id}")],
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"admin_cancel:{user_id}")],
        ]
    )


# ============================================================
# ВОПРОСЫ АНКЕТЫ
# ============================================================
async def ask_school(message: Message, state: FSMContext):
    await message.answer(
        "🏫 <b>Школа</b>\n\nВведите название школы:",
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )
    await state.set_state(Form.school)


async def ask_class(message: Message, state: FSMContext):
    await message.answer(
        "🎓 <b>Класс</b>\n\nВыберите класс:",
        parse_mode="HTML",
        reply_markup=class_keyboard(),
    )
    await state.set_state(Form.class_number)


async def ask_surname(message: Message, state: FSMContext):
    await message.answer(
        "👤 <b>ФИО</b>\n\nВведите фамилию:",
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )
    await state.set_state(Form.surname)


async def ask_name(message: Message, state: FSMContext):
    await message.answer("👤 Теперь введите имя:", parse_mode="HTML", reply_markup=back_keyboard())
    await state.set_state(Form.name)


async def ask_patronymic(message: Message, state: FSMContext):
    await message.answer("👤 Теперь введите отчество:", parse_mode="HTML", reply_markup=back_keyboard())
    await state.set_state(Form.patronymic)


async def ask_student_phone(message: Message, state: FSMContext):
    await message.answer(
        "📱 <b>Телефон</b>\n\n"
        "Поделитесь номером кнопкой ниже или введите его вручную.",
        parse_mode="HTML",
        reply_markup=phone_share_keyboard(),
    )
    await state.set_state(Form.student_phone)


async def ask_exams(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(
        "📝 <b>ЕГЭ</b>\n\nВыберите один или несколько предметов:",
        parse_mode="HTML",
        reply_markup=exams_keyboard(data.get("exams", [])),
    )
    await state.set_state(Form.exams)


async def ask_career(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(
        "💼 <b>Карьерная сфера</b>\n\nВыберите один или несколько вариантов:",
        parse_mode="HTML",
        reply_markup=careers_keyboard(data.get("career", [])),
    )
    await state.set_state(Form.career)


async def show_summary(message: Message, state: FSMContext):
    data = await state.get_data()
    exams = "\n".join(f"• {esc(x)}" for x in data.get("exams", [])) or "не выбраны"
    careers = "\n".join(f"• {esc(x)}" for x in data.get("career", [])) or "не выбраны"

    await message.answer(
        "📋 <b>Проверьте анкету</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🏫 <b>Школа:</b> {esc(data.get('school'))}\n"
        f"🎓 <b>Класс:</b> {esc(data.get('class_number'))}\n\n"
        f"👤 <b>Фамилия:</b> {esc(data.get('surname'))}\n"
        f"👤 <b>Имя:</b> {esc(data.get('name'))}\n"
        f"👤 <b>Отчество:</b> {esc(data.get('patronymic'))}\n\n"
        f"📱 <b>Телефон:</b> {esc(data.get('student_phone'))}\n\n"
        f"📝 <b>ЕГЭ:</b>\n{exams}\n\n"
        f"💼 <b>Карьера:</b>\n{careers}",
        parse_mode="HTML",
        reply_markup=summary_keyboard(),
    )
    await state.set_state(Form.summary)


def build_admin_form_message(data, user) -> str:
    username = f"@{user.username}" if user.username else "не указан"
    full_name = user_name(user)
    exams = ", ".join(data.get("exams", [])) or "не выбраны"
    careers = ", ".join(data.get("career", [])) or "не выбраны"
    booking = get_active_booking(user.id)
    booking_text = format_booking(booking) if booking else "не выбрана"

    return (
        "🆕 <b>НОВАЯ ЗАЯВКА</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Имя:</b> {esc(full_name)}\n"
        f"💬 <b>Telegram:</b> {esc(username)}\n"
        f"🆔 <b>Telegram ID:</b> {user.id}\n"
        f"📱 <b>Телефон:</b> {esc(data.get('consent_phone') or data.get('student_phone'))}\n"
        "🔐 <b>Согласие:</b> Да\n\n"
        f"🏫 <b>Школа:</b> {esc(data.get('school'))}\n"
        f"🎓 <b>Класс:</b> {esc(data.get('class_number'))}\n"
        f"👤 <b>ФИО:</b> {esc(data.get('surname'))} {esc(data.get('name'))} {esc(data.get('patronymic'))}\n"
        f"📝 <b>ЕГЭ:</b> {esc(exams)}\n"
        f"💼 <b>Карьера:</b> {esc(careers)}\n"
        f"🚪 <b>День открытых дверей:</b> {esc(booking_text)}"
    )


# ============================================================
# ДЕНЬ ОТКРЫТЫХ ДВЕРЕЙ
# ============================================================
def next_open_days(days_ahead: int = 21):
    today = datetime.now(MOSCOW_TZ).date()
    result = []
    for offset in range(days_ahead):
        day = today + timedelta(days=offset)
        if day.weekday() != 6:
            result.append(day)
    return result


def open_day_dates_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for day in next_open_days():
        label = f"{WEEKDAYS_SHORT[day.weekday()]} {day.strftime('%d.%m')}"
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"open_date:{day.isoformat()}")
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="open_dates_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def valid_time_slots(selected_date):
    if selected_date.weekday() < 5:
        start_hour, end_hour = 9, 19
    elif selected_date.weekday() == 5:
        start_hour, end_hour = 10, 16
    else:
        return []

    now = datetime.now(MOSCOW_TZ)
    slots = []
    for hour in range(start_hour, end_hour):
        if selected_date == now.date() and hour <= now.hour:
            continue
        slots.append(f"{hour:02d}:00")
    return slots


def open_day_times_keyboard(selected_date) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=time_value, callback_data=f"open_time:{time_value}")]
        for time_value in valid_time_slots(selected_date)
    ]
    if not rows:
        rows.append([
            InlineKeyboardButton(text="Нет доступного времени", callback_data="no_time")
        ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад к датам", callback_data="open_time_back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def offer_open_day(message: Message, state: FSMContext):
    caption = (
        "🚪 <b>День открытых дверей</b>\n\n"
        "Хотите записаться на День открытых дверей?\n\n"
        "📅 Пн–Пт: 09:00–19:00\n"
        "📅 Сб: 10:00–16:00\n"
        "📅 Вс: выходной\n\n"
        "Можно выбрать удобную дату и часовой слот."
    )

    try:
        await message.answer_photo(
            FSInputFile(OPEN_DAY_PHOTO),
            caption=caption,
            parse_mode="HTML",
        )
    except (FileNotFoundError, OSError):
        await message.answer(caption, parse_mode="HTML")

    await message.answer(
        "Выберите действие:",
        reply_markup=open_day_offer_keyboard(),
    )
    await state.set_state(Form.open_day_offer)


# ============================================================
# /START И СОГЛАСИЕ
# ============================================================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    opening_text = (
        "🎓 <b>Добро пожаловать в Московский международный университет!</b>\n\n"
        "Пройдите короткую анкету — это поможет нам лучше понять ваши интересы "
        "и подготовить для вас полезную информацию об университете.\n\n"
        "Заполнение займёт всего несколько минут.\n\n"
        "Перед началом необходимо дать согласие на обработку персональных данных."
    )

    try:
        await message.answer_photo(
            FSInputFile(SITE_PHOTO),
            caption=opening_text,
            parse_mode="HTML",
        )
    except (FileNotFoundError, OSError):
        await message.answer(opening_text, parse_mode="HTML")

    await message.answer(
        f"<b>{esc(CONSENT_TEXT)}</b>",
        parse_mode="HTML",
        reply_markup=start_keyboard(),
    )
    await state.set_state(Form.consent)


@dp.callback_query(Form.consent, F.data == "consent_yes")
async def consent_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "✅ <b>Согласие получено.</b>\n\n"
        "Теперь поделитесь вашим номером Telegram.",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "📱 Нажмите кнопку «Поделиться номером Telegram».",
        reply_markup=phone_share_keyboard(),
    )
    await state.set_state(Form.contact)


@dp.callback_query(Form.consent, F.data == "consent_no")
async def consent_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ Без согласия обработка данных невозможна.\n\n"
        "Чтобы начать снова, нажмите /start."
    )


# ============================================================
# КОНТАКТ ПОСЛЕ СОГЛАСИЯ
# ============================================================
@dp.message(Form.contact, F.contact)
async def save_contact(message: Message, state: FSMContext):
    contact = message.contact
    user = message.from_user

    if contact.user_id is not None and contact.user_id != user.id:
        await message.answer(
            "Пожалуйста, поделитесь именно своим номером.",
            reply_markup=phone_share_keyboard(),
        )
        return

    phone = contact.phone_number
    await state.update_data(consent_phone=phone)

    try:
        await bot.send_message(
            ADMIN_ID,
            (
                "📩 <b>Новый контакт</b>\n\n"
                f"👤 Имя: {esc(user_name(user))}\n"
                f"💬 Telegram: {esc('@' + user.username if user.username else 'не указан')}\n"
                f"🆔 Telegram ID: {user.id}\n"
                f"📱 Номер: {esc(phone)}\n"
                "🔐 Согласие: Да"
            ),
            parse_mode="HTML",
        )
    except Exception:
        logging.exception("Не удалось отправить контакт администратору.")
        await message.answer(
            "⚠️ Не удалось передать номер. Попробуйте ещё раз.",
            reply_markup=phone_share_keyboard(),
        )
        return

    await message.answer(
        "🎓 <b>Спасибо!</b>\n\n"
        "Познакомьтесь с Московским международным университетом.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        await message.answer_photo(
            FSInputFile(SITE_PHOTO),
            caption="🌐 <b>Московский международный университет</b>",
            parse_mode="HTML",
        )
    except (FileNotFoundError, OSError):
        pass

    await message.answer(
        "📍 <b>Адрес университета:</b>\n"
        f"{esc(UNIVERSITY_ADDRESS)}\n\n"
        "🌐 <b>Официальный сайт:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏫 Открыть сайт ММУ", url=UNIVERSITY_URL)],
                [InlineKeyboardButton(text="📍 Построить маршрут", url=MAP_URL)],
            ]
        ),
    )

    existing = get_active_booking(user.id)
    if existing:
        await message.answer(
            "📅 <b>У вас уже есть запись:</b>\n\n"
            f"{esc(format_booking(existing))}\n"
            f"📍 {esc(UNIVERSITY_ADDRESS)}\n\n"
            "Вы можете изменить её или отменить.",
            parse_mode="HTML",
            reply_markup=booking_manage_keyboard(),
        )

    await message.answer("Теперь можно заполнить анкету.")
    await ask_school(message, state)


@dp.message(Form.contact)
async def contact_not_shared(message: Message, state: FSMContext):
    await message.answer(
        "Чтобы продолжить, нажмите «📱 Поделиться номером Telegram».",
        reply_markup=phone_share_keyboard(),
    )


# ============================================================
# АНКЕТА
# ============================================================
@dp.message(Form.school)
async def school(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await start(message, state)
        return
    await state.update_data(school=message.text.strip())
    await ask_class(message, state)


@dp.callback_query(Form.class_number, F.data.startswith("class:"))
async def class_selected(callback: CallbackQuery, state: FSMContext):
    await state.update_data(class_number=callback.data.split(":", 1)[1])
    await callback.answer()
    await callback.message.edit_text(f"Класс: {esc((await state.get_data()).get('class_number'))}")
    await ask_surname(callback.message, state)


@dp.callback_query(Form.class_number, F.data == "back")
async def class_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_school(callback.message, state)


@dp.message(Form.surname)
async def surname(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_school(message, state)
        return
    await state.update_data(surname=message.text.strip())
    await ask_name(message, state)


@dp.message(Form.name)
async def name(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_surname(message, state)
        return
    await state.update_data(name=message.text.strip())
    await ask_patronymic(message, state)


@dp.message(Form.patronymic)
async def patronymic(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_name(message, state)
        return
    await state.update_data(patronymic=message.text.strip())
    await ask_student_phone(message, state)


@dp.message(Form.student_phone, F.contact)
async def student_phone_contact(message: Message, state: FSMContext):
    await state.update_data(student_phone=message.contact.phone_number)
    await message.answer("✅ Номер сохранён.", reply_markup=ReplyKeyboardRemove())
    await ask_exams(message, state)


@dp.message(Form.student_phone)
async def student_phone_text(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_patronymic(message, state)
        return
    await state.update_data(student_phone=message.text.strip())
    await message.answer("✅ Номер сохранён.", reply_markup=ReplyKeyboardRemove())
    await ask_exams(message, state)


@dp.callback_query(Form.exams, F.data.startswith("exam:"))
async def exam_toggle(callback: CallbackQuery, state: FSMContext):
    item = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = list(data.get("exams", []))
    if item in selected:
        selected.remove(item)
    else:
        selected.append(item)
    await state.update_data(exams=selected)
    await callback.message.edit_reply_markup(reply_markup=exams_keyboard(selected))
    await callback.answer()


@dp.callback_query(Form.exams, F.data == "exam_done")
async def exams_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("exams"):
        await callback.answer("Выберите хотя бы один предмет.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text("✅ Предметы сохранены.")
    await ask_career(callback.message, state)


@dp.callback_query(Form.exams, F.data == "back")
async def exams_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_student_phone(callback.message, state)


@dp.callback_query(Form.career, F.data.startswith("career:"))
async def career_toggle(callback: CallbackQuery, state: FSMContext):
    item = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = list(data.get("career", []))
    if item in selected:
        selected.remove(item)
    else:
        selected.append(item)
    await state.update_data(career=selected)
    await callback.message.edit_reply_markup(reply_markup=careers_keyboard(selected))
    await callback.answer()


@dp.callback_query(Form.career, F.data == "career_other")
async def career_other(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("✏️ Напишите свой вариант сферы карьеры:")
    await state.set_state(Form.other_career)


@dp.message(Form.other_career)
async def other_career(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_career(message, state)
        return
    data = await state.get_data()
    selected = [x for x in data.get("career", []) if not x.startswith("Другое:")]
    selected.append(f"Другое: {message.text.strip()}")
    await state.update_data(career=selected)
    await show_summary(message, state)


@dp.callback_query(Form.career, F.data == "career_done")
async def career_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("career"):
        await callback.answer("Выберите хотя бы один вариант.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text("✅ Карьерная сфера сохранена.")
    await show_summary(callback.message, state)


@dp.callback_query(Form.career, F.data == "back")
async def career_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_exams(callback.message, state)


# ============================================================
# РЕДАКТИРОВАНИЕ И ОТПРАВКА
# ============================================================
@dp.callback_query(Form.summary, F.data == "edit:school")
async def edit_school(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_school(callback.message, state)


@dp.callback_query(Form.summary, F.data == "edit:class")
async def edit_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_class(callback.message, state)


@dp.callback_query(Form.summary, F.data == "edit:name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_surname(callback.message, state)


@dp.callback_query(Form.summary, F.data == "edit:phones")
async def edit_phones(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_student_phone(callback.message, state)


@dp.callback_query(Form.summary, F.data == "edit:exams")
async def edit_exams(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_exams(callback.message, state)


@dp.callback_query(Form.summary, F.data == "edit:career")
async def edit_career(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_career(callback.message, state)


@dp.callback_query(Form.summary, F.data == "submit_form")
async def submit_form(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user

    try:
        await bot.send_message(
            ADMIN_ID,
            build_admin_form_message(data, user),
            parse_mode="HTML",
            reply_markup=(
                admin_booking_keyboard(user.id)
                if get_active_booking(user.id)
                else InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(
                        text="👤 Открыть профиль",
                        url=f"tg://user?id={user.id}",
                    )]]
                )
            ),
        )
    except Exception:
        logging.exception("Не удалось отправить анкету администратору.")
        await callback.answer()
        await callback.message.edit_text("⚠️ Не удалось отправить анкету. Попробуйте ещё раз.")
        await state.clear()
        return

    await callback.answer("Анкета отправлена!")
    await callback.message.edit_text(
        "✅ <b>Анкета отправлена.</b>\n\nСпасибо за заполнение!",
        parse_mode="HTML",
    )
    await offer_open_day(callback.message, state)


@dp.callback_query(Form.summary, F.data == "cancel_form")
async def cancel_form(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ Заполнение анкеты отменено.\n\nЧтобы начать снова, нажмите /start."
    )


# ============================================================
# УПРАВЛЕНИЕ ЗАПИСЬЮ
# ============================================================
async def show_current_booking(message: Message, user_id: int):
    booking = get_active_booking(user_id)
    if not booking:
        await message.answer("У вас нет активной записи.")
        return

    await message.answer(
        "📅 <b>Ваша текущая запись</b>\n\n"
        f"{esc(format_booking(booking))}\n"
        f"📍 {esc(UNIVERSITY_ADDRESS)}",
        parse_mode="HTML",
        reply_markup=booking_manage_keyboard(),
    )


@dp.callback_query(F.data == "booking_change")
async def booking_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📅 <b>Выберите новую дату</b>\n\nВоскресенье — выходной.",
        parse_mode="HTML",
        reply_markup=open_day_dates_keyboard(),
    )
    await state.set_state(Form.open_day_date)


@dp.callback_query(F.data == "booking_cancel")
async def booking_cancel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    booking = get_active_booking(user_id)
    if not booking:
        await callback.answer("Активной записи уже нет.", show_alert=True)
        return

    cancel_booking(user_id)
    await callback.answer("Запись отменена.")
    await callback.message.edit_text(
        "❌ <b>Запись отменена.</b>\n\n"
        "При необходимости вы можете записаться снова через бота.",
        parse_mode="HTML",
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            "❌ <b>Пользователь отменил запись</b>\n\n"
            f"👤 {esc(user_name(callback.from_user))}\n"
            f"🆔 {callback.from_user.id}\n"
            f"💬 {esc('@' + callback.from_user.username if callback.from_user.username else 'не указан')}\n"
            f"📅 Было: {esc(format_booking(booking))}",
            parse_mode="HTML",
        )
    except Exception:
        logging.exception("Не удалось уведомить администратора об отмене.")


# ============================================================
# КАЛЕНДАРЬ И ВРЕМЯ
# ============================================================
@dp.callback_query(Form.open_day_offer, F.data == "open_start")
async def open_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📅 <b>Выберите дату</b>\n\nВоскресенье — выходной.",
        parse_mode="HTML",
        reply_markup=open_day_dates_keyboard(),
    )
    await state.set_state(Form.open_day_date)


@dp.callback_query(Form.open_day_offer, F.data == "open_skip")
async def open_skip(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "Спасибо! Если захотите записаться позже, снова обратитесь к боту."
    )
    await callback.message.answer(
        f"👤 <b>Ваш менеджер — {MANAGER_NAME}</b>\n"
        f"💬 Telegram: @{MANAGER_USERNAME}\n\n"
        "По вопросам об университете, записи или анкете можете связаться напрямую.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"💬 Написать {MANAGER_NAME}", url=MANAGER_URL)]]
        ),
    )
    await state.clear()


@dp.callback_query(Form.open_day_date, F.data == "open_dates_back")
async def open_dates_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await offer_open_day(callback.message, state)


@dp.callback_query(Form.open_day_date, F.data.startswith("open_date:"))
async def open_date_selected(callback: CallbackQuery, state: FSMContext):
    raw_date = callback.data.split(":", 1)[1]
    try:
        selected_date = datetime.fromisoformat(raw_date).date()
    except ValueError:
        await callback.answer("Некорректная дата.", show_alert=True)
        return

    today = datetime.now(MOSCOW_TZ).date()
    if selected_date < today or selected_date.weekday() == 6:
        await callback.answer("Эта дата недоступна.", show_alert=True)
        return

    slots = valid_time_slots(selected_date)
    if not slots:
        await callback.answer("На выбранную дату больше нет доступного времени.", show_alert=True)
        return

    await state.update_data(open_day_date=selected_date.isoformat())
    await callback.answer()
    await callback.message.edit_text(
        f"🗓 <b>{WEEKDAYS[selected_date.weekday()]}, {selected_date.strftime('%d.%m.%Y')}</b>\n\n"
        "Выберите время проведения:",
        parse_mode="HTML",
        reply_markup=open_day_times_keyboard(selected_date),
    )
    await state.set_state(Form.open_day_time)


@dp.callback_query(Form.open_day_time, F.data == "open_time_back")
async def open_time_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📅 <b>Выберите дату</b>",
        parse_mode="HTML",
        reply_markup=open_day_dates_keyboard(),
    )
    await state.set_state(Form.open_day_date)


@dp.callback_query(Form.open_day_time, F.data == "no_time")
async def no_time(callback: CallbackQuery):
    await callback.answer("На сегодня свободного времени нет. Выберите другую дату.", show_alert=True)


@dp.callback_query(Form.open_day_time, F.data.startswith("open_time:"))
async def open_time_selected(callback: CallbackQuery, state: FSMContext):
    time_value = callback.data.split(":", 1)[1]
    data = await state.get_data()
    raw_date = data.get("open_day_date")
    if not raw_date:
        await callback.answer("Сначала выберите дату.", show_alert=True)
        return

    selected_date = datetime.fromisoformat(raw_date).date()
    if time_value not in valid_time_slots(selected_date):
        await callback.answer("Это время уже недоступно.", show_alert=True)
        return

    user = callback.from_user
    existing = get_active_booking(user.id)
    await state.update_data(open_day_time=time_value)
    save_booking(
        user,
        data.get("consent_phone") or data.get("student_phone") or "не указан",
        raw_date,
        time_value,
    )
    new_booking = get_active_booking(user.id)
    await callback.answer("Запись сохранена!")

    await callback.message.edit_text(
        "✅ <b>Вы записаны!</b>\n\n"
        f"📅 {esc(format_booking(new_booking))}\n"
        f"📍 <b>Адрес:</b> {esc(UNIVERSITY_ADDRESS)}\n\n"
        "Ждём вас на Дне открытых дверей.",
        parse_mode="HTML",
        reply_markup=booking_manage_keyboard(),
    )

    # Явный блок менеджера в конце подтверждения.
    await callback.message.answer(
        f"👤 <b>Ваш менеджер — {MANAGER_NAME}</b>\n"
        f"💬 Telegram: @{MANAGER_USERNAME}\n\n"
        "По вопросам об университете, записи или анкете можете связаться напрямую.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"💬 Написать {MANAGER_NAME}", url=MANAGER_URL)]]
        ),
    )

    # Администратору — структурированная запись.
    try:
        username = f"@{user.username}" if user.username else "не указан"
        action = "🔄 Запись изменена" if existing else "🚪 Новая запись"
        await bot.send_message(
            ADMIN_ID,
            f"<b>{action}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Имя:</b> {esc(user_name(user))}\n"
            f"💬 <b>Telegram:</b> {esc(username)}\n"
            f"🆔 <b>Telegram ID:</b> {user.id}\n"
            f"📱 <b>Телефон:</b> {esc(new_booking['phone'])}\n"
            f"📅 <b>Дата:</b> {esc(format_booking(new_booking))}\n"
            f"📍 <b>Адрес:</b> {esc(UNIVERSITY_ADDRESS)}",
            parse_mode="HTML",
            reply_markup=admin_booking_keyboard(user.id),
        )
    except Exception:
        logging.exception("Не удалось отправить уведомление администратору о записи.")

    await state.clear()


@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недоступно.", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Некорректный пользователь.", show_alert=True)
        return

    booking = get_active_booking(user_id)
    if not booking:
        await callback.answer("Активной записи уже нет.", show_alert=True)
        return

    cancel_booking(user_id)
    await callback.answer("Запись отменена.")
    await callback.message.edit_reply_markup(reply_markup=None)

    try:
        await bot.send_message(
            user_id,
            "❌ <b>Запись на День открытых дверей отменена менеджером.</b>\n\n"
            "Свяжитесь с Артемом, чтобы выбрать новую дату и время.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💬 Написать Артему", url=MANAGER_URL)]]
            ),
        )
    except Exception:
        logging.exception("Не удалось уведомить пользователя об отмене записи администратором.")


# ============================================================
# НАПОМИНАНИЯ
# ============================================================
async def reminder_loop():
    while True:
        try:
            now = datetime.now(MOSCOW_TZ)
            today = now.date()

            with get_db() as conn:
                bookings = conn.execute(
                    "SELECT * FROM bookings WHERE active = 1"
                ).fetchall()

            for booking in bookings:
                event_date = datetime.fromisoformat(booking["date"]).date()
                event_datetime = datetime.combine(
                    event_date,
                    datetime.strptime(booking["time"], "%H:%M").time(),
                    tzinfo=MOSCOW_TZ,
                )

                # Напоминание за день в 10:00.
                if (
                    event_date == today + timedelta(days=1)
                    and now.hour >= 10
                    and not booking["reminder_day_sent"]
                ):
                    await bot.send_message(
                        booking["user_id"],
                        "🔔 <b>Напоминание</b>\n\n"
                        "Завтра вы записаны на День открытых дверей.\n"
                        f"📅 {esc(format_booking(booking))}\n"
                        f"📍 {esc(UNIVERSITY_ADDRESS)}",
                        parse_mode="HTML",
                        reply_markup=booking_manage_keyboard(),
                    )
                    mark_day_reminder_sent(booking["id"])

                # Утреннее напоминание в день мероприятия в 08:00.
                if (
                    event_date == today
                    and now.hour >= 8
                    and not booking["reminder_morning_sent"]
                    and now < event_datetime
                ):
                    await bot.send_message(
                        booking["user_id"],
                        "☀️ <b>Сегодня День открытых дверей!</b>\n\n"
                        f"🕐 {esc(booking['time'])}\n"
                        f"📍 {esc(UNIVERSITY_ADDRESS)}\n\n"
                        "Ждём вас!",
                        parse_mode="HTML",
                        reply_markup=booking_manage_keyboard(),
                    )
                    mark_morning_reminder_sent(booking["id"])

        except Exception:
            logging.exception("Ошибка в цикле напоминаний.")

        await asyncio.sleep(30)


@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заполнение отменено.\n\nНажмите /start для нового заполнения.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    init_db()
    reminder_task = asyncio.create_task(reminder_loop())
    try:
        print("Telegram questionnaire bot is running")
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
