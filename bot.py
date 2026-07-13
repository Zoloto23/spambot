import asyncio
import os
import logging
import json
import time
import random
import requests
import re

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
DATA_FILE = "rp_bot_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "owner": 1118563484,
            "admins": {},
            "mods": {},
            "nicks": {},
            "settings": {
                "antispam": True,
                "spam_limit": 3,
                "spam_time": 5,
                "antilink": True,
                "whitelist": ["vk.com", "youtube.com", "t.me"]
            },
            "message_history": {},
            "user_stats": {},
            "rp_images": {}  # команда: [список attachments]
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

def get_nick(user_id):
    return data.get("nicks", {}).get(str(user_id), None)

class VKAPI:
    def __init__(self, token, group_id):
        self.token = token
        self.group_id = group_id
        self.base_url = "https://api.vk.com/method/"
        self.version = API_VERSION
    
    def _request(self, method, params):
        params["access_token"] = self.token
        params["v"] = self.version
        try:
            response = requests.post(self.base_url + method, data=params, timeout=15)
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                logger.error(f"VK API error: {result['error']['error_msg']}")
                return {"error": result["error"]}
            return result.get("response", {})
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": {"error_msg": str(e)}}
    
    def messages_send(self, peer_id, message=None, attachment=None, sticker_id=None):
        params = {
            "peer_id": peer_id,
            "random_id": int(time.time() * 1000) + random.randint(1, 99999),
            "disable_mentions": 1
        }
        if message:
            params["message"] = message
        if attachment:
            params["attachment"] = attachment
        if sticker_id:
            params["sticker_id"] = sticker_id
        return self._request("messages.send", params)
    
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
    
    def messages_get_by_id(self, message_ids):
        return self._request("messages.getById", {"message_ids": message_ids})

vk = VKAPI(TOKEN, GROUP_ID)

# ============================================================
# 📤 ЗАГРУЗКА ФОТО НА СЕРВЕР VK
# ============================================================

async def download_and_upload_photo(photo_url):
    """Скачивает фото по URL и загружает на сервер VK"""
    try:
        response = requests.get(photo_url, timeout=10)
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

async def get_photos_from_message(msg):
    """Извлекает все фото из сообщения"""
    photos = []
    attachments = msg.get("attachments", [])
    
    for att in attachments:
        if att.get("type") == "photo":
            photo = att.get("photo", {})
            sizes = photo.get("sizes", [])
            if sizes:
                largest = max(sizes, key=lambda x: x.get("width", 0) * x.get("height", 0))
                photo_url = largest.get("url")
                if photo_url:
                    photos.append(photo_url)
    return photos

async def upload_multiple_photos(photo_urls):
    """Загружает несколько фото и возвращает список attachments"""
    attachments = []
    for url in photo_urls[:30]:  # максимум 30 фото
        attachment = await download_and_upload_photo(url)
        if attachment:
            attachments.append(attachment)
        await asyncio.sleep(0.2)  # небольшая задержка чтобы не перегружать API
    return attachments

# ============================================================
# 🎭 ОСНОВНЫЕ ДЕЙСТВИЯ
# ============================================================

