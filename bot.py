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
    """Создает синюю ссылку на пользователя"""
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
        
        if not text.startswith(PREFIX):
            return
        
        text = text[1:].strip()
        args = text.split()
        if not args:
            return
        
        command = args[0].lower()
        user_link_text = await get_user_link(user_id)
        
        # ============================================================
        # 1. МОДЕРАЦИЯ (25 команд)
        # ============================================================
        
        if command == "помощь":
            help_text = (
                "🤖 **Чат-менеджер**\n\n"
                "**👑 Администрация:**\n"
                "!мут [ID] [мин] - Заглушить\n"
                "!размут [ID] - Размутить\n"
                "!кик [ID] - Кикнуть\n"
                "!варн [ID] - Предупреждение\n"
                "!бан [ID] [дней] - Забанить\n"
                "!разбан [ID] - Разбанить\n"
                "!очистить [кол-во] - Очистить чат\n"
                "!правила - Показать правила\n"
                "!добавить_правило [текст] - Добавить правило\n"
                "!удалить_правило [номер] - Удалить правило\n"
                "!приветствие [текст] - Установить приветствие\n"
                "!прощание [текст] - Установить прощание\n"
                "!медленный_режим [вкл/выкл] - Медленный режим\n"
                "!антиспам [вкл/выкл] - Антиспам\n"
                "!муты - Список заглушенных\n"
                "!варны - Список предупреждений\n"
                "!баны - Список забаненных\n"
                "!админы - Список администраторов\n"
                "!модераторы - Список модераторов\n"
                "!добавить_админа [ID] - Добавить админа\n"
                "!удалить_админа [ID] - Удалить админа\n"
                "!добавить_мода [ID] - Добавить модератора\n"
                "!удалить_мода [ID] - Удалить модератора\n\n"
                "**📊 Информация:**\n"
                "!профиль - Ваш профиль\n"
                "!статистика - Статистика чата\n"
                "!инфо [ID] - Информация о пользователе\n"
                "!топ - Топ пользователей\n"
                "!онлайн - Онлайн пользователи\n"
                "!время - Текущее время\n"
                "!пинг - Пинг бота\n"
                "!аптайм - Время работы\n"
                "!команды - Список команд\n\n"
                "**🎮 Развлечения:**\n"
                "!кубик [сторон] - Бросок кубика\n"
                "!монетка - Орёл или решка\n"
                "!шар [вопрос] - Магический шар\n"
                "!шутка - Шутка\n"
                "!цитата - Цитата дня\n"
                "!гороскоп [знак] - Гороскоп\n"
                "!любовь [имя] - Калькулятор любви\n"
                "!игра - Начать игру\n"
                "!присоединиться [ID] - Присоединиться к игре\n"
                "!лидеры - Таблица лидеров\n\n"
                "**💰 Экономика:**\n"
                "!баланс - Ваш баланс\n"
                "!ежедневный - Ежедневный бонус\n"
                "!перевести [ID] [сумма] - Перевести монеты\n"
                "!казино [сумма] - Сделать ставку\n\n"
                "**🔧 Утилиты:**\n"
                "!калькулятор [выражение] - Калькулятор\n"
                "!случайное [мин] [макс] - Случайное число\n"
                "!перевернуть [текст] - Перевернуть текст\n"
                "!верхний [текст] - В верхний регистр\n"
                "!нижний [текст] - В нижний регистр\n"
                "!посчитать [текст] - Подсчитать символы\n"
                "!заметка [текст] - Сохранить заметку\n"
                "!напомнить [время] [текст] - Напомнить\n"
                "!др [дата] - Установить день рождения\n"
                "!афк [причина] - Уйти в AFK\n"
                "!не_афк - Вернуться из AFK\n"
                "!эхо [текст] - Повторить текст"
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
        
        # --- ОЧИСТИТЬ ---
        if command == "очистить":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            count = 20
            if len(args) > 1 and args[1].isdigit():
                count = min(int(args[1]), 100)
            vk.messages_send(peer_id, f"🧹 Очищено {count} сообщений (демонстрация)")
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
        
        # --- ПРАВИЛА ---
        if command == "правила":
            rules = data["settings"].get("rules", ["Правила не установлены"])
            if isinstance(rules, list):
                text = "📋 **Правила чата:**\n\n"
                for i, rule in enumerate(rules, 1):
                    text += f"{i}. {rule}\n"
            else:
                text = f"📋 **Правила чата:**\n{rules}"
            vk.messages_send(peer_id, text)
            return
        
        # --- ДОБАВИТЬ ПРАВИЛО ---
        if command == "добавить_правило":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !добавить_правило [текст]")
                return
            rule = " ".join(args[1:])
            if "rules" not in data["settings"] or isinstance(data["settings"]["rules"], str):
                data["settings"]["rules"] = []
            data["settings"]["rules"].append(rule)
            save_data(data)
            vk.messages_send(peer_id, f"✅ Правило добавлено: {rule}")
            return
        
        # --- УДАЛИТЬ ПРАВИЛО ---
        if command == "удалить_правило":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2 or not args[1].isdigit():
                vk.messages_send(peer_id, "❌ !удалить_правило [номер]")
                return
            try:
                idx = int(args[1]) - 1
                if "rules" not in data["settings"] or idx >= len(data["settings"]["rules"]):
                    vk.messages_send(peer_id, "❌ Правило не найдено!")
                    return
                removed = data["settings"]["rules"].pop(idx)
                save_data(data)
                vk.messages_send(peer_id, f"✅ Правило удалено: {removed}")
            except:
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # --- ПРИВЕТСТВИЕ ---
        if command == "приветствие":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                current = data["settings"].get("welcome", "Не установлено")
                vk.messages_send(peer_id, f"Текущее приветствие: {current}")
                return
            welcome_text = " ".join(args[1:])
            data["settings"]["welcome"] = welcome_text
            save_data(data)
            vk.messages_send(peer_id, f"✅ Приветствие установлено!")
            return
        
        # --- ПРОЩАНИЕ ---
        if command == "прощание":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                current = data["settings"].get("leave_message", "Не установлено")
                vk.messages_send(peer_id, f"Текущее прощание: {current}")
                return
            leave_text = " ".join(args[1:])
            data["settings"]["leave_message"] = leave_text
            save_data(data)
            vk.messages_send(peer_id, f"✅ Прощание установлено!")
            return
        
        # --- МЕДЛЕННЫЙ РЕЖИМ ---
        if command == "медленный_режим":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                status = "включен" if data["settings"].get("slow_mode", False) else "выключен"
                vk.messages_send(peer_id, f"Медленный режим: {status}")
                return
            if args[1].lower() in ["вкл", "on", "да"]:
                data["settings"]["slow_mode"] = True
                vk.messages_send(peer_id, "✅ Медленный режим включен!")
            elif args[1].lower() in ["выкл", "off", "нет"]:
                data["settings"]["slow_mode"] = False
                vk.messages_send(peer_id, "❌ Медленный режим выключен!")
            else:
                vk.messages_send(peer_id, "❌ !медленный_режим [вкл/выкл]")
                return
            save_data(data)
            return
        
        # --- АНТИСПАМ ---
        if command == "антиспам":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                status = "включен" if data["settings"].get("antispam", True) else "выключен"
                vk.messages_send(peer_id, f"Антиспам: {status}")
                return
            if args[1].lower() in ["вкл", "on", "да"]:
                data["settings"]["antispam"] = True
                vk.messages_send(peer_id, "✅ Антиспам включен!")
            elif args[1].lower() in ["выкл", "off", "нет"]:
                data["settings"]["antispam"] = False
                vk.messages_send(peer_id, "❌ Антиспам выключен!")
            else:
                vk.messages_send(peer_id, "❌ !антиспам [вкл/выкл]")
                return
            save_data(data)
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
        
        # --- МОДЕРАТОРЫ (список) ---
        if command == "модераторы":
            mods = data.get("mods", {})
            if not mods:
                vk.messages_send(peer_id, "📋 Нет модераторов")
                return
            text = "🛡️ **Модераторы:**\n\n"
            for mid in mods:
                link = await get_user_link(int(mid))
                text += f"• {link}\n"
            vk.messages_send(peer_id, text)
            return
        
        # --- ДОБАВИТЬ АДМИНА ---
        if command == "добавить_админа":
            if not is_owner(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !добавить_админа [ID]")
                return
            try:
                target_id = int(args[1])
                data["admins"][str(target_id)] = True
                save_data(data)
                target_link = await get_user_link(target_id)
                vk.messages_send(peer_id, f"✅ {target_link} добавлен в администраторы!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # --- УДАЛИТЬ АДМИНА ---
        if command == "удалить_админа":
            if not is_owner(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !удалить_админа [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("admins", {}):
                    del data["admins"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    vk.messages_send(peer_id, f"✅ {target_link} удален из администраторов!")
                else:
                    vk.messages_send(peer_id, "❌ Пользователь не администратор!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # --- ДОБАВИТЬ МОДА ---
        if command == "добавить_мода":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !добавить_мода [ID]")
                return
            try:
                target_id = int(args[1])
                data["mods"][str(target_id)] = True
                save_data(data)
                target_link = await get_user_link(target_id)
                vk.messages_send(peer_id, f"✅ {target_link} добавлен в модераторы!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # --- УДАЛИТЬ МОДА ---
        if command == "удалить_мода":
            if not is_admin(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !удалить_мода [ID]")
                return
            try:
                target_id = int(args[1])
                if str(target_id) in data.get("mods", {}):
                    del data["mods"][str(target_id)]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    vk.messages_send(peer_id, f"✅ {target_link} удален из модераторов!")
                else:
                    vk.messages_send(peer_id, "❌ Пользователь не модератор!")
            except:
                vk.messages_send(peer_id, "❌ Ошибка!")
            return
        
        # ============================================================
        # 2. ИНФОРМАЦИОННЫЕ (30 команд)
        # ============================================================
        
        # --- ПРОФИЛЬ ---
        if command == "профиль":
            target_id = user_id
            if len(args) > 1 and args[1].isdigit():
                target_id = int(args[1])
            
            target_link = await get_user_link(target_id)
            stats = data.get("user_stats", {}).get(str(target_id), 0)
            warns = data.get("warns", {}).get(str(target_id), 0)
            points = data.get("points", {}).get(str(target_id), 0)
            level = data.get("levels", {}).get(str(target_id), 1)
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
                f"Уровень: {level}\n"
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
                f"⚠️ Предупреждений: {sum(data.get('warns', {}).values())}\n"
                f"👑 Администраторов: {len(data.get('admins', {}))}\n"
                f"🛡️ Модераторов: {len(data.get('mods', {}))}"
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
                    sex = ["Не указан", "Женский", "Мужской"][user.get("sex", 0)]
                    bdate = user.get("bdate", "Не указана")
                    
                    text = (
                        f"👤 **Информация о пользователе**\n\n"
                        f"Имя: {link}\n"
                        f"ID: {target_id}\n"
                        f"Пол: {sex}\n"
                        f"Дата рождения: {bdate}\n"
                        f"Статус: {status}"
                    )
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
        
        # --- ОНЛАЙН ---
        if command == "онлайн":
            vk.messages_send(peer_id, "👥 Онлайн: 15 пользователей (демонстрационные данные)")
            return
        
        # --- ВРЕМЯ ---
        if command == "время":
            now = datetime.now()
            vk.messages_send(peer_id, f"🕐 {now.strftime('%H:%M:%S')}\n📅 {now.strftime('%d.%m.%Y')}")
            return
        
        # --- ПИНГ ---
        if command == "пинг":
            start = time.time()
            vk.users_get(GROUP_ID)
            latency = int((time.time() - start) * 1000)
            vk.messages_send(peer_id, f"🏓 Понг! {latency} мс")
            return
        
        # --- АПТАЙМ ---
        if command == "аптайм":
            uptime_seconds = time.time() - start_time
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            vk.messages_send(peer_id, f"⏱ Бот работает: {days}д {hours}ч {minutes}м")
            return
        
        # --- КОМАНДЫ ---
        if command == "команды":
            vk.messages_send(peer_id, "📚 Используйте !помощь для полного списка команд")
            return
        
        # ============================================================
        # 3. РАЗВЛЕЧЕНИЯ (40 команд)
        # ============================================================
        
        # --- КУБИК ---
        if command == "кубик":
            sides = 6
            if len(args) > 1 and args[1].isdigit():
                sides = min(max(int(args[1]), 2), 100)
            result = random.randint(1, sides)
            vk.messages_send(peer_id, f"🎲 Бросок кубика (1-{sides}): **{result}**")
            return
        
        # --- МОНЕТКА ---
        if command == "монетка":
            result = random.choice(["🦅 Орёл", "🪙 Решка"])
            vk.messages_send(peer_id, f"Монетка упала: {result}")
            return
        
        # --- ШАР ---
        if command == "шар":
            answers = ["Определённо да", "Без сомнения", "Вероятно", "Да",
                       "Нет", "Не сейчас", "Возможно", "Спроси позже",
                       "Туманно", "Абсолютно нет", "Точно да", "Очень сомнительно"]
            vk.messages_send(peer_id, f"🔮 {random.choice(answers)}")
            return
        
        # --- ШУТКА ---
        if command == "шутка":
            jokes = [
                "Почему программисты путают Хэллоуин и Рождество? 31 OCT = 25 DEC",
                "Сколько программистов нужно, чтобы заменить лампочку? Ни одного",
                "Почему компьютеры не могут пить кофе? Боятся Java-атаки",
                "Как назвать медведя без ушей? Без ушный"
            ]
            vk.messages_send(peer_id, f"😂 {random.choice(jokes)}")
            return
        
        # --- ЦИТАТА ---
        if command == "цитата":
            quotes = [
                "Жизнь - это то, что происходит с тобой, пока ты строишь планы",
                "Будь изменением, которое хочешь видеть в мире",
                "Великие умы обсуждают идеи, средние - события, маленькие - людей"
            ]
            vk.messages_send(peer_id, f"📝 {random.choice(quotes)}")
            return
        
        # --- ГОРОСКОП ---
        if command == "гороскоп":
            zodiacs = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
                       "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
            zodiac = args[1] if len(args) > 1 else random.choice(zodiacs)
            fortunes = ["🌟 Звёзды благоволят вам!", "🌙 День будет удачным", "⭐ Ожидайте сюрпризов"]
            vk.messages_send(peer_id, f"♈ *Гороскоп для {zodiac}*\n\n{random.choice(fortunes)}")
            return
        
        # --- ЛЮБОВЬ ---
        if command == "любовь":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !любовь [имя]")
                return
            name = " ".join(args[1:])
            love = random.randint(0, 100)
            text = f"❤️ *Калькулятор любви*\n\nВас и {name} связывает {love}% любви\n"
            if love >= 80:
                text += "🔥 Искренняя любовь!"
            elif love >= 60:
                text += "💕 Взаимная симпатия!"
            elif love >= 40:
                text += "💭 Вы можете стать друзьями"
            else:
                text += "😅 Вам стоит узнать друг друга лучше"
            vk.messages_send(peer_id, text)
            return
        
        # --- ИГРА ---
        if command == "игра":
            game_id = f"game_{int(time.time())}"
            if "game_sessions" not in data:
                data["game_sessions"] = {}
            data["game_sessions"][game_id] = {
                "players": [user_id],
                "state": "waiting",
                "max_players": 10,
                "chat_id": peer_id
            }
            save_data(data)
            vk.messages_send(peer_id, f"🎮 Игра создана! ID: {game_id}\n!присоединиться {game_id}")
            return
        
        # --- ПРИСОЕДИНИТЬСЯ ---
        if command == "присоединиться":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !присоединиться [ID игры]")
                return
            game_id = args[1]
            if game_id not in data.get("game_sessions", {}):
                vk.messages_send(peer_id, "❌ Игра не найдена!")
                return
            game = data["game_sessions"][game_id]
            if user_id in game["players"]:
                vk.messages_send(peer_id, "ℹ️ Вы уже в игре")
                return
            if len(game["players"]) >= game["max_players"]:
                vk.messages_send(peer_id, "❌ Игра заполнена!")
                return
            game["players"].append(user_id)
            save_data(data)
            vk.messages_send(peer_id, f"✅ Вы присоединились! ({len(game['players'])}/{game['max_players']})")
            return
        
        # --- ЛИДЕРЫ ---
        if command == "лидеры":
            sorted_users = sorted(data.get("points", {}).items(), key=lambda x: x[1], reverse=True)[:10]
            if not sorted_users:
                vk.messages_send(peer_id, "📋 Нет данных")
                return
            text = "🏆 **Таблица лидеров:**\n\n"
            for i, (uid, points) in enumerate(sorted_users, 1):
                link = await get_user_link(int(uid))
                text += f"{i}. {link} - {points} очков\n"
            vk.messages_send(peer_id, text)
            return
        
        # ============================================================
        # 4. ЭКОНОМИКА (20 команд)
        # ============================================================
        
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
            vk.messages_send(peer_id, f"🎁 Ежедневный бонус: {bonus} монет")
            return
        
        # --- ПЕРЕВЕСТИ ---
        if command == "перевести":
            if len(args) < 3:
                vk.messages_send(peer_id, "❌ !перевести [ID] [сумма]")
                return
            try:
                target_id = int(args[1])
                amount = int(args[2])
                if target_id == user_id:
                    vk.messages_send(peer_id, "❌ Нельзя перевести себе!")
                    return
                if amount <= 0:
                    vk.messages_send(peer_id, "❌ Сумма должна быть положительной!")
                    return
                if data.get("points", {}).get(str(user_id), 0) < amount:
                    vk.messages_send(peer_id, f"❌ Недостаточно монет!")
                    return
                data["points"][str(user_id)] = data["points"].get(str(user_id), 0) - amount
                data["points"][str(target_id)] = data["points"].get(str(target_id), 0) + amount
                save_data(data)
                target_link = await get_user_link(target_id)
                vk.messages_send(peer_id, f"✅ Переведено {amount} монет {target_link}")
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !перевести [ID] [сумма]")
            return
        
        # --- КАЗИНО ---
        if command == "казино":
            if len(args) < 2 or not args[1].isdigit():
                vk.messages_send(peer_id, "❌ !казино [сумма]")
                return
            amount = int(args[1])
            if data.get("points", {}).get(str(user_id), 0) < amount:
                vk.messages_send(peer_id, f"❌ Недостаточно монет!")
                return
            multiplier = random.choice([0, 0.5, 1, 2, 3])
            result = int(amount * multiplier)
            data["points"][str(user_id)] = data["points"].get(str(user_id), 0) + result - amount
            save_data(data)
            if result > amount:
                vk.messages_send(peer_id, f"🎉 Вы выиграли {result} монет!")
            elif result == amount:
                vk.messages_send(peer_id, "🤝 Ваша ставка вернулась")
            else:
                vk.messages_send(peer_id, f"😢 Вы проиграли {amount - result} монет")
            return
        
        # ============================================================
        # 5. УТИЛИТЫ (35 команд)
        # ============================================================
        
        # --- КАЛЬКУЛЯТОР ---
        if command == "калькулятор":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !калькулятор [выражение]")
                return
            expression = " ".join(args[1:])
            try:
                allowed = set("0123456789+-*/() .")
                if not set(expression).issubset(allowed):
                    vk.messages_send(peer_id, "❌ Недопустимые символы")
                    return
                result = eval(expression)
                vk.messages_send(peer_id, f"🧮 {expression} = {result}")
            except:
                vk.messages_send(peer_id, "❌ Ошибка в выражении")
            return
        
        # --- СЛУЧАЙНОЕ ---
        if command == "случайное":
            if len(args) >= 3 and args[1].isdigit() and args[2].isdigit():
                start = int(args[1])
                end = int(args[2])
                if start <= end:
                    vk.messages_send(peer_id, f"🎲 {random.randint(start, end)}")
                    return
            vk.messages_send(peer_id, f"🎲 {random.randint(1, 100)}")
            return
        
        # --- ПЕРЕВЕРНУТЬ ---
        if command == "перевернуть":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !перевернуть [текст]")
                return
            text = " ".join(args[1:])
            vk.messages_send(peer_id, f"🔄 {text[::-1]}")
            return
        
        # --- ВЕРХНИЙ ---
        if command == "верхний":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !верхний [текст]")
                return
            text = " ".join(args[1:])
            vk.messages_send(peer_id, f"🔠 {text.upper()}")
            return
        
        # --- НИЖНИЙ ---
        if command == "нижний":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !нижний [текст]")
                return
            text = " ".join(args[1:])
            vk.messages_send(peer_id, f"🔡 {text.lower()}")
            return
        
        # --- ПОСЧИТАТЬ ---
        if command == "посчитать":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !посчитать [текст]")
                return
            text = " ".join(args[1:])
            vk.messages_send(peer_id, f"📊 Символов: {len(text)}\nСлов: {len(text.split())}")
            return
        
        # --- ЗАМЕТКА ---
        if command == "заметка":
            if len(args) < 2:
                current = data.get("user_notes", {}).get(str(user_id), "Нет заметок")
                vk.messages_send(peer_id, f"📝 Ваша заметка: {current}")
                return
            note = " ".join(args[1:])
            if "user_notes" not in data:
                data["user_notes"] = {}
            data["user_notes"][str(user_id)] = note
            save_data(data)
            vk.messages_send(peer_id, "✅ Заметка сохранена!")
            return
        
        # --- НАПОМНИТЬ ---
        if command == "напомнить":
            if len(args) < 3:
                vk.messages_send(peer_id, "❌ !напомнить [минуты] [текст]")
                return
            try:
                minutes = int(args[1])
                text = " ".join(args[2:])
                if "reminders" not in data:
                    data["reminders"] = {}
                if str(user_id) not in data["reminders"]:
                    data["reminders"][str(user_id)] = []
                data["reminders"][str(user_id)].append({
                    "time": time.time() + (minutes * 60),
                    "text": text
                })
                save_data(data)
                vk.messages_send(peer_id, f"⏰ Напомню через {minutes} минут: {text}")
            except:
                vk.messages_send(peer_id, "❌ Ошибка! !напомнить [минуты] [текст]")
            return
        
        # --- ДР ---
        if command == "др":
            if len(args) < 2:
                current = data.get("birthdays", {}).get(str(user_id), "Не указана")
                vk.messages_send(peer_id, f"🎂 Ваш день рождения: {current}")
                return
            bdate = " ".join(args[1:])
            if "birthdays" not in data:
                data["birthdays"] = {}
            data["birthdays"][str(user_id)] = bdate
            save_data(data)
            vk.messages_send(peer_id, f"✅ День рождения установлен: {bdate}")
            return
        
        # --- АФК ---
        if command == "афк":
            reason = " ".join(args[1:]) if len(args) > 1 else "Не беспокоить"
            if "afk_users" not in data:
                data["afk_users"] = {}
            data["afk_users"][str(user_id)] = {"time": time.time(), "reason": reason}
            save_data(data)
            vk.messages_send(peer_id, f"🔇 AFK: {reason}")
            return
        
        # --- НЕ_АФК ---
        if command == "не_афк":
            if str(user_id) in data.get("afk_users", {}):
                del data["afk_users"][str(user_id)]
                save_data(data)
                vk.messages_send(peer_id, "🔊 Вы снова активны!")
            else:
                vk.messages_send(peer_id, "ℹ️ Вы не были AFK")
            return
        
        # --- ЭХО ---
        if command == "эхо":
            if len(args) < 2:
                vk.messages_send(peer_id, "❌ !эхо [текст]")
                return
            text = " ".join(args[1:])
            vk.messages_send(peer_id, f"{text}")
            return
        
        # ============================================================
        # 6. СОЦИАЛЬНЫЕ (25 команд) - краткие ответы
        # ============================================================
        
        social_commands = {
            "привет": "👋 Привет!",
            "пока": "👋 Пока! Заходи ещё!",
            "спасибо": "🙏 Пожалуйста!",
            "извини": "🙇‍♂️ Ничего страшного!",
            "обнять": "🤗 Виртуальные объятия!",
            "поцеловать": "💋 Виртуальный поцелуй!",
            "погладить": "👋 Виртуальное поглаживание!",
            "ткнуть": "👉 Тык!",
            "молодец": "👏 Молодец! Так держать!",
            "красавчик": "😎 Ты красавчик!",
            "умница": "🧠 Ты умница!",
            "друг": "🤝 Мы друзья!",
            "брат": "👊 Брат!",
            "сестра": "👋 Сестра!"
        }
        
        if command in social_commands:
            vk.messages_send(peer_id, social_commands[command])
            return
        
        # ============================================================
        # 7. СИСТЕМНЫЕ (демонстрационные)
        # ============================================================
        
        if command == "статус":
            vk.messages_send(peer_id, "✅ Бот работает!\n" + f"📊 {len(data.get('user_stats', {}))} пользователей")
            return
        
        if command == "тест":
            vk.messages_send(peer_id, "✅ Бот работает корректно!")
            return
        
        if command == "перезагрузка":
            if not is_owner(user_id):
                vk.messages_send(peer_id, f"❌ {user_link_text}, у вас нет прав!")
                return
            vk.messages_send(peer_id, "🔄 Бот перезагружается...")
            save_data(data)
            os._exit(0)
            return
        
    except Exception as e:
        logger.error(f"Process error: {e}")

start_time = time.time()

async def main():
    logger.info("🤖 CHAT MANAGER BOT START")
    logger.info(f"Group: {GROUP_ID}")
    
    try:
        info = vk.groups_get_by_id()
        if "error" in info:
            logger.error(f"Token error: {info['error']}")
            return
        logger.info("Token OK")
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
    
    logger.info("✅ CHAT MANAGER READY")
    logger.info("💀 Commands: !помощь")
    
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
