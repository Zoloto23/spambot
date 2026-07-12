import asyncio
import os
import logging
import json
import time
import random
import requests
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
    "сука", "блядь", "хуй", "пизда", "мудила", "гандон",
    "пидор", "лох", "дебил", "идиот", "кретин", "олень",
    "баран", "козел", "свинья", "петух", "шлюха", "блядина",
    "тварь", "урод", "выродок", "мразь", "гад", "крыса",
    "ебать", "ебаный", "ебанутый", "еблан", "заебать",
    "нахуй", "похуй", "дохуя", "охуеть", "пиздец",
    "я твою мать вертел", "иди нахуй", "в пизду",
    "ебанный в рот", "бля буду", "твою мать",
    "заткнись еблан", "ты тупой", "ты чё дурак"
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
    
    def messages_send(self, peer_id: int, message: str) -> Dict:
        return self._request("messages.send", {
            "peer_id": peer_id,
            "message": message,
            "random_id": int(time.time() * 1000) + random.randint(1, 99999)
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

def generate_spam() -> str:
    insult = random.choice(INSULTS)
    if random.random() < 0.3:
        prefix = random.choice(["эй", "слушай", "ты", "а ну"])
        insult = f"{prefix} {insult}"
    if random.random() < 0.5:
        insult = f"{insult}!"
    return insult

async def send_spam(peer_id: int):
    if not data.get("spam_enabled", False):
        return
    
    now = time.time()
    last_spam = data["last_spam"].get(str(peer_id), 0)
    interval = data.get("spam_interval", 1)
    
    if now - last_spam < interval:
        return
    
    message = generate_spam()
    try:
        vk.messages_send(peer_id, message)
        data["last_spam"][str(peer_id)] = now
        save_data(data)
        logger.info(f"Spam to {peer_id}")
    except Exception as e:
        logger.error(f"Send error: {e}")

async def process_message(message_data: dict):
    try:
        peer_id = message_data.get("peer_id", 0)
        user_id = message_data.get("from_id", 0)
        text = message_data.get("text", "")
        
        logger.info(f"Message from {user_id} to {peer_id}: {text[:30]}")
        
        if user_id < 0:
            return
        
        if text.startswith(PREFIX):
            command = text[1:].strip().lower()
            logger.info(f"Command: {command}")
            
            if command == "спам вкл":
                data["spam_enabled"] = True
                save_data(data)
                vk.messages_send(peer_id, "SPAM ON")
                logger.info("Spam turned ON")
                return
            
            if command == "спам выкл":
                data["spam_enabled"] = False
                save_data(data)
                vk.messages_send(peer_id, "SPAM OFF")
                logger.info("Spam turned OFF")
                return
            
            if command.startswith("интервал "):
                try:
                    interval = float(command.split()[1])
                    if interval < 0.5:
                        vk.messages_send(peer_id, "Min 0.5s")
                        return
                    data["spam_interval"] = interval
                    save_data(data)
                    vk.messages_send(peer_id, f"Interval: {interval}s")
                except:
                    vk.messages_send(peer_id, "!interval [seconds]")
                return
            
            if command == "статус":
                status = "ON" if data.get("spam_enabled") else "OFF"
                interval = data.get("spam_interval", 1)
                vk.messages_send(peer_id, f"Status: {status}\nInterval: {interval}s")
                return
            
            if command == "помощь":
                vk.messages_send(peer_id, 
                    "!спам вкл - ON\n"
                    "!спам выкл - OFF\n"
                    "!интервал 1 - Interval\n"
                    "!статус - Status\n"
                    "!помощь - Help")
                return
        
        if peer_id != user_id:
            await send_spam(peer_id)
            
    except Exception as e:
        logger.error(f"Process error: {e}")

async def main():
    logger.info("SPAM BOT START")
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
    
    logger.info(f"Server: {server}")
    logger.info(f"Key: {key[:10]}...")
    logger.info(f"TS: {ts}")
    
    if not server:
        logger.error("No server")
        return
    
    if not server.startswith(('http://', 'https://')):
        server = 'https://' + server
    
    logger.info("BOT READY")
    logger.info("Commands: !помощь")
    
    last_message_id = 0
    
    while True:
        try:
            response = vk.long_poll_request(server, key, ts)
            
            logger.info(f"Long Poll response: {str(response)[:200]}")
            
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
            
            logger.info(f"Updates count: {len(updates)}")
            
            for update in updates:
                try:
                    logger.info(f"Update: {update}")
                    
                    if not isinstance(update, list) or len(update) < 1:
                        continue
                    
                    if update[0] == 4:
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
