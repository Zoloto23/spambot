import asyncio
import os
import logging
import json
import time
import random
import requests
import re
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

# ============================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_debug.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ============================================================
TOKEN = os.environ.get("VK_GROUP_TOKEN")
GROUP_ID = int(os.environ.get("VK_GROUP_ID", 0))

if not TOKEN:
    logger.critical("VK_GROUP_TOKEN не установлен в переменных окружения!")
    raise RuntimeError("VK_GROUP_TOKEN not set")

if not GROUP_ID:
    logger.critical("VK_GROUP_ID не установлен в переменных окружения!")
    raise RuntimeError("VK_GROUP_ID not set")

API_VERSION = "5.199"
DATA_FILE = "bot_data.json"
CONFIG_FILE = "bot_config.json"

# ============================================================
# ЗАГРУЗКА ДАННЫХ С ЗАЩИТОЙ ОТ ОШИБОК
# ============================================================
def safe_load_json(filename: str, default: dict) -> dict:
    """Безопасная загрузка JSON с обработкой ошибок"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в {filename}: {e}")
        backup_name = f"{filename}.backup.{int(time.time())}"
        if os.path.exists(filename):
            os.rename(filename, backup_name)
            logger.info(f"Создана резервная копия: {backup_name}")
        return default
    except Exception as e:
        logger.error(f"Ошибка загрузки {filename}: {e}")
        return default

def safe_save_json(filename: str, data: dict) -> bool:
    """Безопасное сохранение JSON с созданием резервной копии"""
    try:
        if os.path.exists(filename):
            backup_name = f"{filename}.backup"
            os.rename(filename, backup_name)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")
        return False

# ============================================================
# СТРУКТУРА ДАННЫХ
# ============================================================
DEFAULT_DATA = {
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
    "shop_items": {},
    "user_achievements": {},
    "blacklist": {},
    "reports": {},
    "tickets": {},
    "welcome_messages": {},
    "farewell_messages": {},
    "auto_roles": {},
    "level_roles": {},
    "commands_usage": {},
    "economy_log": {},
    "moderation_log": {},
    "marriage_requests": {},
    "todos": {},
    "rep_history": {},
    "settings": {
        "welcome": "👋 Добро пожаловать в чат, {user}!",
        "farewell": "👋 Пока, {user}!",
        "rules": "1. Не материться\n2. Не спамить\n3. Уважать друг друга\n4. Слушаться модераторов",
        "antispam": True,
        "spam_limit": 3,
        "spam_time": 5,
        "antilink": True,
        "whitelist": ["vk.com", "youtube.com", "t.me", "youtu.be"],
        "slow_mode": False,
        "slow_delay": 3,
        "leveling": True,
        "level_multiplier": 1.0,
        "economy": True,
        "daily_amount": 100,
        "rep_limit": 5,
        "max_warns": 3,
        "ban_duration": 7,
        "mute_duration": 5,
        "language": "ru",
        "timezone": "UTC+3"
    },
    "shop": {
        "roles": [
            {"id": "vip", "name": "👑 VIP", "price": 100000, "desc": "VIP статус навсегда"},
            {"id": "premium", "name": "💎 Premium", "price": 50000, "desc": "Premium статус навсегда"},
            {"id": "booster", "name": "⚡ Бустер", "price": 25000, "desc": "Удвоение опыта на месяц"}
        ],
        "colors": [
            {"id": "red", "name": "🔴 Красный", "price": 5000, "desc": "Красный никнейм"},
            {"id": "blue", "name": "🔵 Синий", "price": 5000, "desc": "Синий никнейм"},
            {"id": "gold", "name": "🟡 Золотой", "price": 10000, "desc": "Золотой никнейм"},
            {"id": "rainbow", "name": "🌈 Радужный", "price": 25000, "desc": "Радужный никнейм"}
        ],
        "items": [
            {"id": "lucky_ticket", "name": "🎫 Счастливый билет", "price": 500, "desc": "Увеличивает удачу на 24 часа"},
            {"id": "exp_boost", "name": "📈 Бустер опыта", "price": 1000, "desc": "Удвоение опыта на час"},
            {"id": "money_boost", "name": "💰 Бустер денег", "price": 1000, "desc": "Удвоение денег на час"}
        ]
    }
}

data = safe_load_json(DATA_FILE, DEFAULT_DATA)
config = safe_load_json(CONFIG_FILE, {"version": "2.0", "last_update": time.time()})

# ============================================================
# ОСНОВНОЙ КЛАСС VK API
# ============================================================
class VKAPI:
    __slots__ = ['token', 'group_id', 'base_url', 'version', 'session']
    
    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.base_url = "https://api.vk.com/method/"
        self.version = API_VERSION
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VK-Bot/2.0',
            'Accept': 'application/json'
        })
    
    def _request(self, method: str, params: dict = None) -> dict:
        """Выполнение запроса к VK API с обработкой ошибок"""
        if params is None:
            params = {}
        
        params["access_token"] = self.token
        params["v"] = self.version
        
        try:
            response = self.session.post(
                self.base_url + method,
                data=params,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "error" in result:
                error = result["error"]
                error_code = error.get("error_code", 0)
                error_msg = error.get("error_msg", "Unknown error")
                
                # Обработка известных ошибок
                if error_code == 6:  # Too many requests
                    time.sleep(0.5)
                    return self._request(method, params)
                elif error_code == 14:  # Captcha needed
                    logger.error(f"Требуется капча: {error_msg}")
                elif error_code == 15:  # Access denied
                    logger.error(f"Доступ запрещен: {error_msg}")
                elif error_code == 18:  # User deleted
                    logger.error(f"Пользователь удален: {error_msg}")
                elif error_code == 901:  # Can't send to user
                    logger.error(f"Нельзя отправить пользователю: {error_msg}")
                elif error_code == 911:  # Can't send to group
                    logger.error(f"Нельзя отправить в группу: {error_msg}")
                elif error_code == 917:  # Flood control
                    logger.warning("Флуд-контроль, пауза...")
                    time.sleep(1)
                    return self._request(method, params)
                elif error_code == 936:  # Chat disabled
                    logger.error("Чат отключен")
                else:
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
    
    def messages_send(self, peer_id: int, message: str = None, 
                      attachment: str = None, sticker_id: int = None,
                      keyboard: dict = None) -> dict:
        """Отправка сообщения с поддержкой клавиатуры"""
        params = {
            "peer_id": peer_id,
            "random_id": int(time.time() * 1000000) + random.randint(1, 999999),
            "disable_mentions": 0
        }
        
        if message:
            params["message"] = message
        if attachment:
            params["attachment"] = attachment
        if sticker_id:
            params["sticker_id"] = sticker_id
        if keyboard:
            params["keyboard"] = json.dumps(keyboard)
        
        return self._request("messages.send", params)
    
    def messages_remove_chat_user(self, chat_id: int, user_id: int) -> dict:
        """Удаление пользователя из беседы"""
        return self._request("messages.removeChatUser", {
            "chat_id": chat_id,
            "user_id": user_id
        })
    
    def messages_get_conversations(self, offset: int = 0, count: int = 200) -> dict:
        """Получение списка бесед"""
        return self._request("messages.getConversations", {
            "offset": offset,
            "count": count,
            "extended": 1
        })
    
    def users_get(self, user_ids: Union[int, str, list]) -> dict:
        """Получение информации о пользователях"""
        if isinstance(user_ids, list):
            user_ids = ",".join(map(str, user_ids))
        return self._request("users.get", {
            "user_ids": user_ids,
            "fields": "nickname,photo_100,status,last_seen"
        })
    
    def groups_get_by_id(self) -> dict:
        """Получение информации о группе"""
        return self._request("groups.getById", {
            "group_id": self.group_id
        })
    
    def get_long_poll_server(self) -> dict:
        """Получение сервера Long Poll"""
        return self._request("groups.getLongPollServer", {
            "group_id": self.group_id
        })
    
    def long_poll_request(self, server: str, key: str, ts: int, wait: int = 25) -> dict:
        """Запрос к Long Poll серверу"""
        if not server.startswith(('http://', 'https://')):
            server = 'https://' + server
        
        url = f"{server}?act=a_check&key={key}&ts={ts}&wait={wait}&mode=2&version=3"
        
        try:
            response = self.session.get(url, timeout=wait + 10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Long Poll ошибка: {e}")
            return {"failed": 1}
    
    def upload_photo(self, peer_id: int, file_path: str) -> Optional[str]:
        """Загрузка фото на сервер VK"""
        try:
            # Получение сервера для загрузки
            upload_server = self._request("photos.getMessagesUploadServer", {
                "peer_id": peer_id
            })
            
            if "error" in upload_server:
                return None
            
            upload_url = upload_server.get("upload_url")
            if not upload_url:
                return None
            
            # Загрузка файла
            with open(file_path, 'rb') as f:
                files = {'photo': f}
                response = requests.post(upload_url, files=files, timeout=30)
                result = response.json()
            
            # Сохранение фото
            saved = self._request("photos.saveMessagesPhoto", {
                "photo": result.get("photo", ""),
                "server": result.get("server", 0),
                "hash": result.get("hash", "")
            })
            
            if "error" in saved:
                return None
            
            photo = saved[0]
            return f"photo{photo['owner_id']}_{photo['id']}"
            
        except Exception as e:
            logger.error(f"Ошибка загрузки фото: {e}")
            return None

vk = VKAPI(TOKEN, GROUP_ID)

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def safe_time() -> int:
    """Безопасное получение времени"""
    return int(time.time())

def user_link(user_id: int, name: str = None) -> str:
    """Создание ссылки на пользователя"""
    if name is None:
        return f"[id{user_id}|Пользователь]"
    return f"[id{user_id}|{name}]"

def get_nick(user_id: int) -> Optional[str]:
    """Получение никнейма пользователя"""
    return data.get("nicks", {}).get(str(user_id))

def get_role(user_id: int) -> Optional[str]:
    """Получение роли пользователя"""
    return data.get("user_roles", {}).get(str(user_id))

def is_owner(user_id: int) -> bool:
    """Проверка, является ли пользователь владельцем"""
    return user_id == data.get("owner", 0)

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return is_owner(user_id) or str(user_id) in data.get("admins", {})

def is_mod(user_id: int) -> bool:
    """Проверка, является ли пользователь модератором"""
    return is_admin(user_id) or str(user_id) in data.get("mods", {})

def is_banned(user_id: int, peer_id: int) -> bool:
    """Проверка, забанен ли пользователь"""
    key = f"{peer_id}_{user_id}"
    if key in data.get("banned", {}):
        if data["banned"][key] > time.time():
            return True
        else:
            del data["banned"][key]
            safe_save_json(DATA_FILE, data)
    return False

def is_muted(user_id: int, peer_id: int) -> bool:
    """Проверка, заглушен ли пользователь"""
    key = f"{peer_id}_{user_id}"
    if key in data.get("muted", {}):
        if data["muted"][key] > time.time():
            return True
        else:
            del data["muted"][key]
            safe_save_json(DATA_FILE, data)
    return False

def get_user_level(user_id: int) -> int:
    """Получение уровня пользователя"""
    return data.get("level", {}).get(str(user_id), 1)

def get_user_exp(user_id: int) -> int:
    """Получение опыта пользователя"""
    return data.get("exp", {}).get(str(user_id), 0)

def get_user_money(user_id: int) -> int:
    """Получение денег пользователя"""
    return data.get("money", {}).get(str(user_id), 0)

def get_user_rep(user_id: int) -> int:
    """Получение репутации пользователя"""
    return data.get("rep", {}).get(str(user_id), 0)

def get_user_warns(user_id: int) -> int:
    """Получение количества предупреждений"""
    return data.get("warns", {}).get(str(user_id), 0)

def get_required_exp(level: int) -> int:
    """Расчет опыта для следующего уровня"""
    return level * 100 + 50

async def get_user_name(user_id: int) -> str:
    """Получение имени пользователя"""
    try:
        result = vk.users_get(user_id)
        if "error" not in result and result:
            user = result[0]
            return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return f"ID {user_id}"
    except Exception as e:
        logger.error(f"Ошибка получения имени {user_id}: {e}")
        return f"ID {user_id}"

async def get_display_name(user_id: int) -> str:
    """Получение отображаемого имени"""
    nick = get_nick(user_id)
    if nick:
        return nick
    return await get_user_name(user_id)

async def get_display_link(user_id: int) -> str:
    """Получение ссылки на пользователя с отображаемым именем"""
    name = await get_display_name(user_id)
    return user_link(user_id, name)

async def add_money(user_id: int, amount: int) -> int:
    """Добавление денег пользователю"""
    try:
        data["money"][str(user_id)] = data["money"].get(str(user_id), 0) + amount
        safe_save_json(DATA_FILE, data)
        return data["money"][str(user_id)]
    except Exception as e:
        logger.error(f"Ошибка добавления денег {user_id}: {e}")
        return 0

async def remove_money(user_id: int, amount: int) -> bool:
    """Снятие денег у пользователя"""
    try:
        current = data["money"].get(str(user_id), 0)
        if current < amount:
            return False
        data["money"][str(user_id)] = current - amount
        safe_save_json(DATA_FILE, data)
        return True
    except Exception as e:
        logger.error(f"Ошибка снятия денег {user_id}: {e}")
        return False

async def add_exp(user_id: int, amount: int) -> int:
    """Добавление опыта пользователю"""
    try:
        data["exp"][str(user_id)] = data["exp"].get(str(user_id), 0) + amount
        exp = data["exp"][str(user_id)]
        new_level = int(exp / 100) + 1
        old_level = data["level"].get(str(user_id), 1)
        data["level"][str(user_id)] = new_level
        
        # Проверка на повышение уровня
        if new_level > old_level:
            await on_level_up(user_id, new_level)
        
        safe_save_json(DATA_FILE, data)
        return data["exp"][str(user_id)]
    except Exception as e:
        logger.error(f"Ошибка добавления опыта {user_id}: {e}")
        return 0

async def on_level_up(user_id: int, new_level: int):
    """Обработка повышения уровня"""
    try:
        # Награда за уровень
        reward = new_level * 100
        await add_money(user_id, reward)
        # Уведомление будет отправлено в обработчике
    except Exception as e:
        logger.error(f"Ошибка обработки повышения уровня {user_id}: {e}")

def check_spam(user_id: int, peer_id: int) -> bool:
    """Проверка на спам"""
    try:
        if not data["settings"].get("antispam", True):
            return False
        
        key = f"{peer_id}_{user_id}"
        now = time.time()
        spam_time = data["settings"].get("spam_time", 5)
        spam_limit = data["settings"].get("spam_limit", 3)
        
        if key not in data["message_history"]:
            data["message_history"][key] = []
        
        # Очистка старых сообщений
        data["message_history"][key] = [
            t for t in data["message_history"][key] 
            if now - t < spam_time
        ]
        
        if len(data["message_history"][key]) >= spam_limit:
            return True
        
        data["message_history"][key].append(now)
        safe_save_json(DATA_FILE, data)
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки спама: {e}")
        return False

def check_links(text: str) -> bool:
    """Проверка на ссылки"""
    try:
        if not data["settings"].get("antilink", True):
            return False
        
        whitelist = data["settings"].get("whitelist", ["vk.com", "youtube.com", "t.me"])
        
        # Расширенный паттерн для ссылок
        url_pattern = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
        links = re.findall(url_pattern, text, re.IGNORECASE)
        
        for link in links:
            if not any(w in link.lower() for w in whitelist):
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки ссылок: {e}")
        return False

# ============================================================
# ОБРАБОТКА НАПОМИНАНИЙ
# ============================================================
async def check_reminders():
    """Проверка напоминаний"""
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
                safe_save_json(DATA_FILE, data)
    except Exception as e:
        logger.error(f"Ошибка проверки напоминаний: {e}")

# ============================================================
# ОБРАБОТКА ВХОДА/ВЫХОДА
# ============================================================
async def handle_group_join(event: dict):
    """Обработка входа в беседу"""
    try:
        user_id = event.get("user_id")
        peer_id = event.get("peer_id")
        
        if not user_id or not peer_id:
            return
        
        welcome = data["settings"].get("welcome", "👋 Добро пожаловать в чат, {user}!")
        name = await get_display_name(user_id)
        welcome_text = welcome.replace("{user}", name)
        
        vk.messages_send(peer_id, welcome_text)
    except Exception as e:
        logger.error(f"Ошибка обработки входа: {e}")

async def handle_group_leave(event: dict):
    """Обработка выхода из беседы"""
    try:
        user_id = event.get("user_id")
        peer_id = event.get("peer_id")
        
        if not user_id or not peer_id:
            return
        
        farewell = data["settings"].get("farewell", "👋 Пока, {user}!")
        name = await get_display_name(user_id)
        farewell_text = farewell.replace("{user}", name)
        
        vk.messages_send(peer_id, farewell_text)
    except Exception as e:
        logger.error(f"Ошибка обработки выхода: {e}")

# ============================================================
# ОСНОВНАЯ ЛОГИКА БОТА
# ============================================================
async def process_message(message_data: dict):
    """Обработка входящего сообщения"""
    try:
        if not isinstance(message_data, dict):
            return
        
        if "object" not in message_data or "message" not in message_data["object"]:
            return
        
        msg = message_data["object"]["message"]
        peer_id = msg.get("peer_id", 0)
        user_id = msg.get("from_id", 0)
        text = msg.get("text", "")
        timestamp = msg.get("date", time.time())
        
        # Игнорируем сообщения от самого бота
        if user_id < 0:
            return
        
        # Проверка на бан
        if is_banned(user_id, peer_id):
            return
        
        # Проверка на мут
        if is_muted(user_id, peer_id):
            try:
                vk.messages_send(peer_id, "🔇 Вы заглушены! Подождите снятия.")
            except:
                pass
            return
        
        # Статистика сообщений
        if "user_stats" not in data:
            data["user_stats"] = {}
        data["user_stats"][str(user_id)] = data["user_stats"].get(str(user_id), 0) + 1
        
        # Начисление опыта (10% шанс)
        if data["settings"].get("leveling", True):
            if random.random() < 0.1:
                exp_gain = random.randint(1, 5) * data["settings"].get("level_multiplier", 1.0)
                await add_exp(user_id, int(exp_gain))
        
        # Проверка ссылок (только в беседах)
        if peer_id > 2000000000:
            if check_links(text) and not is_mod(user_id):
                vk.messages_send(peer_id, "🚫 Ссылки запрещены! Используйте только разрешенные домены.")
                return
            
            if check_spam(user_id, peer_id) and not is_mod(user_id):
                mute_time = data["settings"].get("mute_duration", 5)
                data["muted"][f"{peer_id}_{user_id}"] = time.time() + (mute_time * 60)
                safe_save_json(DATA_FILE, data)
                vk.messages_send(peer_id, f"🚫 Заглушен на {mute_time} минут за спам!")
                return
        
        # Если нет текста или не команда
        if not text or not text.startswith("!"):
            return
        
        # Разбор команды
        command = text[1:].strip().lower()
        args = text.split()[1:] if len(text.split()) > 1 else []
        
        # Логирование команды
        if "commands_usage" not in data:
            data["commands_usage"] = {}
        data["commands_usage"][command] = data["commands_usage"].get(command, 0) + 1
        safe_save_json(DATA_FILE, data)
        
        # ============================================================
        # КОМАНДЫ - ОСНОВНЫЕ (250+ команд)
        # ============================================================
        
        # ------------------------------------------------------------
        # 1. КОМАНДЫ ВЛАДЕЛЬЦА (25 команд)
        # ------------------------------------------------------------
        if is_owner(user_id):
            # 1.1 set_owner - смена владельца
            if command == "set_owner":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !set_owner [ID]")
                        return
                    new_owner = int(args[0])
                    data["owner"] = new_owner
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Владелец изменен на {await get_display_link(new_owner)}")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка set_owner: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 1.2 add_admin - добавление админа
            if command == "add_admin":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !add_admin [ID]")
                        return
                    target_id = int(args[0])
                    data["admins"][str(target_id)] = True
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} добавлен в администраторы")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка add_admin: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 1.3 remove_admin - удаление админа
            if command == "remove_admin" or command == "del_admin":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !remove_admin [ID]")
                        return
                    target_id = int(args[0])
                    if str(target_id) in data.get("admins", {}):
                        del data["admins"][str(target_id)]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} удален из администраторов")
                    else:
                        vk.messages_send(peer_id, "❌ Этот пользователь не администратор!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка remove_admin: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 1.4 add_mod - добавление модератора
            if command == "add_mod":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !add_mod [ID]")
                        return
                    target_id = int(args[0])
                    data["mods"][str(target_id)] = True
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} добавлен в модераторы")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка add_mod: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 1.5 remove_mod - удаление модератора
            if command == "remove_mod" or command == "del_mod":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !remove_mod [ID]")
                        return
                    target_id = int(args[0])
                    if str(target_id) in data.get("mods", {}):
                        del data["mods"][str(target_id)]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} удален из модераторов")
                    else:
                        vk.messages_send(peer_id, "❌ Этот пользователь не модератор!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка remove_mod: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 1.6 clear_data - очистка данных
            if command == "clear_data":
                try:
                    data.clear()
                    data.update(DEFAULT_DATA)
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, "✅ Все данные очищены и восстановлены по умолчанию!")
                except Exception as e:
                    logger.error(f"Ошибка clear_data: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка очистки данных!")
                return
            
            # 1.7 save - сохранение данных
            if command == "save":
                if safe_save_json(DATA_FILE, data):
                    vk.messages_send(peer_id, "✅ Данные успешно сохранены!")
                else:
                    vk.messages_send(peer_id, "❌ Ошибка сохранения данных!")
                return
            
            # 1.8 restart - перезагрузка бота
            if command == "restart" or command == "reboot":
                vk.messages_send(peer_id, "🔄 Перезагрузка бота...")
                safe_save_json(DATA_FILE, data)
                os._exit(0)
                return
            
            # 1.9 system_info - информация о системе
            if command == "system_info" or command == "sysinfo":
                try:
                    import sys
                    info = f"""📊 **Информация о системе**
