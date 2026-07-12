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

# --- ЖЕСТОКИЕ МАТЫ И ОСКОРБЛЕНИЯ ---
CRUEL_INSULTS = [
    "сука ебаная, ты че такой тупой?",
    "блядь, у тебя мозгов вообще нет?",
    "ты ебанутый на всю голову, петушара",
    "пиздец, ты реально такой дебил?",
    "залупа ты драная, иди нахуй отсюда",
    "мудила конченый, тебя ебашили в детстве?",
    "гандон вонючий, закрой ебало",
    "пидор гнилой, ты че думаешь ты крутой?",
    "лох педальный, ты даже не человек",
    "дебил ебаный, у тебя вместо мозгов говно",
    "идиот конченый, тебя мать ебашила по голове?",
    "кретин драный, ты че такой тупорылый?",
    "олень ебаный, ты в своем уме?",
    "баран тупой, тебя что в школе ебашили?",
    "козел гнилой, ты че такой вонючий?",
    "свинья поганая, ты че в говне родился?",
    "петух гнилой, твой отец тоже петух?",
    "шлюха драная, ты че такая дешевая?",
    "блядина старая, ты уже износилась вся",
    "тварь ебаная, ты че думаешь ты человек?",
    "урод конченый, тебя природа ебашила?",
    "выродок гнилой, ты че такой страшный?",
    "мразь вонючая, от тебя говном несет",
    "гад ползучий, ты че змея?",
    "крыса ебаная, ты че такой мелкий?",
    "ебать твою мать, ты че такой тупой?",
    "ебаный в рот, ты че сделал?",
    "ёбаный насос, ты че такой дурак?",
    "блядский рот, закройся уже",
    "хуй тебе в рот, пидорас",
    "пиздобол ебаный, ты че трешься?",
    "распиздяй конченый, ты че такой ленивый?",
    "разъебай драный, ты че такой грязный?",
    "еблан тупой, ты че несешь хуйню?",
    "ебальник закрой, петушара",
    "ебашишь хуйню, дебил",
    "заебало уже, иди нахуй",
    "доебались до меня, козлы",
    "поебать мне на тебя, шлюха",
    "твою мать ебал, урод",
    "мат твою мать, заебал",
    "пошёл нахуй, пидор",
    "иди нахуй, козел",
    "нахуй иди, мудила",
    "в пизду иди, гандон",
    "в жопу себе засунь, петух",
    "ебанный в рот, дебил",
    "ёбаный рот, идиот",
    "я твою мать вертел, лох",
    "я твою мать ебал, баран",
    "ты чё дурак что ли? ебаный",
    "ты тупой как пробка, блядь",
    "у тебя мозгов нет совсем, сука",
    "ты вообще тупой? ебать",
    "заткнись еблан, надоел",
    "ты чё такой тупорылый? пиздец",
    "в жопу себе запихни свои слова",
    "ебать ты тупой, бля буду",
    "твоя мать тоже такая тупая?",
    "ты дебил конченый, понял?",
    "идиот полный, ебаный в рот",
    "мудила пизда, заебал",
    "лох педальный, иди нахуй",
    "петух гнилой, ты че такой вонючий?",
    "козел драный, закрой ебало",
    "свинья поганая, ты че в говне?",
    "шлюха драная, ты че такая дешевая?",
    "блядина старая, ты уже износилась",
    "урод конченый, тебя ебали в детстве?",
    "мразь вонючая, от тебя несет",
    "гад ползучий, ты че змея?",
    "крыса ебаная, ты че такой мелкий?",
    "ебать копать, ты че такой тупой?",
    "бля буду, ты че несешь?",
    "твою мать, заебал уже",
    "ёбаный насос, ты че такой дурак?",
    "блядский рот, закройся",
    "хуй тебе в рот, пидорас",
    "пиздобол ебаный, закройся",
    "распиздяй конченый, ты че ленивый?",
    "разъебай драный, ты че грязный?",
    "еблан тупой, закрой ебало",
    "ебальник закрой, петушара",
    "ебашишь хуйню, дебил",
    "заебало уже, иди нахуй",
    "доебались до меня, козлы",
    "поебать мне на тебя, шлюха",
    "твою мать ебал, урод",
    "мат твою мать, заебал",
    "пошёл нахуй, пидор",
    "иди нахуй, козел",
    "нахуй иди, мудила",
    "в пизду иди, гандон",
    "в жопу себе засунь, петух",
    "ебанный в рот, дебил",
    "ёбаный рот, идиот",
    "я твою мать вертел, лох",
    "я твою мать ебал, баран",
    "ты чё дурак что ли? ебаный",
    "ты тупой как пробка, блядь",
    "у тебя мозгов нет совсем, сука",
    "ты вообще тупой? ебать",
    "заткнись еблан, надоел",
    "ты чё такой тупорылый? пиздец",
    "в жопу себе запихни свои слова",
    "ебать ты тупой, бля буду",
    "твоя мать тоже такая тупая?",
    "ты дебил конченый, понял?",
    "идиот полный, ебаный в рот",
    "мудила пизда, заебал",
    "лох педальный, иди нахуй",
    "петух гнилой, ты че такой вонючий?",
    "козел драный, закрой ебало",
    "свинья поганая, ты че в говне?",
    "шлюха драная, ты че такая дешевая?",
    "блядина старая, ты уже износилась",
    "урод конченый, тебя ебали в детстве?",
    "мразь вонючая, от тебя несет",
    "гад ползучий, ты че змея?",
    "крыса ебаная, ты че такой мелкий?",
    "ебать копать, ты че такой тупой?",
    "бля буду, ты че несешь?",
    "твою мать, заебал уже",
    "ёбаный насос, ты че такой дурак?",
    "блядский рот, закройся",
    "хуй тебе в рот, пидорас",
    "пиздобол ебаный, закройся",
    "распиздяй конченый, ты че ленивый?",
    "разъебай драный, ты че грязный?",
    "еблан тупой, закрой ебало",
    "ебальник закрой, петушара",
    "ебашишь хуйню, дебил",
    "заебало уже, иди нахуй",
    "доебались до меня, козлы",
    "поебать мне на тебя, шлюха",
    "твою мать ебал, урод",
    "мат твою мать, заебал",
    "пошёл нахуй, пидор",
    "иди нахуй, козел",
    "нахуй иди, мудила",
    "в пизду иди, гандон",
    "в жопу себе засунь, петух",
    "ебанный в рот, дебил",
    "ёбаный рот, идиот",
    "я твою мать вертел, лох",
    "я твою мать ебал, баран",
    "ты чё дурак что ли? ебаный",
    "ты тупой как пробка, блядь",
    "у тебя мозгов нет совсем, сука",
    "ты вообще тупой? ебать",
    "заткнись еблан, надоел",
    "ты чё такой тупорылый? пиздец",
    "в жопу себе запихни свои слова",
    "ебать ты тупой, бля буду",
    "твоя мать тоже такая тупая?",
    "ты дебил конченый, понял?",
    "идиот полный, ебаный в рот",
    "мудила пизда, заебал",
    "лох педальный, иди нахуй",
    "петух гнилой, ты че такой вонючий?",
    "козел драный, закрой ебало",
    "свинья поганая, ты че в говне?",
    "шлюха драная, ты че такая дешевая?",
    "блядина старая, ты уже износилась",
    "урод конченый, тебя ебали в детстве?",
    "мразь вонючая, от тебя несет",
    "гад ползучий, ты че змея?",
    "крыса ебаная, ты че такой мелкий?",
    "ебать копать, ты че такой тупой?",
    "бля буду, ты че несешь?",
    "твою мать, заебал уже",
    "ёбаный насос, ты че такой дурак?",
    "блядский рот, закройся",
    "хуй тебе в рот, пидорас",
    "пиздобол ебаный, закройся",
    "распиздяй конченый, ты че ленивый?",
    "разъебай драный, ты че грязный?",
    "еблан тупой, закрой ебало"
]

