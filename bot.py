import random
import json
import asyncio
from datetime import datetime, timedelta
from vkwave.bots import SimpleBotRouter, SimpleLongPollBot, simple_bot_message_handler
from vkwave.bots.core.dispatching import filters
from vkwave.types.responses import UsersGetResponse
from vkwave.types.objects import MessagesMessage

# ========== КОНФИГУРАЦИЯ ==========
TOKEN = "vk1.a.vD_wjQlAavWsTfRnzGElRSDldsjm_11FJftLVmok2aRZV2FEvtgwrop3q1-x8XBftgQ6bN_1jfkUl6iSLh6JM8xNBTx7t6v1WDBdWn-oXn5uCVIjoKbIH7btmmqHbmY4euV_sXDZ1IbPURTgeIGoJq4PRQAmRL0LielbKiH3yHG_mWY28KBdQh3WhTPw5l8nuvgzRoJLjmAzBKo8401RZw"
GROUP_ID = 239953393  # ID вашей группы (число)
ADMIN_IDS = [1118563484]  # Ваш VK ID

# ========== ХРАНИЛИЩЕ ДАННЫХ ==========
# В реальном проекте используйте БД (SQLite/PostgreSQL)
# Здесь для примера - словари в памяти
users_data = {}  # user_id: {"coins": 0, "level": 1, "exp": 0, "nick": None, "married_to": None, "role": "user"}
marriages = []   # [{"user1": id, "user2": id, "date": "..."}]
clans = {}       # "название": {"leader": id, "members": [], "treasury": 0}
shop_items = {
    "корона": 50000,
    "машина": 100000,
    "дом": 250000,
    "меч": 15000,
    "зелье": 5000
}
inventory = {}   # user_id: {"item": count}
warnings = {}    # user_id: [{"reason": "...", "date": "..."}]
afk_users = set()
banned_users = {} # user_id: {"until": datetime, "reason": ""}
muted_users = {}  # user_id: {"until": datetime, "reason": ""}
bonus_cooldown = {}  # user_id: datetime
daily_bonus = {}     # user_id: datetime
weekly_bonus = {}    # user_id: datetime
monthly_bonus = {}   # user_id: datetime

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_user(user_id):
    """Получить данные пользователя или создать новые"""
    if user_id not in users_data:
        users_data[user_id] = {
            "coins": 1000,
            "level": 1,
            "exp": 0,
            "nick": None,
            "married_to": None,
            "role": "user",
            "children": []
        }
    return users_data[user_id]

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_moderator(user_id):
    user = get_user(user_id)
    return user["role"] in ["admin", "moderator"] or is_admin(user_id)

def can_mute(user_id):
    return is_moderator(user_id) or is_admin(user_id)

def can_ban(user_id):
    return is_admin(user_id)

def get_mention(user_id):
    user = get_user(user_id)
    if user["nick"]:
        return f"@{user['nick']}"
    return f"[id{user_id}|пользователь]"

def get_level_exp(level):
    return level * 100 + 50

async def add_exp(user_id, amount):
    user = get_user(user_id)
    user["exp"] += amount
    required = get_level_exp(user["level"])
    while user["exp"] >= required:
        user["level"] += 1
        user["exp"] -= required
        required = get_level_exp(user["level"])
        # Можно отправить уведомление о повышении уровня

# ========== ОБРАБОТЧИКИ КОМАНД ==========
router = SimpleBotRouter()