⏱ Время работы: {time.time() - config.get('start_time', time.time()):.0f} сек
💾 Память: {sys.getsizeof(data) / 1024:.2f} KB
📁 Пользователей: {len(data.get('user_stats', {}))}
👑 Владелец: {await get_display_name(data.get('owner', 0))}
👮 Админы: {len(data.get('admins', {}))}
🛡 Модераторы: {len(data.get('mods', {}))}
💰 Всего денег: {sum(data.get('money', {}).values())}"""
                    vk.messages_send(peer_id, info)
                except Exception as e:
                    logger.error(f"Ошибка system_info: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения информации!")
                return
            
            # 1.10 ban_list - список банов
            if command == "ban_list":
                try:
                    banned = []
                    for key, until in data.get("banned", {}).items():
                        if until > time.time():
                            parts = key.split("_")
                            if len(parts) >= 2:
                                user_id_banned = int(parts[1])
                                banned.append((user_id_banned, int((until - time.time()) / 60)))
                    
                    if banned:
                        text = "🚫 **Список забаненных:**\n"
                        for uid, minutes in banned[:20]:
                            text += f"• {await get_display_link(uid)} — {minutes} мин\n"
                        vk.messages_send(peer_id, text)
                    else:
                        vk.messages_send(peer_id, "📋 Нет забаненных пользователей")
                except Exception as e:
                    logger.error(f"Ошибка ban_list: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения списка!")
                return
            
            # 1.11 mute_list - список заглушенных
            if command == "mute_list":
                try:
                    muted = []
                    for key, until in data.get("muted", {}).items():
                        if until > time.time():
                            parts = key.split("_")
                            if len(parts) >= 2:
                                user_id_muted = int(parts[1])
                                muted.append((user_id_muted, int((until - time.time()) / 60)))
                    
                    if muted:
                        text = "🔇 **Список заглушенных:**\n"
                        for uid, minutes in muted[:20]:
                            text += f"• {await get_display_link(uid)} — {minutes} мин\n"
                        vk.messages_send(peer_id, text)
                    else:
                        vk.messages_send(peer_id, "📋 Нет заглушенных пользователей")
                except Exception as e:
                    logger.error(f"Ошибка mute_list: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения списка!")
                return
            
            # 1.12 top_messages - топ по сообщениям
            if command == "top_messages":
                try:
                    stats = data.get("user_stats", {})
                    if not stats:
                        vk.messages_send(peer_id, "📋 Нет статистики сообщений")
                        return
                    
                    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]
                    text = "📊 **Топ по сообщениям:**\n"
                    for i, (uid, count) in enumerate(sorted_stats, 1):
                        text += f"{i}. {await get_display_link(int(uid))} — {count} сообщений\n"
                    vk.messages_send(peer_id, text)
                except Exception as e:
                    logger.error(f"Ошибка top_messages: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения топа!")
                return
            
            # 1.13 top_money - топ по деньгам
            if command == "top_money":
                try:
                    money = data.get("money", {})
                    if not money:
                        vk.messages_send(peer_id, "📋 Нет данных о деньгах")
                        return
                    
                    sorted_money = sorted(money.items(), key=lambda x: x[1], reverse=True)[:10]
                    text = "💰 **Топ по деньгам:**\n"
                    for i, (uid, amount) in enumerate(sorted_money, 1):
                        text += f"{i}. {await get_display_link(int(uid))} — {amount} монет\n"
                    vk.messages_send(peer_id, text)
                except Exception as e:
                    logger.error(f"Ошибка top_money: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения топа!")
                return
            
            # 1.14 top_level - топ по уровню
            if command == "top_level":
                try:
                    level = data.get("level", {})
                    if not level:
                        vk.messages_send(peer_id, "📋 Нет данных об уровнях")
                        return
                    
                    sorted_level = sorted(level.items(), key=lambda x: x[1], reverse=True)[:10]
                    text = "📈 **Топ по уровню:**\n"
                    for i, (uid, lvl) in enumerate(sorted_level, 1):
                        text += f"{i}. {await get_display_link(int(uid))} — {lvl} уровень\n"
                    vk.messages_send(peer_id, text)
                except Exception as e:
                    logger.error(f"Ошибка top_level: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения топа!")
                return
            
            # 1.15 top_rep - топ по репутации
            if command == "top_rep":
                try:
                    rep = data.get("rep", {})
                    if not rep:
                        vk.messages_send(peer_id, "📋 Нет данных о репутации")
                        return
                    
                    sorted_rep = sorted(rep.items(), key=lambda x: x[1], reverse=True)[:10]
                    text = "⭐ **Топ по репутации:**\n"
                    for i, (uid, reps) in enumerate(sorted_rep, 1):
                        text += f"{i}. {await get_display_link(int(uid))} — {reps} репутации\n"
                    vk.messages_send(peer_id, text)
                except Exception as e:
                    logger.error(f"Ошибка top_rep: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения топа!")
                return
            
            # 1.16 broadcast - массовая рассылка
            if command == "broadcast":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !broadcast [сообщение]")
                        return
                    
                    message = " ".join(args)
                    sent = 0
                    for chat in data.get("group_chats", []):
                        try:
                            vk.messages_send(chat, f"📢 **Рассылка от владельца:**\n{message}")
                            sent += 1
                            time.sleep(0.1)
                        except:
                            pass
                    
                    vk.messages_send(peer_id, f"✅ Рассылка выполнена в {sent} чатов")
                except Exception as e:
                    logger.error(f"Ошибка broadcast: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка рассылки!")
                return
            
            # 1.17 config_view - просмотр конфига
            if command == "config_view":
                try:
                    config_text = json.dumps(data.get("settings", {}), ensure_ascii=False, indent=2)
                    if len(config_text) > 4000:
                        config_text = config_text[:4000] + "..."
                    vk.messages_send(peer_id, f"⚙️ **Конфигурация:**\n{config_text}")
                except Exception as e:
                    logger.error(f"Ошибка config_view: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения конфига!")
                return
            
            # 1.18 config_set - установка параметра конфига
            if command == "config_set":
                try:
                    if len(args) < 2:
                        vk.messages_send(peer_id, "❌ Использование: !config_set [ключ] [значение]")
                        return
                    
                    key = args[0]
                    value = " ".join(args[1:])
                    
                    # Преобразование значения
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    data["settings"][key] = value
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Параметр {key} установлен на {value}")
                except Exception as e:
                    logger.error(f"Ошибка config_set: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка установки параметра!")
                return
            
            # 1.19 export_data - экспорт данных
            if command == "export_data":
                try:
                    backup_file = f"backup_{int(time.time())}.json"
                    safe_save_json(backup_file, data)
                    vk.messages_send(peer_id, f"✅ Данные экспортированы в {backup_file}")
                except Exception as e:
                    logger.error(f"Ошибка export_data: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка экспорта данных!")
                return
            
            # 1.20 import_data - импорт данных
            if command == "import_data":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !import_data [имя_файла]")
                        return
                    
                    filename = args[0]
                    if os.path.exists(filename):
                        new_data = safe_load_json(filename, {})
                        if new_data:
                            data.update(new_data)
                            safe_save_json(DATA_FILE, data)
                            vk.messages_send(peer_id, "✅ Данные импортированы!")
                        else:
                            vk.messages_send(peer_id, "❌ Файл пуст или поврежден!")
                    else:
                        vk.messages_send(peer_id, "❌ Файл не найден!")
                except Exception as e:
                    logger.error(f"Ошибка import_data: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка импорта данных!")
                return
            
            # 1.21 add_shop_item - добавление товара
            if command == "add_shop_item":
                try:
                    if len(args) < 3:
                        vk.messages_send(peer_id, "❌ Использование: !add_shop_item [id] [название] [цена]")
                        return
                    
                    item_id = args[0]
                    name = args[1]
                    price = int(args[2])
                    
                    if "shop" not in data:
                        data["shop"] = {}
                    if "items" not in data["shop"]:
                        data["shop"]["items"] = []
                    
                    data["shop"]["items"].append({
                        "id": item_id,
                        "name": name,
                        "price": price,
                        "desc": " ".join(args[3:]) if len(args) > 3 else "Описание отсутствует"
                    })
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Товар {name} добавлен в магазин!")
                except Exception as e:
                    logger.error(f"Ошибка add_shop_item: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка добавления товара!")
                return
            
            # 1.22 remove_shop_item - удаление товара
            if command == "remove_shop_item":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !remove_shop_item [id]")
                        return
                    
                    item_id = args[0]
                    if "shop" in data and "items" in data["shop"]:
                        data["shop"]["items"] = [
                            item for item in data["shop"]["items"] 
                            if item.get("id") != item_id
                        ]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, "✅ Товар удален из магазина!")
                    else:
                        vk.messages_send(peer_id, "❌ Магазин пуст!")
                except Exception as e:
                    logger.error(f"Ошибка remove_shop_item: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка удаления товара!")
                return
            
            # 1.23 set_language - установка языка
            if command == "set_language":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !set_language [ru|en|uk]")
                        return
                    
                    lang = args[0].lower()
                    if lang in ["ru", "en", "uk"]:
                        data["settings"]["language"] = lang
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ Язык установлен на {lang}")
                    else:
                        vk.messages_send(peer_id, "❌ Доступные языки: ru, en, uk")
                except Exception as e:
                    logger.error(f"Ошибка set_language: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка установки языка!")
                return
            
            # 1.24 set_timezone - установка часового пояса
            if command == "set_timezone":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !set_timezone [UTC+3]")
                        return
                    
                    data["settings"]["timezone"] = " ".join(args)
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Часовой пояс установлен на {data['settings']['timezone']}")
                except Exception as e:
                    logger.error(f"Ошибка set_timezone: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка установки часового пояса!")
                return
            
            # 1.25 bot_info - информация о боте
            if command == "bot_info":
                try:
                    info = f"""🤖 **Информация о боте**