RP_ACTIONS = {
    "обнять": "обнял(а)",
    "чмок": "чмокнул(а)",
    "поцеловать": "поцеловал(а)",
    "ударить": "ударил(а)",
    "погладить": "погладил(а)",
    "укусить": "укусил(а)",
    "толкнуть": "толкнул(а)",
    "обнять за шею": "обнял(а) за шею",
    "поцеловать в губы": "поцеловал(а) в губы",
    "поцеловать в щеку": "поцеловал(а) в щеку",
    "поцеловать в лоб": "поцеловал(а) в лоб",
    "взять за руку": "взял(а) за руку",
    "обнять за талию": "обнял(а) за талию",
    "прижать к себе": "прижал(а) к себе",
    "погладить по голове": "погладил(а) по голове",
    "задушить в объятиях": "задушил(а) в объятиях",
    "потискать": "потискал(а)",
    "облизать": "облизал(а)",
    "пощечина": "дал(а) пощёчину",
    "ущипнуть": "ущипнул(а)",
    "кинуть камень": "кинул(а) камень в",
    "полить водой": "полил(а) водой",
    "кинуть торт": "кинул(а) торт в",
    "облить соком": "облил(а) соком",
    "забросать подушками": "забросал(а) подушками",
    "дать пять": "дал(а) пять",
    "кулак": "стукнул(а) кулаком",
    "пожать руку": "пожал(а) руку",
    "поклон": "поклонился(лась)",
    "салют": "отдал(а) честь",
    "обнять сзади": "обнял(а) сзади",
    "поцеловать руку": "поцеловал(а) руку",
    "шепнуть на ухо": "шепнул(а) на ухо",
    "танцевать": "танцевал(а) с",
    "петь": "пел(а) для",
    "играть на гитаре": "играл(а) на гитаре для",
    "рисовать": "нарисовал(а) портрет",
    "читать стихи": "читал(а) стихи",
    "пнуть": "пнул(а)",
    "ударить головой": "ударил(а) головой",
    "кинуть в стену": "кинул(а) в стену",
    "схватить за горло": "схватил(а) за горло",
    "дать подзатыльник": "дал(а) подзатыльник",
    "накормить": "накормил(а)",
    "напоить": "напоил(а)",
    "угостить конфетой": "угостил(а) конфетой",
    "приготовить завтрак": "приготовил(а) завтрак",
    "бегать": "бегал(а) с",
    "плавать": "плавал(а) с",
    "играть в футбол": "играл(а) в футбол с",
    "качаться": "качался(лась) с",
    "гулять": "гулял(а) с",
    "сидеть на траве": "сидел(а) на траве с",
    "смотреть на звёзды": "смотрел(а) на звёзды с",
    "купаться в реке": "купался(лась) в реке с",
    "лететь": "летел(а) с",
    "ехать на машине": "ехал(а) на машине с",
    "плыть на корабле": "плыл(а) на корабле с",
    "идти в горы": "шёл(ла) в горы с",
    "раздеть": "раздел(а)",
    "прикоснуться": "прикоснулся(лась)",
    "снять футболку": "снял(а) футболку с",
    "снять штаны": "снял(а) штаны с",
    "поцеловать в шею": "поцеловал(а) в шею",
    "обнять голым": "обнял(а) голым(ой)",
    "лечь в кровать": "лёг(ла) в кровать с",
    "пригласить в душ": "пригласил(а) в душ",
    "массаж": "сделал(а) массаж",
    "погладить по спине": "погладил(а) по спине",
    "поцеловать в грудь": "поцеловал(а) в грудь",
    "обнять в постели": "обнял(а) в постели",
    "шептать нежности": "шептал(а) нежности",
    "погладить по ноге": "погладил(а) по ноге",
    "поцеловать в плечо": "поцеловал(а) в плечо",
    "обнять за плечи": "обнял(а) за плечи",
    "лечь рядом": "лёг(ла) рядом с",
    "вдохнуть аромат": "вдохнул(а) аромат",
    "погладить по груди": "погладил(а) по груди",
    "шлёпнуть": "шлёпнул(а)",
    "почесать": "почесал(а)",
    "пощекотать": "пощекотал(а)",
    "схватить": "схватил(а)",
    "оттолкнуть": "оттолкнул(а)",
    "прикусить": "прикусил(а)",
    "лобзать": "лобзал(а)",
    "целовать": "целовал(а)",
    "обнимать": "обнимал(а)",
    "ласкать": "ласкал(а)"
}

STICKER_IDS = {
    "сама": 100,
    "бот": 101,
}

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