# ---- ПРОФИЛЬ И ПОЛЬЗОВАТЕЛЬ ----
@simple_bot_message_handler(router, filters.Command("помощь"))
async def help_command(event):
    text = """📋 ПОЛНЫЙ СПИСОК КОМАНД БОТА

👤 ПРОФИЛЬ:
!профиль - Показать профиль
!монеты - Баланс монет
!бонус - Получить 100,000 монет (раз в час)
!ник [имя] - Установить никнейм
!рейтинг - Топ пользователей
!уровень - Ваш уровень
!опыт - Количество опыта
!афк - Отметить, что вы отошли

👑 РОЛИ:
!роли - Список ролей
!роль @user - Повысить роль
!удроль @user - Понизить роль

🛡️ МОДЕРАЦИЯ:
!мут @user [мин] - Заглушить
!размут @user - Размутить
!бан @user [дни] - Забанить
!разбан @user - Разбанить
!пред @user - Выдать предупреждение
!варн @user - Показать предупреждения
!варн сброс @user - Сбросить предупреждения
!кик @user - Кикнуть
!очистить [кол-во] - Удалить сообщения бота

💑 СЕМЬЯ:
!брак @user - Предложить брак
!браки - Список браков
!развод @user - Развестись
!усыновить @user - Усыновить
!удочерить @user - Удочерить
!семья - Информация о семье

💰 ЭКОНОМИКА:
!перевод @user [сумма] - Перевести монеты
!банк - Баланс банка
!банк пополнить [сумма] - Пополнить банк
!банк снять [сумма] - Снять с банка
!работа [профессия] - Устроиться на работу
!зарплата - Получить зарплату
!магазин - Список товаров
!купить [товар] - Купить товар
!инвентарь - Показать инвентарь

📅 БОНУСЫ:
!ежедневно - Ежедневный бонус
!еженедельно - Еженедельный бонус
!ежемесячно - Ежемесячный бонус

🎲 ИГРЫ И РАЗВЛЕЧЕНИЯ:
!слот [ставка] - Игровой автомат
!орёл [ставка] - Орёл/решка
!кнб @user - Камень-ножницы-бумага
!угадай - Угадай число
!шутка - Случайная шутка
!гороскоп [знак] - Гороскоп
!кофе, !чай, !пиво - Напитки
!погода [город] - Погода

🎬 РАЗНОЕ:
!аниме, !фильм, !игра, !музыка - Случайные рекомендации"""
    await event.answer(text)

@simple_bot_message_handler(router, filters.Command("профиль"))
async def profile_command(event):
    user = get_user(event.user_id)
    mention = get_mention(event.user_id)
    married = "Нет" if user["married_to"] is None else f"id{user['married_to']}"
    text = f"""👤 ПРОФИЛЬ {mention}
━━━━━━━━━━━━━━━━━
💰 Монеты: {user["coins"]}
⭐ Уровень: {user["level"]}
📈 Опыт: {user["exp"]}/{get_level_exp(user["level"])}
💍 В браке: {married}
👶 Детей: {len(user["children"])}
🎭 Роль: {user["role"]}"""
    await event.answer(text)

@simple_bot_message_handler(router, filters.Command("монеты"))
async def coins_command(event):
    user = get_user(event.user_id)
    await event.answer(f"💰 Ваш баланс: {user['coins']} монет")

@simple_bot_message_handler(router, filters.Command("бонус"))
async def bonus_command(event):
    user_id = event.user_id
    now = datetime.now()
    if user_id in bonus_cooldown and (now - bonus_cooldown[user_id]) < timedelta(hours=1):
        remaining = timedelta(hours=1) - (now - bonus_cooldown[user_id])
        await event.answer(f"⏳ Подождите {remaining.seconds//60} минут до следующего бонуса")
        return
    user = get_user(user_id)
    user["coins"] += 100000
    bonus_cooldown[user_id] = now
    await event.answer("🎉 Вы получили 100,000 монет! Приходите через час за новым бонусом!")

@simple_bot_message_handler(router, filters.Command("ник"))
async def nick_command(event):
    args = event.object.object.message.text.split(maxsplit=1)
    if len(args) < 2:
        await event.answer("❌ Укажите ник: !ник [имя]")
        return
    new_nick = args[1][:30]  # Ограничение длины
    user = get_user(event.user_id)
    user["nick"] = new_nick
    await event.answer(f"✅ Ваш никнейм установлен: {new_nick}")