📱 Версия: {config.get('version', '2.0')}
⏱ Запущен: {datetime.fromtimestamp(config.get('start_time', time.time())).strftime('%Y-%m-%d %H:%M:%S')}
📊 Команд выполнено: {len(data.get('commands_usage', {}))}
👥 Всего пользователей: {len(data.get('user_stats', {}))}
💬 Чатов: {len(data.get('group_chats', []))}
⚙️ Конфигурация: v{API_VERSION}"""
                    vk.messages_send(peer_id, info)
                except Exception as e:
                    logger.error(f"Ошибка bot_info: {e}")
                    vk.messages_send(peer_id, "❌ Ошибка получения информации!")
                return
        
        # ------------------------------------------------------------
        # 2. КОМАНДЫ МОДЕРАЦИИ (30 команд)
        # ------------------------------------------------------------
        if is_mod(user_id):
            # 2.1 mute - заглушить
            if command == "mute" or command == "мут":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !mute [ID] [минут]")
                        return
                    
                    target_id = int(args[0])
                    minutes = int(args[1]) if len(args) > 1 else data["settings"].get("mute_duration", 5)
                    
                    data["muted"][f"{peer_id}_{target_id}"] = time.time() + (minutes * 60)
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"🔇 {await get_display_link(target_id)} заглушен на {minutes} минут!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID и время должны быть числами!")
                except Exception as e:
                    logger.error(f"Ошибка mute: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.2 unmute - разглушить
            if command == "unmute" or command == "размут":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !unmute [ID]")
                        return
                    
                    target_id = int(args[0])
                    key = f"{peer_id}_{target_id}"
                    if key in data.get("muted", {}):
                        del data["muted"][key]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} разглушен!")
                    else:
                        vk.messages_send(peer_id, "❌ Пользователь не заглушен!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка unmute: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.3 kick - кикнуть
            if command == "kick" or command == "кик":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !kick [ID]")
                        return
                    
                    target_id = int(args[0])
                    chat_id = peer_id - 2000000000
                    result = vk.messages_remove_chat_user(chat_id, target_id)
                    if "error" not in result:
                        vk.messages_send(peer_id, f"👢 {await get_display_link(target_id)} кикнут из беседы!")
                    else:
                        vk.messages_send(peer_id, "❌ Не удалось кикнуть пользователя!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка kick: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.4 ban - забанить
            if command == "ban" or command == "бан":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !ban [ID] [дней]")
                        return
                    
                    target_id = int(args[0])
                    days = int(args[1]) if len(args) > 1 else data["settings"].get("ban_duration", 7)
                    
                    data["banned"][f"{peer_id}_{target_id}"] = time.time() + (days * 24 * 60 * 60)
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"🚫 {await get_display_link(target_id)} забанен на {days} дней!")
                    
                    # Кик из беседы
                    chat_id = peer_id - 2000000000
                    vk.messages_remove_chat_user(chat_id, target_id)
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID и дни должны быть числами!")
                except Exception as e:
                    logger.error(f"Ошибка ban: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.5 unban - разбанить
            if command == "unban" or command == "разбан":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !unban [ID]")
                        return
                    
                    target_id = int(args[0])
                    key = f"{peer_id}_{target_id}"
                    if key in data.get("banned", {}):
                        del data["banned"][key]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} разбанен!")
                    else:
                        vk.messages_send(peer_id, "❌ Пользователь не забанен!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка unban: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.6 warn - предупреждение
            if command == "warn" or command == "варн":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !warn [ID] [причина]")
                        return
                    
                    target_id = int(args[0])
                    reason = " ".join(args[1:]) if len(args) > 1 else "Без причины"
                    
                    data["warns"][str(target_id)] = data["warns"].get(str(target_id), 0) + 1
                    warns = data["warns"][str(target_id)]
                    max_warns = data["settings"].get("max_warns", 3)
                    safe_save_json(DATA_FILE, data)
                    
                    if warns >= max_warns:
                        days = data["settings"].get("ban_duration", 7)
                        data["banned"][f"{peer_id}_{target_id}"] = time.time() + (days * 24 * 60 * 60)
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"🚫 {await get_display_link(target_id)} забанен на {days} дней (3 предупреждения)!")
                    else:
                        vk.messages_send(peer_id, f"⚠️ {await get_display_link(target_id)} предупреждение {warns}/{max_warns}\nПричина: {reason}")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка warn: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.7 unwarn - снять предупреждение
            if command == "unwarn" or command == "снять_варн":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !unwarn [ID]")
                        return
                    
                    target_id = int(args[0])
                    if str(target_id) in data.get("warns", {}):
                        warns = data["warns"][str(target_id)]
                        if warns > 0:
                            data["warns"][str(target_id)] = warns - 1
                            safe_save_json(DATA_FILE, data)
                            vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} снято предупреждение! Осталось: {warns - 1}")
                        else:
                            vk.messages_send(peer_id, "❌ У пользователя нет предупреждений!")
                    else:
                        vk.messages_send(peer_id, "❌ У пользователя нет предупреждений!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка unwarn: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.8 clear_warns - очистить предупреждения
            if command == "clear_warns" or command == "очистить_варны":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !clear_warns [ID]")
                        return
                    
                    target_id = int(args[0])
                    if str(target_id) in data.get("warns", {}):
                        del data["warns"][str(target_id)]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ Предупреждения {await get_display_link(target_id)} очищены!")
                    else:
                        vk.messages_send(peer_id, "❌ У пользователя нет предупреждений!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка clear_warns: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.9 warn_list - список предупреждений
            if command == "warn_list" or command == "варны":
                try:
                    warns = data.get("warns", {})
                    if not warns:
                        vk.messages_send(peer_id, "📋 Нет предупреждений")
                        return
                    
                    text = "⚠️ **Список предупреждений:**\n"
                    for uid, count in warns.items():
                        text += f"• {await get_display_link(int(uid))} — {count}/{data['settings'].get('max_warns', 3)}\n"
                    vk.messages_send(peer_id, text)
                except Exception as e:
                    logger.error(f"Ошибка warn_list: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.10 set_rules - установить правила
            if command == "set_rules" or command == "правила":
                try:
                    if not args:
                        current = data["settings"].get("rules", "Правила не установлены")
                        vk.messages_send(peer_id, f"📋 **Текущие правила:**\n{current}")
                        return
                    
                    rules = " ".join(args)
                    data["settings"]["rules"] = rules
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, "✅ Правила обновлены!")
                except Exception as e:
                    logger.error(f"Ошибка set_rules: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.11 set_welcome - установить приветствие
            if command == "set_welcome" or command == "приветствие":
                try:
                    if not args:
                        current = data["settings"].get("welcome", "Приветствие не установлено")
                        vk.messages_send(peer_id, f"📋 **Текущее приветствие:**\n{current}")
                        return
                    
                    welcome = " ".join(args)
                    data["settings"]["welcome"] = welcome
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, "✅ Приветствие обновлено!")
                except Exception as e:
                    logger.error(f"Ошибка set_welcome: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.12 set_farewell - установить прощание
            if command == "set_farewell" or command == "прощание":
                try:
                    if not args:
                        current = data["settings"].get("farewell", "Прощание не установлено")
                        vk.messages_send(peer_id, f"📋 **Текущее прощание:**\n{current}")
                        return
                    
                    farewell = " ".join(args)
                    data["settings"]["farewell"] = farewell
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, "✅ Прощание обновлено!")
                except Exception as e:
                    logger.error(f"Ошибка set_farewell: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.13 toggle_antispam - включить/выключить антиспам
            if command == "toggle_antispam" or command == "антиспам":
                try:
                    current = data["settings"].get("antispam", True)
                    data["settings"]["antispam"] = not current
                    safe_save_json(DATA_FILE, data)
                    status = "включен" if data["settings"]["antispam"] else "выключен"
                    vk.messages_send(peer_id, f"✅ Антиспам {status}!")
                except Exception as e:
                    logger.error(f"Ошибка toggle_antispam: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.14 toggle_antilink - включить/выключить антиссылку
            if command == "toggle_antilink" or command == "антиссылка":
                try:
                    current = data["settings"].get("antilink", True)
                    data["settings"]["antilink"] = not current
                    safe_save_json(DATA_FILE, data)
                    status = "включена" if data["settings"]["antilink"] else "выключена"
                    vk.messages_send(peer_id, f"✅ Антиссылка {status}!")
                except Exception as e:
                    logger.error(f"Ошибка toggle_antilink: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.15 toggle_leveling - включить/выключить систему уровней
            if command == "toggle_leveling" or command == "уровни":
                try:
                    current = data["settings"].get("leveling", True)
                    data["settings"]["leveling"] = not current
                    safe_save_json(DATA_FILE, data)
                    status = "включена" if data["settings"]["leveling"] else "выключена"
                    vk.messages_send(peer_id, f"✅ Система уровней {status}!")
                except Exception as e:
                    logger.error(f"Ошибка toggle_leveling: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.16 toggle_economy - включить/выключить экономику
            if command == "toggle_economy" or command == "экономика":
                try:
                    current = data["settings"].get("economy", True)
                    data["settings"]["economy"] = not current
                    safe_save_json(DATA_FILE, data)
                    status = "включена" if data["settings"]["economy"] else "выключена"
                    vk.messages_send(peer_id, f"✅ Экономика {status}!")
                except Exception as e:
                    logger.error(f"Ошибка toggle_economy: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.17 toggle_slowmode - включить/выключить медленный режим
            if command == "toggle_slowmode" or command == "медленныйрежим":
                try:
                    current = data["settings"].get("slow_mode", False)
                    data["settings"]["slow_mode"] = not current
                    safe_save_json(DATA_FILE, data)
                    status = "включен" if data["settings"]["slow_mode"] else "выключен"
                    vk.messages_send(peer_id, f"✅ Медленный режим {status}!")
                except Exception as e:
                    logger.error(f"Ошибка toggle_slowmode: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.18 set_spam_limit - установить лимит спама
            if command == "set_spam_limit":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !set_spam_limit [число]")
                        return
                    
                    limit = int(args[0])
                    data["settings"]["spam_limit"] = limit
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Лимит спама установлен на {limit}")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: число должно быть целым!")
                except Exception as e:
                    logger.error(f"Ошибка set_spam_limit: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.19 set_spam_time - установить время спама
            if command == "set_spam_time":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !set_spam_time [секунд]")
                        return
                    
                    seconds = int(args[0])
                    data["settings"]["spam_time"] = seconds
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Время спама установлено на {seconds} секунд")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: число должно быть целым!")
                except Exception as e:
                    logger.error(f"Ошибка set_spam_time: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.20 set_ban_duration - установить длительность бана
            if command == "set_ban_duration":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !set_ban_duration [дней]")
                        return
                    
                    days = int(args[0])
                    data["settings"]["ban_duration"] = days
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Длительность бана установлена на {days} дней")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: число должно быть целым!")
                except Exception as e:
                    logger.error(f"Ошибка set_ban_duration: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.21 set_mute_duration - установить длительность мута
            if command == "set_mute_duration":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !set_mute_duration [минут]")
                        return
                    
                    minutes = int(args[0])
                    data["settings"]["mute_duration"] = minutes
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Длительность мута установлена на {minutes} минут")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: число должно быть целым!")
                except Exception as e:
                    logger.error(f"Ошибка set_mute_duration: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.22 add_whitelist - добавить в белый список
            if command == "add_whitelist" or command == "добавить_белый_список":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !add_whitelist [домен]")
                        return
                    
                    domain = args[0].lower()
                    if "whitelist" not in data["settings"]:
                        data["settings"]["whitelist"] = []
                    
                    if domain not in data["settings"]["whitelist"]:
                        data["settings"]["whitelist"].append(domain)
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ Домен {domain} добавлен в белый список!")
                    else:
                        vk.messages_send(peer_id, "❌ Домен уже в белом списке!")
                except Exception as e:
                    logger.error(f"Ошибка add_whitelist: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.23 remove_whitelist - удалить из белого списка
            if command == "remove_whitelist" or command == "удалить_белый_список":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !remove_whitelist [домен]")
                        return
                    
                    domain = args[0].lower()
                    if "whitelist" in data["settings"]:
                        if domain in data["settings"]["whitelist"]:
                            data["settings"]["whitelist"].remove(domain)
                            safe_save_json(DATA_FILE, data)
                            vk.messages_send(peer_id, f"✅ Домен {domain} удален из белого списка!")
                        else:
                            vk.messages_send(peer_id, "❌ Домен не в белом списке!")
                    else:
                        vk.messages_send(peer_id, "❌ Белый список пуст!")
                except Exception as e:
                    logger.error(f"Ошибка remove_whitelist: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.24 whitelist_list - список белого списка
            if command == "whitelist_list" or command == "белый_список":
                try:
                    whitelist = data["settings"].get("whitelist", [])
                    if whitelist:
                        text = "📋 **Белый список доменов:**\n"
                        for domain in whitelist:
                            text += f"• {domain}\n"
                        vk.messages_send(peer_id, text)
                    else:
                        vk.messages_send(peer_id, "📋 Белый список пуст")
                except Exception as e:
                    logger.error(f"Ошибка whitelist_list: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.25 clear_chat - очистить чат (мут всех)
            if command == "clear_chat" or command == "очистить_чат":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !clear_chat [минут]")
                        return
                    
                    minutes = int(args[0])
                    count = 0
                    
                    # Получение участников
                    members = vk.messages_get_conversations()
                    if "error" not in members:
                        # Мут всех участников
                        for item in members.get("items", []):
                            if "last_message" in item:
                                user_id_member = item["last_message"].get("from_id", 0)
                                if user_id_member > 0 and not is_mod(user_id_member):
                                    data["muted"][f"{peer_id}_{user_id_member}"] = time.time() + (minutes * 60)
                                    count += 1
                        
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"🔇 {count} пользователей заглушены на {minutes} минут!")
                    else:
                        vk.messages_send(peer_id, "❌ Не удалось очистить чат!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: число должно быть целым!")
                except Exception as e:
                    logger.error(f"Ошибка clear_chat: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.26 add_nick - установить никнейм
            if command == "add_nick" or command == "ник":
                try:
                    if len(args) < 2:
                        vk.messages_send(peer_id, "❌ Использование: !add_nick [ID] [никнейм]")
                        return
                    
                    target_id = int(args[0])
                    nick = " ".join(args[1:])
                    
                    data["nicks"][str(target_id)] = nick
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} теперь {nick}")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка add_nick: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.27 remove_nick - удалить никнейм
            if command == "remove_nick" or command == "удалить_ник":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !remove_nick [ID]")
                        return
                    
                    target_id = int(args[0])
                    if str(target_id) in data.get("nicks", {}):
                        del data["nicks"][str(target_id)]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ Никнейм {await get_display_link(target_id)} удален!")
                    else:
                        vk.messages_send(peer_id, "❌ У пользователя нет никнейма!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка remove_nick: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.28 add_role - назначить роль
            if command == "add_role" or command == "роль":
                try:
                    if len(args) < 2:
                        vk.messages_send(peer_id, "❌ Использование: !add_role [ID] [роль]")
                        return
                    
                    target_id = int(args[0])
                    role = " ".join(args[1:])
                    
                    data["user_roles"][str(target_id)] = role
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ {await get_display_link(target_id)} получил роль {role}")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка add_role: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.29 remove_role - удалить роль
            if command == "remove_role" or command == "удалить_роль":
                try:
                    if not args:
                        vk.messages_send(peer_id, "❌ Использование: !remove_role [ID]")
                        return
                    
                    target_id = int(args[0])
                    if str(target_id) in data.get("user_roles", {}):
                        del data["user_roles"][str(target_id)]
                        safe_save_json(DATA_FILE, data)
                        vk.messages_send(peer_id, f"✅ Роль {await get_display_link(target_id)} удалена!")
                    else:
                        vk.messages_send(peer_id, "❌ У пользователя нет роли!")
                except ValueError:
                    vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
                except Exception as e:
                    logger.error(f"Ошибка remove_role: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
            
            # 2.30 moderation_log - лог модерации
            if command == "moderation_log":
                try:
                    log = data.get("moderation_log", [])
                    if not log:
                        vk.messages_send(peer_id, "📋 Лог модерации пуст")
                        return
                    
                    text = "📋 **Последние действия модерации:**\n"
                    for entry in log[-10:]:
                        text += f"• {entry}\n"
                    vk.messages_send(peer_id, text)
                except Exception as e:
                    logger.error(f"Ошибка moderation_log: {e}")
                    vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
                return
        
        # ------------------------------------------------------------
        # 3. ОБЩИЕ КОМАНДЫ (50 команд)
        # ------------------------------------------------------------
        
        # 3.1 help - справка
        if command == "help" or command == "помощь":
            try:
                help_text = """📚 **Доступные команды:**

