
import asyncio
import html
import logging
import os
from datetime import datetime

import gspread
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from google.oauth2.service_account import Credentials


# ============================================================
# НАСТРОЙКИ
# ============================================================
# Вариант 1: впиши значения прямо сюда.
# Вариант 2: задай их через переменные окружения.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8656128752:AAFmXvtjdAM8-OvfnO1xioOWWZmvDPOgpVc")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8904693860"))

# Google Sheets:
GOOGLE_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE",
    "credentials.json"
)
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID",
    "ВСТАВЬ_ID_GOOGLE_ТАБЛИЦЫ"
)
SHEET_NAME = os.getenv("SHEET_NAME", "Анкеты")

# Перед реальным запуском замени этот текст на юридически
# утвержденный вашей организацией текст согласия.
CONSENT_TEXT = """
Я даю согласие на обработку моих персональных данных,
указанных в настоящей анкете, в целях обработки анкеты
и связи со мной по указанным контактным данным.
""".strip()


# ============================================================
# ПРЕДМЕТЫ И СФЕРЫ
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


# ============================================================
# FSM
# ============================================================
class Form(StatesGroup):
    school = State()
    class_number = State()
    surname = State()
    name = State()
    patronymic = State()
    student_phone = State()
    parent_phone = State()
    exams = State()
    career = State()
    other_career = State()
    consent = State()


# ============================================================
# BOT
# ============================================================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# ОБЩИЕ ФУНКЦИИ
# ============================================================
def esc(value) -> str:
    return html.escape(str(value or ""))


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Заполнить анкету",
                callback_data="start_form"
            )]
        ]
    )


def back_button(callback_data="back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=callback_data
            )]
        ]
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="📱 Отправить номер телефона",
                request_contact=True
            )],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def class_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="9", callback_data="class:9"),
                InlineKeyboardButton(text="10", callback_data="class:10"),
                InlineKeyboardButton(text="11", callback_data="class:11"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
            ],
        ]
    )


def exams_keyboard(selected=None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = []

    for item in EXAMS:
        mark = "✅" if item in selected else "⬜"
        rows.append([
            InlineKeyboardButton(
                text=f"{mark} {item}",
                callback_data=f"exam:{item}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="✅ Готово",
            callback_data="exam_done"
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def careers_keyboard(selected=None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = []

    for item in CAREERS:
        mark = "✅" if item in selected else "⬜"
        rows.append([
            InlineKeyboardButton(
                text=f"{mark} {item}",
                callback_data=f"career:{item}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="✏️ Другое",
            callback_data="career_other"
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text="✅ Готово",
            callback_data="career_done"
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Согласен(на)",
                callback_data="consent_yes"
            )],
            [InlineKeyboardButton(
                text="❌ Не согласен(на)",
                callback_data="consent_no"
            )],
            [InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="back"
            )],
        ]
    )


def final_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🏫 Изменить школу",
                callback_data="edit:school"
            )],
            [InlineKeyboardButton(
                text="🎓 Изменить класс",
                callback_data="edit:class"
            )],
            [InlineKeyboardButton(
                text="👤 Изменить ФИО",
                callback_data="edit:name"
            )],
            [InlineKeyboardButton(
                text="📱 Изменить телефоны",
                callback_data="edit:phones"
            )],
            [InlineKeyboardButton(
                text="📝 Изменить ЕГЭ",
                callback_data="edit:exams"
            )],
            [InlineKeyboardButton(
                text="💼 Изменить карьеру",
                callback_data="edit:career"
            )],
            [InlineKeyboardButton(
                text="🔐 Перейти к согласию",
                callback_data="go_consent"
            )],
            [InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="cancel_form"
            )],
        ]
    )


async def ask_school(message: Message, state: FSMContext):
    await message.answer(
        "🏫 <b>Шаг 1 из 8</b>\n\n"
        "Введите название школы:",
        parse_mode="HTML",
        reply_markup=back_button(),
    )
    await state.set_state(Form.school)


async def ask_class(message: Message, state: FSMContext):
    await message.answer(
        "🎓 <b>Шаг 2 из 8</b>\n\n"
        "Выберите класс:",
        parse_mode="HTML",
        reply_markup=class_keyboard(),
    )
    await state.set_state(Form.class_number)


async def ask_surname(message: Message, state: FSMContext):
    await message.answer(
        "👤 <b>Шаг 3 из 8</b>\n\n"
        "Введите фамилию:",
        parse_mode="HTML",
        reply_markup=back_button(),
    )
    await state.set_state(Form.surname)


