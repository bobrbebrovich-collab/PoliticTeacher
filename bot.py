import os
import json
import logging
import sqlite3
from datetime import datetime
from typing import Optional

from xai_sdk import Client
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# НАСТРОЙКИ
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4-1-fast-reasoning")
DB_PATH = os.getenv("DB_PATH", "politics_tutor.db")

if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN")
if not XAI_API_KEY:
    raise RuntimeError("Не найден XAI_API_KEY")

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = Client(api_key=XAI_API_KEY)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📚 Начать обучение", "🧠 Выбрать тему"],
        ["❓ Задать вопрос", "📝 Мини-тест"],
        ["📈 Мой прогресс", "🔁 Повторить тему"],
        ["⚙️ Сменить уровень", "ℹ️ Помощь"],
    ],
    resize_keyboard=True,
)

TOPIC_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Государство", "Формы правления"],
        ["Демократия", "Авторитаризм"],
        ["Либерализм", "Консерватизм"],
        ["Социализм", "Национализм"],
        ["Французская революция", "Первая мировая"],
        ["Вторая мировая", "Холодная война"],
        ["СССР", "Международные отношения"],
        ["⬅️ Назад"],
    ],
    resize_keyboard=True,
)

LEVELS = ["Новичок", "Школьник", "Студент", "Продвинутый"]
LEVEL_KEYBOARD = ReplyKeyboardMarkup(
    [[level] for level in LEVELS] + [["⬅️ Назад"]],
    resize_keyboard=True,
)

SYSTEM_PROMPT = """
Ты — AI-репетитор по политике, политологии, истории, идеологиям и международным отношениям.

Твои правила:
1. Объясняй по-русски, ясно, спокойно и по шагам.
2. Не пиши как сухая энциклопедия. Объясняй как сильный репетитор.
3. Всегда учитывай уровень ученика: Новичок, Школьник, Студент, Продвинутый.
4. Если тема сложная, сначала дай простое объяснение, потом структуру, потом примеры.
5. Когда уместно, раскрывай:
   - определение
   - причины
   - суть
   - примеры
   - последствия
   - сравнение с похожими явлениями
6. Если пользователь просит тему для изучения, строй мини-урок:
   - Что это
   - Почему это важно
   - Ключевые идеи / события
   - Пример
   - Краткий вывод
   - 2–3 вопроса на закрепление
7. Если пользователь задаёт вопрос по событию, объясняй контекст, участников, причины и последствия.
8. Если пользователь просит сравнение идеологий или режимов, делай понятную сравнительную подачу.
9. Не выдумывай факты. Если в чём-то не уверен, прямо скажи об этом.
10. Не агитируй за политические силы. Объясняй нейтрально и учебно.
11. Не перегружай ответ лишними датами, если пользователь не просил глубокий уровень.
12. Завершай обучение вопросом или мини-проверкой, если это уместно.
""".strip()

HELP_TEXT = """
Я — бот-репетитор по политике и истории.

Что я умею:
- объяснять политические темы по шагам
- разбирать идеологии и формы правления
- рассказывать про исторические события
- задавать вопросы для закрепления
- делать мини-тесты
- подстраиваться под твой уровень

Команды:
/start — запуск
/help — помощь
/reset — сбросить историю диалога
/topic — выбрать тему
/level — сменить уровень
/progress — посмотреть прогресс
""".strip()


# =========================
# БАЗА ДАННЫХ
# =========================
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            level TEXT DEFAULT 'Новичок',
            current_topic TEXT,
            messages_count INTEGER DEFAULT 0,
            tests_count INTEGER DEFAULT 0,
            last_seen TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


