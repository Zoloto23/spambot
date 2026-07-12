import asyncio
import os
import logging
import json
import time
import random
import requests
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("VK_GROUP_TOKEN")
GROUP_ID = int(os.environ.get("VK_GROUP_ID", 0))

if not TOKEN:
    logger.error("VK_GROUP_TOKEN not set")
    raise RuntimeError("VK_GROUP_TOKEN not set")

if not GROUP_ID:
    logger.error("VK_GROUP_ID not set")
    raise RuntimeError("VK_GROUP_ID not set")

API_VERSION = "5.199"
PREFIX = "!"

DATA_FILE = "perfect_bot_data.json"

def load_data() -> Dict[str, Any]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "admins": {},
            "mods": {},
            "owner": 1118563484,
            "muted": {},
            "banned": {},
            "warns": {},
            "users": {},
            "shop": {
                "🎮 Роли": {
                    "items": [
                        {"id": "vip", "name": "👑 VIP", "price": 1000000, "desc": "VIP статус навсегда"},
                        {"id": "premium", "name": "💎 Premium", "price": 500000, "desc": "Premium статус на месяц"},
                    ]
                },
                "🎨 Цвета": {
                    "items": [
                        {"id": "red", "name": "🔴 Красный", "price": 50000, "desc": "Красный ник в чате"},
                        {"id": "blue", "name": "🔵 Синий", "price": 50000, "desc": "Синий ник в чате"},
                        {"id": "gold", "name": "🟡 Золотой", "price": 100000, "desc": "Золотой ник в чате"},
                    ]
                },
                "🎯 Бонусы": {
                    "items": [
                        {"id": "xp_boost", "name": "⚡ Буст опыта", "price": 25000, "desc": "x2 опыта на 1 час"},
                        {"id": "money_boost", "name": "💰 Буст денег", "price": 25000, "desc": "x2 денег на 1 час"},
                    ]
                },
                "💫 Особые": {
                    "items": [
                        {"id": "rainbow", "name": "🌈 Радуга", "price": 200000, "desc": "Радужный ник в чате"},
                        {"id": "glow", "name": "✨ Свечение", "price": 150000, "desc": "Светящийся ник"},
                    ]
                }
            },
            "inventory": {},
            "money": {},
            "exp": {},
            "level": {},
            "daily_bonus": {},
            "work": {},
            "marriage": {},
            "rep": {},
            "warns": {},
            "settings": {
                "welcome": "👋 Добро пожаловать в чат, {user}!",
                "rules": "1. Не материться\n2. Не спамить\n3. Уважать друг друга\n4. Без рекламы\n5. Слушаться администрацию",
                "antispam": True,
                "spam_limit": 3,
                "spam_time": 5,
                "antilink": True,
                "whitelist": ["vk.com", "youtube.com", "t.me"],
                "antiflood": True,
                "flood_limit": 5,
                "flood_time": 10,
                "antimute": True,
                "auto_moderate": True,
                "slow_mode": False,
                "slow_delay": 3,
                "welcome_enabled": True,
                "leave_enabled": True
            },
            "message_history": {},
            "user_stats": {},
            "afk_users": {},
            "reminders": {},
            "polls": {},
            "games": {},
            "blacklist": {},
            "reports": {},
            "group_chats": [],
            "private_chats": []
        }

def save_data(data: Dict[str, Any]):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Save error: {e}")

data = load_data()

def user_link(user_id: int, name: str = None) -> str:
    if name is None:
        return f"[id{user_id}|Пользователь]"
    return f"[id{user_id}|{name}]"