@simple_bot_message_handler(router, filters.Command("рейтинг"))
async def rating_command(event):
    sorted_users = sorted(users_data.items(), key=lambda x: x[1]["coins"], reverse=True)[:10]
    text = "🏆 ТОП ПОЛЬЗОВАТЕЛЕЙ ПО МОНЕТАМ\n━━━━━━━━━━━━━━━━━\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        mention = get_mention(uid)
        text += f"{i}. {mention} — {data['coins']} монет\n"
    await event.answer(text)

@simple_bot_message_handler(router, filters.Command("уровень"))
async def level_command(event):
    user = get_user(event.user_id)
    await event.answer(f"⭐ Ваш уровень: {user['level']}")

@simple_bot_message_handler(router, filters.Command("опыт"))
async def exp_command(event):
    user = get_user(event.user_id)
    await event.answer(f"📈 Ваш опыт: {user['exp']}/{get_level_exp(user['level'])}")

@simple_bot_message_handler(router, filters.Command("афк"))
async def afk_command(event):
    if event.user_id in afk_users:
        afk_users.remove(event.user_id)
        await event.answer("✅ Вы вернулись!")
    else:
        afk_users.add(event.user_id)
        await event.answer("😴 Вы отмечены как AFK. Вас не беспокоить!")

# ---- РОЛИ ----
@simple_bot_message_handler(router, filters.Command("роли"))
async def roles_command(event):
    text = """👑 РОЛИ В ЧАТЕ:
━━━━━━━━━━━━━━━━━
👑 Администратор - полный доступ
🛡️ Модератор - модерация
👤 Пользователь - обычный участник"""
    await event.answer(text)

@simple_bot_message_handler(router, filters.Command("роль"))
async def set_role_command(event):
    if not is_admin(event.user_id):
        await event.answer("❌ Только администратор может менять роли")
        return
    args = event.object.object.message.text.split()
    if len(args) < 3:
        await event.answer("❌ Использование: !роль @user [роль]")
        return
    # Парсим упоминание
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    role = args[2].lower()
    if role not in ["admin", "moderator", "user"]:
        await event.answer("❌ Доступные роли: admin, moderator, user")
        return
    user = get_user(target_id)
    user["role"] = role
    await event.answer(f"✅ Пользователю {get_mention(target_id)} назначена роль {role}")

@simple_bot_message_handler(router, filters.Command("удроль"))
async def remove_role_command(event):
    if not is_admin(event.user_id):
        await event.answer("❌ Только администратор может менять роли")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    user = get_user(target_id)
    user["role"] = "user"
    await event.answer(f"✅ Роль пользователя {get_mention(target_id)} сброшена до user")

