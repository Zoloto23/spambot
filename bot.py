import asyncio
import os
import logging
import json
import time
import random
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

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

INSULTS = [
    "сука",
    "блядь",
    "хуй",
    "пизда",
    "залупа",
    "мудила",
    "гандон",
    "пидор",
    "лох",
    "дебил",
    "идиот",
    "кретин",
    "олень",
    "баран",
    "козел",
    "свинья",
    "петух",
    "шлюха",
    "блядина",
    "проститутка",
    "тварь",
    "урод",
    "выродок",
    "мразь",
    "гад",
    "змей",
    "крыса",
    "ебать",
    "ебаный",
    "ебанутый",
    "ебланище",
    "еблан",
    "ебальник",
    "ебашишь",
    "заебать",
    "доебаться",
    "выебать",
    "наебать",
    "объебать",
    "хуярить",
    "нахуй",
    "похуй",
    "дохуя",
    "нехуй",
    "охуеть",
    "охуенный",
    "пиздеть",
    "пиздец",
    "пиздюк",
    "пиздатый",
    "я твою мать вертел",
    "я твою мать ебал",
    "пошёл нахуй",
    "иди нахуй",
    "нахуй иди",
    "в пизду",
    "в жопу",
    "ебанный в рот",
    "ёбаный в рот",
    "ебать твою мать",
    "мат твою мать",
    "бля буду",
    "твою мать",
    "ебать копать",
    "заебало",
    "доебали",
    "поебать",
    "распиздяй",
    "разъебай",
    "иди ты в жопу",
    "заткнись еблан",
    "ты чё дурак",
    "ты тупой",
    "у тебя мозгов нет",
    "ты вообще тупой",
    "ёбаный насос",
    "блядский рот",
    "хуй тебе в рот",
    "пиздобол",
    "мудила пизда",
    "лох педальный",
    "идиот полный",
    "дебил конченый",
    "петух гнилой",
    "козел драный",
    "свинья поганая",
    "шлюха драная",
    "блядина старая",
    "урод конченый",
    "мразь вонючая",
    "ебло",
    "рожа",
    "морда",
    "хрюкало",
    "бивни",
    "копыта",
    "свиное рыло",
    "баранья голова",
    "оленья хари"
]

PREFIXES = [
    "эй",
    "слушай",
    "ты",
    "а ну",
    "ну и",
    "вот ты",
    "да ты",
    "а ты",
    "ну ты",
    "а ну-ка"
]

SUFFIXES = [
    "!",
    "!!!",
    "??",
    "?!",
    "...",
    "))))",
    "))",
    "хаха",
    "ахаха",
    "ахахаха",
    "бля"
]

DATA_FILE = "spam_data.json"

def load_data() -> Dict[str, Any]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "spam_enabled": False,
            "spam_interval": 1,
            "last_spam": {},
            "target_chats": [],
            "spam_intensity": 1
        }

def save_data(data: Dict[str, Any]):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Save error: {e}")

data = load_data()

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
    
    def messages_send(self, peer_id: int, message: str, random_id: int = None) -> Dict:
        if random_id is None:
            random_id = int(time.time() * 1000) + random.randint(1, 99999)
        return self._request("messages.send", {
            "peer_id": peer_id,
            "message": message,
            "random_id": random_id
        })
    
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

def generate_spam_message() -> str:
    insult = random.choice(INSULTS)
    
    if random.random() < 0.3:
        prefix = random.choice(PREFIXES)
        insult = f"{prefix} {insult}"
    
    if random.random() < 0.5:
        suffix = random.choice(SUFFIXES)
        insult = f"{insult}{suffix}"
    
    if random.random() < 0.2:
        insult = insult.upper()
    
    return insult

def generate_spam_sequence(intensity: int = 1) -> str:
    messages = []
    count = random.randint(intensity, intensity * 2)
    
    for _ in range(count):
        msg = generate_spam_message()
        if random.random() < 0.2:
            emojis = ["😈", "🤬", "💀", "🔥", "👊", "💢", "🤡", "😤", "🤮", "👎"]
            msg = f"{msg} {random.choice(emojis)}"
        messages.append(msg)
    
    return "\n".join(messages)