👤 **Профиль:**
!profile — ваш профиль
!profile [ID] — профиль пользователя
!stats — ваша статистика
!level — ваш уровень

💰 **Экономика:**
!money — ваш баланс
!daily — ежедневный бонус
!top_money — топ по деньгам
!shop — магазин
!buy [товар] — купить товар

⭐ **Репутация:**
!rep [ID] — дать репутацию
!rep — ваша репутация
!top_rep — топ репутации

📊 **Статистика:**
!top_messages — топ по сообщениям
!top_level — топ по уровню
!my_stats — ваша статистика

🎮 **Развлечения:**
!roll [число] — бросить кубик
!coin — подбросить монетку
!8ball [вопрос] — магический шар
!rps [камень/ножницы/бумага] — игра

⚙️ **Другое:**
!help — эта справка
!rules — правила чата
!info — информация о боте"""
                vk.messages_send(peer_id, help_text)
            except Exception as e:
                logger.error(f"Ошибка help: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.2 profile - профиль пользователя
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
                role = get_role(target_id) or "Нет"
                nick = get_nick(target_id)
                next_level_exp = get_required_exp(level)
                
                profile_text = f"""👤 **Профиль {name}**
📊 Уровень: {level}
📈 Опыт: {exp}/{next_level_exp}
💰 Денег: {money}
⭐ Репутация: {rep}
⚠️ Предупреждений: {warns}
📝 Сообщений: {stats}
🎭 Роль: {role}
👤 Никнейм: {nick or 'Не установлен'}"""
                vk.messages_send(peer_id, profile_text)
            except Exception as e:
                logger.error(f"Ошибка profile: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.3 money - баланс
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
                logger.error(f"Ошибка money: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.4 daily - ежедневный бонус
        if command == "daily" or command == "ежедневный":
            try:
                key = f"{peer_id}_{user_id}"
                now = time.time()
                last_claim = data.get("daily_bonus", {}).get(key, 0)
                
                if now - last_claim < 86400:  # 24 часа
                    remaining = int(86400 - (now - last_claim))
                    hours = remaining // 3600
                    minutes = (remaining % 3600) // 60
                    vk.messages_send(peer_id, f"⏳ Бонус уже получен! Следующий через {hours}ч {minutes}мин")
                    return
                
                amount = data["settings"].get("daily_amount", 100)
                await add_money(user_id, amount)
                data["daily_bonus"][key] = now
                safe_save_json(DATA_FILE, data)
                vk.messages_send(peer_id, f"🎉 Вы получили ежедневный бонус: +{amount} монет!")
            except Exception as e:
                logger.error(f"Ошибка daily: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.5 shop - магазин
        if command == "shop" or command == "магазин":
            try:
                shop_items = data.get("shop", {}).get("items", [])
                if not shop_items:
                    vk.messages_send(peer_id, "📋 Магазин пуст")
                    return
                
                text = "🛒 **Магазин:**\n"
                for item in shop_items:
                    text += f"• {item['name']} — {item['price']} монет\n"
                    text += f"  ID: {item['id']}\n"
                    text += f"  {item.get('desc', '')}\n\n"
                
                if len(text) > 4000:
                    text = text[:4000] + "..."
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"Ошибка shop: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.6 buy - покупка товара
        if command == "buy" or command == "купить":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ Использование: !buy [ID товара]")
                    return
                
                item_id = args[0]
                shop_items = data.get("shop", {}).get("items", [])
                item = next((i for i in shop_items if i.get("id") == item_id), None)
                
                if not item:
                    vk.messages_send(peer_id, "❌ Товар не найден!")
                    return
                
                price = item.get("price", 0)
                if await remove_money(user_id, price):
                    # Добавление товара в инвентарь
                    if "inventory" not in data:
                        data["inventory"] = {}
                    if str(user_id) not in data["inventory"]:
                        data["inventory"][str(user_id)] = []
                    data["inventory"][str(user_id)].append(item_id)
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, f"✅ Вы купили {item['name']} за {price} монет!")
                else:
                    vk.messages_send(peer_id, f"❌ Недостаточно денег! Нужно: {price}")
            except Exception as e:
                logger.error(f"Ошибка buy: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.7 inventory - инвентарь
        if command == "inventory" or command == "инвентарь":
            try:
                items = data.get("inventory", {}).get(str(user_id), [])
                if not items:
                    vk.messages_send(peer_id, "📋 Ваш инвентарь пуст")
                    return
                
                text = "🎒 **Ваш инвентарь:**\n"
                shop_items = data.get("shop", {}).get("items", [])
                for item_id in items:
                    item = next((i for i in shop_items if i.get("id") == item_id), None)
                    if item:
                        text += f"• {item['name']}\n"
                    else:
                        text += f"• {item_id}\n"
                
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"Ошибка inventory: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.8 level - уровень
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
                logger.error(f"Ошибка level: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.9 stats - статистика
        if command == "stats" or command == "статистика":
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                
                name = await get_display_name(target_id)
                messages = data.get("user_stats", {}).get(str(target_id), 0)
                warns = get_user_warns(target_id)
                level = get_user_level(target_id)
                money = get_user_money(target_id)
                rep = get_user_rep(target_id)
                
                stats_text = f"""📊 **Статистика {name}:**
