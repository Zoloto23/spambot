#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import logging
import json
import time
import random
import requests
import re
from datetime import datetime

# ============================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================
# ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (с понятным выводом)
# ============================================================
TOKEN = os.environ.get("VK_GROUP_TOKEN")
GROUP_ID = os.environ.get("VK_GROUP_ID")

logger.info("=" * 60)
logger.info("🤖 ЗАПУСК VK БОТА")
logger.info("=" * 60)

if not TOKEN:
    logger.error("❌ VK_GROUP_TOKEN не установлен!")
    logger.info("📌 Установите переменную окружения VK_GROUP_TOKEN")
    logger.info("📌 Пример: export VK_GROUP_TOKEN=ваш_токен")
    logger.info("📌 Или добавьте в docker-compose.yml:")
    logger.info("   environment:")
    logger.info("     - VK_GROUP_TOKEN=ваш_токен")
    logger.info("     - VK_GROUP_ID=ваш_id")
    logger.info("=" * 60)
    exit(1)

if not GROUP_ID:
    logger.error("❌ VK_GROUP_ID не установлен!")
    logger.info("📌 Установите переменную окружения VK_GROUP_ID")
    logger.info("📌 Пример: export VK_GROUP_ID=123456789")
    logger.info("=" * 60)
    exit(1)

try:
    GROUP_ID = int(GROUP_ID)
except ValueError:
    logger.error(f"❌ VK_GROUP_ID должен быть числом, получено: {GROUP_ID}")
    exit(1)

logger.info(f"✅ Токен получен (длина: {len(TOKEN)} символов)")
logger.info(f"✅ ID группы: {GROUP_ID}")

API_VERSION = "5.199"
DATA_FILE = "bot_data.json"

# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info("📁 Файл данных не найден, создаю новый...")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
    
    return {
        "owner": 1118563484,
        "admins": {},
        "mods": {},
        "muted": {},
        "banned": {},
        "warns": {},
        "money": {},
        "exp": {},
        "level": {},
        "rep": {},
        "marriage": {},
        "work": {},
        "inventory": {},
        "daily_bonus": {},
        "afk_users": {},
        "reminders": {},
        "polls": {},
        "games": {},
        "user_stats": {},
        "message_history": {},
        "group_chats": [],
        "private_chats": [],
        "nicks": {},
        "user_roles": {},
        "commands_usage": {},
        "todos": {},
        "rep_history": {},
        "marriage_requests": {},
        "settings": {
            "welcome": "👋 Добро пожаловать в чат, {user}!",
            "farewell": "👋 Пока, {user}!",
            "rules": "1. Не материться\n2. Не спамить\n3. Уважать друг друга",
            "antispam": True,
            "spam_limit": 3,
            "spam_time": 5,
            "antilink": True,
            "whitelist": ["vk.com", "youtube.com", "t.me"],
            "slow_mode": False,
            "slow_delay": 3,
            "leveling": True,
            "economy": True,
            "daily_amount": 100,
            "max_warns": 3,
            "ban_duration": 7,
            "mute_duration": 5
        },
        "shop": {
            "items": [
                {"id": "vip", "name": "👑 VIP", "price": 100000, "desc": "VIP статус"},
                {"id": "premium", "name": "💎 Premium", "price": 50000, "desc": "Premium статус"},
                {"id": "red", "name": "🔴 Красный", "price": 5000, "desc": "Красный ник"},
                {"id": "blue", "name": "🔵 Синий", "price": 5000, "desc": "Синий ник"},
                {"id": "gold", "name": "🟡 Золотой", "price": 10000, "desc": "Золотой ник"}
            ]
        }
    }

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        return False

data = load_data()
logger.info(f"✅ Данные загружены: {len(data.get('user_stats', {}))} пользователей")

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def user_link(user_id, name=None):
    if name is None:
        return f"[id{user_id}|Пользователь]"
    return f"[id{user_id}|{name}]"

def get_nick(user_id):
    return data.get("nicks", {}).get(str(user_id))

def is_owner(user_id):
    return user_id == data.get("owner", 0)

