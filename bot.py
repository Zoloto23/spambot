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

API_VERSION = "5.131"
PREFIX = "!"

DATA_FILE = "chat_manager_data.json"

def load_data() -> Dict[str, Any]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "muted": {},
            "banned": {},
            "warns": {},
            "admins": {},
            "mods": {},
            "settings": {
                "welcome": "Добро пожаловать в чат!",
                "rules": ["1. Не материться", "2. Не спамить", "3. Уважать друг друга"],
                "antispam": True,
                "spam_limit": 5,
                "spam_time": 10,
                "auto_moderate": True,
                "slow_mode": False,
                "slow_delay": 3,
                "welcome_enabled": True,
                "leave_enabled": True
            },
            "message_history": {},
            "user_stats": {},
            "points": {},
            "levels": {},
            "achievements": {},
            "reminders": {},
            "polls": {},
            "game_sessions": {},
            "custom_commands": {},
            "user_notes": {},
            "birthdays": {},
            "quests": {},
            "inventory": {},
            "shop_items": {},
            "afk_users": {}
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
    def __init__(self, token: str, group_id: int, version: str = "5.131"):
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
            "random_id": int(time.time() * 1000) + random.randint(1, 99999)
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
        # Исправляем URL если нет протокола
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
    OWNERS = [1118563484]
    return user_id in OWNERS

def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    return str(user_id) in data.get("admins", {})