DATA_FILE = "spam_data.json"

def load_data() -> Dict[str, Any]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "spam_enabled": False,
            "spam_interval": 0.5,
            "last_spam": {},
            "target_user": "",
            "target_name": "",
            "spam_count": 0
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

def generate_spam_message(target: str = "") -> str:
    """Генерирует жестокое оскорбление"""
    insult = random.choice(CRUEL_INSULTS)
    
    # Если есть цель - добавляем имя
    if target and random.random() < 0.7:
        name = target.split()[0] if " " in target else target
        insult = f"{name}, {insult}"
    
    # Случайные украшения
    if random.random() < 0.3:
        emojis = ["🤬", "😈", "💀", "🔥", "👊", "💢", "🤡", "😤", "👎", "💩", "🤮", "😡"]
        insult = f"{insult} {random.choice(emojis)}"
    
    if random.random() < 0.2:
        insult = insult.upper()
    
    return insult

async def send_spam(peer_id: int):
    if not data.get("spam_enabled", False):
        return
    
    now = time.time()
    last_spam = data["last_spam"].get(str(peer_id), 0)
    interval = data.get("spam_interval", 0.5)
    
    if now - last_spam < interval:
        return
    
    target = data.get("target_name", "")
    message = generate_spam_message(target)
    
    # Счётчик
    data["spam_count"] = data.get("spam_count", 0) + 1
    if data["spam_count"] % 5 == 0:
        message = f"{message}\n\n[СПАМ #{data['spam_count']}]"
    
    try:
        vk.messages_send(peer_id, message)
        data["last_spam"][str(peer_id)] = now
        save_data(data)
        logger.info(f"Spam #{data['spam_count']}")
    except Exception as e:
        logger.error(f"Send error: {e}")

