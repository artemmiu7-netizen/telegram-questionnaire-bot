import html
import logging
import os
from datetime import datetime

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

# ============================================================
# НАСТРОЙКИ
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")
UNIVERSITY_URL = "https://mi.university/"
CONSENT_TEXT = "Я даю согласие на обработку персональных данных."

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения.")

if not ADMIN_ID_RAW:
    raise RuntimeError("ADMIN_ID не задан в переменных окружения.")

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError as exc:
    raise RuntimeError("ADMIN_ID должен быть числом.") from exc


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


class Form(StatesGroup):
    consent = State()
    contact = State()
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
    summary = State()


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def esc(value) -> str:
    return html.escape(str(value or ""))


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Дать согласие",
                callback_data="consent_yes",
            )],
            [InlineKeyboardButton(
                text="❌ Не согласен(на)",
                callback_data="consent_no",
            )],
        ]
    )


def phone_share_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="📱 Поделиться номером Telegram",
                request_contact=True,
            )],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="back",
            )]
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
            [InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="back",
            )],
        ]
    )


def exams_keyboard(selected=None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = []

    for item in EXAMS:
        rows.append([
            InlineKeyboardButton(
                text=f"{'✅' if item in selected else '⬜'} {item}",
                callback_data=f"exam:{item}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="exam_done")
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def careers_keyboard(selected=None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = []

    for item in CAREERS:
        rows.append([
            InlineKeyboardButton(
                text=f"{'✅' if item in selected else '⬜'} {item}",
                callback_data=f"career:{item}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="✏️ Другое", callback_data="career_other")
    ])
    rows.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="career_done")
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏫 Изменить школу", callback_data="edit:school")],
            [InlineKeyboardButton(text="🎓 Изменить класс", callback_data="edit:class")],
            [InlineKeyboardButton(text="👤 Изменить ФИО", callback_data="edit:name")],
            [InlineKeyboardButton(text="📱 Изменить телефоны", callback_data="edit:phones")],
            [InlineKeyboardButton(text="📝 Изменить ЕГЭ", callback_data="edit:exams")],
            [InlineKeyboardButton(text="💼 Изменить карьеру", callback_data="edit:career")],
            [InlineKeyboardButton(text="✅ Отправить анкету", callback_data="submit_form")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_form")],
        ]
    )


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
    await message.answer(
        "👤 Теперь введите имя:",
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )
    await state.set_state(Form.name)


async def ask_patronymic(message: Message, state: FSMContext):
    await message.answer(
        "👤 Теперь введите отчество:",
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )
    await state.set_state(Form.patronymic)


async def ask_student_phone(message: Message, state: FSMContext):
    await message.answer(
        "📱 <b>Телефон ученика</b>\n\n"
        "Поделитесь номером кнопкой ниже или введите его вручную.",
        parse_mode="HTML",
        reply_markup=phone_share_keyboard(),
    )
    await state.set_state(Form.student_phone)


async def ask_parent_phone(message: Message, state: FSMContext):
    await message.answer(
        "👨‍👩‍👦 <b>Телефон родителя</b>\n\n"
        "Поделитесь номером кнопкой ниже или введите его вручную.",
        parse_mode="HTML",
        reply_markup=phone_share_keyboard(),
    )
    await state.set_state(Form.parent_phone)


async def ask_exams(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(
        "📝 <b>ЕГЭ</b>\n\n"
        "Выберите один или несколько предметов:",
        parse_mode="HTML",
        reply_markup=exams_keyboard(data.get("exams", [])),
    )
    await state.set_state(Form.exams)


async def ask_career(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(
        "💼 <b>Карьерная сфера</b>\n\n"
        "Выберите один или несколько вариантов:",
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
        f"📱 <b>Телефон ученика:</b> {esc(data.get('student_phone'))}\n"
        f"👨‍👩‍👦 <b>Телефон родителя:</b> {esc(data.get('parent_phone'))}\n\n"
        f"📝 <b>ЕГЭ:</b>\n{exams}\n\n"
        f"💼 <b>Карьера:</b>\n{careers}\n",
        parse_mode="HTML",
        reply_markup=summary_keyboard(),
    )
    await state.set_state(Form.summary)


def build_admin_message(data, user, consent_phone: str) -> str:
    username = f"@{user.username}" if user.username else "не указан"
    full_name = " ".join(x for x in [user.first_name, user.last_name] if x) or "не указано"

    exams = "\n".join(f"• {esc(x)}" for x in data.get("exams", [])) or "не выбраны"
    careers = "\n".join(f"• {esc(x)}" for x in data.get("career", [])) or "не выбраны"

    return (
        "🆕 <b>НОВЫЙ ЛИД</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Имя:</b> {esc(full_name)}\n"
        f"💬 <b>Telegram:</b> {esc(username)}\n"
        f"🆔 <b>Telegram ID:</b> {user.id}\n"
        f"📱 <b>Телефон Telegram:</b> {esc(consent_phone)}\n"
        "🔐 <b>Согласие:</b> Да\n"
        f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        "📋 <b>Анкета:</b>\n"
        f"🏫 {esc(data.get('school'))}\n"
        f"🎓 {esc(data.get('class_number'))}\n"
        f"👤 {esc(data.get('surname'))} {esc(data.get('name'))} {esc(data.get('patronymic'))}\n"
        f"📱 {esc(data.get('student_phone'))}\n"
        f"👨‍👩‍👦 {esc(data.get('parent_phone'))}\n"
        f"📝 {exams}\n"
        f"💼 {careers}"
    )


# ============================================================
# START: СНАЧАЛА СОГЛАСИЕ
# ============================================================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(consent_phone=None)

    await message.answer(
        "👋 <b>Здравствуйте!</b>\n\n"
        "Перед началом необходимо ваше согласие:\n\n"
        f"<i>{esc(CONSENT_TEXT)}</i>",
        parse_mode="HTML",
        reply_markup=start_keyboard(),
    )
    await state.set_state(Form.consent)


@dp.callback_query(Form.consent, F.data == "consent_yes")
async def consent_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "✅ <b>Согласие получено.</b>\n\n"
        "Теперь поделитесь вашим номером Telegram.\n"
        "Нажмите кнопку ниже.",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "📱 <b>Поделиться номером Telegram</b>",
        parse_mode="HTML",
        reply_markup=phone_share_keyboard(),
    )
    await state.set_state(Form.contact)


@dp.callback_query(Form.consent, F.data == "consent_no")
async def consent_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ Без согласия обработка данных невозможна.\n\n"
        "Чтобы начать заново, нажмите /start."
    )


# ============================================================
# КОНТАКТ СРАЗУ ПОСЛЕ СОГЛАСИЯ
# ============================================================
@dp.message(Form.contact, F.contact)
async def save_contact(message: Message, state: FSMContext):
    contact = message.contact
    user = message.from_user

    # Принимаем только контакт самого пользователя.
    if contact.user_id is not None and contact.user_id != user.id:
        await message.answer(
            "Пожалуйста, отправьте именно свой номер телефона.",
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
                f"👤 Имя: {esc(user.first_name or '')} {esc(user.last_name or '')}\n"
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
            "⚠️ Не удалось передать номер ответственному сотруднику. "
            "Попробуйте ещё раз.",
            reply_markup=phone_share_keyboard(),
        )
        return

    # Сразу после согласия и передачи контакта отправляем сайт.
    await message.answer(
        "🎓 Спасибо!\n\n"
        "Сайт Московского международного университета:\n"
        f"{UNIVERSITY_URL}",
        reply_markup=ReplyKeyboardRemove(),
    )

    # После этого продолжаем анкету.
    await message.answer("Теперь можно заполнить анкету.")
    await ask_school(message, state)


@dp.message(Form.contact)
async def contact_not_shared(message: Message, state: FSMContext):
    await message.answer(
        "Чтобы продолжить, нажмите кнопку «📱 Поделиться номером Telegram».",
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
    value = callback.data.split(":", 1)[1]
    await state.update_data(class_number=value)
    await callback.answer()
    await callback.message.edit_text(f"Класс: {esc(value)}")
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
    await state.update_data(parent_phone=message.contact.phone_number)
    await ask_exams(message, state)


@dp.message(Form.parent_phone)
async def parent_phone_text(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ask_student_phone(message, state)
        return
    await state.update_data(parent_phone=message.text.strip())
    await ask_exams(message, state)


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
    await callback.message.edit_text("✅ Предметы сохранены.")
    await ask_career(callback.message, state)


@dp.callback_query(Form.exams, F.data == "back")
async def exams_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await ask_parent_phone(callback.message, state)


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
    )
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
        await callback.answer(
            "Выберите хотя бы один вариант.",
            show_alert=True,
        )
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
# РЕДАКТИРОВАНИЕ / ОТПРАВКА АНКЕТЫ
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
    consent_phone = data.get("consent_phone") or data.get("student_phone") or "не указан"

    try:
        await bot.send_message(
            ADMIN_ID,
            build_admin_message(data, user, consent_phone),
            parse_mode="HTML",
        )
    except Exception:
        logging.exception("Не удалось отправить анкету администратору.")
        await callback.answer()
        await callback.message.edit_text(
            "⚠️ Не удалось отправить анкету. Попробуйте ещё раз."
        )
        await state.clear()
        return

    await callback.answer("Анкета отправлена!")
    await callback.message.edit_text(
        "✅ <b>Анкета отправлена.</b>\n\n"
        "Спасибо за заполнение!",
        parse_mode="HTML",
    )
    await state.clear()


@dp.callback_query(Form.summary, F.data == "cancel_form")
async def cancel_form(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ Заполнение анкеты отменено.\n\n"
        "Чтобы начать снова, нажмите /start."
    )


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
    print("Telegram questionnaire bot is running")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
