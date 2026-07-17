import asyncio
import os
import logging
import json
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- НАСТРОЙКА ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not TOKEN:
    logger.error("TELEGRAM_TOKEN not set")
    raise RuntimeError("TELEGRAM_TOKEN not set")

# --- ДАННЫЕ ---
DATA_FILE = "bot_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "owner": None,
            "admins": {},
            "muted": {},
            "banned": {},
            "warns": {},
            "money": {},
            "exp": {},
            "level": {},
            "daily_bonus": {},
            "work": {},
            "games": {},
            "settings": {
                "welcome": "👋 Добро пожаловать в чат!",
                "rules": "1. Не материться\n2. Не спамить\n3. Уважать друг друга",
                "antispam": True
            },
            "message_history": {}
        }

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Save error: {e}")

data = load_data()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def is_admin(user_id: int) -> bool:
    if data.get("owner") == user_id:
        return True
    return str(user_id) in data.get("admins", {})

def is_banned(user_id: int) -> bool:
    if str(user_id) in data.get("banned", {}):
        if data["banned"][str(user_id)] > time.time():
            return True
        else:
            del data["banned"][str(user_id)]
            save_data(data)
    return False

def is_muted(user_id: int) -> bool:
    if str(user_id) in data.get("muted", {}):
        if data["muted"][str(user_id)] > time.time():
            return True
        else:
            del data["muted"][str(user_id)]
            save_data(data)
    return False

async def add_money(user_id: int, amount: int):
    data["money"][str(user_id)] = data["money"].get(str(user_id), 0) + amount
    save_data(data)

async def remove_money(user_id: int, amount: int) -> bool:
    current = data["money"].get(str(user_id), 0)
    if current < amount:
        return False
    data["money"][str(user_id)] = current - amount
    save_data(data)
    return True