async def process_message(message_data: dict):
    try:
        # Правильный парсинг сообщения от группы
        if "object" in message_data and "message" in message_data["object"]:
            msg = message_data["object"]["message"]
            peer_id = msg.get("peer_id", 0)
            user_id = msg.get("from_id", 0)
            text = msg.get("text", "")
        else:
            peer_id = message_data.get("peer_id", 0)
            user_id = message_data.get("from_id", 0)
            text = message_data.get("text", "")
        
        # Игнорируем сообщения от бота
        if user_id < 0:
            return
        
        logger.info(f"Msg from {user_id}: {text[:30]}")
        
        # --- КОМАНДЫ ---
        if text.startswith(PREFIX):
            command = text[1:].strip().lower()
            
            if command == "спам вкл":
                data["spam_enabled"] = True
                data["spam_count"] = 0
                save_data(data)
                vk.messages_send(peer_id, "🤬 СПАМ ВКЛЮЧЕН! ЩАС ВСЕХ РАЗЪЕБУ!")
                logger.info("SPAM ON")
                return
            
            if command == "спам выкл":
                data["spam_enabled"] = False
                save_data(data)
                vk.messages_send(peer_id, "💀 СПАМ ВЫКЛЮЧЕН! УШЕЛ В ТЕНЬ...")
                logger.info("SPAM OFF")
                return
            
            if command.startswith("цель "):
                parts = command.split()
                if len(parts) > 1 and parts[1].isdigit():
                    target_id = int(parts[1])
                    name = await get_user_name(target_id)
                    data["target_user"] = target_id
                    data["target_name"] = name
                    save_data(data)
                    vk.messages_send(peer_id, f"🎯 ЦЕЛЬ: {name}\nЕБАШЬ ЕГО!")
                else:
                    vk.messages_send(peer_id, "❌ !цель [ID]")
                return
            
            if command == "цель выкл":
                data["target_user"] = ""
                data["target_name"] = ""
                save_data(data)
                vk.messages_send(peer_id, "❌ ЦЕЛЬ СНЯТА! ЕБАШУ ВСЕХ!")
                return
            
            if command.startswith("интервал "):
                try:
                    interval = float(command.split()[1])
                    if interval < 0.1:
                        vk.messages_send(peer_id, "❌ МИНИМУМ 0.1 СЕКУНДЫ!")
                        return
                    data["spam_interval"] = interval
                    save_data(data)
                    vk.messages_send(peer_id, f"⏱ ИНТЕРВАЛ: {interval}С")
                except:
                    vk.messages_send(peer_id, "❌ !интервал [секунды]")
                return
            
            if command == "статус":
                status = "🔴 ВКЛ" if data.get("spam_enabled") else "🟢 ВЫКЛ"
                interval = data.get("spam_interval", 0.5)
                target = data.get("target_name", "НЕТ")
                count = data.get("spam_count", 0)
                vk.messages_send(peer_id, 
                    f"🤬 СТАТУС\n"
                    f"СПАМ: {status}\n"
                    f"ИНТЕРВАЛ: {interval}С\n"
                    f"ЦЕЛЬ: {target}\n"
                    f"ВСЕГО: {count}")
                return
            
            if command == "помощь":
                vk.messages_send(peer_id, 
                    "🤬 КОМАНДЫ:\n\n"
                    "!спам вкл - ЗАПУСТИТЬ\n"
                    "!спам выкл - ОСТАНОВИТЬ\n"
                    "!цель [ID] - НАЗНАЧИТЬ ЖЕРТВУ\n"
                    "!цель выкл - ОТМЕНИТЬ\n"
                    "!интервал [сек] - СКОРОСТЬ\n"
                    "!статус - СТАТУС\n"
                    "!помощь - ЭТО")
                return
        
        # Автоспам
        await send_spam(peer_id)
            
    except Exception as e:
        logger.error(f"Process error: {e}")

async def main():
    logger.info("🤬 CRUEL SPAM BOT START")
    logger.info(f"Group: {GROUP_ID}")
    logger.info(f"Insults: {len(CRUEL_INSULTS)}")
    
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
    
    logger.info("✅ CRUEL SPAM BOT READY")
    logger.info("💀 !помощь")
    
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