📝 Сообщений: {messages}
⚠️ Предупреждений: {warns}
📈 Уровень: {level}
💰 Денег: {money}
⭐ Репутация: {rep}"""
                vk.messages_send(peer_id, stats_text)
            except Exception as e:
                logger.error(f"Ошибка stats: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.10 rep - репутация
        if command == "rep" or command == "репутация":
            try:
                if not args:
                    rep = get_user_rep(user_id)
                    vk.messages_send(peer_id, f"⭐ Ваша репутация: {rep}")
                    return
                
                target_id = int(args[0])
                # Проверка на выдачу репутации (только раз в сутки)
                key = f"rep_{user_id}_{target_id}"
                if key in data.get("rep_history", {}):
                    last_time = data["rep_history"][key]
                    if time.time() - last_time < 86400:
                        vk.messages_send(peer_id, "⏳ Вы уже давали репутацию этому пользователю сегодня!")
                        return
                
                data["rep"][str(target_id)] = data["rep"].get(str(target_id), 0) + 1
                if "rep_history" not in data:
                    data["rep_history"] = {}
                data["rep_history"][key] = time.time()
                safe_save_json(DATA_FILE, data)
                vk.messages_send(peer_id, f"⭐ {await get_display_link(target_id)} получил репутацию!")
            except ValueError:
                vk.messages_send(peer_id, "❌ Ошибка: ID должен быть числом!")
            except Exception as e:
                logger.error(f"Ошибка rep: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.11 top_messages - топ по сообщениям
        if command == "top_messages" or command == "топ_сообщений":
            try:
                stats = data.get("user_stats", {})
                if not stats:
                    vk.messages_send(peer_id, "📋 Нет статистики сообщений")
                    return
                
                sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]
                text = "📊 **Топ по сообщениям:**\n"
                for i, (uid, count) in enumerate(sorted_stats, 1):
                    text += f"{i}. {await get_display_link(int(uid))} — {count}\n"
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"Ошибка top_messages: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.12 top_level - топ по уровню
        if command == "top_level" or command == "топ_уровней":
            try:
                levels = data.get("level", {})
                if not levels:
                    vk.messages_send(peer_id, "📋 Нет данных об уровнях")
                    return
                
                sorted_levels = sorted(levels.items(), key=lambda x: x[1], reverse=True)[:10]
                text = "📈 **Топ по уровню:**\n"
                for i, (uid, level) in enumerate(sorted_levels, 1):
                    text += f"{i}. {await get_display_link(int(uid))} — {level} уровень\n"
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"Ошибка top_level: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.13 top_money - топ по деньгам
        if command == "top_money" or command == "топ_денег":
            try:
                money = data.get("money", {})
                if not money:
                    vk.messages_send(peer_id, "📋 Нет данных о деньгах")
                    return
                
                sorted_money = sorted(money.items(), key=lambda x: x[1], reverse=True)[:10]
                text = "💰 **Топ по деньгам:**\n"
                for i, (uid, amount) in enumerate(sorted_money, 1):
                    text += f"{i}. {await get_display_link(int(uid))} — {amount}\n"
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"Ошибка top_money: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.14 top_rep - топ по репутации
        if command == "top_rep" or command == "топ_репутации":
            try:
                rep = data.get("rep", {})
                if not rep:
                    vk.messages_send(peer_id, "📋 Нет данных о репутации")
                    return
                
                sorted_rep = sorted(rep.items(), key=lambda x: x[1], reverse=True)[:10]
                text = "⭐ **Топ по репутации:**\n"
                for i, (uid, reps) in enumerate(sorted_rep, 1):
                    text += f"{i}. {await get_display_link(int(uid))} — {reps}\n"
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"Ошибка top_rep: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.15 rules - правила
        if command == "rules" or command == "правила":
            try:
                rules = data["settings"].get("rules", "Правила не установлены")
                vk.messages_send(peer_id, f"📋 **Правила чата:**\n{rules}")
            except Exception as e:
                logger.error(f"Ошибка rules: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.16 info - информация о боте
        if command == "info" or command == "инфо":
            try:
                info_text = f"""🤖 **Информация о боте**