def is_mod(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    return str(user_id) in data.get("mods", {})

async def check_spam(message_data: dict) -> bool:
    if not data["settings"].get("antispam", True):
        return False
    
    user_id = message_data.get("from_id", 0)
    peer_id = message_data.get("peer_id", 0)
    key = f"{user_id}_{peer_id}"
    now = time.time()
    
    if key not in data["message_history"]:
        data["message_history"][key] = []
    
    spam_time = data["settings"].get("spam_time", 10)
    data["message_history"][key] = [t for t in data["message_history"][key] if now - t < spam_time]
    
    spam_limit = data["settings"].get("spam_limit", 5)
    if len(data["message_history"][key]) >= spam_limit:
        return True
    
    data["message_history"][key].append(now)
    save_data(data)
    return False

async def process_message(message_data: dict):
    try:
        # Парсим сообщение
        if "object" in message_data and "message" in message_data["object"]:
            msg = message_data["object"]["message"]
            peer_id = msg.get("peer_id", 0)
            user_id = msg.get("from_id", 0)
            text = msg.get("text", "")
        else:
            peer_id = message_data.get("peer_id", 0)
            user_id = message_data.get("from_id", 0)
            text = message_data.get("text", "")
        
        # Логируем все сообщения для отладки
        logger.info(f"📩 Message from {user_id}: {text[:30] if text else '[empty]'}")
        
        if user_id < 0:
            return
        
        # Статистика
        if "user_stats" not in data:
            data["user_stats"] = {}
        data["user_stats"][str(user_id)] = data["user_stats"].get(str(user_id), 0) + 1
        save_data(data)
        
        # Проверка на спам
        if await check_spam(message_data):
            mute_time = 5
            data["muted"][str(user_id)] = time.time() + (mute_time * 60)
            save_data(data)
            vk.messages_send(peer_id, f"🚫 Пользователь заглушен на {mute_time} минут за спам!")
            return
        
        # Проверка на мут
        if str(user_id) in data.get("muted", {}):
            if data["muted"][str(user_id)] > time.time():
                return
            else:
                del data["muted"][str(user_id)]
                save_data(data)
        
        # Проверка на бан
        if str(user_id) in data.get("banned", {}):
            if data["banned"][str(user_id)] > time.time():
                return
            else:
                del data["banned"][str(user_id)]
                save_data(data)
        
        # Slow mode
        if data["settings"].get("slow_mode", False):
            if str(user_id) in data.get("last_message_time", {}):
                if time.time() - data["last_message_time"][str(user_id)] < data["settings"].get("slow_delay", 3):
                    return
            data["last_message_time"][str(user_id)] = time.time()
            save_data(data)
        
        # Проверяем команды
        if not text.startswith(PREFIX):
            return
        
        text = text[1:].strip()
        args = text.split()
        if not args:
            return
        
        command = args[0].lower()
        user_link_text = await get_user_link(user_id)
        
        logger.info(f"⚡ Command: {command} from {user_id}")
        
        # --- ПОМОЩЬ ---
        if command == "помощь":
            help_text = (
                "🤖 **Чат-менеджер**\n\n"
                "!мут [ID] [мин] - Заглушить\n"
                "!размут [ID] - Размутить\n"
                "!кик [ID] - Кикнуть\n"
                "!варн [ID] - Предупреждение\n"
                "!бан [ID] [дней] - Забанить\n"
                "!разбан [ID] - Разбанить\n"
                "!муты - Список заглушенных\n"
                "!варны - Список предупреждений\n"
                "!баны - Список забаненных\n"
                "!админы - Список администраторов\n"
                "!профиль - Ваш профиль\n"
                "!статистика - Статистика чата\n"
                "!инфо [ID] - Информация о пользователе\n"
                "!топ - Топ пользователей\n"
                "!пинг - Пинг бота\n"
                "!кубик - Бросок кубика\n"
                "!монетка - Орёл или решка\n"
                "!баланс - Ваш баланс\n"
                "!ежедневный - Ежедневный бонус"
            )
            vk.messages_send(peer_id, help_text)
            return
        
        # --- МУТ ---
        if command == "мут":
            if not is_mod(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !мут [ID] [минут]")
                return
            try:
                target_id = int(args[1])
                minutes = int(args[2]) if len(args) > 2 else 5
                data["muted"][str(target_id)] = time.time() + (minutes * 60)
                save_data(data)
                target_link = await get_user_link(target_id)
                vk.messages_send(peer_id, f"🔇 {target_link} заглушен на {minutes} минут!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !мут [ID] [минут]")
            return
        
        # --- РАЗМУТ ---
        if command == "размут":
            if not is_mod(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !размут [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("muted", {}):
                    del data["muted"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    vk.messages_send(peer_id, f"✅ {target_link} размучен!")
                else:
                    vk.messages_send(peer_id, "❌ Пользователь не заглушен!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !размут [ID]")
            return
        
        # --- КИК ---
        if command == "кик":
            if not is_mod(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !кик [ID]")
                return
            try:
                target_id = int(args[1])
                chat_id = peer_id - 2000000000
                target_link = await get_user_link(target_id)
                result = vk.messages_remove_chat_user(chat_id, target_id)
                if "error" not in result:
                    vk.messages_send(peer_id, f"👢 {target_link} кикнут!")
                else:
                    vk.messages_send(peer_id, "❌ Не удалось кикнуть!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !кик [ID]")
            return
        
        # --- ВАРН ---
        if command == "варн":
            if not is_mod(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !варн [ID]")
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
                    vk.messages_send(peer_id, f"⚠️ {target_link} получил 3 предупреждения! Заглушен на час!")
                else:
                    vk.messages_send(peer_id, f"⚠️ {target_link} предупреждение {warns}/3")
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !варн [ID]")
            return
        
        # --- БАН ---
        if command == "бан":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !бан [ID] [дней]")
                return
            try:
                target_id = int(args[1])
                days = int(args[2]) if len(args) > 2 else 7
                data["banned"][str(target_id)] = time.time() + (days * 24 * 60 * 60)
                save_data(data)
                target_link = await get_user_link(target_id)
                vk.messages_send(peer_id, f"🚫 {target_link} забанен на {days} дней!")
                chat_id = peer_id - 2000000000
                vk.messages_remove_chat_user(chat_id, target_id)
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !бан [ID] [дней]")
            return
        
        # --- РАЗБАН ---
        if command == "разбан":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !разбан [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("banned", {}):
                    del data["banned"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    vk.messages_send(peer_id, f"✅ {target_link} разбанен!")
                else:
                    vk.messages_send(peer_id, "❌ Пользователь не забанен!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !разбан [ID]")
            return
        
        # --- МУТЫ (список) ---
        if command == "муты":
            if not data.get("muted"):
                vk.messages_send(peer_id, "📋 Нет заглушенных пользователей")
                return
            text = "🔇 **Заглушенные:**\n\n"
            now = time.time()
            for uid, until in data["muted"].items():
                if until > now:
                    link = await get_user_link(int(uid))
                    minutes = int((until - now) / 60)
                    text += f"• {link} - {minutes} мин\n"
            vk.messages_send(peer_id, text)
            return
        
        # --- ВАРНЫ (список) ---
        if command == "варны":
            if not data.get("warns"):
                vk.messages_send(peer_id, "📋 Нет предупреждений")
                return
            text = "⚠️ **Предупреждения:**\n\n"
            for uid, warns in data["warns"].items():
                if warns > 0:
                    link = await get_user_link(int(uid))
                    text += f"• {link} - {warns}/3\n"
            vk.messages_send(peer_id, text)
            return
        
        # --- БАНЫ (список) ---
        if command == "баны":
            if not data.get("banned"):
                vk.messages_send(peer_id, "📋 Нет забаненных пользователей")
                return
            text = "🚫 **Забаненные:**\n\n"
            now = time.time()
            for uid, until in data["banned"].items():
                if until > now:
                    link = await get_user_link(int(uid))
                    days = int((until - now) / (24 * 60 * 60))
                    text += f"• {link} - {days} дней\n"
            vk.messages_send(peer_id, text)
            return
        
        # --- АДМИНЫ (список) ---
        if command == "админы":
            admins = data.get("admins", {})
            if not admins:
                vk.messages_send(peer_id, "📋 Нет администраторов")
                return
            text = "👑 **Администраторы:**\n\n"
            for aid in admins:
                link = await get_user_link(int(aid))
                text += f"• {link}\n"
            vk.messages_send(peer_id, text)
            return
        
        # --- ПРОФИЛЬ ---
        if command == "профиль":
            target_id = user_id
            if len(args) > 1 and args[1].isdigit():
                target_id = int(args[1])
            
            target_link = await get_user_link(target_id)
            stats = data.get("user_stats", {}).get(str(target_id), 0)
            warns = data.get("warns", {}).get(str(target_id), 0)
            points = data.get("points", {}).get(str(target_id), 0)
            is_muted = str(target_id) in data.get("muted", {})
            is_banned = str(target_id) in data.get("banned", {})
            
            status = "✅ Активен"
            if is_banned:
                status = "🔴 Забанен"
            elif is_muted:
                status = "🔇 Заглушен"
            
            text = (
                f"👤 **Профиль**\n\n"
                f"Пользователь: {target_link}\n"
                f"ID: {target_id}\n"
                f"Сообщений: {stats}\n"
                f"Предупреждений: {warns}/3\n"
                f"Монет: {points}\n"
                f"Статус: {status}"
            )
            vk.messages_send(peer_id, text)
            return
        
        # --- СТАТИСТИКА ---
        if command == "статистика":
            total_users = len(data.get("user_stats", {}))
            total_messages = sum(data.get("user_stats", {}).values())
            text = (
                f"📊 **Статистика чата:**\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"💬 Всего сообщений: {total_messages}\n"
                f"🚫 Забанено: {len(data.get('banned', {}))}\n"
                f"🔇 Заглушено: {len(data.get('muted', {}))}\n"
                f"⚠️ Предупреждений: {sum(data.get('warns', {}).values())}"
            )
            vk.messages_send(peer_id, text)
            return
        
        # --- ИНФО ---
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
                    vk.messages_send(peer_id, text)
                else:
                    vk.messages_send(peer_id, "❌ Не удалось получить информацию")
            except:
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # --- ТОП ---
        if command == "топ":
            sorted_users = sorted(data.get("points", {}).items(), key=lambda x: x[1], reverse=True)[:10]
            if not sorted_users:
                vk.messages_send(peer_id, "📋 Нет данных для топа")
                return
            text = "🏆 **Топ пользователей:**\n\n"
            for i, (uid, points) in enumerate(sorted_users, 1):
                link = await get_user_link(int(uid))
                text += f"{i}. {link} - {points} монет\n"
            vk.messages_send(peer_id, text)
            return
        
        # --- ПИНГ ---
        if command == "пинг":
            start = time.time()
            vk.users_get(GROUP_ID)
            latency = int((time.time() - start) * 1000)
            vk.messages_send(peer_id, f"🏓 Понг! {latency} мс")
            return
        
        # --- КУБИК ---
        if command == "кубик":
            sides = 6
            if len(args) > 1 and args[1].isdigit():
                sides = min(max(int(args[1]), 2), 100)
            result = random.randint(1, sides)
            vk.messages_send(peer_id, f"🎲 {result} (1-{sides})")
            return
        
        # --- МОНЕТКА ---
        if command == "монетка":
            result = random.choice(["🦅 Орёл", "🪙 Решка"])
            vk.messages_send(peer_id, f"{result}")
            return
        
        # --- БАЛАНС ---
        if command == "баланс":
            points = data.get("points", {}).get(str(user_id), 0)
            vk.messages_send(peer_id, f"💰 Ваш баланс: {points} монет")
            return
        
        # --- ЕЖЕДНЕВНЫЙ ---
        if command == "ежедневный":
            if "points" not in data:
                data["points"] = {}
            bonus = random.randint(50, 150)
            data["points"][str(user_id)] = data["points"].get(str(user_id), 0) + bonus
            save_data(data)
            vk.messages_send(peer_id, f"🎁 Бонус: {bonus} монет")
            return
        
    except Exception as e:
        logger.error(f"Process error: {e}")

start_time = time.time()

async def main():
    logger.info("🚀 CHAT MANAGER BOT START")
    logger.info(f"Group: {GROUP_ID}")
    
    # Проверка токена
    try:
        info = vk.groups_get_by_id()
        if "error" in info:
            logger.error(f"Token error: {info['error']}")
            return
        logger.info("✅ Token OK")
    except Exception as e:
        logger.error(f"Error: {e}")
        return
    
    # Получаем Long Poll
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
    logger.info(f"🔑 Key: {key[:20]}...")
    logger.info(f"🕐 TS: {ts}")
    
    logger.info("✅ BOT READY")
    logger.info("💀 Commands: !помощь")
    
    last_message_id = 0
    
    while True:
        try:
            response = vk.long_poll_request(server, key, ts)
            
            # Логируем ответ Long Poll
            if "failed" in response:
                logger.warning(f"Long Poll failed: {response['failed']}")
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
            
            if updates:
                logger.info(f"📨 Updates: {len(updates)}")
            
            for update in updates:
                try:
                    # Обрабатываем только новые сообщения
                    if update.get("type") == "message_new":
                        await process_message(update)
                    else:
                        # Логируем другие типы обновлений
                        logger.info(f"ℹ️ Other update: {update.get('type', 'unknown')}")
                except Exception as e:
                    logger.error(f"Update error: {e}")
                    
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