async def process_message(message_data):
    try:
        if not isinstance(message_data, dict):
            return
        
        if "object" in message_data and "message" in message_data["object"]:
            msg = message_data["object"]["message"]
            peer_id = msg.get("peer_id", 0)
            user_id = msg.get("from_id", 0)
            text = msg.get("text", "")
            reply_user_id = await get_reply_user_id(message_data)
        else:
            return
        
        if user_id < 0:
            return
        
        if is_banned(user_id, peer_id):
            return
        
        if is_muted(user_id, peer_id):
            try:
                await vk.messages_send(peer_id, "🔇 Вы заглушены!")
            except:
                pass
            return
        
        if "user_stats" not in data:
            data["user_stats"] = {}
        data["user_stats"][str(user_id)] = data["user_stats"].get(str(user_id), 0) + 1
        
        if peer_id > 2000000000:
            if await check_links(text) and not is_mod(user_id):
                await vk.messages_send(peer_id, "🔗 Ссылки запрещены!")
                return
            
            if await check_spam(user_id, peer_id) and not is_mod(user_id):
                mute_time = 5
                data["muted"][f"{peer_id}_{user_id}"] = time.time() + (mute_time * 60)
                save_data(data)
                await vk.messages_send(peer_id, f"🚫 Заглушен на {mute_time} минут за спам!")
                return
        
        if not text:
            return
        
        if not text.startswith("!"):
            return
        
        command = text[1:].strip().lower()
        
        # ============================================================
        # 📸 ЗАГРУЗКА ФОТО: !загрузить [команда] (своё сообщение)
        # 📸 ЗАГРУЗКА ФОТО ПО ОТВЕТУ: ответить на сообщение с фото !загрузить [команда]
        # 📸 МАССОВАЯ ЗАГРУЗКА: !загрузить все [команда]
        # ============================================================
        if command.startswith("загрузить "):
            if not is_mod(user_id):
                await vk.messages_send(peer_id, "❌ Нет прав для загрузки фото!")
                return
            
            # Парсим команду: !загрузить [все] [команда]
            parts = command.split()
            if len(parts) < 2:
                await vk.messages_send(peer_id, "❌ Укажите команду: !загрузить обнять")
                return
            
            is_bulk = False
            if parts[1] == "все" and len(parts) > 2:
                is_bulk = True
                rp_cmd = parts[2]
            else:
                rp_cmd = parts[1]
            
            if rp_cmd not in RP_ACTIONS:
                await vk.messages_send(peer_id, f"❌ Команда '{rp_cmd}' не найдена")
                return
            
            # Проверяем, откуда брать фото
            photos_to_upload = []
            
            # 1. Если есть ответ на сообщение — берём фото из него
            if reply_user_id:
                try:
                    reply_msg = msg.get("reply_message", {})
                    if reply_msg:
                        reply_photos = await get_photos_from_message(reply_msg)
                        if reply_photos:
                            photos_to_upload.extend(reply_photos)
                            await vk.messages_send(peer_id, f"📸 Найдено {len(reply_photos)} фото в сообщении, на которое вы ответили")
                except Exception as e:
                    logger.error(f"Reply photo error: {e}")
            
            # 2. Если есть фото в текущем сообщении
            current_photos = await get_photos_from_message(msg)
            if current_photos:
                photos_to_upload.extend(current_photos)
                await vk.messages_send(peer_id, f"📸 Найдено {len(current_photos)} фото в вашем сообщении")
            
            # Если фото не найдены
            if not photos_to_upload:
                await vk.messages_send(peer_id, "❌ Не найдено фото в сообщении или в ответе! Прикрепите фото или ответьте на сообщение с фото.")
                return
            
            # Ограничиваем количество фото
            if len(photos_to_upload) > 30:
                photos_to_upload = photos_to_upload[:30]
                await vk.messages_send(peer_id, f"⚠️ Загружаю только 30 фото из {len(photos_to_upload)}")
            
            # Загружаем фото
            await vk.messages_send(peer_id, f"⏳ Загрузка {len(photos_to_upload)} фото для команды '{rp_cmd}'...")
            
            attachments = await upload_multiple_photos(photos_to_upload)
            
            if not attachments:
                await vk.messages_send(peer_id, "❌ Не удалось загрузить ни одного фото!")
                return
            
            # Сохраняем в базу
            if rp_cmd not in data["rp_images"]:
                data["rp_images"][rp_cmd] = []
            data["rp_images"][rp_cmd].extend(attachments)
            save_data(data)
            
            # Показываем первое загруженное фото как подтверждение
            await vk.messages_send(
                peer_id, 
                f"✅ Загружено {len(attachments)} фото для команды '{rp_cmd}'!", 
                attachment=attachments[0]
            )
            return
        
        # ============================================================
        # 🎯 СТИКЕРЫ
        # ============================================================
        if command in STICKER_IDS:
            await vk.messages_send(peer_id, sticker_id=STICKER_IDS[command])
            return
        
        # ============================================================
        # 🎭 RP КОМАНДЫ
        # ============================================================
        if command in RP_ACTIONS:
            target_id = reply_user_id if reply_user_id else user_id
            user_name = await get_display_link(user_id)
            target_name = await get_display_link(target_id)
            action_desc = RP_ACTIONS[command]
            
            result_text = f"{user_name} {action_desc} {target_name}!"
            
            images = data.get("rp_images", {}).get(command, [])
            if images:
                # Выбираем случайное фото из загруженных
                attachment = random.choice(images)
                await vk.messages_send(peer_id, result_text, attachment=attachment)
            else:
                await vk.messages_send(peer_id, result_text)
            return
        
        # ============================================================
        # 📛 НИК (для всех)
        # ============================================================
        if command.startswith("ник "):
            new_nick = command[4:].strip()
            if len(new_nick) > 30:
                await vk.messages_send(peer_id, "❌ Ник не более 30 символов!")
                return
            if len(new_nick) < 2:
                await vk.messages_send(peer_id, "❌ Ник не менее 2 символов!")
                return
            data["nicks"][str(user_id)] = new_nick
            save_data(data)
            await vk.messages_send(peer_id, f"✅ Ваш ник: {new_nick}")
            return
        
        if command == "снять ник":
            if str(user_id) in data.get("nicks", {}):
                del data["nicks"][str(user_id)]
                save_data(data)
                await vk.messages_send(peer_id, "✅ Ник снят")
            else:
                await vk.messages_send(peer_id, "❌ Нет ника")
            return
        
        # ============================================================
        # 🆘 ПОМОЩЬ
        # ============================================================
        if command == "помощь":
            help_text = """
🎭 **RP БОТ**

💬 Доступные команды (с !):
!обнять, !чмок, !поцеловать, !ударить, !погладить, !укусить
!толкнуть, !обнять за шею, !поцеловать в губы
!поцеловать в щеку, !поцеловать в лоб, !взять за руку
!обнять за талию, !прижать к себе, !погладить по голове
и многие другие...

📸 Загрузка фото:
!загрузить [команда] — прикрепи фото к сообщению
!загрузить все [команда] — загрузить ВСЕ фото из сообщения
(ответьте на сообщение с фото — бот возьмёт фото оттуда)

Примеры:
!загрузить обнять (с фото в сообщении)
!загрузить все чмок (загрузить все фото из сообщения)

📌 Чтобы применить команду к пользователю:
Ответь на его сообщение и напиши команду

🎯 Стикеры:
!сама, !бот

📛 Ник:
!ник [текст] — установить ник
!снять ник — снять ник
"""
            await vk.messages_send(peer_id, help_text)
            return
        
    except Exception as e:
        logger.error(f"Process error: {e}")

async def main():
    logger.info("🚀 RP BOT STARTED")
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
    logger.info("💬 Commands: !обнять, !чмок, !ник, !сама, !бот, !помощь")
    logger.info("📸 !загрузить [команда] — загрузить фото")
    logger.info("📸 !загрузить все [команда] — загрузить все фото")
    logger.info("📸 Ответьте на сообщение с фото + !загрузить [команда]")
    
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
