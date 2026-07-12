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

# --- ЖЕСТОКИЕ ОСКОРБЛЕНИЯ ---
CRUEL_INSULTS = [
    "ты даже не человек, ты ошибка природы",
    "твои родители тебя не любили, и я понимаю почему",
    "ты настолько тупой, что даже бот это видит",
    "ты позор для своей семьи",
    "твой мозг весит меньше чем твои комплексы",
    "ты бесполезнее чем кнопка на пульте",
    "ты - причина почему люди не верят в бога",
    "даже моя бабушка умнее тебя, а она умерла 10 лет назад",
    "ты как программа без кода - просто ошибка",
    "твоя жизнь - это баг в матрице",
    "ты настолько тупой, что бот тебя переумнее",
    "если бы тупость была олимпийским спортом, ты был бы чемпионом",
    "ты как подарок, который никто не хотел получать",
    "твоё лицо даже мать не может любить",
    "ты такой тупой, что даже гугл не знает ответа",
    "твой отец хотел сына, а получил это",
    "ты как ошибка 404 - просто не найден",
    "твой IQ равен комнатной температуре",
    "ты настолько бесполезен, что даже паразиты тебя игнорируют",
    "ты как сломанный будильник - бесполезный и раздражающий",
    "твоя жизнь - это мем, только никому не смешно",
    "ты как Windows Vista - одна большая ошибка",
    "ты настолько тупой, что это заразно",
    "даже стул умнее тебя, он хотя бы стоит прямо",
    "ты как курица без головы - бегаешь и не знаешь зачем",
    "твои друзья - просто актёры, которые получают зарплату за общение с тобой",
    "ты как просроченный йогурт - уже никому не нужен",
    "твоя жизнь - это плохая шутка, которую никто не понял",
    "ты как игра без сохранения - всё зря",
    "даже мой код чище, чем твои мысли"
]

# --- УНИЧИТАЛЬНЫЕ ФРАЗЫ ---
DESTROY_PHRASES = [
    "я сейчас тебя так унижу, что ты удалишь вк",
    "ты просто кусок мяса на стуле",
    "твой отец ошибся, когда не использовал резинку",
    "ты как ошибка в коде - одна большая проблема",
    "даже вирусы не хотят жить в твоём теле",
    "ты - причина почему аборты не запрещают",
    "твоя мама плачет каждую ночь, глядя на тебя",
    "ты как Windows без антивируса - одна сплошная уязвимость",
    "твой мозг нуждается в перезагрузке, хотя там и так пусто",
    "ты настолько глуп, что даже рыба из аквариума переплывает в другой угол, когда видит тебя"
]

# --- НАСМЕШКИ ---
MOCK_PHRASES = [
    "ха-ха, ты реально думал что ты важен?",
    "ты смешной, даже когда не пытаешься",
    "ооо, какой смешной, продолжай, мне нужен повод посмеяться",
    "аххахахаха, ты серьёзно?",
    "ты как клоун, только без работы",
    "даже шутки про тебя смешнее тебя самого",
    "ты как мем, только несмешной"
]

def get_random_insult(target: str = "") -> str:
    """Генерирует оскорбление с упоминанием цели"""
    insult = random.choice(CRUEL_INSULTS)
    if target and random.random() < 0.7:
        name = target.split()[0] if " " in target else target
        insult = f"{name}, {insult}"
    
    # Добавляем случайный суффикс
    suffixes = ["", "!!!", "?!", "...", "))))", "хаха", "бля", "как тебе такое?"]
    if random.random() < 0.4:
        insult = f"{insult} {random.choice(suffixes)}"
    
    # Иногда добавляем эмодзи
    if random.random() < 0.3:
        emojis = ["🤬", "😈", "💀", "👊", "🔥", "🤡", "😤", "👎", "💩", "🤮"]
        insult = f"{insult} {random.choice(emojis)}"
    
    return insult

def get_destroy_phrase(target: str = "") -> str:
    """Уничтожительная фраза"""
    phrase = random.choice(DESTROY_PHRASES)
    if target and random.random() < 0.5:
        name = target.split()[0] if " " in target else target
        phrase = f"{name}, {phrase}"
    return phrase

def get_mock_phrase() -> str:
    """Насмешка"""
    return random.choice(MOCK_PHRASES)

def generate_spam_message(target: str = "") -> str:
    """Генерация спам-сообщения"""
    types = ["insult", "destroy", "mock", "insult", "insult"]
    choice = random.choice(types)
    
    if choice == "insult":
        return get_random_insult(target)
    elif choice == "destroy":
        return get_destroy_phrase(target)
    else:
        return get_mock_phrase()

# --- ХРАНЕНИЕ ДАННЫХ ---
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

# --- КЛАСС VK API ---
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
    """Получает имя пользователя по ID"""
    try:
        result = vk.users_get(user_id)
        if "error" not in result and result:
            user = result[0]
            return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return f"ID {user_id}"
    except:
        return f"ID {user_id}"