# ---- МОДЕРАЦИЯ ----
@simple_bot_message_handler(router, filters.Command("мут"))
async def mute_command(event):
    if not can_mute(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    args = event.object.object.message.text.split()
    minutes = 5
    if len(args) > 2:
        try:
            minutes = int(args[2])
        except:
            pass
    muted_users[target_id] = {"until": datetime.now() + timedelta(minutes=minutes), "reason": "Мут от модератора"}
    await event.answer(f"🔇 Пользователь {get_mention(target_id)} заглушен на {minutes} минут")

@simple_bot_message_handler(router, filters.Command("размут"))
async def unmute_command(event):
    if not can_mute(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    if target_id in muted_users:
        del muted_users[target_id]
        await event.answer(f"✅ {get_mention(target_id)} размучен")
    else:
        await event.answer(f"❌ {get_mention(target_id)} не в муте")

@simple_bot_message_handler(router, filters.Command("бан"))
async def ban_command(event):
    if not can_ban(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    args = event.object.object.message.text.split()
    days = 7
    if len(args) > 2:
        try:
            days = int(args[2])
        except:
            pass
    banned_users[target_id] = {"until": datetime.now() + timedelta(days=days), "reason": "Бан от администратора"}
    await event.answer(f"🚫 {get_mention(target_id)} забанен на {days} дней")

@simple_bot_message_handler(router, filters.Command("разбан"))
async def unban_command(event):
    if not can_ban(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    if target_id in banned_users:
        del banned_users[target_id]
        await event.answer(f"✅ {get_mention(target_id)} разбанен")
    else:
        await event.answer(f"❌ {get_mention(target_id)} не в бане")

@simple_bot_message_handler(router, filters.Command("пред"))
async def warn_command(event):
    if not can_mute(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    if target_id not in warnings:
        warnings[target_id] = []
    warnings[target_id].append({"reason": "Нарушение правил", "date": datetime.now().strftime("%d.%m.%Y")})
    await event.answer(f"⚠️ {get_mention(target_id)} получил предупреждение. Всего: {len(warnings[target_id])}")

@simple_bot_message_handler(router, filters.Command("варн"))
async def warns_command(event):
    target_id = event.user_id
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id not in warnings or not warnings[target_id]:
        await event.answer(f"✅ У {get_mention(target_id)} нет предупреждений")
        return
    text = f"⚠️ ПРЕДУПРЕЖДЕНИЯ ДЛЯ {get_mention(target_id)}:\n━━━━━━━━━━━━━━━━━\n"
    for i, warn in enumerate(warnings[target_id], 1):
        text += f"{i}. {warn['reason']} ({warn['date']})\n"
    await event.answer(text)

@simple_bot_message_handler(router, filters.Command("варн сброс"))
async def clear_warns_command(event):
    if not can_mute(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    if target_id in warnings:
        warnings[target_id] = []
        await event.answer(f"✅ Предупреждения {get_mention(target_id)} сброшены")
    else:
        await event.answer(f"❌ У {get_mention(target_id)} нет предупреждений")

@simple_bot_message_handler(router, filters.Command("кик"))
async def kick_command(event):
    if not can_mute(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    await event.answer(f"👢 {get_mention(target_id)} был исключён из чата (только в реальном чате)")

@simple_bot_message_handler(router, filters.Command("очистить"))
async def clear_command(event):
    if not can_mute(event.user_id):
        await event.answer("❌ Недостаточно прав")
        return
    args = event.object.object.message.text.split()
    count = 5
    if len(args) > 1:
        try:
            count = min(int(args[1]), 20)
        except:
            pass
    await event.answer(f"🧹 Удалено {count} сообщений бота (только сообщения бота)")

# ---- СЕМЬЯ ----
@simple_bot_message_handler(router, filters.Command("брак"))
async def marry_command(event):
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    if target_id == event.user_id:
        await event.answer("❌ Нельзя жениться на себе")
        return
    user = get_user(event.user_id)
    if user["married_to"]:
        await event.answer("❌ Вы уже в браке")
        return
    target = get_user(target_id)
    if target["married_to"]:
        await event.answer(f"❌ {get_mention(target_id)} уже в браке")
        return
    # Простое предложение (в реальном боте нужна система согласия)
    user["married_to"] = target_id
    target["married_to"] = event.user_id
    marriages.append({"user1": event.user_id, "user2": target_id, "date": datetime.now().strftime("%d.%m.%Y")})
    await event.answer(f"💑 {get_mention(event.user_id)} и {get_mention(target_id)} поженились! Поздравляем!")

@simple_bot_message_handler(router, filters.Command("браки"))
async def marriages_command(event):
    if not marriages:
        await event.answer("💑 В чате нет браков")
        return
    text = "💑 СПИСОК БРАКОВ:\n━━━━━━━━━━━━━━━━━\n"
    for m in marriages:
        text += f"{get_mention(m['user1'])} + {get_mention(m['user2'])} ({m['date']})\n"
    await event.answer(text)

@simple_bot_message_handler(router, filters.Command("развод"))
async def divorce_command(event):
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    user = get_user(event.user_id)
    if user["married_to"] != target_id:
        await event.answer("❌ Вы не состоите в браке с этим пользователем")
        return
    target = get_user(target_id)
    user["married_to"] = None
    target["married_to"] = None
    # Удалить брак из списка
    marriages[:] = [m for m in marriages if not (m["user1"] == event.user_id and m["user2"] == target_id or m["user1"] == target_id and m["user2"] == event.user_id)]
    await event.answer(f"💔 {get_mention(event.user_id)} и {get_mention(target_id)} развелись")

@simple_bot_message_handler(router, filters.Command("усыновить"))
@simple_bot_message_handler(router, filters.Command("удочерить"))
async def adopt_command(event):
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    user = get_user(event.user_id)
    if target_id in user["children"]:
        await event.answer("❌ Этот пользователь уже ваш ребёнок")
        return
    user["children"].append(target_id)
    await event.answer(f"👨‍👦 {get_mention(event.user_id)} усыновил/удочерил {get_mention(target_id)}!")

@simple_bot_message_handler(router, filters.Command("семья"))
async def family_command(event):
    user = get_user(event.user_id)
    text = f"👨‍👩‍👧‍👦 СЕМЬЯ {get_mention(event.user_id)}\n━━━━━━━━━━━━━━━━━\n"
    if user["married_to"]:
        text += f"💑 Супруг(а): {get_mention(user['married_to'])}\n"
    if user["children"]:
        text += f"👶 Дети: " + ", ".join([get_mention(c) for c in user["children"]]) + "\n"
    else:
        text += "👶 Детей нет\n"
    await event.answer(text)

# ---- ЭКОНОМИКА ----
bank_balance = 1000000  # Банк

@simple_bot_message_handler(router, filters.Command("перевод"))
async def transfer_command(event):
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    args = event.object.object.message.text.split()
    if len(args) < 3:
        await event.answer("❌ Укажите сумму: !перевод @user 100")
        return
    try:
        amount = int(args[2])
    except:
        await event.answer("❌ Укажите число")
        return
    if amount <= 0:
        await event.answer("❌ Сумма должна быть больше 0")
        return
    user = get_user(event.user_id)
    if user["coins"] < amount:
        await event.answer("❌ Недостаточно монет")
        return
    target = get_user(target_id)
    user["coins"] -= amount
    target["coins"] += amount
    await event.answer(f"✅ Переведено {amount} монет {get_mention(target_id)}")

@simple_bot_message_handler(router, filters.Command("банк"))
async def bank_command(event):
    await event.answer(f"🏦 Баланс банка: {bank_balance} монет")

@simple_bot_message_handler(router, filters.Command("банк пополнить"))
async def bank_deposit_command(event):
    args = event.object.object.message.text.split()
    if len(args) < 3:
        await event.answer("❌ Укажите сумму: !банк пополнить 100")
        return
    try:
        amount = int(args[2])
    except:
        await event.answer("❌ Укажите число")
        return
    if amount <= 0:
        await event.answer("❌ Сумма должна быть больше 0")
        return
    user = get_user(event.user_id)
    if user["coins"] < amount:
        await event.answer("❌ Недостаточно монет")
        return
    global bank_balance
    user["coins"] -= amount
    bank_balance += amount
    await event.answer(f"✅ Вы пополнили банк на {amount} монет")

@simple_bot_message_handler(router, filters.Command("банк снять"))
async def bank_withdraw_command(event):
    args = event.object.object.message.text.split()
    if len(args) < 3:
        await event.answer("❌ Укажите сумму: !банк снять 100")
        return
    try:
        amount = int(args[2])
    except:
        await event.answer("❌ Укажите число")
        return
    if amount <= 0:
        await event.answer("❌ Сумма должна быть больше 0")
        return
    global bank_balance
    if bank_balance < amount:
        await event.answer("❌ В банке недостаточно средств")
        return
    user = get_user(event.user_id)
    bank_balance -= amount
    user["coins"] += amount
    await event.answer(f"✅ Вы сняли с банка {amount} монет")

@simple_bot_message_handler(router, filters.Command("работа"))
async def work_command(event):
    professions = ["программист", "строитель", "повар", "водитель", "учитель", "врач"]
    args = event.object.object.message.text.split()
    if len(args) < 2:
        await event.answer(f"❌ Укажите профессию из списка: {', '.join(professions)}")
        return
    profession = args[1].lower()
    if profession not in professions:
        await event.answer(f"❌ Нет такой профессии. Доступны: {', '.join(professions)}")
        return
    user = get_user(event.user_id)
    user["profession"] = profession
    await event.answer(f"✅ Вы устроились на работу: {profession}. Используйте !зарплата для получения денег")

@simple_bot_message_handler(router, filters.Command("зарплата"))
async def salary_command(event):
    user = get_user(event.user_id)
    if "profession" not in user:
        await event.answer("❌ Вы не устроены на работу. Используйте !работа [профессия]")
        return
    if "last_salary" in user and (datetime.now() - user["last_salary"]) < timedelta(hours=1):
        await event.answer("⏳ Вы уже получали зарплату. Подождите 1 час")
        return
    salary = random.randint(500, 2000)
    user["coins"] += salary
    user["last_salary"] = datetime.now()
    await event.answer(f"💰 Вы получили зарплату {salary} монет как {user['profession']}")

@simple_bot_message_handler(router, filters.Command("магазин"))
async def shop_command(event):
    text = "🛍️ МАГАЗИН:\n━━━━━━━━━━━━━━━━━\n"
    for item, price in shop_items.items():
        text += f"• {item} — {price} монет\n"
    text += "\nИспользуйте: !купить [товар]"
    await event.answer(text)

@simple_bot_message_handler(router, filters.Command("купить"))
async def buy_command(event):
    args = event.object.object.message.text.split(maxsplit=1)
    if len(args) < 2:
        await event.answer("❌ Укажите товар: !купить [товар]")
        return
    item = args[1].lower()
    if item not in shop_items:
        await event.answer("❌ Такого товара нет в магазине")
        return
    user = get_user(event.user_id)
    price = shop_items[item]
    if user["coins"] < price:
        await event.answer(f"❌ Недостаточно монет. Нужно: {price}")
        return
    user["coins"] -= price
    if event.user_id not in inventory:
        inventory[event.user_id] = {}
    if item not in inventory[event.user_id]:
        inventory[event.user_id][item] = 0
    inventory[event.user_id][item] += 1
    await event.answer(f"✅ Вы купили {item} за {price} монет")

@simple_bot_message_handler(router, filters.Command("инвентарь"))
async def inventory_command(event):
    if event.user_id not in inventory or not inventory[event.user_id]:
        await event.answer("📦 Ваш инвентарь пуст")
        return
    text = "📦 ИНВЕНТАРЬ:\n━━━━━━━━━━━━━━━━━\n"
    for item, count in inventory[event.user_id].items():
        text += f"• {item} — {count} шт.\n"
    await event.answer(text)

# ---- БОНУСЫ ----
@simple_bot_message_handler(router, filters.Command("ежедневно"))
async def daily_command(event):
    user_id = event.user_id
    now = datetime.now()
    if user_id in daily_bonus and (now - daily_bonus[user_id]) < timedelta(days=1):
        remaining = timedelta(days=1) - (now - daily_bonus[user_id])
        await event.answer(f"⏳ Подождите {remaining.seconds//3600} часов до следующего ежедневного бонуса")
        return
    user = get_user(user_id)
    bonus = 5000
    user["coins"] += bonus
    daily_bonus[user_id] = now
    await event.answer(f"🎉 Ежедневный бонус: +{bonus} монет!")

@simple_bot_message_handler(router, filters.Command("еженедельно"))
async def weekly_command(event):
    user_id = event.user_id
    now = datetime.now()
    if user_id in weekly_bonus and (now - weekly_bonus[user_id]) < timedelta(days=7):
        remaining = timedelta(days=7) - (now - weekly_bonus[user_id])
        await event.answer(f"⏳ Подождите {remaining.days} дней до следующего еженедельного бонуса")
        return
    user = get_user(user_id)
    bonus = 25000
    user["coins"] += bonus
    weekly_bonus[user_id] = now
    await event.answer(f"🎉 Еженедельный бонус: +{bonus} монет!")

@simple_bot_message_handler(router, filters.Command("ежемесячно"))
async def monthly_command(event):
    user_id = event.user_id
    now = datetime.now()
    if user_id in monthly_bonus and (now - monthly_bonus[user_id]) < timedelta(days=30):
        remaining = timedelta(days=30) - (now - monthly_bonus[user_id])
        await event.answer(f"⏳ Подождите {remaining.days} дней до следующего ежемесячного бонуса")
        return
    user = get_user(user_id)
    bonus = 100000
    user["coins"] += bonus
    monthly_bonus[user_id] = now
    await event.answer(f"🎉 Ежемесячный бонус: +{bonus} монет!")

# ---- ИГРЫ ----
@simple_bot_message_handler(router, filters.Command("слот"))
async def slot_command(event):
    args = event.object.object.message.text.split()
    bet = 100
    if len(args) > 1:
        try:
            bet = int(args[1])
        except:
            pass
    user = get_user(event.user_id)
    if user["coins"] < bet:
        await event.answer("❌ Недостаточно монет")
        return
    symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]
    if result[0] == result[1] == result[2]:
        win = bet * 10
        user["coins"] += win
        await event.answer(f"🎰 {result[0]} {result[1]} {result[2]} — ДЖЕКПОТ! Вы выиграли {win} монет!")
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        win = bet * 2
        user["coins"] += win
        await event.answer(f"🎰 {result[0]} {result[1]} {result[2]} — Вы выиграли {win} монет!")
    else:
        user["coins"] -= bet
        await event.answer(f"🎰 {result[0]} {result[1]} {result[2]} — Вы проиграли {bet} монет")

@simple_bot_message_handler(router, filters.Command("орёл"))
async def coinflip_command(event):
    args = event.object.object.message.text.split()
    bet = 100
    if len(args) > 1:
        try:
            bet = int(args[1])
        except:
            pass
    user = get_user(event.user_id)
    if user["coins"] < bet:
        await event.answer("❌ Недостаточно монет")
        return
    result = random.choice(["Орёл", "Решка"])
    if random.random() < 0.5:  # 50% шанс выигрыша
        user["coins"] += bet
        await event.answer(f"🪙 {result}! Вы выиграли {bet} монет!")
    else:
        user["coins"] -= bet
        await event.answer(f"🪙 {result}! Вы проиграли {bet} монет")

@simple_bot_message_handler(router, filters.Command("кнб"))
async def rps_command(event):
    target_id = None
    for mention in event.object.object.message.mentions:
        target_id = mention.id
        break
    if target_id is None:
        await event.answer("❌ Упомяните пользователя")
        return
    await event.answer(f"✊ Камень-ножницы-бумага с {get_mention(target_id)}!\nНапишите: !камень, !ножницы или !бумага")

@simple_bot_message_handler(router, filters.Command("камень"))
async def rock_command(event):
    await event.answer("✊ Вы выбрали камень!")

@simple_bot_message_handler(router, filters.Command("ножницы"))
async def scissors_command(event):
    await event.answer("✌️ Вы выбрали ножницы!")

@simple_bot_message_handler(router, filters.Command("бумага"))
async def paper_command(event):
    await event.answer("✋ Вы выбрали бумагу!")

@simple_bot_message_handler(router, filters.Command("угадай"))
async def guess_command(event):
    number = random.randint(1, 100)
    # В реальном боте нужно хранить число для каждого пользователя
    await event.answer("🔢 Я загадал число от 1 до 100. Напишите !цифра [число]")

@simple_bot_message_handler(router, filters.Command("цифра"))
async def guess_number_command(event):
    args = event.object.object.message.text.split()
    if len(args) < 2:
        await event.answer("❌ Напишите число: !цифра [число]")
        return
    try:
        num = int(args[1])
    except:
        await event.answer("❌ Введите число")
        return
    # В реальном боте нужно проверять с сохранённым числом
    await event.answer(f"🔢 Вы сказали {num}")

@simple_bot_message_handler(router, filters.Command("шутка"))
async def joke_command(event):
    jokes = [
        "Почему программисты не любят природу? Слишком много багов!",
        "Что говорит один бит другому? 'Я тебя дополню!'",
        "Почему слон не играет в шахматы? Не умеет ходить конём!",
        "Как называется медведь без ушей? Ми-ми-мишка!",
        "Почему компьютер не ест? У него нет желудка!"
    ]
    await event.answer(random.choice(jokes))

@simple_bot_message_handler(router, filters.Command("гороскоп"))
async def horoscope_command(event):
    args = event.object.object.message.text.split()
    signs = ["овен", "телец", "близнецы", "рак", "лев", "дева", "весы", "скорпион", "стрелец", "козерог", "водолей", "рыбы"]
    if len(args) < 2:
        await event.answer(f"❌ Укажите знак зодиака: {', '.join(signs)}")
        return
    sign = args[1].lower()
    if sign not in signs:
        await event.answer("❌ Неверный знак зодиака")
        return
    predictions = [
        "Сегодня вас ждёт удача!",
        "Будьте осторожны с решениями.",
        "Ждите неожиданных новостей.",
        "День будет продуктивным.",
        "Вас ждёт приятный сюрприз."
    ]
    await event.answer(f"♈ Гороскоп для {sign}: {random.choice(predictions)}")

@simple_bot_message_handler(router, filters.Command("кофе"))
async def coffee_command(event):
    await event.answer("☕ Вы выпили кофе! Бодрость +100%")

@simple_bot_message_handler(router, filters.Command("чай"))
async def tea_command(event):
    await event.answer("🍵 Вы выпили чай! Тепло и уютно ☺️")

@simple_bot_message_handler(router, filters.Command("пиво"))
async def beer_command(event):
    await event.answer("🍺 Вы выпили пиво! Счастье в каждой капле!")

@simple_bot_message_handler(router, filters.Command("погода"))
async def weather_command(event):
    args = event.object.object.message.text.split()
    city = "Москва" if len(args) < 2 else args[1]
    # В реальности нужно API погоды
    temp = random.randint(-20, 35)
    conditions = ["солнечно", "облачно", "дождливо", "снежно", "ветрено"]
    await event.answer(f"🌤️ Погода в {city}: {temp}°C, {random.choice(conditions)}")

@simple_bot_message_handler(router, filters.Command("аниме"))
async def anime_command(event):
    animes = ["Наруто", "Ван-Пис", "Атака Титанов", "Токийский гуль", "Меланхолия Харухи Судзумии", "Клинок, рассекающий демонов", "Моя геройская академия", "Блич", "Магическая битва", "Покемоны"]
    await event.answer(f"🎬 Рекомендую посмотреть: {random.choice(animes)}")

@simple_bot_message_handler(router, filters.Command("фильм"))
async def movie_command(event):
    movies = ["Побег из Шоушенка", "Крёстный отец", "Тёмный рыцарь", "Список Шиндлера", "Форрест Гамп", "Начало", "Матрица", "Зелёная миля", "Хороший, плохой, злой", "Бойцовский клуб"]
    await event.answer(f"🎬 Рекомендую посмотреть: {random.choice(movies)}")

@simple_bot_message_handler(router, filters.Command("время"))
async def time_command(event):
    now = datetime.now()
    await event.answer(f"🕐 Текущее время: {now.strftime('%H:%M:%S')}")

@simple_bot_message_handler(router, filters.Command("дата"))
async def date_command(event):
    now = datetime.now()
    await event.answer(f"📅 Сегодня: {now.strftime('%d.%m.%Y')}")

@simple_bot_message_handler(router, filters.Command("жив"))
async def alive_command(event):
    await event.answer("✅ Я жив! Работаю исправно!")

@simple_bot_message_handler(router, filters.Command("пинг"))
async def ping_command(event):
    await event.answer("🏓 Понг! Задержка: ~100ms")

@simple_bot_message_handler(router, filters.Command("кто"))
async def who_command(event):
    # Случайный пользователь из беседы (в реальном боте нужна API)
    await event.answer("🤔 Случайный участник... (только в реальном чате)")

# ========== ЗАПУСК БОТА ==========
async def main():
    bot = SimpleLongPollBot(router, TOKEN, group_id=GROUP_ID)
    print("🤖 Бот запущен! Ожидание сообщений...")
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
