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
PREFIX = "/"
DATA_FILE = "assistant_bot_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "owner": 1118563484,
            "roles": {
                "admin": {"name": "👑 Администратор", "level": 4},
                "supermoderator": {"name": "🔑 Старший модератор", "level": 3},
                "moderator": {"name": "🔨 Модератор", "level": 2},
                "normal": {"name": "🧑 Участник", "level": 1}
            },
            "user_roles": {},
            "bans": {},
            "mutes": {},
            "chat_settings": {},
            "mutes": {},
            "bans": {},
            "warns": {},
            "antimat": {},
            "antispam": {},
            "antilink": {},
            "antiphoto": {},
            "antiflood": {},
            "clean_history": {},
            "autodelete": {},
            "all_in_pm": {},
            "log_chats": {},
            "prefixes": {},
            "welcome": {},
            "autokick": {},
            "fixinvite": {},
            "per_minute": {},
            "antiraid": {},
            "antibot": {},
            "antipriziv": {},
            "invite_link": {},
            "descriptions": {},
            "macros": {},
            "events": {},
            "game_links": {},
            "clan_default": {},
            "clan_history": {},
            "server_data": {},
            "channel_names": {},
            "server_members": {}
        }

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Save error: {e}")

data = load_data()

def user_link(user_id, name=None):
    if name is None:
        return f"[id{user_id}|Пользователь]"
    return f"[id{user_id}|{name}]"

class VKAPI:
    def __init__(self, token, group_id, version="5.199"):
        self.token = token
        self.group_id = group_id
        self.version = version
        self.base_url = "https://api.vk.com/method/"
    
    def _request(self, method, params=None):
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
    
    def messages_send(self, peer_id, message):
        return self._request("messages.send", {
            "peer_id": peer_id,
            "message": message,
            "random_id": int(time.time() * 1000) + random.randint(1, 99999),
            "disable_mentions": 1
        })
    
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
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Long Poll error: {e}")
            return {"failed": 1}

vk = VKAPI(TOKEN, GROUP_ID)

async def get_user_name(user_id):
    try:
        result = vk.users_get(user_id)
        if "error" not in result and result:
            user = result[0]
            return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return f"ID {user_id}"
    except:
        return f"ID {user_id}"

async def get_user_link(user_id):
    name = await get_user_name(user_id)
    return user_link(user_id, name)

def get_role_level(user_id, peer_id):
    """Получает уровень роли пользователя в беседе"""
    user_roles = data.get("user_roles", {}).get(str(peer_id), {})
    role = user_roles.get(str(user_id), "normal")
    return data.get("roles", {}).get(role, {}).get("level", 1)

def is_admin(user_id, peer_id):
    return get_role_level(user_id, peer_id) >= 4

def is_supermoderator(user_id, peer_id):
    return get_role_level(user_id, peer_id) >= 3

def is_moderator(user_id, peer_id):
    return get_role_level(user_id, peer_id) >= 2

def is_banned(user_id, peer_id):
    bans = data.get("bans", {}).get(str(peer_id), {})
    if str(user_id) in bans:
        if bans[str(user_id)] > time.time():
            return True
        else:
            del bans[str(user_id)]
            save_data(data)
    return False

def is_muted(user_id, peer_id):
    mutes = data.get("mutes", {}).get(str(peer_id), {})
    if str(user_id) in mutes:
        if mutes[str(user_id)] > time.time():
            return True
        else:
            del mutes[str(user_id)]
            save_data(data)
    return False