async def send_spam(peer_id: int):
    """Отправляет спам-сообщение"""
    if not data.get("spam_enabled", False):
        return
    
    now = time.time()
    last_spam = data["last_spam"].get(str(peer_id), 0)
    interval = data.get("spam_interval", 0.5)
    
    if now - last_spam < interval:
        return
    
    # Получаем цель
    target = data.get("target_name", "")
    
    # Генерируем сообщение
    message = generate_spam_message(target)
    
    # Счётчик спама
    data["spam_count"] = data.get("spam_count", 0) + 1
    
    # Добавляем счётчик каждые 10 сообщений
    if data["spam_count"] % 10 == 0:
        message = f"{message}\n\n[СПАМ №{data['spam_count']}]"
    
    try:
        vk.messages_send(peer_id, message)
        data["last_spam"][str(peer_id)] = now
        save_data(data)
        logger.info(f"Spam #{data['spam_count']} to {peer_id}")
    except Exception as e:
        logger.error(f"Send error: {e}")

async def process_message(message_data: dict):
    try:
        # Получаем сообщение из правильного формата
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
        
        logger.info(f"Message from {user_id}: {text[:30]}")
        
        # Обработка команд
        if text.startswith(PREFIX):
            command = text[1:].strip().lower()
            
            # --- ВКЛЮЧИТЬ СПАМ ---
            if command == "спам вкл":
                data["spam_enabled"] = True
                data["spam_count"] = 0
                save_data(data)
                vk.messages_send(peer_id, "🤬 СПАМ ВКЛЮЧЕН! Начинаю уничтожать чат!")
                logger.info("Spam ON")
                return
            
            # --- ВЫКЛЮЧИТЬ СПАМ ---
            if command == "спам выкл":
                data["spam_enabled"] = False
                save_data(data)
                vk.messages_send(peer_id, "💀 СПАМ ВЫКЛЮЧЕН! Ухожу в тень...")
                logger.info("Spam OFF")
                return
            
            # --- УСТАНОВИТЬ ЦЕЛЬ ---
            if command.startswith("цель "):
                target_id = command.split()[1] if len(command.split()) > 1 else ""
                if target_id.isdigit():
                    target_id = int(target_id)
                    name = await get_user_name(target_id)
                    data["target_user"] = target_id
                    data["target_name"] = name
                    save_data(data)
                    vk.messages_send(peer_id, f"🎯 Цель установлена: {name}\nТеперь спам будет по ней!")
                    logger.info(f"Target set: {name} ({target_id})")
                else:
                    vk.messages_send(peer_id, "❌ Укажите ID пользователя\nПример: !цель 123456789")
                return
            
            # --- ОТМЕНИТЬ ЦЕЛЬ ---
            if command == "цель выкл":
                data["target_user"] = ""
                data["target_name"] = ""
                save_data(data)
                vk.messages_send(peer_id, "❌ Цель отменена! Спам по всем")
                return
            
            # --- УСТАНОВИТЬ ИНТЕРВАЛ ---
            if command.startswith("интервал "):
                try:
                    interval = float(command.split()[1])
                    if interval < 0.1:
                        vk.messages_send(peer_id, "❌ Минимум 0.1 секунды!")
                        return
                    data["spam_interval"] = interval
                    save_data(data)
                    vk.messages_send(peer_id, f"⏱ Интервал: {interval} секунд")
                except:
                    vk.messages_send(peer_id, "❌ !интервал [секунды]")
                return
            
            # --- СТАТУС ---
            if command == "статус":
                status = "ВКЛЮЧЕН 🔥" if data.get("spam_enabled") else "ВЫКЛЮЧЕН 💤"
                interval = data.get("spam_interval", 0.5)
                target = data.get("target_name", "Нет")
                count = data.get("spam_count", 0)
                vk.messages_send(peer_id, 
                    f"🤬 **СТАТУС СПАМ-БОТА**\n\n"
                    f"Статус: {status}\n"
                    f"Интервал: {interval}с\n"
                    f"Цель: {target}\n"
                    f"Всего спама: {count}\n"
                    f"Фраз: {len(CRUEL_INSULTS)}")
                return
            
            # --- ПОМОЩЬ ---
            if command == "помощь":
                help_text = (
                    "🤬 **КОМАНДЫ ЖЕСТОКОГО СПАМ-БОТА**\n\n"
                    "!спам вкл - Включить адский спам\n"
                    "!спам выкл - Выключить спам\n"
                    "!цель [ID] - Установить жертву\n"
                    "!цель выкл - Отменить цель\n"
                    "!интервал [сек] - Скорость спама\n"
                    "!статус - Статус бота\n"
                    "!помощь - Эта справка\n\n"
                    "💀 Бот уничтожает всех без админки!\n"
                    f"🔥 Всего оскорблений: {len(CRUEL_INSULTS)}"
                )
                vk.messages_send(peer_id, help_text)
                return
        
        # --- АВТОМАТИЧЕСКИЙ СПАМ (если включен) ---
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
    
    logger.info(f"Server: {server}")
    logger.info(f"TS: {ts}")
    
    if not server:
        logger.error("No server")
        return
    
    if not server.startswith(('http://', 'https://')):
        server = 'https://' + server
    
    logger.info("✅ CRUEL SPAM BOT READY")
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