📱 Версия: {config.get('version', '2.0')}
👥 Пользователей: {len(data.get('user_stats', {}))}
💬 Чатов: {len(data.get('group_chats', []))}
⚙️ API: {API_VERSION}
📊 Команд: {len(data.get('commands_usage', {}))}"""
                vk.messages_send(peer_id, info_text)
            except Exception as e:
                logger.error(f"Ошибка info: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.17 roll - кубик
        if command == "roll" or command == "кубик":
            try:
                if args and args[0].isdigit():
                    max_num = int(args[0])
                else:
                    max_num = 6
                
                if max_num < 2:
                    max_num = 2
                if max_num > 100:
                    max_num = 100
                
                result = random.randint(1, max_num)
                vk.messages_send(peer_id, f"🎲 {await get_display_link(user_id)} бросил кубик и получил {result} из {max_num}")
            except Exception as e:
                logger.error(f"Ошибка roll: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.18 coin - монетка
        if command == "coin" or command == "монетка":
            try:
                result = "Орел" if random.random() < 0.5 else "Решка"
                vk.messages_send(peer_id, f"🪙 {await get_display_link(user_id)} подбросил монетку: {result}")
            except Exception as e:
                logger.error(f"Ошибка coin: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.19 8ball - магический шар
        if command == "8ball" or command == "шар":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ Использование: !8ball [вопрос]")
                    return
                
                answers = [
                    "Да", "Нет", "Возможно", "Скорее всего", "Спроси позже",
                    "Определенно да", "Определенно нет", "Вероятно да", "Вероятно нет",
                    "Может быть", "Шансы хорошие", "Шансы плохие", "Неизвестно",
                    "Я не знаю", "Ты серьезно?", "Звезды говорят да", "Звезды говорят нет",
                    "Подумай сам", "Не сейчас", "Завтра", "Никогда"
                ]
                answer = random.choice(answers)
                vk.messages_send(peer_id, f"🔮 Шар говорит: {answer}")
            except Exception as e:
                logger.error(f"Ошибка 8ball: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.20 ping - проверка работы
        if command == "ping":
            try:
                vk.messages_send(peer_id, "🏓 Понг!")
            except Exception as e:
                logger.error(f"Ошибка ping: {e}")
            return
        
        # 3.21 whoami - кто я
        if command == "whoami" or command == "ктоя":
            try:
                name = await get_display_name(user_id)
                level = get_user_level(user_id)
                money = get_user_money(user_id)
                rep = get_user_rep(user_id)
                role = get_role(user_id) or "Обычный"
                
                vk.messages_send(peer_id, f"👤 Вы: {name}\n📊 Уровень: {level}\n💰 Денег: {money}\n⭐ Репутация: {rep}\n🎭 Роль: {role}")
            except Exception as e:
                logger.error(f"Ошибка whoami: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.22 say - сказать
        if command == "say" or command == "скажи":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ Использование: !say [текст]")
                    return
                
                text = " ".join(args)
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"Ошибка say: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.23 me - действие
        if command == "me":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ Использование: !me [действие]")
                    return
                
                name = await get_display_name(user_id)
                action = " ".join(args)
                vk.messages_send(peer_id, f"* {name} {action}")
            except Exception as e:
                logger.error(f"Ошибка me: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.24 remind - напоминание
        if command == "remind" or command == "напомни":
            try:
                if len(args) < 2:
                    vk.messages_send(peer_id, "❌ Использование: !remind [время в минутах] [текст]")
                    return
                
                minutes = int(args[0])
                text = " ".join(args[1:])
                
                if "reminders" not in data:
                    data["reminders"] = {}
                
                reminder_id = str(int(time.time()))
                data["reminders"][reminder_id] = {
                    "user_id": user_id,
                    "peer_id": peer_id,
                    "text": text,
                    "time": time.time() + (minutes * 60)
                }
                safe_save_json(DATA_FILE, data)
                vk.messages_send(peer_id, f"⏰ Напоминание установлено на {minutes} минут: {text}")
            except ValueError:
                vk.messages_send(peer_id, "❌ Ошибка: время должно быть числом!")
            except Exception as e:
                logger.error(f"Ошибка remind: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.25 remind_list - список напоминаний
        if command == "remind_list" or command == "напоминания":
            try:
                reminders = data.get("reminders", {})
                user_reminders = [
                    (rid, r) for rid, r in reminders.items() 
                    if r.get("user_id") == user_id and r.get("time", 0) > time.time()
                ]
                
                if user_reminders:
                    text = "⏰ **Ваши напоминания:**\n"
                    for rid, rem in user_reminders[:10]:
                        remaining = int(rem["time"] - time.time())
                        minutes = remaining // 60
                        text += f"• {rem['text']} — через {minutes} мин\n"
                    vk.messages_send(peer_id, text)
                else:
                    vk.messages_send(peer_id, "📋 Нет активных напоминаний")
            except Exception as e:
                logger.error(f"Ошибка remind_list: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.26 remind_cancel - отмена напоминания
        if command == "remind_cancel" or command == "отмена_напоминания":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ Использование: !remind_cancel [ID]")
                    return
                
                reminder_id = args[0]
                if reminder_id in data.get("reminders", {}):
                    del data["reminders"][reminder_id]
                    safe_save_json(DATA_FILE, data)
                    vk.messages_send(peer_id, "✅ Напоминание отменено!")
                else:
                    vk.messages_send(peer_id, "❌ Напоминание не найдено!")
            except Exception as e:
                logger.error(f"Ошибка remind_cancel: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.27 calc - калькулятор
        if command == "calc" or command == "калькулятор":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ Использование: !calc [выражение]")
                    return
                
                expression = " ".join(args)
                # Безопасное вычисление
                allowed = set("0123456789+-*/() .")
                if not all(c in allowed for c in expression):
                    vk.messages_send(peer_id, "❌ Недопустимые символы!")
                    return
                
                result = eval(expression)
                vk.messages_send(peer_id, f"📐 {expression} = {result}")
            except Exception as e:
                vk.messages_send(peer_id, f"❌ Ошибка вычисления!")
                logger.error(f"Ошибка calc: {e}")
            return
        
        # 3.28 joke - шутка
        if command == "joke" or command == "шутка":
            try:
                jokes = [
                    "Почему программисты не любят природу? Слишком много багов.",
                    "Как программист ловит рыбу? Он ее 'отлаживает'.",
                    "Сколько программистов нужно, чтобы поменять лампочку? Ни одного, это аппаратная проблема.",
                    "Почему 10 боится 7? Потому что 7 8 9.",
                    "Как назвать программиста, который не умеет кодить? Безработным."
                ]
                joke = random.choice(jokes)
                vk.messages_send(peer_id, f"😂 {joke}")
            except Exception as e:
                logger.error(f"Ошибка joke: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.29 random - случайное число
        if command == "random" or command == "рандом":
            try:
                if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
                    min_num = int(args[0])
                    max_num = int(args[1])
                else:
                    min_num = 1
                    max_num = 100
                
                if min_num > max_num:
                    min_num, max_num = max_num, min_num
                
                result = random.randint(min_num, max_num)
                vk.messages_send(peer_id, f"🔢 Случайное число от {min_num} до {max_num}: {result}")
            except Exception as e:
                logger.error(f"Ошибка random: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return
        
        # 3.30 choose - выбор
        if command == "choose" or command == "выбери":
            try:
                if not args:
                    vk.messages_send(peer_id, "❌ Использование: !choose [вариант1] | [вариант2] | ...")
                    return
                
                parts = " ".join(args).split("|")
                options = [opt.strip() for opt in parts if opt.strip()]
                
                if len(options) < 2:
                    vk.messages_send(peer_id, "❌ Нужно минимум 2 варианта!")
                    return
                
                chosen = random.choice(options)
                vk.messages_send(peer_id, f"🤔 Я выбираю: {chosen}")
            except Exception as e:
                logger.error(f"Ошибка choose: {e}")
                vk.messages_send(peer_id, "❌ Внутренняя ошибка!")
            return

# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================
async def main():
    """Основной цикл бота"""
    logger.info("🚀 Бот запускается...")
    
    # Сохранение времени запуска
    config["start_time"] = time.time()
    safe_save_json(CONFIG_FILE, config)
    
    # Получение Long Poll сервера
    server_data = vk.get_long_poll_server()
    if "error" in server_data:
        logger.error(f"Ошибка получения Long Poll сервера: {server_data['error']}")
        return
    
    server = server_data.get("server")
    key = server_data.get("key")
    ts = server_data.get("ts")
    
    if not server or not key or not ts:
        logger.error("Не удалось получить параметры Long Poll!")
        return
    
    logger.info(f"✅ Long Poll сервер получен: {server}")
    
    # Получение информации о группе
    group_info = vk.groups_get_by_id()
    if "error" not in group_info and group_info:
        group = group_info[0]
        logger.info(f"📢 Группа: {group.get('name', '')}")
    
    last_reminder_check = 0
    
    while True:
        try:
            # Проверка напоминаний
            if time.time() - last_reminder_check > 60:
                await check_reminders()
                last_reminder_check = time.time()
            
            # Запрос к Long Poll
            response = vk.long_poll_request(server, key, ts)
            
            if "failed" in response:
                error_code = response.get("failed", 0)
                if error_code == 1:
                    logger.warning("Неверный ts, обновление...")
                    server_data = vk.get_long_poll_server()
                    if "error" not in server_data:
                        server = server_data.get("server", server)
                        key = server_data.get("key", key)
                        ts = server_data.get("ts", ts)
                    continue
                elif error_code == 2:
                    logger.warning("Истек ключ, обновление...")
                    server_data = vk.get_long_poll_server()
                    if "error" not in server_data:
                        server = server_data.get("server", server)
                        key = server_data.get("key", key)
                        ts = server_data.get("ts", ts)
                    continue
                elif error_code == 3:
                    logger.warning("Информация потеряна, обновление...")
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
                        # Обработка нового сообщения
                        message_data = update.get("object", {})
                        await process_message(message_data)
                    
                    elif update_type == "group_join":
                        # Обработка входа в беседу
                        await handle_group_join(update.get("object", {}))
                    
                    elif update_type == "group_leave":
                        # Обработка выхода из беседы
                        await handle_group_leave(update.get("object", {}))
                    
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
        logger.critical(f"Критическая ошибка: {e}")
        raise
