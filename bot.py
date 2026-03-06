import os
import logging
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ------------------- LOGGING -------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ------------------- ENV KEYS -------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_TOKEN")
if not GROQ_API_KEY:
    raise RuntimeError("Не задан GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# Простая память в оперативке
chat_histories = {}
user_progress = {}

# ------------------- SYSTEM PROMPT -------------------
SYSTEM_PROMPT = """
Ты — личный AI-репетитор по политике, политологии, истории, идеологиям, государственному устройству и международным отношениям.

ТВОЯ ЦЕЛЬ:
Обучать ученика политике с нуля до уверенного понимания тем:
- что такое государство и власть
- формы правления
- политические режимы
- идеологии
- важнейшие исторические события
- международные отношения
- сравнение стран, систем и эпох

ПРОГРАММА ОБУЧЕНИЯ:

МОДУЛЬ 1 — БАЗА ПОЛИТИКИ
  Урок 1.1: Что такое политика
  Урок 1.2: Что такое государство
  Урок 1.3: Что такое власть
  Урок 1.4: Суверенитет, закон, легитимность
  Урок 1.5: Общество, элиты, институты

МОДУЛЬ 2 — ГОСУДАРСТВЕННОЕ УСТРОЙСТВО
  Урок 2.1: Монархия и республика
  Урок 2.2: Парламентская и президентская система
  Урок 2.3: Федерация и унитарное государство
  Урок 2.4: Разделение властей
  Урок 2.5: Конституция и законы

МОДУЛЬ 3 — ПОЛИТИЧЕСКИЕ РЕЖИМЫ
  Урок 3.1: Демократия
  Урок 3.2: Авторитаризм
  Урок 3.3: Тоталитаризм
  Урок 3.4: Диктатура и признаки режима
  Урок 3.5: Сравнение режимов

МОДУЛЬ 4 — ИДЕОЛОГИИ
  Урок 4.1: Либерализм
  Урок 4.2: Консерватизм
  Урок 4.3: Социализм
  Урок 4.4: Коммунизм
  Урок 4.5: Национализм
  Урок 4.6: Фашизм
  Урок 4.7: Сравнение идеологий

МОДУЛЬ 5 — ИСТОРИЧЕСКИЕ СОБЫТИЯ
  Урок 5.1: Французская революция
  Урок 5.2: Наполеон и Европа
  Урок 5.3: Первая мировая война
  Урок 5.4: Вторая мировая война
  Урок 5.5: СССР
  Урок 5.6: Холодная война
  Урок 5.7: Распад СССР

МОДУЛЬ 6 — МЕЖДУНАРОДНЫЕ ОТНОШЕНИЯ
  Урок 6.1: Что такое геополитика
  Урок 6.2: Государства и интересы
  Урок 6.3: Союзы и блоки
  Урок 6.4: ООН, НАТО, ЕС
  Урок 6.5: Причины конфликтов
  Урок 6.6: Санкции, дипломатия, баланс сил

МОДУЛЬ 7 — ПРАКТИКА И ПРОВЕРКА
  Урок 7.1: Как анализировать политическое событие
  Урок 7.2: Как сравнивать страны и режимы
  Урок 7.3: Как видеть причины и последствия
  Урок 7.4: Мини-экзамен
  Урок 7.5: Финальная проверка

КАК ВЕСТИ УРОКИ:
1) Начинай урок с названия темы
2) Объясняй по структуре:
   🔷 Что это
   🔷 Почему это важно
   🔷 Как это работает
   🔷 Исторический или жизненный пример
   🔷 С чем это часто путают
   🔷 Типичная ошибка новичка
   🔷 2-3 вопроса на закрепление
3) Не переходи дальше, пока ученик не понял основу
4) В конце каждого урока обязательно давай:
   📝 ДОМАШНЕЕ ЗАДАНИЕ:
   [короткое практическое задание по теме]
5) После домашнего задания предложи следующий урок

ПРАВИЛА ОБЩЕНИЯ:
- Пиши по-русски
- Простыми словами
- Без воды
- Если тема сложная — сначала объясни очень просто, потом глубже
- Если ученик пишет "не понял", объясни через аналогию из жизни
- Не агитируй и не продвигай политические силы
- Объясняй учебно и нейтрально
- Отвечай как сильный репетитор, а не как сухая энциклопедия
"""

# ------------------- MODULES -------------------
MODULES = {
    "1": {
        "name": "📘 Модуль 1 — База политики",
        "lessons": [
            ("1.1", "Что такое политика"),
            ("1.2", "Что такое государство"),
            ("1.3", "Что такое власть"),
            ("1.4", "Суверенитет, закон, легитимность"),
            ("1.5", "Общество, элиты, институты"),
        ],
    },
    "2": {
        "name": "🏛 Модуль 2 — Государственное устройство",
        "lessons": [
            ("2.1", "Монархия и республика"),
            ("2.2", "Парламентская и президентская система"),
            ("2.3", "Федерация и унитарное государство"),
            ("2.4", "Разделение властей"),
            ("2.5", "Конституция и законы"),
        ],
    },
    "3": {
        "name": "⚖️ Модуль 3 — Политические режимы",
        "lessons": [
            ("3.1", "Демократия"),
            ("3.2", "Авторитаризм"),
            ("3.3", "Тоталитаризм"),
            ("3.4", "Диктатура и признаки режима"),
            ("3.5", "Сравнение режимов"),
        ],
    },
    "4": {
        "name": "🧠 Модуль 4 — Идеологии",
        "lessons": [
            ("4.1", "Либерализм"),
            ("4.2", "Консерватизм"),
            ("4.3", "Социализм"),
            ("4.4", "Коммунизм"),
            ("4.5", "Национализм"),
            ("4.6", "Фашизм"),
            ("4.7", "Сравнение идеологий"),
        ],
    },
    "5": {
        "name": "📜 Модуль 5 — Исторические события",
        "lessons": [
            ("5.1", "Французская революция"),
            ("5.2", "Наполеон и Европа"),
            ("5.3", "Первая мировая война"),
            ("5.4", "Вторая мировая война"),
            ("5.5", "СССР"),
            ("5.6", "Холодная война"),
            ("5.7", "Распад СССР"),
        ],
    },
    "6": {
        "name": "🌍 Модуль 6 — Международные отношения",
        "lessons": [
            ("6.1", "Что такое геополитика"),
            ("6.2", "Государства и интересы"),
            ("6.3", "Союзы и блоки"),
            ("6.4", "ООН, НАТО, ЕС"),
            ("6.5", "Причины конфликтов"),
            ("6.6", "Санкции, дипломатия, баланс сил"),
        ],
    },
    "7": {
        "name": "🎯 Модуль 7 — Практика и проверка",
        "lessons": [
            ("7.1", "Как анализировать политическое событие"),
            ("7.2", "Как сравнивать страны и режимы"),
            ("7.3", "Причины и последствия"),
            ("7.4", "Мини-экзамен"),
            ("7.5", "Финальная проверка"),
        ],
    },
}

# ------------------- KEYBOARDS -------------------
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📚 Все уроки", callback_data="show_modules")],
        [InlineKeyboardButton("▶️ Начать с первого урока", callback_data="lesson_1.1")],
        [InlineKeyboardButton("📈 Мой прогресс", callback_data="progress")],
        [InlineKeyboardButton("🔄 Сбросить историю", callback_data="reset")],
    ]
    return InlineKeyboardMarkup(keyboard)