def is_admin(user_id):
    return is_owner(user_id) or str(user_id) in data.get("admins", {})

def is_mod(user_id):
    return is_admin(user_id) or str(user_id) in data.get("mods", {})

def is_banned(user_id, peer_id):
    key = f"{peer_id}_{user_id}"
    if key in data.get("banned", {}):
        if data["banned"][key] > time.time():
            return True
        else:
            del data["banned"][key]
            save_data()
    return False

def is_muted(user_id, peer_id):
    key = f"{peer_id}_{user_id}"
    if key in data.get("muted", {}):
        if data["muted"][key] > time.time():
            return True
        else:
            del data["muted"][key]
            save_data()
    return False

def get_user_level(user_id):
    return data.get("level", {}).get(str(user_id), 1)

def get_user_exp(user_id):
    return data.get("exp", {}).get(str(user_id), 0)

def get_user_money(user_id):
    return data.get("money", {}).get(str(user_id), 0)

def get_user_rep(user_id):
    return data.get("rep", {}).get(str(user_id), 0)

def get_user_warns(user_id):
    return data.get("warns", {}).get(str(user_id), 0)

def get_required_exp(level):
    return level * 100 + 50

async def get_user_name(user_id):
    try:
        result = vk.users_get(user_id)
        if "error" not in result and result:
            user = result[0]
            return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return f"ID {user_id}"
    except:
        return f"ID {user_id}"

async def get_display_name(user_id):
    nick = get_nick(user_id)
    if nick:
        return nick
    return await get_user_name(user_id)

async def get_display_link(user_id):
    name = await get_display_name(user_id)
    return user_link(user_id, name)

async def add_money(user_id, amount):
    data["money"][str(user_id)] = data["money"].get(str(user_id), 0) + amount
    save_data()

async def remove_money(user_id, amount):
    current = data["money"].get(str(user_id), 0)
    if current < amount:
        return False
    data["money"][str(user_id)] = current - amount
    save_data()
    return True

async def add_exp(user_id, amount):
    data["exp"][str(user_id)] = data["exp"].get(str(user_id), 0) + amount
    exp = data["exp"][str(user_id)]
    data["level"][str(user_id)] = int(exp / 100) + 1
    save_data()

def check_spam(user_id, peer_id):
    if not data["settings"].get("antispam", True):
        return False
    key = f"{peer_id}_{user_id}"
    now = time.time()
    spam_time = data["settings"].get("spam_time", 5)
    spam_limit = data["settings"].get("spam_limit", 3)
    if key not in data["message_history"]:
        data["message_history"][key] = []
    data["message_history"][key] = [t for t in data["message_history"][key] if now - t < spam_time]
    if len(data["message_history"][key]) >= spam_limit:
        return True
    data["message_history"][key].append(now)
    save_data()
    return False

def check_links(text):
    if not data["settings"].get("antilink", True):
        return False
    whitelist = data["settings"].get("whitelist", ["vk.com", "youtube.com", "t.me"])
    url_pattern = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
    links = re.findall(url_pattern, text, re.IGNORECASE)
    for link in links:
        if not any(w in link.lower() for w in whitelist):
            return True
    return False