async def send_spam(peer_id: int):
    if not data.get("spam_enabled", False):
        return
    
    now = time.time()
    last_spam = data["last_spam"].get(str(peer_id), 0)
    interval = data.get("spam_interval", 1)
    
    if now - last_spam < interval:
        return
    
    intensity = data.get("spam_intensity", 1)
    message = generate_spam_sequence(intensity)
    
    try:
        vk.messages_send(peer_id, message)
        data["last_spam"][str(peer_id)] = now
        save_data(data)
        logger.info(f"Spam sent to {peer_id}")
    except Exception as e:
        logger.error(f"Send error: {e}")

async def process_message(message_data: dict):
    try:
        peer_id = message_data.get("peer_id", 0)
        user_id = message_data.get("from_id", 0)
        text = message_data.get("text", "")
        
        if user_id < 0:
            return
        
        if text.startswith(PREFIX):
            command = text[1:].strip().lower()
            
            if command == "спам вкл":
                data["spam_enabled"] = True
                save_data(data)
                vk.messages_send(peer_id, "SPAM ON")
                logger.info(f"Spam ON in {peer_id}")
                return
            
            if command == "спам выкл":
                data["spam_enabled"] = False
                save_data(data)
                vk.messages_send(peer_id, "SPAM OFF")
                logger.info(f"Spam OFF in {peer_id}")
                return
            
            if command.startswith("интервал "):
                try:
                    interval = float(command.split()[1])
                    if interval < 0.5:
                        vk.messages_send(peer_id, "Minimum 0.5 sec")
                        return
                    data["spam_interval"] = interval
                    save_data(data)
                    vk.messages_send(peer_id, f"Interval: {interval}s")
                except:
                    vk.messages_send(peer_id, "!interval [seconds]")
                return
            
            if command.startswith("интенсивность "):
                try:
                    intensity = int(command.split()[1])
                    if intensity < 1 or intensity > 5:
                        vk.messages_send(peer_id, "Intensity 1-5")
                        return
                    data["spam_intensity"] = intensity
                    save_data(data)
                    vk.messages_send(peer_id, f"Intensity: {intensity}/5")
                except:
                    vk.messages_send(peer_id, "!intensity [1-5]")
                return
            
            if command == "статус":
                status = "ON" if data.get("spam_enabled", False) else "OFF"
                interval = data.get("spam_interval", 1)
                intensity = data.get("spam_intensity", 1)
                vk.messages_send(peer_id, 
                    f"Status: {status}\n"
                    f"Interval: {interval}s\n"
                    f"Intensity: {intensity}/5\n"
                    f"Phrases: {len(INSULTS)}")
                return
            
            if command == "помощь":
                help_text = (
                    "COMMANDS:\n\n"
                    "!spam on - Enable spam\n"
                    "!spam off - Disable spam\n"
                    "!interval [sec] - Set interval\n"
                    "!intensity [1-5] - Set intensity\n"
                    "!status - Show status\n"
                    "!help - This message\n\n"
                    f"Total phrases: {len(INSULTS)}"
                )
                vk.messages_send(peer_id, help_text)
                return
        
        await send_spam(peer_id)
            
    except Exception as e:
        logger.error(f"Process error: {e}")

async def main():
    logger.info("Starting SPAM BOT...")
    logger.info(f"Group ID: {GROUP_ID}")
    logger.info(f"Total phrases: {len(INSULTS)}")
    
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
    
    logger.info("SPAM BOT READY")
    logger.info("Commands: !help")
    
    last_message_id = 0
    
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
                    if not isinstance(update, list) or len(update) < 1:
                        continue
                    
                    update_type = update[0]
                    
                    if update_type == 4:
                        if len(update) < 2:
                            continue
                        message_data = update[1]
                        if not isinstance(message_data, dict):
                            continue
                        
                        message_id = message_data.get("id", 0)
                        if message_id <= last_message_id:
                            continue
                        last_message_id = message_id
                        
                        await process_message(message_data)
                    
                except Exception as e:
                    logger.error(f"Update error: {e}")
                    
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
