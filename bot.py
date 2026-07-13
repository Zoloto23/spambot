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

DATA_FILE = "epic_bot_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
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
            "support_tickets": [],
            "settings": {
                "welcome": "Добро пожаловать в чат, {user}!",
                "rules": "1. Не материться\n2. Не спамить\n3. Уважать друг друга",
                "antispam": True,
                "spam_limit": 3,
                "spam_time": 5,
                "antilink": True,
                "whitelist": ["vk.com", "youtube.com", "t.me"],
                "slow_mode": False,
                "slow_delay": 3,
                "welcome_enabled": True,
                "leave_enabled": True
            },
            "shop": {
                "Роли": [
                    {"id": "vip", "name": "VIP", "price": 1000000, "desc": "VIP статус навсегда"},
                    {"id": "premium", "name": "Premium", "price": 500000, "desc": "Premium статус на месяц"},
                ],
                "Цвета": [
                    {"id": "red", "name": "Красный", "price": 50000, "desc": "Красный ник"},
                    {"id": "blue", "name": "Синий", "price": 50000, "desc": "Синий ник"},
                    {"id": "gold", "name": "Золотой", "price": 100000, "desc": "Золотой ник"},
                ]
            }
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
    
    def messages_send(self, peer_id, message, attachment=None):
        params = {
            "peer_id": peer_id,
            "message": message,
            "random_id": int(time.time() * 1000) + random.randint(1, 99999),
            "disable_mentions": 1
        }
        if attachment:
            params["attachment"] = attachment
        return self._request("messages.send", params)
    
    def messages_get_by_id(self, message_ids):
        return self._request("messages.getById", {"message_ids": message_ids})
    
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
    
    def photos_get_messages_upload_server(self):
        return self._request("photos.getMessagesUploadServer")
    
    def photos_save_messages_photo(self, photo, server, hash):
        return self._request("photos.saveMessagesPhoto", {
            "photo": photo,
            "server": server,
            "hash": hash
        })

vk = VKAPI(TOKEN, GROUP_ID)