# ============================================================
# КЛАСС VK API
# ============================================================
class VKAPI:
    def __init__(self, token, group_id):
        self.token = token
        self.group_id = group_id
        self.base_url = "https://api.vk.com/method/"
        self.version = API_VERSION
        self.session = requests.Session()
    
    def _request(self, method, params=None):
        if params is None:
            params = {}
        params["access_token"] = self.token
        params["v"] = self.version
        try:
            response = self.session.post(self.base_url + method, data=params, timeout=15)
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                error = result["error"]
                error_msg = error.get("error_msg", "Unknown error")
                error_code = error.get("error_code", 0)
                
                if error_code == 917:  # Flood control
                    logger.warning("Флуд-контроль, пауза 1 секунда...")
                    time.sleep(1)
                    return self._request(method, params)
                elif error_code == 6:  # Too many requests
                    time.sleep(0.5)
                    return self._request(method, params)
                
                logger.error(f"VK API ошибка {error_code}: {error_msg}")
                return {"error": error}
            return result.get("response", {})
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут запроса к {method}")
            return {"error": {"error_msg": "Timeout"}}
        except requests.exceptions.ConnectionError:
            logger.error(f"Ошибка соединения при запросе к {method}")
            return {"error": {"error_msg": "Connection error"}}
        except Exception as e:
            logger.error(f"Неизвестная ошибка в {method}: {e}")
            return {"error": {"error_msg": str(e)}}
    
    def messages_send(self, peer_id, message=None, attachment=None, sticker_id=None):
        params = {
            "peer_id": peer_id,
            "random_id": int(time.time() * 1000000) + random.randint(1, 999999),
            "disable_mentions": 0
        }
        if message:
            params["message"] = message[:4096]  # Лимит ВК
        if attachment:
            params["attachment"] = attachment
        if sticker_id:
            params["sticker_id"] = sticker_id
        return self._request("messages.send", params)
    
    def messages_remove_chat_user(self, chat_id, user_id):
        return self._request("messages.removeChatUser", {
            "chat_id": chat_id,
            "user_id": user_id
        })
    
    def users_get(self, user_ids):
        return self._request("users.get", {"user_ids": user_ids})
    
    def groups_get_by_id(self):
        return self._request("groups.getById", {"group_id": self.group_id})
    
    def get_long_poll_server(self):
        return self._request("groups.getLongPollServer", {"group_id": self.group_id})
    
    def long_poll_request(self, server, key, ts, wait=25):
        if not server.startswith(('http://', 'https://')):
            server = 'https://' + server
        url = f"{server}?act=a_check&key={key}&ts={ts}&wait={wait}&mode=2&version=2"
        try:
            response = self.session.get(url, timeout=wait + 10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Long Poll ошибка: {e}")
            return {"failed": 1}

vk = VKAPI(TOKEN, GROUP_ID)

# ============================================================
# ОБРАБОТКА НАПОМИНАНИЙ
# ============================================================
async def check_reminders():
    try:
        now = time.time()
        for rid, reminder in list(data.get("reminders", {}).items()):
            if reminder.get("time", 0) <= now:
                user_id = reminder.get("user_id")
                peer_id = reminder.get("peer_id")
                text = reminder.get("text", "Напоминание")
                try:
                    name = await get_display_name(user_id)
                    vk.messages_send(peer_id, f"⏰ **Напоминание для {name}:**\n{text}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания: {e}")
                del data["reminders"][rid]
                save_data()
    except Exception as e:
        logger.error(f"Ошибка проверки напоминаний: {e}")

# ============================================================
# ОБРАБОТКА СООБЩЕНИЙ
# ============================================================
async def process_message(message_data):
    try:
        if not isinstance(message_data, dict):
            return
        if "object" not in message_data or "message" not in message_data["object"]:
            return
        
        msg = message_data["object"]["message"]
        peer_id = msg.get("peer_id", 0)
        user_id = msg.get("from_id", 0)
        text = msg.get("text", "")
        
        if user_id < 0:
            return
        
        if is_banned(user_id, peer_id):
            return
        
        if is_muted(user_id, peer_id):
            try:
                vk.messages_send(peer_id, "🔇 Вы заглушены!")
            except:
                pass
            return
        
        # Статистика
        data["user_stats"][str(user_id)] = data["user_stats"].get(str(user_id), 0) + 1
        save_data()
        
        # Опыт
        if data["settings"].get("leveling", True):
            if random.random() < 0.1:
                await add_exp(user_id, random.randint(1, 5))
        
        # Антиспам и антиссылки
        if peer_id > 2000000000:
            if check_links(text) and not is_mod(user_id):
                vk.messages_send(peer_id, "🚫 Ссылки запрещены!")
                return
            if check_spam(user_id, peer_id) and not is_mod(user_id):
                mute_time = data["settings"].get("mute_duration", 5)
                data["muted"][f"{peer_id}_{user_id}"] = time.time() + (mute_time * 60)
                save_data()
                vk.messages_send(peer_id, f"🚫 Заглушен на {mute_time} минут за спам!")
                return
        
        if not text or not text.startswith("!"):
            return
        
        command = text[1:].strip().lower()
        args = text.split()[1:] if len(text.split()) > 1 else []
        
        # ============================================================
        # КОМАНДЫ ВЛАДЕЛЬЦА
        # ============================================================
        if is_owner(user_id):
            if command == "set_owner":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !set_owner [ID]")
                        return
                    new_owner = int(args[0])
                    data["owner"] = new_owner
                    save_data()
                    vk.messages_send(peer_id, f"✅ Владелец изменен на {await get_display_link(new_owner)}")
                except Exception as e:
                    logger.error(f"set_owner ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "add_admin":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !add_admin [ID]")
                        return
                    target_id = int(args[0])
                    data["admins"][str(target_id)] = True
                    save_data()
                    vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} добавлен в админы")
                except Exception as e:
                    logger.error(f"add_admin ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "remove_admin":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !remove_admin [ID]")
                        return
                    target_id = int(args[0])
                    if str(target_id) in data.get("admins", {}):
                        del data["admins"][str(target_id)]
                        save_data()
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} удален из админов")
                    else:
                        vk.messages_send(peer_id, "❌ Не админ!")
                except Exception as e:
                    logger.error(f"remove_admin ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "add_mod":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !add_mod [ID]")
                        return
                    target_id = int(args[0])
                    data["mods"][str(target_id)] = True
                    save_data()
                    vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} добавлен в модераторы")
                except Exception as e:
                    logger.error(f"add_mod ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "remove_mod":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !remove_mod [ID]")
                        return
                    target_id = int(args[0])
                    if str(target_id) in data.get("mods", {}):
                        del data["mods"][str(target_id)]
                        save_data()
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} удален из модераторов")
                    else:
                        vk.messages_send(peer_id, "❌ Не модератор!")
                except Exception as e:
                    logger.error(f"remove_mod ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "save":
                if save_data():
                    vk.messages_send(peer_id, "✅ Данные сохранены!")
                else:
                    vk.messages_send(peer_id, "❌ Ошибка сохранения!")
                return
            
            if command == "restart" or command == "reboot":
                vk.messages_send(peer_id, "🔄 Перезагрузка...")
                save_data()
                os._exit(0)
                return
        
        # ============================================================
        # КОМАНДЫ МОДЕРАЦИИ
        # ============================================================
        if is_mod(user_id):
            if command == "mute" or command == "мут":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !mute [ID] [минут]")
                        return
                    target_id = int(args[0])
                    minutes = int(args[1]) if len(args) > 1 else data["settings"].get("mute_duration", 5)
                    data["muted"][f"{peer_id}_{target_id}"] = time.time() + (minutes * 60)
                    save_data()
                    vk.messages_send(peer_id, f"🔇 {await get_display_link(target_id)} заглушен на {minutes} минут!")
                except Exception as e:
                    logger.error(f"mute ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "unmute" or command == "размут":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !unmute [ID]")
                        return
                    target_id = int(args[0])
                    key = f"{peer_id}_{target_id}"
                    if key in data.get("muted", {}):
                        del data["muted"][key]
                        save_data()
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} размучен!")
                    else:
                        vk.messages_send(peer_id, "❌ Не заглушен!")
                except Exception as e:
                    logger.error(f"unmute ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "kick" or command == "кик":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !kick [ID]")
                        return
                    target_id = int(args[0])
                    chat_id = peer_id - 2000000000
                    result = vk.messages_remove_chat_user(chat_id, target_id)
                    if "error" not in result:
                        vk.messages_send(peer_id, f"👢 {await get_display_link(target_id)} кикнут!")
                    else:
                        vk.messages_send(peer_id, "❌ Ошибка!")
                except Exception as e:
                    logger.error(f"kick ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "ban" or command == "бан":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !ban [ID] [дней]")
                        return
                    target_id = int(args[0])
                    days = int(args[1]) if len(args) > 1 else data["settings"].get("ban_duration", 7)
                    data["banned"][f"{peer_id}_{target_id}"] = time.time() + (days * 24 * 60 * 60)
                    save_data()
                    vk.messages_send(peer_id, f"🚫 {await get_display_link(target_id)} забанен на {days} дней!")
                    chat_id = peer_id - 2000000000
                    vk.messages_remove_chat_user(chat_id, target_id)
                except Exception as e:
                    logger.error(f"ban ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "unban" or command == "разбан":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !unban [ID]")
                        return
                    target_id = int(args[0])
                    key = f"{peer_id}_{target_id}"
                    if key in data.get("banned", {}):
                        del data["banned"][key]
                        save_data()
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} разбанен!")
                    else:
                        vk.messages_send(peer_id, "❌ Не забанен!")
                except Exception as e:
                    logger.error(f"unban ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "warn" or command == "варн":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ !warn [ID]")
                        return
                    target_id = int(args[0])
                    data["warns"][str(target_id)] = data["warns"].get(str(target_id), 0) + 1
                    warns = data["warns"][str(target_id)]
                    max_warns = data["settings"].get("max_warns", 3)
                    save_data()
                    if warns >= max_warns:
                        days = data["settings"].get("ban_duration", 7)
                        data["banned"][f"{peer_id}_{target_id}"] = time.time() + (days * 24 * 60 * 60)
                        save_data()
                        vk.messages_send(peer_id, f"🚫 {await get_display_link(target_id)} забанен на {days} дней ({max_warns} предупреждений)!")
                    else:
                        vk.messages_send(peer_id, f"⚠️ {await get_display_link(target_id)} предупреждение {warns}/{max_warns}")
                except Exception as e:
                    logger.error(f"warn ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
            
            if command == "set_rules" or command == "правила":
                try:
                    if not args:
                        current = data["settings"].get("rules", "Правила не установлены")
                        vk.messages_send(peer_id, f"📋 **Текущие правила:**\n{current}")
                        return
                    rules = " ".join(args)
                    data["settings"]["rules"] = rules
                    save_data()
                    vk.messages_send(peer_id, "✅ Правила обновлены!")
                except Exception as e:
                    logger.error(f"set_rules ошибка: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка!")
                return
        
        # ============================================================
        # ОБЩИЕ КОМАНДЫ
        # ============================================================
        
        # help
        if command == "help" or command == "помощь":
            help_text = """📚 **Доступные команды:**

👤 **Профиль:**
!profile — ваш профиль
!profile [ID] — профиль пользователя
!stats — ваша статистика
!level — ваш уровень

💰 **Экономика:**
!money — ваш баланс
!daily — ежедневный бонус
!shop — магазин
!buy [товар] — купить товар

⭐ **Репутация:**
!rep [ID] — дать репутацию

🎮 **Развлечения:**
!roll [число] — бросить кубик
!coin — подбросить монетку
!8ball [вопрос] — магический шар

⚙️ **Другое:**
!help — эта справка
!rules — правила чата
!info — информация о боте"""
            vk.messages_send(peer_id, help_text)
            return
        
        # profile
        if command == "profile" or command == "профиль":
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                name = await get_display_name(target_id)
                level = get_user_level(target_id)
                exp = get_user_exp(target_id)
                money = get_user_money(target_id)
                rep = get_user_rep(target_id)
                warns = get_user_warns(target_id)
                stats = data.get("user_stats", {}).get(str(target_id), 0)
                next_level_exp = get_required_exp(level)
                profile_text = f"""👤 **Профиль {name}**
📊 Уровень: {level}
📈 Опыт: {exp}/{next_level_exp}
💰 Денег: {money}
⭐ Репутация: {rep}
⚠️ Предупреждений: {warns}
📝 Сообщений: {stats}"""
                vk.messages_send(peer_id, profile_text)
            except Exception as e:
                logger.error(f"profile ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # money
        if command == "money" or command == "баланс" or command == "деньги":
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                name = await get_display_name(target_id)
                money = get_user_money(target_id)
                vk.messages_send(peer_id, f"💰 Баланс {name}: {money} монет")
            except Exception as e:
                logger.error(f"money ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # daily
        if command == "daily" or command == "ежедневный":
            try:
                key = f"{peer_id}_{user_id}"
                now = time.time()
                last_claim = data.get("daily_bonus", {}).get(key, 0)
                if now - last_claim < 86400:
                    remaining = int(86400 - (now - last_claim))
                    hours = remaining // 3600
                    minutes = (remaining % 3600) // 60
                    vk.messages_send(peer_id, f"⏳ Бонус через {hours}ч {minutes}мин")
                    return
                amount = data["settings"].get("daily_amount", 100)
                await add_money(user_id, amount)
                data["daily_bonus"][key] = now
                save_data()
                vk.messages_send(peer_id, f"🎉 +{amount} монет!")
            except Exception as e:
                logger.error(f"daily ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # shop
        if command == "shop" or command == "магазин":
            try:
                items = data.get("shop", {}).get("items", [])
                if not items:
                    vk.messages_send(peer_id, "📋 Магазин пуст")
                    return
                text = "🛒 **Магазин:**\n"
                for item in items:
                    text += f"• {item['name']} — {item['price']} монет (ID: {item['id']})\n"
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"shop ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # buy
        if command == "buy" or command == "купить":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ !buy [ID товара]")
                    return
                item_id = args[0]
                items = data.get("shop", {}).get("items", [])
                item = next((i for i in items if i.get("id") == item_id), None)
                if not item:
                    vk.messages_send(peer_id, "❌ Товар не найден!")
                    return
                price = item.get("price", 0)
                if await remove_money(user_id, price):
                    if "inventory" not in data:
                        data["inventory"] = {}
                    if str(user_id) not in data["inventory"]:
                        data["inventory"][str(user_id)] = []
                    data["inventory"][str(user_id)].append(item_id)
                    save_data()
                    vk.messages_send(peer_id, f"✅ Куплено {item['name']} за {price} монет!")
                else:
                    vk.messages_send(peer_id, f"❌ Недостаточно денег! Нужно: {price}")
            except Exception as e:
                logger.error(f"buy ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # level
        if command == "level" or command == "уровень":
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                name = await get_display_name(target_id)
                level = get_user_level(target_id)
                exp = get_user_exp(target_id)
                next_level_exp = get_required_exp(level)
                vk.messages_send(peer_id, f"📊 Уровень {name}: {level}\n📈 Опыт: {exp}/{next_level_exp}")
            except Exception as e:
                logger.error(f"level ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # rep
        if command == "rep" or command == "репутация":
            try:
                if not args:
                    rep = get_user_rep(user_id)
                    vk.messages_send(peer_id, f"⭐ Ваша репутация: {rep}")
                    return
                target_id = int(args[0])
                key = f"rep_{user_id}_{target_id}"
                if key in data.get("rep_history", {}):
                    if time.time() - data["rep_history"][key] < 86400:
                        vk.messages_send(peer_id, "⏳ Вы уже давали репутацию сегодня!")
                        return
                data["rep"][str(target_id)] = data["rep"].get(str(target_id), 0) + 1
                data["rep_history"][key] = time.time()
                save_data()
                vk.messages_send(peer_id, f"⭐ {await get_display_link(target_id)} получил репутацию!")
            except Exception as e:
                logger.error(f"rep ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # rules
        if command == "rules" or command == "правила":
            try:
                rules = data["settings"].get("rules", "Правила не установлены")
                vk.messages_send(peer_id, f"📋 **Правила чата:**\n{rules}")
            except Exception as e:
                logger.error(f"rules ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # info
        if command == "info" or command == "инфо":
            try:
                info_text = f"""🤖 **Информация о боте**
👥 Пользователей: {len(data.get('user_stats', {}))}
💬 Чатов: {len(data.get('group_chats', []))}
⚙️ API: {API_VERSION}"""
                vk.messages_send(peer_id, info_text)
            except Exception as e:
                logger.error(f"info ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # roll
        if command == "roll" or command == "кубик":
            try:
                max_num = int(args[0]) if args and args[0].isdigit() else 6
                if max_num < 2:
                    max_num = 2
                if max_num > 100:
                    max_num = 100
                result = random.randint(1, max_num)
                vk.messages_send(peer_id, f"🎲 {await get_display_link(user_id)} выбросил {result} из {max_num}")
            except Exception as e:
                logger.error(f"roll ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # coin
        if command == "coin" or command == "монетка":
            try:
                result = "Орел" if random.random() < 0.5 else "Решка"
                vk.messages_send(peer_id, f"🪙 {await get_display_link(user_id)}: {result}")
            except Exception as e:
                logger.error(f"coin ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # 8ball
        if command == "8ball" or command == "шар":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ !8ball [вопрос]")
                    return
                answers = ["Да", "Нет", "Возможно", "Скорее всего", "Спроси позже", 
                          "Определенно да", "Определенно нет", "Может быть", "Неизвестно"]
                answer = random.choice(answers)
                vk.messages_send(peer_id, f"🔮 {answer}")
            except Exception as e:
                logger.error(f"8ball ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # ping
        if command == "ping":
            vk.messages_send(peer_id, "🏓 Понг!")
            return
        
        # whoami
        if command == "whoami" or command == "ктоя":
            try:
                name = await get_display_name(user_id)
                level = get_user_level(user_id)
                money = get_user_money(user_id)
                vk.messages_send(peer_id, f"👤 Вы: {name}\n📊 Уровень: {level}\n💰 Денег: {money}")
            except Exception as e:
                logger.error(f"whoami ошибка: {e}")
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
    except Exception as e:
        logger.error(f"Ошибка в process_message: {e}")

# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================
async def main():
    logger.info("=" * 60)
    logger.info("🚀 Бот запускается...")
    logger.info("=" * 60)
    
    # Проверка подключения к VK
    try:
        logger.info("📡 Проверка подключения к VK API...")
        group_info = vk.groups_get_by_id()
        if "error" in group_info:
            logger.error(f"❌ Ошибка подключения: {group_info['error']}")
            logger.info("⚠️ Проверьте токен и ID группы!")
            return
        if group_info:
            group = group_info[0] if isinstance(group_info, list) else group_info
            logger.info(f"✅ Подключено к группе: {group.get('name', 'Неизвестно')}")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подключения: {e}")
        return
    
    # Получение Long Poll сервера
    logger.info("📡 Получение Long Poll сервера...")
    server_data = vk.get_long_poll_server()
    if "error" in server_data:
        logger.error(f"❌ Ошибка получения Long Poll: {server_data['error']}")
        return
    
    server = server_data.get("server")
    key = server_data.get("key")
    ts = server_data.get("ts")
    
    if not server or not key or not ts:
        logger.error("❌ Не удалось получить параметры Long Poll!")
        return
    
    logger.info(f"✅ Long Poll сервер получен")
    logger.info("=" * 60)
    logger.info("🤖 Бот готов к работе! Ожидание сообщений...")
    logger.info("=" * 60)
    
    last_reminder_check = 0
    
    while True:
        try:
            if time.time() - last_reminder_check > 60:
                await check_reminders()
                last_reminder_check = time.time()
            
            response = vk.long_poll_request(server, key, ts)
            
            if "failed" in response:
                error_code = response.get("failed", 0)
                if error_code in [1, 2, 3]:
                    logger.warning(f"Long Poll ошибка {error_code}, обновление...")
                    server_data = vk.get_long_poll_server()
                    if "error" not in server_data:
                        server = server_data.get("server", server)
                        key = server_data.get("key", key)
                        ts = server_data.get("ts", ts)
                    continue
                else:
                    logger.error(f"Неизвестная ошибка Long Poll: {response}")
                    time.sleep(5)
                    continue
            
            ts = response.get("ts", ts)
            updates = response.get("updates", [])
            
            for update in updates:
                try:
                    update_type = update.get("type")
                    if update_type == "message_new":
                        await process_message(update.get("object", {}))
                except Exception as e:
                    logger.error(f"Ошибка обработки обновления: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"💀 Критическая ошибка: {e}")
        raise