async def ask_name(message: Message, state: FSMContext):
    await message.answer(
        "👤 <b>Шаг 3 из 8</b>\n\n"
        "Введите имя:",
        parse_mode="HTML",
        reply_markup=back_button(),
    )
    await state.set_state(Form.name)


async def ask_patronymic(message: Message, state: FSMContext):
    await message.answer(
        "👤 <b>Шаг 3 из 8</b>\n\n"
        "Введите отчество:",
        parse_mode="HTML",
        reply_markup=back_button(),
    )
    await state.set_state(Form.patronymic)


async def ask_student_phone(message: Message, state: FSMContext):
    await message.answer(
        "📱 <b>Шаг 4 из 8</b>\n\n"
        "Отправьте мобильный телефон ученика кнопкой ниже.\n\n"
        "Можно также ввести номер вручную.",
        parse_mode="HTML",
        reply_markup=phone_keyboard(),
    )
    await state.set_state(Form.student_phone)


async def ask_parent_phone(message: Message, state: FSMContext):
    await message.answer(
        "👨‍👩‍👦 <b>Шаг 5 из 8</b>\n\n"
        "Отправьте мобильный телефон родителя.\n\n"
        "Можно также ввести номер вручную.",
        parse_mode="HTML",
        reply_markup=phone_keyboard(),
    )
    await state.set_state(Form.parent_phone)