# --- КОМАНДЫ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if data.get("owner") is None:
        data["owner"] = user.id
        save_data(data)
        await update.message.reply_text(f"👑 Вы назначены владельцем бота!")
    
    await update.message.reply_text(
        f"🤖 **Привет, {user.first_name}!**\n\n"
        "Я мощный бот-менеджер для Telegram!\n"
        "Используй /help для списка команд."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **Доступные команды:**

**👤 Для всех:**
/start — Начать
/help — Помощь
/profile — Профиль
/balance — Баланс
/daily — Ежедневный бонус
/top — Топ пользователей
/work — Устроиться на работу
/salary — Получить зарплату
/dice — Бросить кости
/coin — Орёл или решка
/casino [сумма] — Казино
/guess [число] — Угадать число (1-100)

**🛡️ Модерация (для админов):**
/mute [ID] [минут] — Заглушить
/unmute [ID] — Размутить
/kick [ID] — Кикнуть
/warn [ID] — Предупреждение
/ban [ID] [дней] — Забанить
/unban [ID] — Разбанить
/rules — Правила
/welcome [текст] — Приветствие

**👑 Администрирование:**
/add_admin [ID] — Добавить админа
/remove_admin [ID] — Удалить админа
/settings — Настройки
"""
    await update.message.reply_text(help_text)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    money = data.get("money", {}).get(str(user_id), 0)
    exp = data.get("exp", {}).get(str(user_id), 0)
    level = data.get("level", {}).get(str(user_id), 1)
    warns = data.get("warns", {}).get(str(user_id), 0)
    is_muted_user = is_muted(user_id)
    is_banned_user = is_banned(user_id)
    
    status = "✅ Активен"
    if is_banned_user:
        status = "🔴 Забанен"
    elif is_muted_user:
        status = "🔇 Заглушен"
    
    text = f"""
👤 **Профиль**
Имя: {name}
ID: {user_id}
Монет: {money}
Опыт: {exp}
Уровень: {level}
Предупреждений: {warns}/3
Статус: {status}
"""
    await update.message.reply_text(text)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    money = data.get("money", {}).get(str(user_id), 0)
    await update.message.reply_text(f"💰 Ваш баланс: {money} монет")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    last_bonus = data.get("daily_bonus", {}).get(str(user_id), 0)
    now = time.time()
    if now - last_bonus < 86400:
        remaining = int(86400 - (now - last_bonus))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(f"⏳ Бонус через {hours}ч {minutes}м")
        return
    bonus = random.randint(1000, 5000)
    await add_money(user_id, bonus)
    data["daily_bonus"][str(user_id)] = now
    save_data(data)
    await update.message.reply_text(f"🎁 Ежедневный бонус: {bonus} монет!")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_users = sorted(data.get("money", {}).items(), key=lambda x: x[1], reverse=True)[:10]
    if not sorted_users:
        await update.message.reply_text("📋 Нет данных")
        return
    text = "🏆 **Топ богачей:**\n"
    for i, (uid, money) in enumerate(sorted_users, 1):
        name = "User"
        try:
            user = await context.bot.get_chat(int(uid))
            name = user.first_name or "User"
        except:
            pass
        text += f"{i}. {name} — {money} монет\n"
    await update.message.reply_text(text)

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jobs = ["Программист", "Дизайнер", "Менеджер", "Копирайтер", "Маркетолог", "Аналитик"]
    if str(user_id) in data.get("work", {}):
        job = data["work"][str(user_id)]
        await update.message.reply_text(f"💼 Вы уже работаете {job.get('job', '')}")
        return
    job = random.choice(jobs)
    data["work"][str(user_id)] = {"job": job, "start": time.time()}
    save_data(data)
    await update.message.reply_text(f"✅ Вы устроились на работу: {job}!")

async def salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) not in data.get("work", {}):
        await update.message.reply_text("❌ Вы не работаете! Используйте /work")
        return
    work = data["work"][str(user_id)]
    hours = (time.time() - work["start"]) / 3600
    if hours < 2:
        remaining = int((2 - hours) * 60)
        await update.message.reply_text(f"⏳ Работайте ещё {remaining} минут")
        return
    salary = int(500 * hours)
    await add_money(user_id, salary)
    data["work"][str(user_id)]["start"] = time.time()
    save_data(data)
    await update.message.reply_text(f"💰 Зарплата: {salary} монет!")

# --- ИГРЫ ---

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sides = 6
    if context.args and context.args[0].isdigit():
        sides = min(max(int(context.args[0]), 2), 100)
    result = random.randint(1, sides)
    await update.message.reply_text(f"🎲 Выпало: {result} (1-{sides})")

async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["🦅 Орёл", "🪙 Решка"])
    await update.message.reply_text(f"{result}")

async def casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Использование: /casino [сумма]")
        return
    user_id = update.effective_user.id
    amount = int(context.args[0])
    if not await remove_money(user_id, amount):
        await update.message.reply_text("❌ Недостаточно монет!")
        return
    multiplier = random.choice([0, 0.5, 1, 2, 3, 5, 10])
    result = int(amount * multiplier)
    await add_money(user_id, result)
    if result > amount:
        await update.message.reply_text(f"🎉 Выиграл {result} монет! (+{result-amount})")
    elif result == amount:
        await update.message.reply_text("🤝 Ставка вернулась")
    else:
        await update.message.reply_text(f"😢 Проиграл {amount-result} монет")

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Введите число: /guess [число] (1-100)")
        return
    user_id = update.effective_user.id
    guess_num = int(context.args[0])
    if guess_num < 1 or guess_num > 100:
        await update.message.reply_text("❌ Число должно быть от 1 до 100!")
        return
    if "guess_number" not in data:
        data["guess_number"] = {}
    if str(user_id) not in data["guess_number"]:
        data["guess_number"][str(user_id)] = random.randint(1, 100)
        await update.message.reply_text("🎯 Я загадал число от 1 до 100. Угадай!")
        return
    target = data["guess_number"][str(user_id)]
    if guess_num < target:
        await update.message.reply_text("📈 Больше!")
    elif guess_num > target:
        await update.message.reply_text("📉 Меньше!")
    else:
        await update.message.reply_text(f"🎉 Угадал! Это было {target}!")
        await add_money(user_id, 500)
        del data["guess_number"][str(user_id)]
        save_data(data)

# --- МОДЕРАЦИЯ ---

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /mute [ID] [минут]")
        return
    try:
        target_id = int(context.args[0])
        minutes = int(context.args[1]) if len(context.args) > 1 else 5
        data["muted"][str(target_id)] = time.time() + (minutes * 60)
        save_data(data)
        await update.message.reply_text(f"🔇 Пользователь заглушен на {minutes} минут!")
    except:
        await update.message.reply_text("❌ Ошибка! Используйте: /mute [ID] [минут]")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /unmute [ID]")
        return
    try:
        target_id = int(context.args[0])
        if str(target_id) in data.get("muted", {}):
            del data["muted"][str(target_id)]
            save_data(data)
            await update.message.reply_text(f"✅ Пользователь размучен!")
        else:
            await update.message.reply_text("❌ Не заглушен!")
    except:
        await update.message.reply_text("❌ Ошибка!")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /kick [ID]")
        return
    try:
        target_id = int(context.args[0])
        await context.bot.ban_chat_member(update.effective_chat.id, target_id)
        await context.bot.unban_chat_member(update.effective_chat.id, target_id)
        await update.message.reply_text(f"👢 Пользователь кикнут!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /warn [ID]")
        return
    try:
        target_id = int(context.args[0])
        data["warns"][str(target_id)] = data.get("warns", {}).get(str(target_id), 0) + 1
        warns = data["warns"][str(target_id)]
        save_data(data)
        if warns >= 3:
            data["banned"][str(target_id)] = time.time() + (7 * 24 * 60 * 60)
            save_data(data)
            await update.message.reply_text(f"🚫 Пользователь забанен на 7 дней (3 предупреждения)!")
        else:
            await update.message.reply_text(f"⚠️ Предупреждение {warns}/3")
    except:
        await update.message.reply_text("❌ Ошибка!")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /ban [ID] [дней]")
        return
    try:
        target_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 7
        data["banned"][str(target_id)] = time.time() + (days * 24 * 60 * 60)
        save_data(data)
        await context.bot.ban_chat_member(update.effective_chat.id, target_id)
        await update.message.reply_text(f"🚫 Пользователь забанен на {days} дней!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /unban [ID]")
        return
    try:
        target_id = int(context.args[0])
        if str(target_id) in data.get("banned", {}):
            del data["banned"][str(target_id)]
            save_data(data)
            await context.bot.unban_chat_member(update.effective_chat.id, target_id)
            await update.message.reply_text(f"✅ Пользователь разбанен!")
        else:
            await update.message.reply_text("❌ Не забанен!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = data.get("settings", {}).get("rules", "Правила не установлены")
    await update.message.reply_text(f"📋 **Правила чата:**\n{rules_text}")

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /welcome [текст]")
        return
    welcome = " ".join(context.args)
    data["settings"]["welcome"] = welcome
    save_data(data)
    await update.message.reply_text("✅ Приветствие установлено!")

# --- АДМИНИСТРИРОВАНИЕ ---

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /add_admin [ID]")
        return
    try:
        target_id = int(context.args[0])
        data["admins"][str(target_id)] = True
        save_data(data)
        await update.message.reply_text(f"✅ Администратор добавлен!")
    except:
        await update.message.reply_text("❌ Ошибка!")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /remove_admin [ID]")
        return
    try:
        target_id = int(context.args[0])
        if str(target_id) in data.get("admins", {}):
            del data["admins"][str(target_id)]
            save_data(data)
            await update.message.reply_text(f"✅ Администратор удален!")
        else:
            await update.message.reply_text("❌ Не администратор!")
    except:
        await update.message.reply_text("❌ Ошибка!")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав!")
        return
    settings = data.get("settings", {})
    text = f"""
⚙️ **Настройки бота:**

Приветствие: {settings.get('welcome', 'Не установлено')}
Антиспам: {'✅' if settings.get('antispam', True) else '❌'}
"""
    await update.message.reply_text(text)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if is_banned(user_id):
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
        except:
            pass
        return
    
    if is_muted(user_id):
        try:
            await update.message.delete()
        except:
            pass
        return

# --- ОСНОВНОЙ ЗАПУСК ---

async def main():
    app = Application.builder().token(TOKEN).build()

    # Команды для всех
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("work", work))
    app.add_handler(CommandHandler("salary", salary))
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("coin", coin))
    app.add_handler(CommandHandler("casino", casino))
    app.add_handler(CommandHandler("guess", guess))

    # Модерация
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("welcome", set_welcome))

    # Администрирование
    app.add_handler(CommandHandler("add_admin", add_admin))
    app.add_handler(CommandHandler("remove_admin", remove_admin))
    app.add_handler(CommandHandler("settings", settings))

    # Обработчик сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