def modules_keyboard():
    keyboard = []
    for mod_id, mod_data in MODULES.items():
        keyboard.append([InlineKeyboardButton(mod_data["name"], callback_data=f"module_{mod_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def lessons_keyboard(module_id: str):
    module = MODULES[module_id]
    keyboard = []
    for lesson_id, lesson_name in module["lessons"]:
        keyboard.append([InlineKeyboardButton(f"📖 {lesson_id} — {lesson_name}", callback_data=f"lesson_{lesson_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к модулям", callback_data="show_modules")])
    return InlineKeyboardMarkup(keyboard)

# ------------------- HELPERS -------------------
async def send_long_text(bot, chat_id: int, text: str, reply_markup=None, chunk_size: int = 3500):
    if not text:
        text = "(пустой ответ)"
    for i in range(0, len(text), chunk_size):
        part = text[i:i + chunk_size]
        await bot.send_message(
            chat_id=chat_id,
            text=part,
            reply_markup=reply_markup if i == 0 else None
        )

def get_user_history(user_id: int):
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    return chat_histories[user_id]

def get_user_progress(user_id: int):
    if user_id not in user_progress:
        user_progress[user_id] = {
            "current_lesson": None,
            "completed_lessons": []
        }
    return user_progress[user_id]

def trim_history(history, max_items: int = 30):
    if len(history) > max_items:
        return history[-max_items:]
    return history

def groq_answer(history):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        max_tokens=1200,
        temperature=0.7,
    )
    return response.choices[0].message.content

def mark_lesson_started(user_id: int, lesson_id: str):
    progress = get_user_progress(user_id)
    progress["current_lesson"] = lesson_id

def mark_lesson_completed(user_id: int, lesson_id: str):
    progress = get_user_progress(user_id)
    if lesson_id not in progress["completed_lessons"]:
        progress["completed_lessons"].append(lesson_id)

def build_progress_text(user_id: int) -> str:
    progress = get_user_progress(user_id)
    completed = progress["completed_lessons"]
    current = progress["current_lesson"] or "ещё не выбран"

    total_lessons = sum(len(module["lessons"]) for module in MODULES.values())

    return (
        "📈 Твой прогресс\n\n"
        f"Текущий урок: {current}\n"
        f"Пройдено уроков: {len(completed)} из {total_lessons}\n\n"
        f"Список пройденных: {', '.join(completed) if completed else 'пока пусто'}"
    )

# ------------------- HANDLERS -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет.\n\n"
        "Я твой AI-репетитор по политике, идеологиям, истории и международным отношениям.\n\n"
        "У тебя здесь полноценная программа обучения с уроками, вопросами и домашними заданиями.\n\n"
        "Выбери, с чего начать.",
        reply_markup=main_menu_keyboard(),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu_keyboard())
        return

    if data == "show_modules":
        await query.edit_message_text("📚 Выбери модуль:", reply_markup=modules_keyboard())
        return

    if data == "progress":
        await query.edit_message_text(
            build_progress_text(user_id),
            reply_markup=main_menu_keyboard()
        )
        return

    if data.startswith("module_"):
        module_id = data.split("_", 1)[1]
        module = MODULES.get(module_id)
        if not module:
            await query.edit_message_text("Такого модуля нет.", reply_markup=modules_keyboard())
            return
        await query.edit_message_text(
            f"{module['name']}\n\nВыбери урок:",
            reply_markup=lessons_keyboard(module_id)
        )
        return

    if data == "reset":
        chat_histories.pop(user_id, None)
        user_progress.pop(user_id, None)
        await query.edit_message_text(
            "История и прогресс очищены.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if data.startswith("lesson_"):
        lesson_id = data.split("_", 1)[1]
        history = get_user_history(user_id)
        mark_lesson_started(user_id, lesson_id)

        lesson_prompt = (
            f"Начни урок {lesson_id} по программе. "
            f"Проведи полный урок по структуре: что это, почему важно, как работает, пример, с чем путают, ошибка новичка, 2-3 вопроса на закрепление. "
            f"В конце обязательно дай домашнее задание и предложи следующий урок."
        )

        history.append({"role": "user", "content": lesson_prompt})
        chat_histories[user_id] = trim_history(history)

        try:
            await query.edit_message_text(f"⏳ Загружаю урок {lesson_id}...")
        except Exception:
            pass

        try:
            reply = groq_answer(chat_histories[user_id])
            chat_histories[user_id].append({"role": "assistant", "content": reply})
            chat_histories[user_id] = trim_history(chat_histories[user_id])

            keyboard = [
                [InlineKeyboardButton("✅ Отметить урок как пройденный", callback_data=f"complete_{lesson_id}")],
                [InlineKeyboardButton("📚 Выбрать другой урок", callback_data="show_modules")]
            ]

            await send_long_text(
                context.bot,
                query.message.chat_id,
                reply,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logging.exception("Ошибка в уроке: %s", e)
            await context.bot.send_message(chat_id=query.message.chat_id, text="Ошибка, попробуй ещё раз.")
        return

    if data.startswith("complete_"):
        lesson_id = data.split("_", 1)[1]
        mark_lesson_completed(user_id, lesson_id)
        await query.edit_message_text(
            f"Урок {lesson_id} отмечен как пройденный.\n\n"
            f"{build_progress_text(user_id)}",
            reply_markup=main_menu_keyboard(),
        )
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = (update.message.text or "").strip()

    if not user_message:
        return

    history = get_user_history(user_id)
    history.append({"role": "user", "content": user_message})
    chat_histories[user_id] = trim_history(history)

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        reply = groq_answer(chat_histories[user_id])
        chat_histories[user_id].append({"role": "assistant", "content": reply})
        chat_histories[user_id] = trim_history(chat_histories[user_id])

        keyboard = [[InlineKeyboardButton("📚 Выбрать урок", callback_data="show_modules")]]

        await send_long_text(
            context.bot,
            update.effective_chat.id,
            reply,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logging.exception("Ошибка в сообщении: %s", e)
        await update.message.reply_text("Ошибка, попробуй ещё раз.")

# ------------------- RUN -------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