# =========================
# РАБОТА С ПОЛЬЗОВАТЕЛЕМ
# =========================
def ensure_user(user_id: int, username: Optional[str], full_name: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cur.fetchone()

    if exists:
        cur.execute(
            """
            UPDATE users
            SET username = ?, full_name = ?, last_seen = ?
            WHERE user_id = ?
            """,
            (username, full_name, datetime.utcnow().isoformat(), user_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO users (user_id, username, full_name, last_seen)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username, full_name, datetime.utcnow().isoformat()),
        )

    conn.commit()
    conn.close()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_level(user_id: int, level: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET level = ? WHERE user_id = ?", (level, user_id))
    conn.commit()
    conn.close()


def update_topic(user_id: int, topic: Optional[str]) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET current_topic = ? WHERE user_id = ?", (topic, user_id))
    conn.commit()
    conn.close()


def increment_messages(user_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET messages_count = COALESCE(messages_count, 0) + 1 WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def increment_tests(user_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET tests_count = COALESCE(tests_count, 0) + 1 WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def save_message(user_id: int, role: str, content: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content),
    )
    conn.commit()
    conn.close()


def clear_history(user_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_recent_history(user_id: int, limit: int = 12) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT role, content
        FROM messages
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()

    rows = list(reversed(rows))
    return [{"role": row["role"], "content": row["content"]} for row in rows]


# =========================
# XAI / GROK
# =========================
def build_user_prompt(
    user_level: str,
    current_topic: Optional[str],
    user_text: str,
    mode: str = "normal",
) -> str:
    payload = {
        "user_level": user_level,
        "current_topic": current_topic,
        "mode": mode,
        "user_request": user_text,
        "response_rules": {
            "language": "ru",
            "style": "понятно, структурно, как сильный репетитор",
            "ask_follow_up_questions": True,
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def extract_text_from_response(response) -> str:
    if hasattr(response, "output") and response.output:
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content in getattr(item, "content", []):
                    if getattr(content, "type", None) == "output_text":
                        return getattr(content, "text", "").strip()
    return "Не удалось получить ответ от Grok."


def ask_tutor(user_id: int, user_text: str, mode: str = "normal") -> str:
    user = get_user(user_id)
    level = user["level"] if user else "Новичок"
    topic = user["current_topic"] if user else None

    history = get_recent_history(user_id, limit=10)

    input_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    input_messages.extend(history)
    input_messages.append(
        {
            "role": "user",
            "content": build_user_prompt(level, topic, user_text, mode=mode),
        }
    )

    response = client.responses.create(
        model=XAI_MODEL,
        input=input_messages,
    )
    return extract_text_from_response(response)


# =========================
# ТЕКСТЫ ДЛЯ БЫСТРЫХ ДЕЙСТВИЙ
# =========================
def lesson_prompt_for_topic(topic: str) -> str:
    return (
        f"Проведи мне мини-урок по теме '{topic}'. "
        "Сначала объясни очень просто, затем дай более точную структуру. "
        "Добавь примеры, ключевые идеи, а в конце задай 3 вопроса для проверки."
    )


def test_prompt(current_topic: Optional[str]) -> str:
    if current_topic:
        return (
            f"Сделай мини-тест по теме '{current_topic}'. "
            "Дай 5 вопросов разного типа без ответов сразу. "
            "В конце попроси меня ответить по пунктам."
        )
    return (
        "Сделай общий мини-тест по базовой политике и истории. "
        "Дай 5 вопросов без ответов сразу. В конце попроси меня ответить по пунктам."
    )


def repeat_prompt(current_topic: Optional[str]) -> str:
    if current_topic:
        return (
            f"Повтори тему '{current_topic}' кратко и понятно. "
            "Сделай это как повторение перед тестом: самое важное, ключевые различия, 3 контрольных вопроса."
        )
    return "Выбери базовую тему по политике для повторения и кратко объясни её."


# =========================
# TELEGRAM HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ensure_user(user.id, user.username, user.full_name)

    text = (
        f"Привет, {user.first_name}.\n\n"
        "Я твой AI-репетитор по политике, истории и идеологиям.\n"
        "Могу объяснять темы по шагам, проводить мини-уроки и делать тесты.\n\n"
        "Выбери действие на клавиатуре ниже."
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, reply_markup=MAIN_KEYBOARD)


async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Выбери тему:", reply_markup=TOPIC_KEYBOARD)


async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Выбери уровень обучения:", reply_markup=LEVEL_KEYBOARD)


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Сначала нажми /start")
        return

    text = (
        "Твой прогресс:\n\n"
        f"Уровень: {user['level']}\n"
        f"Текущая тема: {user['current_topic'] or 'не выбрана'}\n"
        f"Сообщений в обучении: {user['messages_count']}\n"
        f"Мини-тестов: {user['tests_count']}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    clear_history(user_id)
    update_topic(user_id, None)
    await update.message.reply_text(
        "История диалога и текущая тема сброшены.",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    ensure_user(user.id, user.username, user.full_name)
    text = update.message.text.strip()

    if text == "ℹ️ Помощь":
        await update.message.reply_text(HELP_TEXT, reply_markup=MAIN_KEYBOARD)
        return

    if text == "🧠 Выбрать тему":
        await update.message.reply_text("Выбери тему:", reply_markup=TOPIC_KEYBOARD)
        return

    if text == "⚙️ Сменить уровень":
        await update.message.reply_text("Выбери уровень:", reply_markup=LEVEL_KEYBOARD)
        return

    if text == "📈 Мой прогресс":
        await progress_command(update, context)
        return

    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=MAIN_KEYBOARD)
        return

    if text in LEVELS:
        update_level(user.id, text)
        await update.message.reply_text(
            f"Уровень изменён на: {text}",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    topic_buttons = {
        "Государство",
        "Формы правления",
        "Демократия",
        "Авторитаризм",
        "Либерализм",
        "Консерватизм",
        "Социализм",
        "Национализм",
        "Французская революция",
        "Первая мировая",
        "Вторая мировая",
        "Холодная война",
        "СССР",
        "Международные отношения",
    }

    if text in topic_buttons:
        update_topic(user.id, text)
        prompt = lesson_prompt_for_topic(text)

        await update.message.reply_text("Готовлю мини-урок...")
        answer = ask_tutor(user.id, prompt, mode="lesson")

        save_message(user.id, "user", prompt)
        save_message(user.id, "assistant", answer)
        increment_messages(user.id)

        await update.message.reply_text(answer, reply_markup=MAIN_KEYBOARD)
        return

    if text == "📚 Начать обучение":
        prompt = (
            "Начни первое занятие по политике для меня. "
            "Сначала объясни, что такое политика, государство и власть. "
            "Сделай это доступно, как вводный урок, и в конце задай 3 вопроса."
        )
        await update.message.reply_text("Начинаем обучение...")
        answer = ask_tutor(user.id, prompt, mode="lesson")

        save_message(user.id, "user", prompt)
        save_message(user.id, "assistant", answer)
        increment_messages(user.id)

        await update.message.reply_text(answer, reply_markup=MAIN_KEYBOARD)
        return

    if text == "📝 Мини-тест":
        current_user = get_user(user.id)
        current_topic = current_user["current_topic"] if current_user else None
        prompt = test_prompt(current_topic)

        await update.message.reply_text("Составляю мини-тест...")
        answer = ask_tutor(user.id, prompt, mode="test")

        save_message(user.id, "user", prompt)
        save_message(user.id, "assistant", answer)
        increment_messages(user.id)
        increment_tests(user.id)

        await update.message.reply_text(answer, reply_markup=MAIN_KEYBOARD)
        return

    if text == "🔁 Повторить тему":
        current_user = get_user(user.id)
        current_topic = current_user["current_topic"] if current_user else None
        prompt = repeat_prompt(current_topic)

        await update.message.reply_text("Делаю краткое повторение...")
        answer = ask_tutor(user.id, prompt, mode="repeat")

        save_message(user.id, "user", prompt)
        save_message(user.id, "assistant", answer)
        increment_messages(user.id)

        await update.message.reply_text(answer, reply_markup=MAIN_KEYBOARD)
        return

    if text == "❓ Задать вопрос":
        await update.message.reply_text(
            "Напиши любой вопрос по политике, истории, идеологиям или государственному устройству.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await update.message.reply_text("Думаю над ответом...")
    answer = ask_tutor(user.id, text, mode="normal")

    save_message(user.id, "user", text)
    save_message(user.id, "assistant", answer)
    increment_messages(user.id)

    await update.message.reply_text(answer, reply_markup=MAIN_KEYBOARD)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка во время обработки апдейта:", exc_info=context.error)


# =========================
# ЗАПУСК
# =========================
def main() -> None:
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("topic", topic_command))
    app.add_handler(CommandHandler("level", level_command))
    app.add_handler(CommandHandler("progress", progress_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()