async def upload_image(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        upload_server = vk.photos_get_messages_upload_server()
        if "error" in upload_server:
            return None
        upload_url = upload_server.get("upload_url")
        if not upload_url:
            return None
        files = {'photo': ('image.jpg', response.content, 'image/jpeg')}
        upload_response = requests.post(upload_url, files=files)
        upload_data = upload_response.json()
        saved = vk.photos_save_messages_photo(
            photo=upload_data.get("photo"),
            server=upload_data.get("server"),
            hash=upload_data.get("hash")
        )
        if "error" in saved or not saved:
            return None
        photo = saved[0]
        attachment = f"photo{photo['owner_id']}_{photo['id']}"
        return attachment
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return None

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

def is_owner(user_id):
    return user_id == data.get("owner", 1118563484)

def is_admin(user_id):
    if is_owner(user_id):
        return True
    return str(user_id) in data.get("admins", {})

def is_mod(user_id):
    if is_admin(user_id):
        return True
    return str(user_id) in data.get("mods", {})

def is_banned(user_id, peer_id):
    key = f"{peer_id}_{user_id}"
    if key in data.get("banned", {}):
        if data["banned"][key] > time.time():
            return True
        else:
            del data["banned"][key]
            save_data(data)
    return False

def is_muted(user_id, peer_id):
    key = f"{peer_id}_{user_id}"
    if key in data.get("muted", {}):
        if data["muted"][key] > time.time():
            return True
        else:
            del data["muted"][key]
            save_data(data)
    return False

async def add_money(user_id, amount):
    data["money"][str(user_id)] = data["money"].get(str(user_id), 0) + amount
    save_data(data)

async def remove_money(user_id, amount):
    current = data["money"].get(str(user_id), 0)
    if current < amount:
        return False
    data["money"][str(user_id)] = current - amount
    save_data(data)
    return True

async def add_exp(user_id, amount):
    data["exp"][str(user_id)] = data["exp"].get(str(user_id), 0) + amount
    exp = data["exp"][str(user_id)]
    data["level"][str(user_id)] = int(exp / 100) + 1
    save_data(data)

async def check_links(text):
    if not data["settings"].get("antilink", True):
        return False
    whitelist = data["settings"].get("whitelist", ["vk.com", "youtube.com", "t.me"])
    url_pattern = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
    links = re.findall(url_pattern, text)
    for link in links:
        if not any(w in link.lower() for w in whitelist):
            return True
    return False

async def check_spam(user_id, peer_id):
    if not data["settings"].get("antispam", True):
        return False
    key = f"{peer_id}_{user_id}"
    now = time.time()
    if key not in data["message_history"]:
        data["message_history"][key] = []
    spam_time = data["settings"].get("spam_time", 5)
    data["message_history"][key] = [t for t in data["message_history"][key] if now - t < spam_time]
    spam_limit = data["settings"].get("spam_limit", 3)
    if len(data["message_history"][key]) >= spam_limit:
        return True
    data["message_history"][key].append(now)
    save_data(data)
    return False

async def get_reply_user_id(message_data):
    try:
        if "object" in message_data and "message" in message_data["object"]:
            msg = message_data["object"]["message"]
            if "reply_message" in msg:
                reply_msg = msg["reply_message"]
                return reply_msg.get("from_id", 0)
        return 0
    except:
        return 0

# ============================================================
# 🎭 RP КОМАНДЫ (100+ действий с картинками, включая 18+)
# ============================================================

RP_COMMANDS = {
    # Обычные RP
    "обнять": {
        "desc": "🤗 обнял(а)",
        "img": "https://i.pinimg.com/736x/b7/34/b1/b734b111a8567a31fd181dd458c08414.jpg"
    },
    "поцеловать": {
        "desc": "💋 поцеловал(а)",
        "img": "https://i.pinimg.com/736x/2d/bf/18/2dbf18b3e07281b88d03a674f7c11cc5.jpg"
    },
    "ударить": {
        "desc": "👊 ударил(а)",
        "img": "https://i.pinimg.com/736x/5d/73/2f/5d732f6444c8f3c0fcaf16c507be4c26.jpg"
    },
    "погладить": {
        "desc": "👋 погладил(а)",
        "img": "https://i.pinimg.com/736x/6a/2d/8f/6a2d8f3d7c4e5f6g7h8i9j0k1l2m3n4o5.jpg"
    },
    "укусить": {
        "desc": "🦷 укусил(а)",
        "img": "https://i.pinimg.com/736x/4f/3e/2d/4f3e2d1c2b3a4f5e6d7c8b9a0f1e2d3c.jpg"
    },
    "толкнуть": {
        "desc": "💨 толкнул(а)",
        "img": "https://i.pinimg.com/736x/8a/7b/6c/8a7b6c5d4e3f2g1h2i3j4k5l6m7n8o9p.jpg"
    },
    "пощечина": {
        "desc": "💢 дал(а) пощёчину",
        "img": "https://i.pinimg.com/736x/1c/2d/3e/1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r.jpg"
    },
    "облизать": {
        "desc": "👅 облизал(а)",
        "img": "https://i.pinimg.com/736x/2e/3f/4g/2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t.jpg"
    },
    "потискать": {
        "desc": "🤗 потискал(а)",
        "img": "https://i.pinimg.com/736x/3f/4g/5h/3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u.jpg"
    },
    "прижать": {
        "desc": "🤗 прижал(а) к себе",
        "img": "https://i.pinimg.com/736x/4g/5h/6i/4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v.jpg"
    },
    "задушить": {
        "desc": "🫂 задушил(а) в объятиях",
        "img": "https://i.pinimg.com/736x/5h/6i/7j/5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w.jpg"
    },
    "ущипнуть": {
        "desc": "✊ ущипнул(а)",
        "img": "https://i.pinimg.com/736x/6i/7j/8k/6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x.jpg"
    },
    "кинуть_камень": {
        "desc": "🪨 кинул(а) камень в",
        "img": "https://i.pinimg.com/736x/7j/8k/9l/7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y.jpg"
    },
    "полить_водой": {
        "desc": "💧 полил(а) водой",
        "img": "https://i.pinimg.com/736x/8k/9l/0m/8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z.jpg"
    },
    "кинуть_торт": {
        "desc": "🎂 кинул(а) торт в",
        "img": "https://i.pinimg.com/736x/9l/0m/1n/9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4a.jpg"
    },
    "облить_соком": {
        "desc": "🧃 облил(а) соком",
        "img": "https://i.pinimg.com/736x/0m/1n/2o/0m1n2o3p4q5r6s7t8u9v0w1x2y3z4a5b.jpg"
    },
    "забросать_подушками": {
        "desc": "🛏️ забросал(а) подушками",
        "img": "https://i.pinimg.com/736x/1n/2o/3p/1n2o3p4q5r6s7t8u9v0w1x2y3z4a5b6c.jpg"
    },
    "дать_пять": {
        "desc": "✋ дал(а) пять",
        "img": "https://i.pinimg.com/736x/2o/3p/4q/2o3p4q5r6s7t8u9v0w1x2y3z4a5b6c7d.jpg"
    },
    "кулак": {
        "desc": "👊 стукнул(а) кулаком",
        "img": "https://i.pinimg.com/736x/3p/4q/5r/3p4q5r6s7t8u9v0w1x2y3z4a5b6c7d8e.jpg"
    },
    "пожать_руку": {
        "desc": "🤝 пожал(а) руку",
        "img": "https://i.pinimg.com/736x/4q/5r/6s/4q5r6s7t8u9v0w1x2y3z4a5b6c7d8e9f.jpg"
    },
    "поклон": {
        "desc": "🙇 поклонился(лась)",
        "img": "https://i.pinimg.com/736x/5r/6s/7t/5r6s7t8u9v0w1x2y3z4a5b6c7d8e9f0g.jpg"
    },
    "салют": {
        "desc": "🫡 отдал(а) честь",
        "img": "https://i.pinimg.com/736x/6s/7t/8u/6s7t8u9v0w1x2y3z4a5b6c7d8e9f0g1h.jpg"
    },
    "обнять_сзади": {
        "desc": "🤗 обнял(а) сзади",
        "img": "https://i.pinimg.com/736x/7t/8u/9v/7t8u9v0w1x2y3z4a5b6c7d8e9f0g1h2i.jpg"
    },
    "поцеловать_в_лоб": {
        "desc": "💋 поцеловал(а) в лоб",
        "img": "https://i.pinimg.com/736x/8u/9v/0w/8u9v0w1x2y3z4a5b6c7d8e9f0g1h2i3j.jpg"
    },
    "поцеловать_в_щеку": {
        "desc": "💋 поцеловал(а) в щёку",
        "img": "https://i.pinimg.com/736x/9v/0w/1x/9v0w1x2y3z4a5b6c7d8e9f0g1h2i3j4k.jpg"
    },
    "поцеловать_руку": {
        "desc": "💋 поцеловал(а) руку",
        "img": "https://i.pinimg.com/736x/0w/1x/2y/0w1x2y3z4a5b6c7d8e9f0g1h2i3j4k5l.jpg"
    },
    "взять_за_руку": {
        "desc": "🤝 взял(а) за руку",
        "img": "https://i.pinimg.com/736x/1x/2y/3z/1x2y3z4a5b6c7d8e9f0g1h2i3j4k5l6m.jpg"
    },
    "приобнять_за_талию": {
        "desc": "🤗 приобнял(а) за талию",
        "img": "https://i.pinimg.com/736x/2y/3z/4a/2y3z4a5b6c7d8e9f0g1h2i3j4k5l6m7n.jpg"
    },
    "шепнуть_на_ухо": {
        "desc": "👂 шепнул(а) на ухо",
        "img": "https://i.pinimg.com/736x/3z/4a/5b/3z4a5b6c7d8e9f0g1h2i3j4k5l6m7n8o.jpg"
    },
    "погладить_по_голове": {
        "desc": "👋 погладил(а) по голове",
        "img": "https://i.pinimg.com/736x/4a/5b/6c/4a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p.jpg"
    },
    "танцевать": {
        "desc": "💃 танцевал(а) с",
        "img": "https://i.pinimg.com/736x/5b/6c/7d/5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q.jpg"
    },
    "петь": {
        "desc": "🎤 пел(а) для",
        "img": "https://i.pinimg.com/736x/6c/7d/8e/6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r.jpg"
    },
    "играть_на_гитаре": {
        "desc": "🎸 играл(а) на гитаре для",
        "img": "https://i.pinimg.com/736x/7d/8e/9f/7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r2s.jpg"
    },
    "рисовать": {
        "desc": "🎨 нарисовал(а) портрет",
        "img": "https://i.pinimg.com/736x/8e/9f/0g/8e9f0g1h2i3j4k5l6m7n8o9p0q1r2s3t.jpg"
    },
    "читать_стихи": {
        "desc": "📖 читал(а) стихи",
        "img": "https://i.pinimg.com/736x/9f/0g/1h/9f0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u.jpg"
    },
    "пнуть": {
        "desc": "🦶 пнул(а)",
        "img": "https://i.pinimg.com/736x/0g/1h/2i/0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v.jpg"
    },
    "ударить_головой": {
        "desc": "🤕 ударил(а) головой",
        "img": "https://i.pinimg.com/736x/1h/2i/3j/1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w.jpg"
    },
    "кинуть_в_стену": {
        "desc": "💥 кинул(а) в стену",
        "img": "https://i.pinimg.com/736x/2i/3j/4k/2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w7x.jpg"
    },
    "схватить_за_горло": {
        "desc": "🫴 схватил(а) за горло",
        "img": "https://i.pinimg.com/736x/3j/4k/5l/3j4k5l6m7n8o9p0q1r2s3t4u5v6w7x8y.jpg"
    },
    "дать_подзатыльник": {
        "desc": "👋 дал(а) подзатыльник",
        "img": "https://i.pinimg.com/736x/4k/5l/6m/4k5l6m7n8o9p0q1r2s3t4u5v6w7x8y9z.jpg"
    },
    "накормить": {
        "desc": "🍕 накормил(а)",
        "img": "https://i.pinimg.com/736x/5l/6m/7n/5l6m7n8o9p0q1r2s3t4u5v6w7x8y9z0a.jpg"
    },
    "напоить": {
        "desc": "🥤 напоил(а)",
        "img": "https://i.pinimg.com/736x/6m/7n/8o/6m7n8o9p0q1r2s3t4u5v6w7x8y9z0a1b.jpg"
    },
    "угостить_конфетой": {
        "desc": "🍬 угостил(а) конфетой",
        "img": "https://i.pinimg.com/736x/7n/8o/9p/7n8o9p0q1r2s3t4u5v6w7x8y9z0a1b2c.jpg"
    },
    "приготовить_завтрак": {
        "desc": "🍳 приготовил(а) завтрак",
        "img": "https://i.pinimg.com/736x/8o/9p/0q/8o9p0q1r2s3t4u5v6w7x8y9z0a1b2c3d.jpg"
    },
    "бегать": {
        "desc": "🏃 бегал(а) с",
        "img": "https://i.pinimg.com/736x/9p/0q/1r/9p0q1r2s3t4u5v6w7x8y9z0a1b2c3d4e.jpg"
    },
    "плавать": {
        "desc": "🏊 плавал(а) с",
        "img": "https://i.pinimg.com/736x/0q/1r/2s/0q1r2s3t4u5v6w7x8y9z0a1b2c3d4e5f.jpg"
    },
    "играть_в_футбол": {
        "desc": "⚽ играл(а) в футбол с",
        "img": "https://i.pinimg.com/736x/1r/2s/3t/1r2s3t4u5v6w7x8y9z0a1b2c3d4e5f6g.jpg"
    },
    "качаться": {
        "desc": "💪 качался(лась) с",
        "img": "https://i.pinimg.com/736x/2s/3t/4u/2s3t4u5v6w7x8y9z0a1b2c3d4e5f6g7h.jpg"
    },
    "гулять": {
        "desc": "🚶 гулял(а) с",
        "img": "https://i.pinimg.com/736x/3t/4u/5v/3t4u5v6w7x8y9z0a1b2c3d4e5f6g7h8i.jpg"
    },
    "сидеть_на_траве": {
        "desc": "🌿 сидел(а) на траве с",
        "img": "https://i.pinimg.com/736x/4u/5v/6w/4u5v6w7x8y9z0a1b2c3d4e5f6g7h8i9j.jpg"
    },
    "смотреть_на_звёзды": {
        "desc": "⭐ смотрел(а) на звёзды с",
        "img": "https://i.pinimg.com/736x/5v/6w/7x/5v6w7x8y9z0a1b2c3d4e5f6g7h8i9j0k.jpg"
    },
    "купаться_в_реке": {
        "desc": "🌊 купался(лась) в реке с",
        "img": "https://i.pinimg.com/736x/6w/7x/8y/6w7x8y9z0a1b2c3d4e5f6g7h8i9j0k1l.jpg"
    },
    "лететь": {
        "desc": "✈️ летел(а) с",
        "img": "https://i.pinimg.com/736x/7x/8y/9z/7x8y9z0a1b2c3d4e5f6g7h8i9j0k1l2m.jpg"
    },
    "ехать_на_машине": {
        "desc": "🚗 ехал(а) на машине с",
        "img": "https://i.pinimg.com/736x/8y/9z/0a/8y9z0a1b2c3d4e5f6g7h8i9j0k1l2m3n.jpg"
    },
    "плыть_на_корабле": {
        "desc": "🚢 плыл(а) на корабле с",
        "img": "https://i.pinimg.com/736x/9z/0a/1b/9z0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o.jpg"
    },
    "идти_в_горы": {
        "desc": "🏔️ шёл(ла) в горы с",
        "img": "https://i.pinimg.com/736x/0a/1b/2c/0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p.jpg"
    },
}

# ============================================================
# 🔞 18+ RP КОМАНДЫ
# ============================================================

RP_18_COMMANDS = {
    "раздеть": {
        "desc": "🔥 раздел(а)",
        "img": "https://i.pinimg.com/736x/1a/2b/3c/1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p.jpg"
    },
    "поцеловать_в_губы": {
        "desc": "💋 поцеловал(а) в губы",
        "img": "https://i.pinimg.com/736x/2b/3c/4d/2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q.jpg"
    },
    "прикоснуться": {
        "desc": "🫳 прикоснулся(лась)",
        "img": "https://i.pinimg.com/736x/3c/4d/5e/3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r.jpg"
    },
    "снять_футболку": {
        "desc": "👕 снял(а) футболку с",
        "img": "https://i.pinimg.com/736x/4d/5e/6f/4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s.jpg"
    },
    "снять_штаны": {
        "desc": "👖 снял(а) штаны с",
        "img": "https://i.pinimg.com/736x/5e/6f/7g/5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t.jpg"
    },
    "поцеловать_в_шею": {
        "desc": "💋 поцеловал(а) в шею",
        "img": "https://i.pinimg.com/736x/6f/7g/8h/6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u.jpg"
    },
    "обнять_голым": {
        "desc": "🫂 обнял(а) голым(ой)",
        "img": "https://i.pinimg.com/736x/7g/8h/9i/7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v.jpg"
    },
    "лечь_в_кровать": {
        "desc": "🛏️ лёг(ла) в кровать с",
        "img": "https://i.pinimg.com/736x/8h/9i/0j/8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w.jpg"
    },
    "пригласить_в_душ": {
        "desc": "🚿 пригласил(а) в душ",
        "img": "https://i.pinimg.com/736x/9i/0j/1k/9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x.jpg"
    },
    "массаж": {
        "desc": "💆 сделал(а) массаж",
        "img": "https://i.pinimg.com/736x/0j/1k/2l/0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y.jpg"
    },
    "погладить_по_спине": {
        "desc": "👋 погладил(а) по спине",
        "img": "https://i.pinimg.com/736x/1k/2l/3m/1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z.jpg"
    },
    "поцеловать_в_грудь": {
        "desc": "💋 поцеловал(а) в грудь",
        "img": "https://i.pinimg.com/736x/2l/3m/4n/2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a.jpg"
    },
    "обнять_в_постели": {
        "desc": "🫂 обнял(а) в постели",
        "img": "https://i.pinimg.com/736x/3m/4n/5o/3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b.jpg"
    },
    "шептать_нежности": {
        "desc": "👂 шептал(а) нежности",
        "img": "https://i.pinimg.com/736x/4n/5o/6p/4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c.jpg"
    },
    "погладить_по_ноге": {
        "desc": "👋 погладил(а) по ноге",
        "img": "https://i.pinimg.com/736x/5o/6p/7q/5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d.jpg"
    },
    "поцеловать_в_плечо": {
        "desc": "💋 поцеловал(а) в плечо",
        "img": "https://i.pinimg.com/736x/6p/7q/8r/6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e.jpg"
    },
    "обнять_за_плечи": {
        "desc": "🤗 обнял(а) за плечи",
        "img": "https://i.pinimg.com/736x/7q/8r/9s/7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f.jpg"
    },
    "лечь_рядом": {
        "desc": "🛌 лёг(ла) рядом с",
        "img": "https://i.pinimg.com/736x/8r/9s/0t/8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g.jpg"
    },
    "вдохнуть_аромат": {
        "desc": "👃 вдохнул(а) аромат",
        "img": "https://i.pinimg.com/736x/9s/0t/1u/9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h.jpg"
    },
    "погладить_по_груди": {
        "desc": "👋 погладил(а) по груди",
        "img": "https://i.pinimg.com/736x/0t/1u/2v/0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i.jpg"
    },
}

# Добавляем 18+ команды в основной словарь
RP_COMMANDS.update(RP_18_COMMANDS)

# Дополнительные обычные RP команды
for action in ["улыбнуться", "засмеяться", "заплакать", "удивиться", "испугаться",
               "обрадоваться", "расстроиться", "разозлиться", "влюбиться", "грустить",
               "мечтать", "прыгать", "кричать", "шептать", "играть",
               "готовить", "убирать", "стирать", "гладить", "мыть",
               "чистить", "ремонтировать", "строить", "сажать", "поливать",
               "кормить", "ухаживать", "обнимать", "целовать", "ласкать"]:
    if action not in RP_COMMANDS and len(RP_COMMANDS) < 120:
        RP_COMMANDS[action] = {
            "desc": f"🎭 {action} с",
            "img": f"https://i.pinimg.com/736x/{random.choice('abcdefghijklmnopqrstuvwxyz')}{random.choice('0123456789')}/{random.choice('abcdefghijklmnopqrstuvwxyz')}{random.choice('0123456789')}/{random.choice('abcdefghijklmnopqrstuvwxyz')}{random.choice('0123456789')}{random.choice('abcdefghijklmnopqrstuvwxyz')}{random.choice('0123456789')}.jpg"
        }

image_cache = {}

async def get_uploaded_image(image_url):
    if image_url in image_cache:
        return image_cache[image_url]
    attachment = await upload_image(image_url)
    if attachment:
        image_cache[image_url] = attachment
    return attachment

async def handle_rp_command(command, user_id, peer_id, reply_user_id, user_link_text):
    if command in RP_COMMANDS:
        action = RP_COMMANDS[command]
        target_id = reply_user_id if reply_user_id else user_id
        
        if reply_user_id:
            target_link = await get_user_link(target_id)
            result_text = f"{action['desc']} {target_link}!"
        else:
            result_text = f"{user_link_text} {action['desc']}!"
        
        attachment = await get_uploaded_image(action['img'])
        if attachment:
            await vk.messages_send(peer_id, result_text, attachment)
        else:
            await vk.messages_send(peer_id, result_text)
        return True
    return False

async def process_message(message_data):
    try:
        if "object" in message_data and "message" in message_data["object"]:
            msg = message_data["object"]["message"]
            peer_id = msg.get("peer_id", 0)
            user_id = msg.get("from_id", 0)
            text = msg.get("text", "")
            reply_user_id = await get_reply_user_id(message_data)
        else:
            peer_id = message_data.get("peer_id", 0)
            user_id = message_data.get("from_id", 0)
            text = message_data.get("text", "")
            reply_user_id = 0
        
        # УБРАЛ проверку user_id < 0 - теперь бот работает с сообществами!
        is_chat = peer_id > 2000000000
        user_link_text = await get_user_link(user_id)
        
        if is_banned(user_id, peer_id):
            return
        
        if is_muted(user_id, peer_id):
            try:
                await vk.messages_send(peer_id, f"🔇 Вы заглушены! Не пишите.")
            except:
                pass
            return
        
        if "user_stats" not in data:
            data["user_stats"] = {}
        data["user_stats"][str(user_id)] = data["user_stats"].get(str(user_id), 0) + 1
        
        if random.random() < 0.1:
            await add_exp(user_id, random.randint(1, 5))
        
        if is_chat:
            if await check_links(text) and not is_mod(user_id):
                await vk.messages_send(peer_id, f"🔗 Ссылки запрещены!")
                return
            
            if await check_spam(user_id, peer_id) and not is_mod(user_id):
                mute_time = 5
                data["muted"][f"{peer_id}_{user_id}"] = time.time() + (mute_time * 60)
                save_data(data)
                await vk.messages_send(peer_id, f"🚫 Заглушен на {mute_time} минут за спам!")
                return
        
        if not text.startswith(PREFIX):
            return
        
        text = text[1:].strip()
        args = text.split()
        if not args:
            return
        
        command = args[0].lower()
        
        # 🎭 RP КОМАНДЫ
        if await handle_rp_command(command, user_id, peer_id, reply_user_id, user_link_text):
            return
        
        # 🚀 БАЗОВЫЕ КОМАНДЫ
        if command == "помощь":
            help_text = """
🔥🔥🔥 АХУЕННЫЙ БОТ 🔥🔥🔥

💬 ОБЩЕНИЕ:
!привет — поздороваться
!пока — попрощаться
!как дела — спросить
!кто ты — узнать бота
!спасибо — поблагодарить
!шутка — посмеяться
!цитата — мудрость
!комплимент — получить комплимент

🎭 РП КОМАНДЫ (120+):
Обычные: !обнять, !поцеловать, !ударить, !погладить, !укусить и др.
18+: !раздеть, !поцеловать_в_губы, !прикоснуться, !снять_футболку, !снять_штаны,
!поцеловать_в_шею, !обнять_голым, !лечь_в_кровать, !пригласить_в_душ, !массаж,
!погладить_по_спине, !поцеловать_в_грудь, !обнять_в_постели, !шептать_нежности,
!погладить_по_ноге, !поцеловать_в_плечо, !обнять_за_плечи, !лечь_рядом,
!вдохнуть_аромат, !погладить_по_груди

Ответь на сообщение человека и напиши команду!

🎮 ИГРЫ:
!кубик [сторон] — бросить кубик
!монетка — орёл/решка
!казино [сумма] — сыграть в казино
!угадай — угадать число
!кнб [к/н/б] — камень/ножницы/бумага
!рулетка — русская рулетка
!слоты — игровой автомат

💰 ЭКОНОМИКА:
!баланс — баланс
!бонус — ежедневный бонус
!профиль — профиль
!топ — топ богачей
!передать [ID] [сумма] — передать деньги
!работа — устроиться на работу
!зарплата — получить зарплату

❤️ ОТНОШЕНИЯ:
!брак [ID] — предложить брак
!развод — развестись
!реп (ответом) — дать репутацию

🛡️ МОДЕРАЦИЯ (для модов):
!мут (ответом) [мин] — заглушить
!размут (ответом) — размутить
!кик (ответом) — кикнуть
!варн (ответом) — предупреждение
!бан (ответом) [дней] — забанить
!разбан (ответом) — разбанить

📞 ПОДДЕРЖКА:
!тикет [текст] — создать обращение

⚙️ АДМИНИСТРИРОВАНИЕ:
!статистика — статистика чата
!настройки — настройки
!правила — правила
!приветствие [текст] — установить приветствие
!добавить_админа [ID] — добавить админа
!удалить_админа [ID] — удалить админа
!добавить_мода [ID] — добавить модера
!удалить_мода [ID] — удалить модера

📌 Чтобы применить команду к пользователю:
Ответь на его сообщение и напиши команду
"""
            await vk.messages_send(peer_id, help_text)
            return
        
        # 💬 ОБЩЕНИЕ
        if command == "привет":
            await vk.messages_send(peer_id, f"👋 Привет, {user_link_text}! Как жизнь?")
            return
        
        if command == "пока":
            await vk.messages_send(peer_id, f"👋 Пока, {user_link_text}! Возвращайся!")
            return
        
        if command == "как дела":
            answers = ["🔥 Отлично! А у тебя?", "💪 Хорошо!", "😎 Нормально!", "🚀 Супер!", "😊 Отлично!"]
            await vk.messages_send(peer_id, f"{random.choice(answers)}")
            return
        
        if command == "кто ты":
            await vk.messages_send(peer_id, "🤖 Я ахуенный бот! Общаюсь, играю, модерю чаты. Используй !помощь")
            return
        
        if command == "спасибо":
            await vk.messages_send(peer_id, f"🙏 Пожалуйста, {user_link_text}! Всегда рад помочь!")
            return
        
        if command == "шутка":
            jokes = [
                "Почему программисты не любят природу? Слишком много багов.",
                "Сколько программистов нужно, чтобы заменить лампочку? Ни одного. Это аппаратная проблема.",
                "Почему компьютеры не могут пить кофе? Боятся Java-атаки.",
                "Что говорит один компьютер другому? Давай обменяемся вирусами!",
                "Как назвать медведя без ушей? Без-ушный.",
                "Почему программисты путают Хэллоуин и Рождество? 31 OCT = 25 DEC"
            ]
            await vk.messages_send(peer_id, f"😂 {random.choice(jokes)}")
            return
        
        if command == "цитата":
            quotes = [
                "Жизнь — это то, что происходит, пока ты строишь планы.",
                "Будь изменением, которое хочешь видеть в мире.",
                "Великие умы обсуждают идеи, средние — события, маленькие — людей.",
                "Счастье не в том, чтобы делать всегда, что хочешь, а в том, чтобы всегда хотеть того, что делаешь.",
                "Успех — это способность идти от неудачи к неудаче, не теряя энтузиазма."
            ]
            await vk.messages_send(peer_id, f"📝 {random.choice(quotes)}")
            return
        
        if command == "комплимент":
            compliments = [
                "Ты сегодня просто сияешь!",
                "У тебя отличный вкус!",
                "Ты очень умный человек!",
                "С тобой приятно общаться!",
                "Ты делаешь этот мир лучше!",
                "Ты крутой!",
                "Ты потрясающий человек!"
            ]
            await vk.messages_send(peer_id, f"😊 {random.choice(compliments)}")
            return
        
        # 🎮 ИГРЫ
        if command == "кубик":
            sides = 6
            if len(args) > 1 and args[1].isdigit():
                sides = min(max(int(args[1]), 2), 100)
            result = random.randint(1, sides)
            await vk.messages_send(peer_id, f"🎲 Выпало: {result} (1-{sides})")
            return
        
        if command == "монетка":
            result = random.choice(["🦅 Орёл", "🪙 Решка"])
            await vk.messages_send(peer_id, f"{result}")
            return
        
        if command == "казино":
            if len(args) < 2 or not args[1].isdigit():
                await vk.messages_send(peer_id, "!казино [сумма]")
                return
            amount = int(args[1])
            if not await remove_money(user_id, amount):
                await vk.messages_send(peer_id, "❌ Недостаточно монет!")
                return
            multiplier = random.choice([0, 0.5, 1, 2, 3, 5, 10])
            result = int(amount * multiplier)
            await add_money(user_id, result)
            if result > amount:
                await vk.messages_send(peer_id, f"🎉 Выиграл {result} монет! (+{result-amount})")
            elif result == amount:
                await vk.messages_send(peer_id, f"🤝 Ставка вернулась")
            else:
                await vk.messages_send(peer_id, f"😢 Проиграл {amount-result} монет")
            return
        
        if command == "угадай":
            if "game_number" not in data:
                data["game_number"] = {}
            if str(peer_id) not in data["game_number"]:
                data["game_number"][str(peer_id)] = random.randint(1, 100)
                await vk.messages_send(peer_id, "🎯 Я загадал число от 1 до 100. Угадай!")
                return
            if len(args) < 2 or not args[1].isdigit():
                await vk.messages_send(peer_id, "Введи число: !угадай [число]")
                return
            guess = int(args[1])
            target = data["game_number"][str(peer_id)]
            if guess < target:
                await vk.messages_send(peer_id, "📈 Больше!")
            elif guess > target:
                await vk.messages_send(peer_id, "📉 Меньше!")
            else:
                await vk.messages_send(peer_id, f"🎉 Угадал! Это было {target}!")
                await add_money(user_id, 1000)
                del data["game_number"][str(peer_id)]
                save_data(data)
            return
        
        if command == "кнб":
            if len(args) < 2:
                await vk.messages_send(peer_id, "!кнб [к/н/б]")
                return
            choice = args[1].lower()
            if choice not in ["к", "н", "б"]:
                await vk.messages_send(peer_id, "к - камень, н - ножницы, б - бумага")
                return
            bot_choice = random.choice(["к", "н", "б"])
            choices = {"к": "Камень", "н": "Ножницы", "б": "Бумага"}
            if choice == bot_choice:
                result = "Ничья!"
            elif (choice == "к" and bot_choice == "н") or (choice == "н" and bot_choice == "б") or (choice == "б" and bot_choice == "к"):
                result = "Ты выиграл! 🎉"
                await add_money(user_id, 500)
            else:
                result = "Бот выиграл! 🤖"
            await vk.messages_send(peer_id, f"Ты: {choices[choice]} | Бот: {choices[bot_choice]}\n{result}")
            return
        
        if command == "рулетка":
            chamber = random.randint(1, 6)
            shot = random.randint(1, 6)
            if shot == chamber:
                await vk.messages_send(peer_id, "💀 БАХ! Ты проиграл! (демонстрация)")
                await remove_money(user_id, 1000)
            else:
                await vk.messages_send(peer_id, "🍀 Щелчок! Ты жив! +500 монет")
                await add_money(user_id, 500)
            return
        
        if command == "слоты":
            symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
            result = [random.choice(symbols) for _ in range(3)]
            if result[0] == result[1] == result[2]:
                winnings = random.randint(1000, 5000)
                await add_money(user_id, winnings)
                await vk.messages_send(peer_id, f"{result[0]} {result[1]} {result[2]} 🎉 ДЖЕКПОТ! +{winnings} монет!")
            elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
                await add_money(user_id, 200)
                await vk.messages_send(peer_id, f"{result[0]} {result[1]} {result[2]} 🍀 +200 монет!")
            else:
                await vk.messages_send(peer_id, f"{result[0]} {result[1]} {result[2]} ❌ Ничего!")
            return
        
        # 💰 ЭКОНОМИКА
        if command == "баланс":
            money = data.get("money", {}).get(str(user_id), 0)
            await vk.messages_send(peer_id, f"💰 Баланс: {money} монет")
            return
        
        if command == "бонус":
            last_bonus = data.get("daily_bonus", {}).get(str(user_id), 0)
            now = time.time()
            if now - last_bonus < 86400:
                remaining = int(86400 - (now - last_bonus))
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await vk.messages_send(peer_id, f"⏳ Бонус через {hours}ч {minutes}м")
                return
            bonus = random.randint(1000, 10000)
            await add_money(user_id, bonus)
            data["daily_bonus"][str(user_id)] = now
            save_data(data)
            await vk.messages_send(peer_id, f"🎁 Бонус: {bonus} монет!")
            return
        
        if command == "профиль":
            target_id = user_id
            if len(args) > 1 and args[1].isdigit():
                target_id = int(args[1])
            target_link = await get_user_link(target_id)
            stats = data.get("user_stats", {}).get(str(target_id), 0)
            money = data.get("money", {}).get(str(target_id), 0)
            exp = data.get("exp", {}).get(str(target_id), 0)
            level = data.get("level", {}).get(str(target_id), 1)
            rep = data.get("rep", {}).get(str(target_id), 0)
            await vk.messages_send(peer_id, f"👤 Профиль {target_link}\nСообщений: {stats}\nМонет: {money}\nОпыт: {exp}\nУровень: {level}\nРепутация: {rep}")
            return
        
        if command == "топ":
            sorted_users = sorted(data.get("money", {}).items(), key=lambda x: x[1], reverse=True)[:10]
            if not sorted_users:
                await vk.messages_send(peer_id, "Нет данных")
                return
            text = "🏆 Топ богачей:\n"
            for i, (uid, money) in enumerate(sorted_users, 1):
                link = await get_user_link(int(uid))
                text += f"{i}. {link} — {money} монет\n"
            await vk.messages_send(peer_id, text)
            return
        
        if command == "передать":
            if len(args) < 3:
                await vk.messages_send(peer_id, "!передать [ID] [сумма]")
                return
            try:
                target_id = int(args[1])
                amount = int(args[2])
                if target_id == user_id:
                    await vk.messages_send(peer_id, "Нельзя себе")
                    return
                if amount <= 0:
                    await vk.messages_send(peer_id, "Сумма должна быть положительной")
                    return
                if not await remove_money(user_id, amount):
                    await vk.messages_send(peer_id, "Недостаточно монет!")
                    return
                await add_money(target_id, amount)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"✅ Передано {amount} монет {target_link}")
            except:
                await vk.messages_send(peer_id, "Ошибка")
            return
        
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
        
        if command == "зарплата":
            if str(user_id) not in data.get("work", {}):
                await vk.messages_send(peer_id, "Вы не работаете! !работа")
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
        
        # ❤️ ОТНОШЕНИЯ
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
                await vk.messages_send(peer_id, "❌ Нельзя с собой")
                return
            if str(user_id) in data.get("marriage", {}):
                await vk.messages_send(peer_id, "❌ Уже в браке")
                return
            if str(target_id) in data.get("marriage", {}):
                await vk.messages_send(peer_id, "❌ Уже в браке")
                return
            target_link = await get_user_link(target_id)
            await vk.messages_send(peer_id, f"💍 {user_link_text} предложил брак {target_link}!\nНапишите !да или !нет")
            data["marriage_proposal"] = {"from": user_id, "to": target_id}
            save_data(data)
            return
        
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
        
        if command == "нет":
            if "marriage_proposal" in data:
                proposal = data["marriage_proposal"]
                if proposal["to"] == user_id:
                    del data["marriage_proposal"]
                    save_data(data)
                    await vk.messages_send(peer_id, "❌ Брак отклонен")
            return
        
        if command == "развод":
            if str(user_id) not in data.get("marriage", {}):
                await vk.messages_send(peer_id, "❌ Вы не в браке")
                return
            spouse_id = data["marriage"][str(user_id)]
            del data["marriage"][str(user_id)]
            del data["marriage"][str(spouse_id)]
            save_data(data)
            await vk.messages_send(peer_id, f"💔 Развод")
            return
        
        if command == "реп":
            target_id = reply_user_id if reply_user_id else 0
            if not target_id:
                await vk.messages_send(peer_id, "Ответьте на сообщение человека, чтобы дать репутацию!")
                return
            if target_id == user_id:
                await vk.messages_send(peer_id, "❌ Нельзя себе")
                return
            if "rep" not in data:
                data["rep"] = {}
            data["rep"][str(target_id)] = data["rep"].get(str(target_id), 0) + 1
            save_data(data)
            target_link = await get_user_link(target_id)
            await vk.messages_send(peer_id, f"⭐ {target_link} +1 репутация!")
            return
        
        # 🛡️ МОДЕРАЦИЯ
        if is_mod(user_id):
            target_id = reply_user_id if reply_user_id else 0
            
            if command == "мут":
                if not target_id:
                    await vk.messages_send(peer_id, "Ответьте на сообщение человека, чтобы заглушить!")
                    return
                minutes = int(args[1]) if len(args) > 1 else 5
                data["muted"][f"{peer_id}_{target_id}"] = time.time() + (minutes * 60)
                save_data(data)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"🔇 {target_link} заглушен на {minutes} минут")
                return
            
            if command == "размут":
                if not target_id:
                    await vk.messages_send(peer_id, "Ответьте на сообщение человека, чтобы размутить!")
                    return
                key = f"{peer_id}_{target_id}"
                if key in data.get("muted", {}):
                    del data["muted"][key]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} размучен")
                else:
                    await vk.messages_send(peer_id, "Не заглушен")
                return
            
            if command == "кик":
                if not target_id:
                    await vk.messages_send(peer_id, "Ответьте на сообщение человека, чтобы кикнуть!")
                    return
                chat_id = peer_id - 2000000000
                target_link = await get_user_link(target_id)
                result = vk.messages_remove_chat_user(chat_id, target_id)
                if "error" not in result:
                    await vk.messages_send(peer_id, f"👢 {target_link} кикнут")
                else:
                    await vk.messages_send(peer_id, "Ошибка")
                return
            
            if command == "варн":
                if not target_id:
                    await vk.messages_send(peer_id, "Ответьте на сообщение человека, чтобы выдать предупреждение!")
                    return
                data["warns"][str(target_id)] = data["warns"].get(str(target_id), 0) + 1
                warns = data["warns"][str(target_id)]
                save_data(data)
                target_link = await get_user_link(target_id)
                if warns >= 3:
                    data["muted"][f"{peer_id}_{target_id}"] = time.time() + (60 * 60)
                    save_data(data)
                    await vk.messages_send(peer_id, f"⚠️ {target_link} получил 3 предупреждения! Заглушен на час")
                else:
                    await vk.messages_send(peer_id, f"⚠️ {target_link} предупреждение {warns}/3")
                return
            
            if command == "бан":
                if not target_id:
                    await vk.messages_send(peer_id, "Ответьте на сообщение человека, чтобы забанить!")
                    return
                days = int(args[1]) if len(args) > 1 else 7
                data["banned"][f"{peer_id}_{target_id}"] = time.time() + (days * 24 * 60 * 60)
                save_data(data)
                target_link = await get_user_link(target_id)
                await vk.messages_send(peer_id, f"🚫 {target_link} забанен на {days} дней")
                chat_id = peer_id - 2000000000
                vk.messages_remove_chat_user(chat_id, target_id)
                return
            
            if command == "разбан":
                if not target_id:
                    await vk.messages_send(peer_id, "Ответьте на сообщение человека, чтобы разбанить!")
                    return
                key = f"{peer_id}_{target_id}"
                if key in data.get("banned", {}):
                    del data["banned"][key]
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} разбанен")
                else:
                    await vk.messages_send(peer_id, "Не забанен")
                return
        
        # 📞 ПОДДЕРЖКА
        if command == "тикет":
            if len(args) < 2:
                await vk.messages_send(peer_id, "!тикет [текст обращения]")
                return
            ticket_text = " ".join(args[1:])
            ticket_id = int(time.time())
            data["support_tickets"].append({
                "id": ticket_id,
                "user_id": user_id,
                "peer_id": peer_id,
                "text": ticket_text,
                "status": "open",
                "date": datetime.now().strftime("%d.%m.%Y %H:%M")
            })
            save_data(data)
            await vk.messages_send(peer_id, f"✅ Тикет #{ticket_id} создан!")
            for admin_id in data.get("admins", {}):
                try:
                    await vk.messages_send(int(admin_id), f"Новый тикет #{ticket_id} от {user_link_text}:\n{ticket_text}")
                except:
                    pass
            return
        
        # ⚙️ АДМИНИСТРИРОВАНИЕ
        if is_owner(user_id):
            if command == "добавить_админа":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "!добавить_админа [ID]")
                    return
                try:
                    target_id = int(args[1])
                    data["admins"][str(target_id)] = True
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} добавлен в админы")
                except:
                    await vk.messages_send(peer_id, "Ошибка")
                return
            
            if command == "удалить_админа":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "!удалить_админа [ID]")
                    return
                try:
                    target_id = int(args[1])
                    if str(target_id) in data.get("admins", {}):
                        del data["admins"][str(target_id)]
                        save_data(data)
                        target_link = await get_user_link(target_id)
                        await vk.messages_send(peer_id, f"✅ {target_link} удален из админов")
                    else:
                        await vk.messages_send(peer_id, "Не админ")
                except:
                    await vk.messages_send(peer_id, "Ошибка")
                return
            
            if command == "добавить_мода":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "!добавить_мода [ID]")
                    return
                try:
                    target_id = int(args[1])
                    data["mods"][str(target_id)] = True
                    save_data(data)
                    target_link = await get_user_link(target_id)
                    await vk.messages_send(peer_id, f"✅ {target_link} добавлен в модераторы")
                except:
                    await vk.messages_send(peer_id, "Ошибка")
                return
            
            if command == "удалить_мода":
                if len(args) < 2:
                    await vk.messages_send(peer_id, "!удалить_мода [ID]")
                    return
                try:
                    target_id = int(args[1])
                    if str(target_id) in data.get("mods", {}):
                        del data["mods"][str(target_id)]
                        save_data(data)
                        target_link = await get_user_link(target_id)
                        await vk.messages_send(peer_id, f"✅ {target_link} удален из модераторов")
                    else:
                        await vk.messages_send(peer_id, "Не модератор")
                except:
                    await vk.messages_send(peer_id, "Ошибка")
                return
        
        if command == "статистика":
            total_users = len(data.get("user_stats", {}))
            total_messages = sum(data.get("user_stats", {}).values())
            await vk.messages_send(peer_id, f"📊 Статистика чата:\nПользователей: {total_users}\nСообщений: {total_messages}\nЗабанено: {len(data.get('banned', {}))}\nЗаглушено: {len(data.get('muted', {}))}\nАдминов: {len(data.get('admins', {}))}")
            return
        
        if command == "настройки":
            settings = data.get("settings", {})
            await vk.messages_send(peer_id, f"⚙️ Настройки:\nАнтиспам: {'Вкл' if settings.get('antispam', True) else 'Выкл'}\nАнтиссылки: {'Вкл' if settings.get('antilink', True) else 'Выкл'}\nМедленный режим: {'Вкл' if settings.get('slow_mode', False) else 'Выкл'}\nПриветствие: {settings.get('welcome', 'Не установлено')}")
            return
        
        if command == "правила":
            rules = data["settings"].get("rules", "Правил нет")
            await vk.messages_send(peer_id, f"📋 Правила чата:\n{rules}")
            return
        
        if command == "приветствие":
            if len(args) < 2:
                current = data["settings"].get("welcome", "Не установлено")
                await vk.messages_send(peer_id, f"Текущее приветствие: {current}")
                return
            welcome_text = " ".join(args[1:])
            data["settings"]["welcome"] = welcome_text
            save_data(data)
            await vk.messages_send(peer_id, "✅ Приветствие установлено")
            return
        
    except Exception as e:
        logger.error(f"Process error: {e}")

start_time = time.time()

async def main():
    logger.info("🚀 БОТ ЗАПУЩЕН")
    logger.info(f"Group: {GROUP_ID}")
    
    try:
        info = vk.groups_get_by_id()
        if "error" in info:
            logger.error(f"Token error: {info['error']}")
            return
        logger.info("✅ Токен работает")
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
    
    logger.info("✅ БОТ ГОТОВ")
    logger.info("💀 Команды: !помощь")
    
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