async def ask_exams(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("exams", [])

    await message.answer(
        "📝 <b>Шаг 6 из 8</b>\n\n"
        "Какие предметы ЕГЭ вы планируете сдавать?\n\n"
        "Можно выбрать несколько вариантов.",
        parse_mode="HTML",
        reply_markup=exams_keyboard(selected),
    )
    await state.set_state(Form.exams)


async def ask_career(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("career", [])

    await message.answer(
        "💼 <b>Шаг 7 из 8</b>\n\n"
        "В какой сфере вы планируете строить карьеру?\n\n"
        "Можно выбрать несколько вариантов.",
        parse_mode="HTML",
        reply_markup=careers_keyboard(selected),
    )
    await state.set_state(Form.career)


async def ask_consent(message: Message, state: FSMContext):
    await message.answer(
        "🔐 <b>Согласие на обработку персональных данных</b>\n\n"
        f"{esc(CONSENT_TEXT)}\n\n"
        "Нажимая «Согласен(на)», вы подтверждаете свое согласие.",
        parse_mode="HTML",
        reply_markup=consent_keyboard(),
    )
    await state.set_state(Form.consent)


async def show_summary(message: Message, state: FSMContext):
    data = await state.get_data()

    exams = data.get("exams", [])
    careers = data.get("career", [])

    exams_text = "\n".join(f"• {esc(x)}" for x in exams) or "не выбраны"
    careers_text = "\n".join(f"• {esc(x)}" for x in careers) or "не выбраны"

    text = (
        "📋 <b>ПРОВЕРЬТЕ АНКЕТУ</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🏫 <b>Школа:</b> {esc(data.get('school'))}\n"
        f"🎓 <b>Класс:</b> {esc(data.get('class_number'))}\n\n"
        f"👤 <b>Фамилия:</b> {esc(data.get('surname'))}\n"
        f"👤 <b>Имя:</b> {esc(data.get('name'))}\n"
        f"👤 <b>Отчество:</b> {esc(data.get('patronymic'))}\n\n"
        f"📱 <b>Телефон ученика:</b> {esc(data.get('student_phone'))}\n"
        f"👨‍👩‍👦 <b>Телефон родителя:</b> {esc(data.get('parent_phone'))}\n\n"
        f"📝 <b>ЕГЭ:</b>\n{exams_text}\n\n"
        f"💼 <b>Карьера:</b>\n{careers_text}\n\n"
        "Если всё верно, нажмите «Перейти к согласию»."
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=final_keyboard(),
    )


# ============================================================
# GOOGLE SHEETS
# ============================================================
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=scopes,
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return spreadsheet.worksheet(SHEET_NAME)


def append_to_google_sheet(data, user):
    sheet = get_sheet()

    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    exams = ", ".join(data.get("exams", []))
    career = ", ".join(data.get("career", []))

    username = f"@{user.username}" if user.username else ""

    row = [
        timestamp,
        data.get("school", ""),
        data.get("class_number", ""),
        data.get("surname", ""),
        data.get("name", ""),
        data.get("patronymic", ""),
        data.get("student_phone", ""),
        data.get("parent_phone", ""),
        exams,
        career,
        username,
        str(user.id),
        "Да",
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")


def format_admin_message(data, user):
    exams_text = "\n".join(
        f"• {esc(x)}" for x in data.get("exams", [])
    )

    career_text = "\n".join(
        f"• {esc(x)}" for x in data.get("career", [])
    )

    username = f"@{user.username}" if user.username else "не указан"

    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    return (
        "📩 <b>НОВАЯ АНКЕТА</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🏫 <b>Школа:</b> {esc(data.get('school'))}\n"
        f"🎓 <b>Класс:</b> {esc(data.get('class_number'))}\n\n"
        f"👤 <b>Фамилия:</b> {esc(data.get('surname'))}\n"
        f"👤 <b>Имя:</b> {esc(data.get('name'))}\n"
        f"👤 <b>Отчество:</b> {esc(data.get('patronymic'))}\n\n"
        f"📱 <b>Телефон ученика:</b> {esc(data.get('student_phone'))}\n"
        f"👨‍👩‍👦 <b>Телефон родителя:</b> {esc(data.get('parent_phone'))}\n\n"
        f"📝 <b>Предметы ЕГЭ:</b>\n{exams_text}\n\n"
        f"💼 <b>Сфера карьеры:</b>\n{career_text}\n\n"
        "🔐 <b>Согласие:</b> Да\n"
        f"📅 <b>Дата:</b> {timestamp}\n"
        f"💬 <b>Telegram:</b> {esc(username)}\n"
        f"🆔 <b>Telegram ID:</b> {user.id}"
    )


# ============================================================
# START
# ============================================================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "👋 <b>Здравствуйте!</b>\n\n"
        "Это электронная версия анкеты.\n"
        "Заполнение занимает около 2–3 минут.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "start_form")
async def start_form(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "Начинаем заполнение анкеты."
    )
    await ask_school(callback.message, state)


# ============================================================
# ШКОЛА
# ============================================================
@dp.message(Form.school)
async def school(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer(
            "Вы вернулись в начало.",
            reply_markup=main_menu(),
        )
        return

    await state.update_data(school=message.text.strip())
    await ask_class(message, state)


# ============================================================
# КЛАСС
# ============================================================
@dp.callback_query(Form.class_number, F.data.startswith("class:"))
async def class_selected(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await state.update_data(class_number=value)
    await callback.answer()
    await callback.message.edit_text(
        f"Класс: {esc(value)}"
    )
    await ask_surname(callback.message, state)


# ============================================================
# ФАМИЛИЯ / ИМЯ / ОТЧЕСТВО
# ============================================================
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


# ============================================================
# ТЕЛЕФОНЫ
# ============================================================
@dp.message(Form.student_phone, F.contact)
async def student_phone_contact(message: Message, state: FSMContext):
    await state.update_data(
        student_phone=message.contact.phone_number
    )
    await ask_parent_phone(message, state)


@dp.message(Form.student_phone)
async def student_phone_text(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_patronymic(message, state)
        return

    await state.update_data(student_phone=message.text.strip())
    await ask_parent_phone(message, state)


@dp.message(Form.parent_phone, F.contact)
async def parent_phone_contact(message: Message, state: FSMContext):
    await state.update_data(
        parent_phone=message.contact.phone_number
    )
    await ask_exams(message, state)


@dp.message(Form.parent_phone)
async def parent_phone_text(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_student_phone(message, state)
        return

    await state.update_data(parent_phone=message.text.strip())
    await ask_exams(message, state)


# ============================================================
# ЕГЭ
# ============================================================
@dp.callback_query(Form.exams, F.data.startswith("exam:"))
async def exam_toggle(callback: CallbackQuery, state: FSMContext):
    item = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("exams", [])

    if item in selected:
        selected.remove(item)
    else:
        selected.append(item)

    await state.update_data(exams=selected)
    await callback.message.edit_reply_markup(
        reply_markup=exams_keyboard(selected)
    )
    await callback.answer()


@dp.callback_query(Form.exams, F.data == "exam_done")
async def exams_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if not data.get("exams"):
        await callback.answer(
            "Выберите хотя бы один предмет.",
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.edit_text("Предметы ЕГЭ сохранены.")
    await ask_career(callback.message, state)


@dp.callback_query(Form.exams, F.data == "back")
async def exams_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_parent_phone(callback.message, state)


# ============================================================
# КАРЬЕРА
# ============================================================
@dp.callback_query(Form.career, F.data.startswith("career:"))
async def career_toggle(callback: CallbackQuery, state: FSMContext):
    item = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("career", [])

    if item in selected:
        selected.remove(item)
    else:
        selected.append(item)

    await state.update_data(career=selected)
    await callback.message.edit_reply_markup(
        reply_markup=careers_keyboard(selected)
    )
    await callback.answer()


@dp.callback_query(Form.career, F.data == "career_other")
async def career_other(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "✏️ Напишите свой вариант сферы карьеры:",
        parse_mode="HTML",
    )
    await state.set_state(Form.other_career)


@dp.message(Form.other_career)
async def other_career(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_career(message, state)
        return

    data = await state.get_data()
    selected = data.get("career", [])

    custom = f"Другое: {message.text.strip()}"

    # Удаляем старое "Другое", если пользователь исправляет вариант.
    selected = [
        x for x in selected if not x.startswith("Другое:")
    ]
    selected.append(custom)

    await state.update_data(career=selected)

    await show_summary(message, state)


@dp.callback_query(Form.career, F.data == "career_done")
async def career_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if not data.get("career"):
        await callback.answer(
            "Выберите хотя бы один вариант.",
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.edit_text("Сфера карьеры сохранена.")
    await show_summary(callback.message, state)


@dp.callback_query(Form.career, F.data == "back")
async def career_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_exams(callback.message, state)


# ============================================================
# РЕДАКТИРОВАНИЕ
# ============================================================
@dp.callback_query(F.data == "edit:school")
async def edit_school(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_school(callback.message, state)


@dp.callback_query(F.data == "edit:class")
async def edit_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_class(callback.message, state)


@dp.callback_query(F.data == "edit:name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_surname(callback.message, state)


@dp.callback_query(F.data == "edit:phones")
async def edit_phones(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_student_phone(callback.message, state)


@dp.callback_query(F.data == "edit:exams")
async def edit_exams(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_exams(callback.message, state)


@dp.callback_query(F.data == "edit:career")
async def edit_career(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_career(callback.message, state)


@dp.callback_query(F.data == "go_consent")
async def go_consent(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_consent(callback.message, state)


# ============================================================
# СОГЛАСИЕ
# ============================================================
@dp.callback_query(Form.consent, F.data == "consent_yes")
async def consent_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user

    # 1. Отправляем тебе в Telegram.
    admin_text = format_admin_message(data, user)

    try:
        await bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="HTML",
        )
    except Exception:
        logging.exception("Не удалось отправить анкету администратору.")
        await callback.answer()
        await callback.message.edit_text(
            "⚠️ Не удалось отправить анкету ответственному сотруднику.\n"
            "Пожалуйста, попробуйте ещё раз."
        )
        await state.clear()
        return

    # 2. Записываем в Google Sheets.
    try:
        await asyncio.to_thread(
            append_to_google_sheet,
            data,
            user,
        )
        sheet_status = "и сохранена в таблицу"
    except Exception:
        logging.exception("Не удалось записать анкету в Google Sheets.")
        sheet_status = "и отправлена ответственному сотруднику"

        # Чтобы пользователь не потерял анкету, мы всё равно
        # считаем отправку в Telegram успешной.

    await callback.answer("Анкета отправлена!")

    await callback.message.edit_text(
        "✅ <b>Анкета успешно отправлена!</b>\n\n"
        f"Данные переданы ответственному сотруднику {sheet_status}.\n\n"
        "Спасибо!",
        parse_mode="HTML",
    )

    await state.clear()


@dp.callback_query(Form.consent, F.data == "consent_no")
async def consent_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    await callback.message.edit_text(
        "❌ Без согласия на обработку персональных данных "
        "заполнение анкеты невозможно.\n\n"
        "Чтобы начать заново, нажмите /start."
    )


@dp.callback_query(Form.consent, F.data == "back")
async def consent_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await show_summary(callback.message, state)


# ============================================================
# ОТМЕНА
# ============================================================
@dp.callback_query(F.data == "cancel_form")
async def cancel_form(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    await callback.message.edit_text(
        "❌ Заполнение анкеты отменено.\n\n"
        "Чтобы начать заново, нажмите /start."
    )


@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заполнение анкеты отменено.\n\n"
        "Для нового заполнения нажмите /start.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ============================================================
# ЗАПУСК
# ============================================================
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("==========================================")
    print(" Telegram questionnaire bot is running")
    print("==========================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