class VKGroupAPI:
    def __init__(self, token: str, group_id: int, version: str = "5.199"):
        self.token = token
        self.group_id = group_id
        self.version = version
        self.base_url = "https://api.vk.com/method/"
    
    def _request(self, method: str, params: Dict = None) -> Dict:
        if params is None:
            params = {}
        params["access_token"] = self.token
        params["v"] = self.version
        
        try:
            response = requests.post(self.base_url + method, data=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                logger.error(f"VK API error: {result['error']['error_msg']}")
                return {"error": result["error"]}
            return result.get("response", {})
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": {"error_msg": str(e)}}
    
    def messages_send(self, peer_id: int, message: str) -> Dict:
        return self._request("messages.send", {
            "peer_id": peer_id,
            "message": message,
            "random_id": int(time.time() * 1000) + random.randint(1, 99999),
            "disable_mentions": 1
        })
    
    def messages_remove_chat_user(self, chat_id: int, user_id: int) -> Dict:
        return self._request("messages.removeChatUser", {
            "chat_id": chat_id,
            "user_id": user_id
        })
    
    def users_get(self, user_ids: int) -> Dict:
        return self._request("users.get", {"user_ids": user_ids})
    
    def groups_get_by_id(self) -> Dict:
        return self._request("groups.getById", {"group_id": self.group_id})
    
    def get_long_poll_server(self) -> Dict:
        return self._request("groups.getLongPollServer", {"group_id": self.group_id})
    
    def long_poll_request(self, server: str, key: str, ts: int, wait: int = 25) -> Dict:
        if not server.startswith(('http://', 'https://')):
            server = 'https://' + server
        url = f"{server}?act=a_check&key={key}&ts={ts}&wait={wait}&mode=2&version=2"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Long Poll error: {e}")
            return {"failed": 1}

vk = VKGroupAPI(TOKEN, GROUP_ID)

async def get_user_name(user_id: int) -> str:
    try:
        result = vk.users_get(user_id)
        if "error" not in result and result:
            user = result[0]
            return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return f"ID {user_id}"
    except:
        return f"ID {user_id}"

async def get_user_link(user_id: int) -> str:
    name = await get_user_name(user_id)
    return user_link(user_id, name)

def is_owner(user_id: int) -> bool:
    return user_id == data.get("owner", 1118563484)

def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    return str(user_id) in data.get("admins", {})

def is_mod(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    return str(user_id) in data.get("mods", {})

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

async def get_money(user_id: int) -> int:
    return data.get("money", {}).get(str(user_id), 0)

async def add_money(user_id: int, amount: int):
    if "money" not in data:
        data["money"] = {}
    data["money"][str(user_id)] = data["money"].get(str(user_id), 0) + amount
    save_data(data)

async def remove_money(user_id: int, amount: int) -> bool:
    if "money" not in data:
        data["money"] = {}
    current = data["money"].get(str(user_id), 0)
    if current < amount:
        return False
    data["money"][str(user_id)] = current - amount
    save_data(data)
    return True

async def add_exp(user_id: int, amount: int):
    if "exp" not in data:
        data["exp"] = {}
    data["exp"][str(user_id)] = data["exp"].get(str(user_id), 0) + amount
    
    # Уровни
    exp = data["exp"][str(user_id)]
    level = int(exp / 100) + 1
    if "level" not in data:
        data["level"] = {}
    data["level"][str(user_id)] = level
    save_data(data)

async def check_links(text: str) -> bool:
    if not data["settings"].get("antilink", True):
        return False
    whitelist = data["settings"].get("whitelist", ["vk.com", "youtube.com", "t.me"])
    url_pattern = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
    links = re.findall(url_pattern, text)
    for link in links:
        if not any(w in link.lower() for w in whitelist):
            return True
    return False

async def process_message(message_data: dict):
    try:
        if "object" in message_data and "message" in message_data["object"]:
            msg = message_data["object"]["message"]
            peer_id = msg.get("peer_id", 0)
            user_id = msg.get("from_id", 0)
            text = msg.get("text", "")
        else:
            peer_id = message_data.get("peer_id", 0)
            user_id = message_data.get("from_id", 0)
            text = message_data.get("text", "")
        
        if user_id < 0:
            return
        
        is_chat = peer_id > 2000000000
        user_link_text = await get_user_link(user_id)
        
        # Сохраняем чаты
        if is_chat:
            if peer_id not in data.get("group_chats", []):
                data["group_chats"].append(peer_id)
                save_data(data)
        else:
            if user_id not in data.get("private_chats", []):
                data["private_chats"].append(user_id)
                save_data(data)
        
        # Проверка бана
        if is_banned(user_id):
            return
        
        # Проверка мута
        if is_muted(user_id):
            try:
                await vk.messages_send(peer_id, f"🔇 Вы заглушены! Не пишите.")
            except:
                pass
            return
        
        # Статистика
        if "user_stats" not in data:
            data["user_stats"] = {}
        data["user_stats"][str(user_id)] = data["user_stats"].get(str(user_id), 0) + 1
        
        # Опыт за сообщения
        if random.random() < 0.1:
            await add_exp(user_id, random.randint(1, 5))
        
        # Модерация (только в чатах)
        if is_chat:
            # Антиссылки
            if await check_links(text):
                if not is_mod(user_id):
                    await vk.messages_send(peer_id, f"❌ {user_link_text}, ссылки запрещены!")
                    return
            
            # Антиспам/флуд
            if data["settings"].get("antispam", True):
                key = f"{user_id}_{peer_id}"
                now = time.time()
                if key not in data["message_history"]:
                    data["message_history"][key] = []
                spam_time = data["settings"].get("spam_time", 5)
                data["message_history"][key] = [t for t in data["message_history"][key] if now - t < spam_time]
                spam_limit = data["settings"].get("spam_limit", 3)
                if len(data["message_history"][key]) >= spam_limit and not is_mod(user_id):
                    mute_time = 5
                    data["muted"][str(user_id)] = time.time() + (mute_time * 60)
                    save_data(data)
                    await vk.messages_send(peer_id, f"🚫 {user_link_text} заглушен на {mute_time} минут за спам!")
                    return
                data["message_history"][key].append(now)
                save_data(data)
        
        # Обработка команд
        if not text.startswith(PREFIX):
            return
        
        text = text[1:].strip()
        args = text.split()
        if not args:
            return
        
        command = args[0].lower()
        
        # === ВЛАДЕЛЕЦ (только владелец) ===
        if command == "owner_set":
            if is_owner(user_id):
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ !owner_set [ID]")
                    return
                try:
                    new_owner = int(args[1])
                    data["owner"] = new_owner
                    save_data(data)
                    await vk.messages_send(peer_id, f"✅ Владелец изменен на {await get_user_link(new_owner)}")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # === СТАРТ (активация бота) ===
        if command == "старт":
            if not is_chat:
                await vk.messages_send(peer_id, "ℹ️ Команда работает только в чатах!")
                return
            if not is_mod(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            # Добавляем чат в активные
            if peer_id not in data.get("group_chats", []):
                data["group_chats"].append(peer_id)
            # Приветственное сообщение
            welcome = data["settings"].get("welcome", "👋 Добро пожаловать в чат, {user}!")
            await vk.messages_send(peer_id, f"✅ Бот активирован!\n{welcome}")
            save_data(data)
            return
        
        # === ПОМОЩЬ ===
        if command == "помощь":
            help_text = (
                "👑 **ИДЕАЛЬНЫЙ БОТ VK 2026**\n\n"
                "**📊 Основные команды:**\n"
                "!профиль - Ваш профиль\n"
                "!статистика - Статистика чата\n"
                "!топ - Топ пользователей\n"
                "!инфо [ID] - Информация\n"
                "!пинг - Пинг бота\n"
                "!время - Текущее время\n\n"
                "**💰 Экономика:**\n"
                "!баланс - Ваш баланс\n"
                "!бонус - Ежедневный бонус\n"
                "!передать [ID] [сумма] - Передать деньги\n"
                "!работа - Устроиться на работу\n"
                "!зарплата - Получить зарплату\n"
                "!магазин - Магазин\n"
                "!купить [товар] - Купить товар\n"
                "!инвентарь - Ваш инвентарь\n"
                "!казино [сумма] - Казино\n\n"
                "**🎮 Развлечения:**\n"
                "!кубик - Бросок кубика\n"
                "!монетка - Орёл или решка\n"
                "!шар [вопрос] - Магический шар\n"
                "!шутка - Шутка\n"
                "!брак [ID] - Предложение брака\n"
                "!развод - Развод\n"
                "!реп [ID] - Репутация\n"
                "!афк [причина] - Уйти в AFK\n\n"
                "**⚙️ Модерация:**\n"
                "!мут [ID] [мин] - Заглушить\n"
                "!размут [ID] - Размутить\n"
                "!кик [ID] - Кикнуть\n"
                "!варн [ID] - Предупреждение\n"
                "!бан [ID] [дней] - Забанить\n"
                "!разбан [ID] - Разбанить\n"
                "!очистить [кол-во] - Очистить чат\n"
                "!правила - Правила\n"
                "!приветствие [текст] - Приветствие\n"
                "!админы - Список админов\n"
                "!добавить_админа [ID] - Добавить админа\n"
                "!удалить_админа [ID] - Удалить админа\n\n"
                "**🔧 Настройки:**\n"
                "!настройки - Показать настройки\n"
                "!антиспам [вкл/выкл] - Антиспам\n"
                "!антиссылки [вкл/выкл] - Антиссылки\n"
                "!медленный [вкл/выкл] - Медленный режим"
            )
            await vk.messages_send(peer_id, help_text)
            return
        
        # === ПРОФИЛЬ ===
        if command == "профиль":
            target_id = user_id
            if len(args) > 1 and args[1].isdigit():
                target_id = int(args[1])
            
            target_link = await get_user_link(target_id)
            stats = data.get("user_stats", {}).get(str(target_id), 0)
            warns = data.get("warns", {}).get(str(target_id), 0)
            money = await get_money(target_id)
            exp = data.get("exp", {}).get(str(target_id), 0)
            level = data.get("level", {}).get(str(target_id), 1)
            rep = data.get("rep", {}).get(str(target_id), 0)
            
            is_muted_user = is_muted(target_id)
            is_banned_user = is_banned(target_id)
            
            status = "✅ Активен"
            if is_banned_user:
                status = "🔴 Забанен"
            elif is_muted_user:
                status = "🔇 Заглушен"
            
            text = (
                f"👤 **Профиль**\n\n"
                f"Пользователь: {target_link}\n"
                f"ID: {target_id}\n"
                f"Сообщений: {stats}\n"
                f"Уровень: {level}\n"
                f"Опыт: {exp}\n"
                f"Монет: {money}\n"
                f"Репутация: {rep}\n"
                f"Предупреждений: {warns}/3\n"
                f"Статус: {status}"
            )
            await vk.messages_send(peer_id, text)
            return
        
        # === СТАТИСТИКА ===
        if command == "статистика":
            total_users = len(data.get("user_stats", {}))
            total_messages = sum(data.get("user_stats", {}).values())
            text = (
                f"📊 **Статистика чата:**\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"💬 Всего сообщений: {total_messages}\n"
                f"🚫 Забанено: {len(data.get('banned', {}))}\n"
                f"🔇 Заглушено: {len(data.get('muted', {}))}\n"
                f"⚠️ Предупреждений: {sum(data.get('warns', {}).values())}\n"
                f"👑 Администраторов: {len(data.get('admins', {}))}\n"
                f"💑 Браков: {len(data.get('marriage', {}))//2}\n"
                f"💰 Всего монет: {sum(data.get('money', {}).values())}"
            )
            await vk.messages_send(peer_id, text)
            return
        
        # === ТОП ===
        if command == "топ":
            sorted_users = sorted(data.get("money", {}).items(), key=lambda x: x[1], reverse=True)[:10]
            if not sorted_users:
                await vk.messages_send(peer_id, "📋 Нет данных для топа")
                return
            text = "🏆 **Топ богачей:**\n\n"
            for i, (uid, money) in enumerate(sorted_users, 1):
                link = await get_user_link(int(uid))
                text += f"{i}. {link} - {money} монет\n"
            await vk.messages_send(peer_id, text)
            return
        
        # === ИНФО ===
        if command == "инфо":
            target_id = user_id
            if len(args) > 1:
                try:
                    target_id = int(args[1])
                except:
                    pass
            try:
                user_info = vk.users_get(target_id)
                if "error" not in user_info and user_info:
                    user = user_info[0]
                    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                    link = user_link(target_id, name)
                    status = "🟢 Онлайн" if user.get("online", 0) else "⚫ Офлайн"
                    text = f"👤 **Информация**\n\nИмя: {link}\nID: {target_id}\nСтатус: {status}"
                    await vk.messages_send(peer_id, text)
                else:
                    await vk.messages_send(peer_id, "❌ Не удалось получить информацию")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # === ПИНГ ===
        if command == "пинг":
            start = time.time()
            vk.users_get(GROUP_ID)
            latency = int((time.time() - start) * 1000)
            await vk.messages_send(peer_id, f"🏓 Понг! {latency} мс")
            return
        
        # === ВРЕМЯ ===
        if command == "время":
            now = datetime.now()
            await vk.messages_send(peer_id, f"🕐 {now.strftime('%H:%M:%S')}\n📅 {now.strftime('%d.%m.%Y')}")
            return
        
        # === БАЛАНС ===
        if command == "баланс":
            money = await get_money(user_id)
            await vk.messages_send(peer_id, f"💰 Ваш баланс: {money} монет")
            return
        
        # === БОНУС ===
        if command == "бонус":
            last_bonus = data.get("daily_bonus", {}).get(str(user_id), 0)
            now = time.time()
            if now - last_bonus < 86400:
                remaining = int(86400 - (now - last_bonus))
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await vk.messages_send(peer_id, f"⏳ Бонус доступен через {hours}ч {minutes}м")
                return
            bonus = random.randint(1000, 10000)
            await add_money(user_id, bonus)
            data["daily_bonus"][str(user_id)] = now
            save_data(data)
            await vk.messages_send(peer_id, f"🎁 Ежедневный бонус: {bonus} монет!")
            return
        
        # === ПЕРЕДАТЬ ===
        if command == "передать":
            if len(args) < 3:
                await vk.messages_send(peer_id, "❌ !передать [ID] [сумма]")
                return
            try:
                target_id = int(args[1])
                amount = int(args[2])
                if target_id == user_id:
                    await vk.messages_send(peer_id, "❌ Нельзя передать себе!")
                    return
                if amount <= 0:
                    await vk.messages_send(peer_id, "❌ Сумма должна быть положительной!")
                    return
                if not await remove_money(user_id, amount):
                    await vk.messages_send(peer_id, f"❌ Недостаточно монет!")
                    return
                await add_money(target_id, amount)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"✅ Передано {amount} монет {target_link}")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !передать [ID] [сумма]")
            return
        
        # === РАБОТА ===
        if command == "работа":
            jobs = ["Программист", "Дизайнер", "Менеджер", "Копирайтер", "Маркетолог"]
            if str(user_id) in data.get("work", {}):
                job = data["work"][str(user_id)]
                await vk.messages_send(peer_id, f"💼 Вы работаете {job['name']}")
                return
            job_name = random.choice(jobs)
            data["work"][str(user_id)] = {"name": job_name, "start": time.time()}
            save_data(data)
            await vk.messages_send(peer_id, f"✅ Вы устроились на работу {job_name}!")
            return
        
        # === ЗАРПЛАТА ===
        if command == "зарплата":
            if str(user_id) not in data.get("work", {}):
                await vk.messages_send(peer_id, "❌ Вы не работаете! !работа")
                return
            work = data["work"][str(user_id)]
            hours = (time.time() - work["start"]) / 3600
            if hours < 2:
                remaining = int((2 - hours) * 60)
                await vk.messages_send(peer_id, f"⏳ Работайте еще {remaining} минут")
                return
            salary = int(500 * hours)
            await add_money(user_id, salary)
            data["work"][str(user_id)]["start"] = time.time()
            save_data(data)
            await vk.messages_send(peer_id, f"💰 Зарплата: {salary} монет!")
            return
        
        # === МАГАЗИН ===
        if command == "магазин":
            shop = data.get("shop", {})
            if not shop:
                await vk.messages_send(peer_id, "❌ Магазин пуст!")
                return
            text = "🛒 **Магазин:**\n\n"
            for category, items in shop.items():
                text += f"**{category}**\n"
                for item in items["items"]:
                    text += f"• {item['name']} - {item['price']} монет\n"
                    text += f"  {item['desc']}\n"
                text += "\n"
            text += "Используйте !купить [ID товара]"
            await vk.messages_send(peer_id, text)
            return
        
        # === КУПИТЬ ===
        if command == "купить":
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !купить [ID товара]")
                return
            item_id = args[1]
            found = None
            for category, items in data.get("shop", {}).items():
                for item in items["items"]:
                    if item["id"] == item_id:
                        found = item
                        break
                if found:
                    break
            if not found:
                await vk.messages_send(peer_id, "❌ Товар не найден!")
                return
            if not await remove_money(user_id, found["price"]):
                await vk.messages_send(peer_id, f"❌ Недостаточно монет! Нужно {found['price']}")
                return
            if "inventory" not in data:
                data["inventory"] = {}
            if str(user_id) not in data["inventory"]:
                data["inventory"][str(user_id)] = []
            data["inventory"][str(user_id)].append(found["id"])
            save_data(data)
            await vk.messages_send(peer_id, f"✅ Вы купили {found['name']}!")
            return
        
        # === ИНВЕНТАРЬ ===
        if command == "инвентарь":
            if str(user_id) not in data.get("inventory", {}):
                await vk.messages_send(peer_id, "📭 Ваш инвентарь пуст")
                return
            items = data["inventory"][str(user_id)]
            text = "🎒 **Инвентарь:**\n\n"
            for item_id in items:
                for category, cat_items in data.get("shop", {}).items():
                    for item in cat_items["items"]:
                        if item["id"] == item_id:
                            text += f"• {item['name']}\n"
            await vk.messages_send(peer_id, text)
            return
        
        # === КАЗИНО ===
        if command == "казино":
            if len(args) < 2 or not args[1].isdigit():
                await vk.messages_send(peer_id, "❌ !казино [сумма]")
                return
            amount = int(args[1])
            if not await remove_money(user_id, amount):
                await vk.messages_send(peer_id, f"❌ Недостаточно монет!")
                return
            multiplier = random.choice([0, 0.5, 1, 2, 3, 5])
            result = int(amount * multiplier)
            await add_money(user_id, result)
            if result > amount:
                await vk.messages_send(peer_id, f"🎉 Вы выиграли {result} монет! (+{result-amount})")
            elif result == amount:
                await vk.messages_send(peer_id, f"🤝 Ваша ставка вернулась")
            else:
                await vk.messages_send(peer_id, f"😢 Вы проиграли {amount-result} монет")
            return
        
        # === КУБИК ===
        if command == "кубик":
            sides = 6
            if len(args) > 1 and args[1].isdigit():
                sides = min(max(int(args[1]), 2), 100)
            result = random.randint(1, sides)
            await vk.messages_send(peer_id, f"🎲 {result} (1-{sides})")
            return
        
        # === МОНЕТКА ===
        if command == "монетка":
            result = random.choice(["🦅 Орёл", "🪙 Решка"])
            await vk.messages_send(peer_id, f"{result}")
            return
        
        # === ШАР ===
        if command == "шар":
            answers = ["Определённо да", "Без сомнения", "Вероятно", "Да",
                       "Нет", "Не сейчас", "Возможно", "Спроси позже",
                       "Туманно", "Абсолютно нет", "Точно да", "Очень сомнительно"]
            await vk.messages_send(peer_id, f"🔮 {random.choice(answers)}")
            return
        
        # === ШУТКА ===
        if command == "шутка":
            jokes = [
                "Почему программисты путают Хэллоуин и Рождество? 31 OCT = 25 DEC",
                "Сколько программистов нужно, чтобы заменить лампочку? Ни одного",
                "Как назвать медведя без ушей? Без-ушный",
                "Что говорит один компьютер другому? Давай обменяемся вирусами!"
            ]
            await vk.messages_send(peer_id, f"😂 {random.choice(jokes)}")
            return
        
        # === БРАК ===
        if command == "брак":
            if len(args) < 2:
                if str(user_id) in data.get("marriage", {}):
                    spouse_id = data["marriage"][str(user_id)]
                    spouse_link = await get_user_link(spouse_id)
                    await vk.messages_send(peer_id, f"💑 Вы в браке с {spouse_link}")
                else:
                    await vk.messages_send(peer_id, "❌ Вы не в браке")
                return
            target_id = int(args[1])
            if target_id == user_id:
                await vk.messages_send(peer_id, "❌ Нельзя жениться на себе!")
                return
            if str(user_id) in data.get("marriage", {}):
                await vk.messages_send(peer_id, "❌ Вы уже в браке!")
                return
            if str(target_id) in data.get("marriage", {}):
                await vk.messages_send(peer_id, "❌ Пользователь уже в браке!")
                return
            target_link = await get_user_link(target_id)
            await vk.messages_send(peer_id, f"💍 {user_link_text} предлагает брак {target_link}!\nНапишите !да или !нет")
            data["marriage_proposal"] = {"from": user_id, "to": target_id}
            save_data(data)
            return
        
        # === ДА (принятие брака) ===
        if command == "да":
            if "marriage_proposal" in data:
                proposal = data["marriage_proposal"]
                if proposal["to"] == user_id:
                    if "marriage" not in data:
                        data["marriage"] = {}
                    data["marriage"][str(proposal["from"])] = proposal["to"]
                    data["marriage"][str(proposal["to"])] = proposal["from"]
                    del data["marriage_proposal"]
                    save_data(data)
                    from_link = await get_user_link(proposal["from"])
                    to_link = await get_user_link(proposal["to"])
                    await vk.messages_send(peer_id, f"💑 {from_link} и {to_link} теперь муж и жена!")
                else:
                    await vk.messages_send(peer_id, "❌ Вам не предлагали брак")
            return
        
        # === НЕТ (отказ от брака) ===
        if command == "нет":
            if "marriage_proposal" in data:
                proposal = data["marriage_proposal"]
                if proposal["to"] == user_id:
                    del data["marriage_proposal"]
                    save_data(data)
                    await vk.messages_send(peer_id, "❌ Брак отклонен")
            return
        
        # === РАЗВОД ===
        if command == "развод":
            if str(user_id) not in data.get("marriage", {}):
                await vk.messages_send(peer_id, "❌ Вы не в браке!")
                return
            spouse_id = data["marriage"][str(user_id)]
            del data["marriage"][str(user_id)]
            del data["marriage"][str(spouse_id)]
            save_data(data)
            spouse_link = await get_user_link(spouse_id)
            await vk.messages_send(peer_id, f"💔 {user_link_text} и {spouse_link} развелись!")
            return
        
        # === РЕПУТАЦИЯ ===
        if command == "реп":
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !реп [ID]")
                return
            try:
                target_id = int(args[1])
                if target_id == user_id:
                    await vk.messages_send(peer_id, "❌ Нельзя дать репутацию себе!")
                    return
                if "rep" not in data:
                    data["rep"] = {}
                data["rep"][str(target_id)] = data["rep"].get(str(target_id), 0) + 1
                save_data(data)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"⭐ {target_link} +1 репутация!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !реп [ID]")
            return
        
        # === АФК ===
        if command == "афк":
            reason = " ".join(args[1:]) if len(args) > 1 else "Не беспокоить"
            if "afk_users" not in data:
                data["afk_users"] = {}
            data["afk_users"][str(user_id)] = {"time": time.time(), "reason": reason}
            save_data(data)
            await vk.messages_send(peer_id, f"🔇 AFK: {reason}")
            return
        
        # === НЕ_АФК ===
        if command == "не_афк":
            if str(user_id) in data.get("afk_users", {}):
                del data["afk_users"][str(user_id)]
                save_data(data)
                await vk.messages_send(peer_id, "🔊 Вы снова активны!")
            else:
                await vk.messages_send(peer_id, "ℹ️ Вы не были AFK")
            return
        
        # === МУТ ===
        if command == "мут":
            if not is_mod(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !мут [ID] [минут]")
                return
            try:
                target_id = int(args[1])
                minutes = int(args[2]) if len(args) > 2 else 5
                data["muted"][str(target_id)] = time.time() + (minutes * 60)
                save_data(data)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"🔇 {target_link} заглушен на {minutes} минут!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !мут [ID] [минут]")
            return
        
        # === РАЗМУТ ===
        if command == "размут":
            if not is_mod(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !размут [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("muted", {}):
                    del data["muted"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} размучен!")
                else:
                    await vk.messages_send(peer_id, "❌ Пользователь не заглушен!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !размут [ID]")
            return
        
        # === КИК ===
        if command == "кик":
            if not is_mod(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !кик [ID]")
                return
            try:
                target_id = int(args[1])
                if not is_chat:
                    await vk.messages_send(peer_id, "❌ Команда только в чатах!")
                    return
                chat_id = peer_id - 2000000000
                target_link = await get_user_link(target_id)
                result = vk.messages_remove_chat_user(chat_id, target_id)
                if "error" not in result:
                    await vk.messages_send(peer_id, f"👢 {target_link} кикнут!")
                else:
                    await vk.messages_send(peer_id, "❌ Не удалось кикнуть!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !кик [ID]")
            return
        
        # === ВАРН ===
        if command == "варн":
            if not is_mod(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !варн [ID]")
                return
            try:
                target_id = int(args[1])
                if "warns" not in data:
                    data["warns"] = {}
                data["warns"][str(target_id)] = data["warns"].get(str(target_id), 0) + 1
                warns = data["warns"][str(target_id)]
                save_data(data)
                target_link = await get_user_link(target_id)
                if warns >= 3:
                    data["muted"][str(target_id)] = time.time() + (60 * 60)
                    save_data(data)
                    await vk.messages_send(peer_id, f"⚠️ {target_link} получил 3 предупреждения! Заглушен на час!")
                else:
                    await vk.messages_send(peer_id, f"⚠️ {target_link} предупреждение {warns}/3")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !варн [ID]")
            return
        
        # === БАН ===
        if command == "бан":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !бан [ID] [дней]")
                return
            try:
                target_id = int(args[1])
                days = int(args[2]) if len(args) > 2 else 7
                data["banned"][str(target_id)] = time.time() + (days * 24 * 60 * 60)
                save_data(data)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"🚫 {target_link} забанен на {days} дней!")
                if is_chat:
                    chat_id = peer_id - 2000000000
                    vk.messages_remove_chat_user(chat_id, target_id)
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !бан [ID] [дней]")
            return
        
        # === РАЗБАН ===
        if command == "разбан":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !разбан [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("banned", {}):
                    del data["banned"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} разбанен!")
                else:
                    await vk.messages_send(peer_id, "❌ Пользователь не забанен!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка! !разбан [ID]")
            return
        
        # === ОЧИСТИТЬ ===
        if command == "очистить":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            count = 20
            if len(args) > 1 and args[1].isdigit():
                count = min(int(args[1]), 100)
            await vk.messages_send(peer_id, f"🧹 Очищено {count} сообщений (демонстрация)")
            return
        
        # === ПРАВИЛА ===
        if command == "правила":
            rules = data["settings"].get("rules", "Правила не установлены")
            await vk.messages_send(peer_id, f"📋 **Правила чата:**\n{rules}")
            return
        
        # === ПРИВЕТСТВИЕ ===
        if command == "приветствие":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                current = data["settings"].get("welcome", "Не установлено")
                await vk.messages_send(peer_id, f"Текущее приветствие: {current}")
                return
            welcome_text = " ".join(args[1:])
            data["settings"]["welcome"] = welcome_text
            save_data(data)
            await vk.messages_send(peer_id, f"✅ Приветствие установлено!")
            return
        
        # === АДМИНЫ ===
        if command == "админы":
            admins = data.get("admins", {})
            if not admins:
                await vk.messages_send(peer_id, "📋 Нет администраторов")
                return
            text = "👑 **Администраторы:**\n\n"
            for aid in admins:
                link = await get_user_link(int(aid))
                text += f"• {link}\n"
            await vk.messages_send(peer_id, text)
            return
        
        # === ДОБАВИТЬ_АДМИНА ===
        if command == "добавить_админа":
            if not is_owner(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !добавить_админа [ID]")
                return
            try:
                target_id = int(args[1])
                data["admins"][str(target_id)] = True
                save_data(data)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"✅ {target_link} добавлен в администраторы!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # === УДАЛИТЬ_АДМИНА ===
        if command == "удалить_админа":
            if not is_owner(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !удалить_админа [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("admins", {}):
                    del data["admins"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} удален из администраторов!")
                else:
                    await vk.messages_send(peer_id, "❌ Пользователь не администратор!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # === ДОБАВИТЬ_МОДА ===
        if command == "добавить_мода":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !добавить_мода [ID]")
                return
            try:
                target_id = int(args[1])
                data["mods"][str(target_id)] = True
                save_data(data)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"✅ {target_link} добавлен в модераторы!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # === УДАЛИТЬ_МОДА ===
        if command == "удалить_мода":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !удалить_мода [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("mods", {}):
                    del data["mods"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} удален из модераторов!")
                else:
                    await vk.messages_send(peer_id, "❌ Пользователь не модератор!")
            except:
                await vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # === НАСТРОЙКИ ===
        if command == "настройки":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            settings = data.get("settings", {})
            text = (
                f"⚙️ **Настройки:**\n\n"
                f"Антиспам: {'✅' if settings.get('antispam', True) else '❌'}\n"
                f"Лимит спама: {settings.get('spam_limit', 3)} за {settings.get('spam_time', 5)}с\n"
                f"Антиссылки: {'✅' if settings.get('antilink', True) else '❌'}\n"
                f"Антифлуд: {'✅' if settings.get('antiflood', True) else '❌'}\n"
                f"Медленный режим: {'✅' if settings.get('slow_mode', False) else '❌'}\n"
                f"Приветствие: {settings.get('welcome', 'Не установлено')[:30]}..."
            )
            await vk.messages_send(peer_id, text)
            return
        
        # === АНТИСПАМ ===
        if command == "антиспам":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !антиспам [вкл/выкл]")
                return
            if args[1].lower() in ["вкл", "on", "да"]:
                data["settings"]["antispam"] = True
                await vk.messages_send(peer_id, "✅ Антиспам включен!")
            elif args[1].lower() in ["выкл", "off", "нет"]:
                data["settings"]["antispam"] = False
                await vk.messages_send(peer_id, "❌ Антиспам выключен!")
            else:
                await vk.messages_send(peer_id, "❌ !антиспам [вкл/выкл]")
                return
            save_data(data)
            return
        
        # === АНТИССЫЛКИ ===
        if command == "антиссылки":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !антиссылки [вкл/выкл]")
                return
            if args[1].lower() in ["вкл", "on", "да"]:
                data["settings"]["antilink"] = True
                await vk.messages_send(peer_id, "✅ Антиссылки включены!")
            elif args[1].lower() in ["выкл", "off", "нет"]:
                data["settings"]["antilink"] = False
                await vk.messages_send(peer_id, "❌ Антиссылки выключены!")
            else:
                await vk.messages_send(peer_id, "❌ !антиссылки [вкл/выкл]")
                return
            save_data(data)
            return
        
        # === МЕДЛЕННЫЙ ===
        if command == "медленный":
            if not is_admin(user_id):
                await vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ !медленный [вкл/выкл]")
                return
            if args[1].lower() in ["вкл", "on", "да"]:
                data["settings"]["slow_mode"] = True
                await vk.messages_send(peer_id, "✅ Медленный режим включен!")
            elif args[1].lower() in ["выкл", "off", "нет"]:
                data["settings"]["slow_mode"] = False
                await vk.messages_send(peer_id, "❌ Медленный режим выключен!")
            else:
                await vk.messages_send(peer_id, "❌ !медленный [вкл/выкл]")
                return
            save_data(data)
            return
        
    except Exception as e:
        logger.error(f"Process error: {e}")

start_time = time.time()

async def main():
    logger.info("🚀 PERFECT BOT VK 2026 START")
    logger.info(f"👥 Group: {GROUP_ID}")
    logger.info(f"👑 Owner: {data.get('owner', 1118563484)}")
    
    try:
        info = vk.groups_get_by_id()
        if "error" in info:
            logger.error(f"Token error: {info['error']}")
            return
        logger.info("✅ Token OK")
    except Exception as e:
        logger.error(f"Error: {e}")
        return
    
    lp_info = vk.get_long_poll_server()
    if "error" in lp_info:
        logger.error(f"Long Poll error: {lp_info['error']}")
        return
    
    server = lp_info.get("server")
    key = lp_info.get("key")
    ts = lp_info.get("ts")
    
    if not server:
        logger.error("No server")
        return
    
    if not server.startswith(('http://', 'https://')):
        server = 'https://' + server
    
    logger.info(f"📡 Server: {server}")
    logger.info("✅ BOT READY")
    logger.info("💀 Commands: !помощь или !старт (для активации)")
    
    while True:
        try:
            response = vk.long_poll_request(server, key, ts)
            
            if "failed" in response:
                if response["failed"] == 1:
                    ts = response.get("ts", ts)
                    continue
                elif response["failed"] in [2, 3]:
                    lp_info = vk.get_long_poll_server()
                    if "error" not in lp_info:
                        server = lp_info.get("server")
                        key = lp_info.get("key")
                        ts = lp_info.get("ts")
                        if server and not server.startswith(('http://', 'https://')):
                            server = 'https://' + server
                    continue
            
            ts = response.get("ts", ts)
            updates = response.get("updates", [])
            
            for update in updates:
                try:
                    if update.get("type") == "message_new":
                        await process_message(update)
                except Exception as e:
                    logger.error(f"Update error: {e}")
                    
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