async def process_message(message_data):
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
        
        if not is_chat:
            # В ЛС только базовые команды
            if text.startswith(PREFIX):
                text = text[1:].strip()
                args = text.split()
                if not args:
                    return
                command = args[0].lower()
                
                if command == "start":
                    await vk.messages_send(peer_id, "🤖 Бот-помощник активен!\nИспользуйте /help для списка команд в беседе.")
                    return
                
                if command == "help" or command == "помощь":
                    await vk.messages_send(peer_id, "🤖 Бот-помощник для управления беседами.\nДобавьте бота в беседу и выдайте права администратора.\nКоманды: /start, /help, /ping")
                    return
                
                if command == "ping":
                    await vk.messages_send(peer_id, "🏓 Pong!")
                    return
            return
        
        # Проверка бана/мута
        if is_banned(user_id, peer_id):
            return
        
        if is_muted(user_id, peer_id):
            return
        
        # Обработка команд
        if not text.startswith(PREFIX):
            return
        
        text = text[1:].strip()
        args = text.split()
        if not args:
            return
        
        command = args[0].lower()
        
        # ============================================================
        # 1. ОБЩИЕ КОМАНДЫ
        # ============================================================
        if command == "help" or command == "помощь":
            help_text = (
                "🤖 **Бот-помощник**\n\n"
                "**Общие:**\n"
                "/start — начать\n"
                "/ping — проверка\n"
                "/online — онлайн\n"
                "/неактив [время] — неактивные\n\n"
                "**Модерация:**\n"
                "/кик [пользователь] — кикнуть\n"
                "/бан [время] [пользователь] — забанить\n"
                "/разбан [пользователь] — разбанить\n"
                "/мут [время] [пользователь] — заглушить\n"
                "/размут [пользователь] — размутить\n"
                "/банлист — список банов\n\n"
                "**Роли:**\n"
                "/роли — список ролей\n"
                "/дать [роль] [пользователь] — выдать роль\n"
                "/забрать [роль] [пользователь] — забрать роль\n"
                "/начальники — руководящие роли\n"
                "/создатель [пользователь] — назначить создателем\n"
                "/админ [пользователь] — назначить админом\n"
                "/модератор [пользователь] — назначить модератором\n\n"
                "**Настройки:**\n"
                "/настройки — показать настройки\n"
                "/префикс [префикс] — изменить префикс\n"
                "/приветствие [текст] — установить приветствие\n"
                "/антимат — переключить антимат\n"
                "/антиссылки — переключить антиссылки\n"
                "/антифото — переключить антифото\n"
                "/антифлуд — переключить антифлуд\n"
                "/тишина — только модераторы могут писать\n\n"
                "**Удаление:**\n"
                "/удали [сообщение] — удалить сообщение\n"
                "/чистка [время] [пользователь] — очистка\n"
                "/чистаяистория [время] — автоочистка\n\n"
                "**Рейтинг:**\n"
                "/рейтинг [пользователь] — рейтинг\n"
                "/рейтинги [время] — топ рейтинга\n\n"
                "**Макросы:**\n"
                "/макросы — список макросов\n"
                "/новыймакрос [название] [текст] — создать макрос\n"
                "/правила — показать правила\n"
                "/новыеправила [текст] — установить правила"
            )
            await vk.messages_send(peer_id, help_text)
            return
        
        if command == "ping":
            start = time.time()
            vk.users_get(GROUP_ID)
            latency = int((time.time() - start) * 1000)
            await vk.messages_send(peer_id, f"🏓 Pong! {latency}ms")
            return
        
        if command == "start":
            await vk.messages_send(peer_id, "🤖 Бот-помощник активен!\nИспользуйте /help для списка команд.")
            return
        
        if command == "online":
            await vk.messages_send(peer_id, "👥 Онлайн: 15 пользователей (демонстрация)")
            return
        
        if command == "неактив":
            time_arg = args[1] if len(args) > 1 else "30м"
            await vk.messages_send(peer_id, f"⏳ Неактивные за {time_arg}: (демонстрация)")
            return
        
        # ============================================================
        # 2. КОМАНДЫ МОДЕРАЦИИ (требуют роли)
        # ============================================================
        if is_moderator(user_id, peer_id) or is_supermoderator(user_id, peer_id) or is_admin(user_id, peer_id):
            
            if command == "кик":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /кик [пользователь]")
                    return
                try:
                    target_id = int(args[1])
                    chat_id = peer_id - 2000000000
                    target_link = await get_user_link(target_id)
                    result = vk.messages_remove_chat_user(chat_id, target_id)
                    if "error" not in result:
                        await vk.messages_send(peer_id, f"👢 {target_link} кикнут")
                    else:
                        await vk.messages_send(peer_id, "❌ Ошибка")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "бан":
                if len(args) < 3:
                    await vk.messages_send(peer_id, "❌ /бан [время] [пользователь]")
                    return
                try:
                    time_str = args[1]
                    target_id = int(args[2])
                    seconds = parse_time(time_str)
                    if seconds == 0:
                        seconds = 7 * 24 * 60 * 60
                    if "bans" not in data:
                        data["bans"] = {}
                    if str(peer_id) not in data["bans"]:
                        data["bans"][str(peer_id)] = {}
                    data["bans"][str(peer_id)][str(target_id)] = time.time() + seconds
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"🚫 {target_link} забанен на {time_str}")
                    chat_id = peer_id - 2000000000
                    vk.messages_remove_chat_user(chat_id, target_id)
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "разбан":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /разбан [пользователь]")
                    return
                try:
                    target_id = int(args[1])
                    if str(peer_id) in data.get("bans", {}) and str(target_id) in data["bans"][str(peer_id)]:
                        del data["bans"][str(peer_id)][str(target_id)]
                        save_data(data)
                        target_link = await get_user_link(target_id)
                        await vk.messages_send(peer_id, f"✅ {target_link} разбанен")
                    else:
                        await vk.messages_send(peer_id, "❌ Не забанен")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "мут":
                if len(args) < 3:
                    await vk.messages_send(peer_id, "❌ /мут [время] [пользователь]")
                    return
                try:
                    time_str = args[1]
                    target_id = int(args[2])
                    seconds = parse_time(time_str)
                    if seconds == 0:
                        seconds = 5 * 60
                    if "mutes" not in data:
                        data["mutes"] = {}
                    if str(peer_id) not in data["mutes"]:
                        data["mutes"][str(peer_id)] = {}
                    data["mutes"][str(peer_id)][str(target_id)] = time.time() + seconds
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"🔇 {target_link} заглушен на {time_str}")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "размут":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /размут [пользователь]")
                    return
                try:
                    target_id = int(args[1])
                    if str(peer_id) in data.get("mutes", {}) and str(target_id) in data["mutes"][str(peer_id)]:
                        del data["mutes"][str(peer_id)][str(target_id)]
                        save_data(data)
                        target_link = await get_user_link(target_id)
                        await vk.messages_send(peer_id, f"✅ {target_link} размучен")
                    else:
                        await vk.messages_send(peer_id, "❌ Не заглушен")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "банлист":
                bans = data.get("bans", {}).get(str(peer_id), {})
                if not bans:
                    await vk.messages_send(peer_id, "📋 Нет забаненных")
                    return
                text = "🚫 **Банлист:**\n"
                for uid, until in bans.items():
                    if until > time.time():
                        link = await get_user_link(int(uid))
                        remaining = int((until - time.time()) / 60)
                        text += f"• {link} — {remaining} мин\n"
                await vk.messages_send(peer_id, text)
                return
        
        # ============================================================
        # 3. РОЛИ (требуют прав)
        # ============================================================
        if is_supermoderator(user_id, peer_id) or is_admin(user_id, peer_id):
            
            if command == "роли":
                roles = data.get("roles", {})
                text = "👑 **Роли:**\n"
                for role, info in roles.items():
                    text += f"• {info['name']} — уровень {info['level']}\n"
                await vk.messages_send(peer_id, text)
                return
            
            if command == "дать":
                if len(args) < 3:
                    await vk.messages_send(peer_id, "❌ /дать [роль] [пользователь]")
                    return
                try:
                    role = args[1]
                    target_id = int(args[2])
                    if role not in data.get("roles", {}):
                        await vk.messages_send(peer_id, "❌ Роль не найдена")
                        return
                    if "user_roles" not in data:
                        data["user_roles"] = {}
                    if str(peer_id) not in data["user_roles"]:
                        data["user_roles"][str(peer_id)] = {}
                    data["user_roles"][str(peer_id)][str(target_id)] = role
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} получил роль {role}")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "забрать":
                if len(args) < 3:
                    await vk.messages_send(peer_id, "❌ /забрать [роль] [пользователь]")
                    return
                try:
                    role = args[1]
                    target_id = int(args[2])
                    if str(peer_id) in data.get("user_roles", {}) and str(target_id) in data["user_roles"][str(peer_id)]:
                        del data["user_roles"][str(peer_id)][str(target_id)]
                        save_data(data)
                        target_link = await get_user_link(target_id)
                        await vk.messages_send(peer_id, f"✅ {target_link} лишен роли {role}")
                    else:
                        await vk.messages_send(peer_id, "❌ Роль не найдена")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "начальники":
                text = "👑 **Руководящие роли:**\n"
                roles = data.get("roles", {})
                for role, info in roles.items():
                    if info["level"] >= 2:
                        text += f"• {info['name']}:\n"
                        for uid, r in data.get("user_roles", {}).get(str(peer_id), {}).items():
                            if r == role:
                                link = await get_user_link(int(uid))
                                text += f"  {link}\n"
                await vk.messages_send(peer_id, text)
                return
            
            if command == "создатель":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /создатель [пользователь]")
                    return
                try:
                    target_id = int(args[1])
                    if "user_roles" not in data:
                        data["user_roles"] = {}
                    if str(peer_id) not in data["user_roles"]:
                        data["user_roles"][str(peer_id)] = {}
                    data["user_roles"][str(peer_id)][str(target_id)] = "admin"
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"👑 {target_link} назначен создателем")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "админ":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /админ [пользователь]")
                    return
                try:
                    target_id = int(args[1])
                    if "user_roles" not in data:
                        data["user_roles"] = {}
                    if str(peer_id) not in data["user_roles"]:
                        data["user_roles"][str(peer_id)] = {}
                    data["user_roles"][str(peer_id)][str(target_id)] = "supermoderator"
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"🔑 {target_link} назначен админом")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
            
            if command == "модератор":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /модератор [пользователь]")
                    return
                try:
                    target_id = int(args[1])
                    if "user_roles" not in data:
                        data["user_roles"] = {}
                    if str(peer_id) not in data["user_roles"]:
                        data["user_roles"][str(peer_id)] = {}
                    data["user_roles"][str(peer_id)][str(target_id)] = "moderator"
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"🔨 {target_link} назначен модератором")
                except:
                    await vk.messages_send(peer_id, "❌ Ошибка")
                return
        
        # ============================================================
        # 4. НАСТРОЙКИ БЕСЕДЫ
        # ============================================================
        if is_supermoderator(user_id, peer_id) or is_admin(user_id, peer_id):
            
            if command == "настройки":
                settings = data.get("chat_settings", {}).get(str(peer_id), {})
                text = "⚙️ **Настройки беседы:**\n"
                for key, value in settings.items():
                    text += f"• {key}: {value}\n"
                await vk.messages_send(peer_id, text)
                return
            
            if command == "префикс":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /префикс [префикс]")
                    return
                prefix = args[1]
                if "prefixes" not in data:
                    data["prefixes"] = {}
                data["prefixes"][str(peer_id)] = prefix
                save_data(data)
                await vk.messages_send(peer_id, f"✅ Префикс установлен: {prefix}")
                return
            
            if command == "приветствие":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /приветствие [текст]")
                    return
                welcome_text = " ".join(args[1:])
                if "welcome" not in data:
                    data["welcome"] = {}
                data["welcome"][str(peer_id)] = welcome_text
                save_data(data)
                await vk.messages_send(peer_id, f"✅ Приветствие установлено")
                return
            
            if command == "антимат":
                if "antimat" not in data:
                    data["antimat"] = {}
                data["antimat"][str(peer_id)] = not data["antimat"].get(str(peer_id), False)
                save_data(data)
                status = "включен" if data["antimat"][str(peer_id)] else "выключен"
                await vk.messages_send(peer_id, f"✅ Антимат {status}")
                return
            
            if command == "антиссылки":
                if "antilink" not in data:
                    data["antilink"] = {}
                data["antilink"][str(peer_id)] = not data["antilink"].get(str(peer_id), False)
                save_data(data)
                status = "включены" if data["antilink"][str(peer_id)] else "выключены"
                await vk.messages_send(peer_id, f"✅ Антиссылки {status}")
                return
            
            if command == "антифото":
                if "antiphoto" not in data:
                    data["antiphoto"] = {}
                data["antiphoto"][str(peer_id)] = not data["antiphoto"].get(str(peer_id), False)
                save_data(data)
                status = "включено" if data["antiphoto"][str(peer_id)] else "выключено"
                await vk.messages_send(peer_id, f"✅ Антифото {status}")
                return
            
            if command == "антифлуд":
                if "antiflood" not in data:
                    data["antiflood"] = {}
                data["antiflood"][str(peer_id)] = not data["antiflood"].get(str(peer_id), False)
                save_data(data)
                status = "включен" if data["antiflood"][str(peer_id)] else "выключен"
                await vk.messages_send(peer_id, f"✅ Антифлуд {status}")
                return
            
            if command == "тишина":
                if "silence" not in data:
                    data["silence"] = {}
                data["silence"][str(peer_id)] = not data["silence"].get(str(peer_id), False)
                save_data(data)
                status = "включена" if data["silence"][str(peer_id)] else "выключена"
                await vk.messages_send(peer_id, f"✅ Тишина {status}")
                return
        
        # ============================================================
        # 5. УДАЛЕНИЕ СООБЩЕНИЙ
        # ============================================================
        if is_moderator(user_id, peer_id) or is_supermoderator(user_id, peer_id) or is_admin(user_id, peer_id):
            
            if command == "удали":
                await vk.messages_send(peer_id, "✅ Сообщение удалено (демонстрация)")
                return
            
            if command == "чистка":
                await vk.messages_send(peer_id, "🧹 Очистка выполнена (демонстрация)")
                return
            
            if command == "чистаяистория":
                await vk.messages_send(peer_id, "✅ Чистая история включена (демонстрация)")
                return
        
        # ============================================================
        # 6. РЕЙТИНГ
        # ============================================================
        if command == "рейтинг":
            await vk.messages_send(peer_id, "📊 Рейтинг: (демонстрация)")
            return
        
        if command == "рейтинги":
            await vk.messages_send(peer_id, "🏆 Рейтинги: (демонстрация)")
            return
        
        # ============================================================
        # 7. МАКРОСЫ
        # ============================================================
        if command == "макросы":
            macros = data.get("macros", {}).get(str(peer_id), {})
            if not macros:
                await vk.messages_send(peer_id, "📋 Нет макросов")
                return
            text = "📋 **Макросы:**\n"
            for name, value in macros.items():
                text += f"• {name}: {value[:30]}...\n"
            await vk.messages_send(peer_id, text)
            return
        
        if command == "новыймакрос":
            if len(args) < 3:
                await vk.messages_send(peer_id, "❌ /новыймакрос [название] [текст]")
                return
            if "macros" not in data:
                data["macros"] = {}
            if str(peer_id) not in data["macros"]:
                data["macros"][str(peer_id)] = {}
            name = args[1]
            value = " ".join(args[2:])
            data["macros"][str(peer_id)][name] = value
            save_data(data)
            await vk.messages_send(peer_id, f"✅ Макрос создан: {name}")
            return
        
        if command == "правила":
            rules = data.get("chat_settings", {}).get(str(peer_id), {}).get("rules", "Правил нет")
            await vk.messages_send(peer_id, f"📋 **Правила:**\n{rules}")
            return
        
        if command == "новыеправила":
            if len(args) < 2:
                await vk.messages_send(peer_id, "❌ /новыеправила [текст]")
                return
            rules_text = " ".join(args[1:])
            if "chat_settings" not in data:
                data["chat_settings"] = {}
            if str(peer_id) not in data["chat_settings"]:
                data["chat_settings"][str(peer_id)] = {}
            data["chat_settings"][str(peer_id)]["rules"] = rules_text
            save_data(data)
            await vk.messages_send(peer_id, "✅ Правила установлены")
            return
        
        # ============================================================
        # 8. CR/BS КОМАНДЫ (демонстрация)
        # ============================================================
        if command == "кто":
            await vk.messages_send(peer_id, "👤 Информация о пользователе (демонстрация)")
            return
        
        if command == "клан":
            await vk.messages_send(peer_id, "🏰 Информация о клане (демонстрация)")
            return
        
        if command == "профиль":
            await vk.messages_send(peer_id, "👤 Профиль игрока (демонстрация)")
            return
        
        # ============================================================
        # 9. СЕРВЕРЫ
        # ============================================================
        if is_admin(user_id, peer_id):
            if command == "сервер":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "❌ /сервер [имя]")
                    return
                server_name = args[1]
                if "server_data" not in data:
                    data["server_data"] = {}
                data["server_data"][server_name] = {"chats": [peer_id]}
                save_data(data)
                await vk.messages_send(peer_id, f"✅ Сервер создан: {server_name}")
                return
        
    except Exception as e:
        logger.error(f"Process error: {e}")

def parse_time(time_str):
    """Парсит время из строки вида 30м, 2ч, 7д"""
    if not time_str:
        return 0
    if time_str.endswith("м"):
        return int(time_str[:-1]) * 60
    elif time_str.endswith("ч"):
        return int(time_str[:-1]) * 60 * 60
    elif time_str.endswith("д"):
        return int(time_str[:-1]) * 24 * 60 * 60
    else:
        return int(time_str)

start_time = time.time()

async def main():
    logger.info("🤖 ASSISTANT BOT START")
    logger.info(f"Group: {GROUP_ID}")
    
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
    
    logger.info("✅ BOT READY")
    logger.info("💀 Commands: /help")
    
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
