#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import logging
import json
import time
import random
import requests
import re
from datetime import datetime

# ============================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================
# ПРОВЕРКА ПЕРЕМЕННЫХ
# ============================================================
TOKEN = os.environ.get("VK_GROUP_TOKEN")
GROUP_ID = os.environ.get("VK_GROUP_ID")

if not TOKEN:
    logger.error("Токен не найден!")
    exit(1)

if not GROUP_ID:
    logger.error("ID группы не найден!")
    exit(1)

try:
    GROUP_ID = int(GROUP_ID)
except ValueError:
    logger.error(f"ID группы должен быть числом, получено: {GROUP_ID}")
    exit(1)

API_VERSION = "5.199"
DATA_FILE = "bot_data.json"

# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "owner": 1118563484,
            "admins": [],
            "mods": [],
            "banned": [],
            "muted": {},
            "warns": {},
            "money": {},
            "exp": {},
            "level": {},
            "rep": {},
            "daily_bonus": {},
            "user_stats": {},
            "message_history": {},
            "nicks": {},
            "settings": {
                "welcome": "Привет, {user}! Я твой дружелюбный бот!",
                "farewell": "Пока, {user}! Заходи ещё!",
                "rules": "Правила чата:\n1. Без мата\n2. Без спама\n3. Уважай других",
                "antispam": True,
                "spam_limit": 5,
                "spam_time": 5,
                "antilink": True,
                "whitelist": ["vk.com", "youtube.com", "t.me"],
                "leveling": True,
                "economy": True,
                "daily_amount": 100,
                "max_warns": 3,
                "mute_duration": 5,
                "ban_duration": 7,
                "response_chance": 60
            },
            "shop": {
                "items": [
                    {"id": "vip", "name": "VIP статус", "price": 100000, "desc": "VIP навсегда"},
                    {"id": "premium", "name": "Premium статус", "price": 50000, "desc": "Premium навсегда"},
                    {"id": "gold_nick", "name": "Золотой ник", "price": 10000, "desc": "Золотой цвет ника"}
                ]
            }
        }

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        return False

data = load_data()

# ============================================================
# КЛАСС VK API
# ============================================================
class VKAPI:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://api.vk.com/method/"
        self.version = API_VERSION
        self.session = requests.Session()
    
    def _request(self, method, params=None):
        if params is None:
            params = {}
        params["access_token"] = self.token
        params["v"] = self.version
        try:
            response = self.session.post(self.base_url + method, data=params, timeout=15)
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                logger.error(f"Ошибка VK: {result['error'].get('error_msg')}")
                return {"error": result["error"]}
            return result.get("response", {})
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return {"error": {"error_msg": str(e)}}
    
    def messages_send(self, peer_id, message=None):
        params = {
            "peer_id": peer_id,
            "random_id": int(time.time() * 1000) + random.randint(1, 99999),
            "disable_mentions": 0
        }
        if message:
            params["message"] = message[:4096]
        return self._request("messages.send", params)
    
    def messages_remove_chat_user(self, chat_id, user_id):
        return self._request("messages.removeChatUser", {
            "chat_id": chat_id,
            "user_id": user_id
        })
    
    def users_get(self, user_ids):
        return self._request("users.get", {"user_ids": user_ids})
    
    def groups_get_by_id(self):
        return self._request("groups.getById", {"group_id": GROUP_ID})
    
    def get_long_poll_server(self):
        return self._request("groups.getLongPollServer", {"group_id": GROUP_ID})
    
    def long_poll_request(self, server, key, ts, wait=25):
        if not server.startswith(('http://', 'https://')):
            server = 'https://' + server
        url = f"{server}?act=a_check&key={key}&ts={ts}&wait={wait}&mode=2&version=2"
        try:
            response = self.session.get(url, timeout=wait + 10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Long Poll ошибка: {e}")
            return {"failed": 1}

vk = VKAPI(TOKEN)

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def is_owner(user_id):
    return user_id == data.get("owner", 0)

def is_admin(user_id):
    return is_owner(user_id) or user_id in data.get("admins", [])

def is_mod(user_id):
    return is_admin(user_id) or user_id in data.get("mods", [])

def is_banned(user_id):
    return user_id in data.get("banned", [])

def is_muted(user_id, peer_id):
    key = f"{peer_id}_{user_id}"
    if key in data.get("muted", {}):
        if data["muted"][key] > time.time():
            return True
        else:
            del data["muted"][key]
            save_data()
    return False

def get_user_level(user_id):
    return data.get("level", {}).get(str(user_id), 1)

def get_user_exp(user_id):
    return data.get("exp", {}).get(str(user_id), 0)

def get_user_money(user_id):
    return data.get("money", {}).get(str(user_id), 0)

def get_user_rep(user_id):
    return data.get("rep", {}).get(str(user_id), 0)

def get_user_warns(user_id):
    return data.get("warns", {}).get(str(user_id), 0)

def get_required_exp(level):
    return level * 100 + 50

def get_user_name(user_id):
    try:
        result = vk.users_get(user_id)
        if "error" not in result and result:
            user = result[0]
            return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return f"ID{user_id}"
    except:
        return f"ID{user_id}"

def get_nick(user_id):
    return data.get("nicks", {}).get(str(user_id))

def get_display_name(user_id):
    nick = get_nick(user_id)
    if nick:
        return nick
    return get_user_name(user_id)

def user_link(user_id):
    name = get_display_name(user_id)
    return f"[id{user_id}|{name}]"

async def add_money(user_id, amount):
    data["money"][str(user_id)] = data["money"].get(str(user_id), 0) + amount
    save_data()

async def remove_money(user_id, amount):
    current = data["money"].get(str(user_id), 0)
    if current < amount:
        return False
    data["money"][str(user_id)] = current - amount
    save_data()
    return True

async def add_exp(user_id, amount):
    data["exp"][str(user_id)] = data["exp"].get(str(user_id), 0) + amount
    exp = data["exp"][str(user_id)]
    data["level"][str(user_id)] = int(exp / 100) + 1
    save_data()

def check_spam(user_id, peer_id):
    if not data["settings"].get("antispam", True):
        return False
    key = f"{peer_id}_{user_id}"
    now = time.time()
    spam_time = data["settings"].get("spam_time", 5)
    spam_limit = data["settings"].get("spam_limit", 5)
    if key not in data["message_history"]:
        data["message_history"][key] = []
    data["message_history"][key] = [t for t in data["message_history"][key] if now - t < spam_time]
    if len(data["message_history"][key]) >= spam_limit:
        return True
    data["message_history"][key].append(now)
    save_data()
    return False

def check_links(text):
    if not data["settings"].get("antilink", True):
        return False
    whitelist = data["settings"].get("whitelist", ["vk.com", "youtube.com", "t.me"])
    url_pattern = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
    links = re.findall(url_pattern, text, re.IGNORECASE)
    for link in links:
        if not any(w in link.lower() for w in whitelist):
            return True
    return False

# ============================================================
# ЖИВЫЕ ОТВЕТЫ (без звездочек и смайликов)
# ============================================================
FRIENDLY_RESPONSES = {
    # Приветствия
    r'привет|здарова|салют|хай|hello|hi|здравствуй|доброе утро|добрый день|добрый вечер': [
        "Привет! Как дела?",
        "Здравствуй! Рад тебя видеть!",
        "Привет-привет! Как жизнь?",
        "Здарова! Что нового?",
        "Хай! Как настроение?",
        "Приветик! Давно не виделись!",
        "Здравствуй, друг! Как поживаешь?",
        "Привет! Чем занимаешься?"
    ],
    
    # Прощания
    r'пока|до встречи|удачи|бывай|bye|до свидания|покеда|счастливо|всего хорошего': [
        "Пока! Приходи ещё!",
        "До встречи! Было приятно пообщаться!",
        "Удачи тебе!",
        "Счастливого пути!",
        "Пока-пока! Не забывай про меня!",
        "До связи! Обязательно заглядывай!",
        "Всего доброго! Рад был поболтать!",
        "Пока! Хорошего дня!"
    ],
    
    # Благодарности
    r'спасибо|благодарю|thanks|thx|благодар|мерси': [
        "Всегда пожалуйста!",
        "Рад помочь!",
        "Обращайся, всегда помогу!",
        "Не за что, друг!",
        "Всегда рад помочь тебе!",
        "Пожалуйста! Обращайся ещё!"
    ],
    
    # Как дела
    r'как дела|как ты|как жизнь|как настроение|what\'s up': [
        "У меня всё отлично! А у тебя как?",
        "Супер! Жизнь прекрасна!",
        "Классно, спасибо что спросил!",
        "Всё замечательно! А у тебя?",
        "Лучше всех! Как сам?",
        "Отлично! Что у тебя нового?"
    ],
    
    # Хорошо/отлично
    r'отлично|супер|класс|ого|круто|вау|огонь|зашибись|збс': [
        "Круто, я рад за тебя!",
        "Вот это здорово!",
        "Супер! Так держать!",
        "Отлично! Продолжай в том же духе!",
        "Классно, я тоже рад!",
        "Это прекрасные новости!"
    ],
    
    # Плохо/грустно
    r'плохо|грустно|печально|ужасно|кошмар|не очень': [
        "Ой, что случилось? Расскажи!",
        "Держись, всё будет хорошо!",
        "Не переживай, завтра будет лучше!",
        "Хочешь поговорить об этом?",
        "Я тебя понимаю, бывает грустно...",
        "Держу за тебя кулачки, всё наладится!"
    ],
    
    # Вопросы
    r'\?': [
        "Хороший вопрос! Дай подумать...",
        "Интересно, а как ты думаешь?",
        "Мне кажется, что всё зависит от ситуации!",
        "Честно говоря, я не знаю, но это очень интересно!",
        "А давай вместе подумаем?",
        "Сложный вопрос! Но я уверен, ты найдёшь ответ!"
    ],
    
    # Шутки
    r'шут|юмор|смешн|joke|анекдот': [
        "Сейчас расскажу!",
        "О, люблю шутки! Слушай!",
        "Держи свежую шутку!",
        "Хорошо, приготовься смеяться!"
    ],
    
    # Факты
    r'факт|интересн|знаешь|truth|fact': [
        "Знаешь, есть один интересный факт...",
        "Я как раз недавно узнал!",
        "Вот тебе факт, который тебя удивит!",
        "Держи порцию интересных знаний!",
        "О, я знаю кое-что занятное!"
    ],
    
    # Упоминание бота
    r'бот|bot': [
        "Я здесь! Что нужно?",
        "Слушаю тебя внимательно!",
        "Да, я тут! Как дела?",
        "Звал меня? Я весь во внимании!",
        "Я здесь, всегда готов помочь!",
        "Привет! Чем могу быть полезен?"
    ]
}

RANDOM_REPLIES = [
    "Хорошо сказано!",
    "Согласен с тобой!",
    "Интересная мысль!",
    "Да ну? Серьёзно?",
    "Круто, я тоже так думаю!",
    "Ну такое себе, но ладно!",
    "Ого, вот это поворот!",
    "Ахахах, умора!",
    "Ты сегодня в ударе!",
    "Мне нравится твой настрой!",
    "Так держать, друг!",
    "Вот это я понимаю!",
    "Ну ты даёшь, молодец!",
    "Отличная идея, кстати!",
    "Да, я тоже так считаю!",
    "Ну, тут я с тобой согласен!",
    "Вот это новость!",
    "Классно провели время!",
    "Я в восторге от этого!",
    "Давай ещё пообщаемся!"
]

JOKES_LIST = [
    "Идёт программист по улице, видит банку. Поднимает, а там написано: Открой меня! Он открыл, а оттуда джинн вылезает. Джинн говорит: Я исполню три твоих желания! Программист говорит: Сделай так, чтобы в моём коде не было багов! Джинн: Это невозможно, загадывай другое!",
    "Как программист ловит рыбу? Он её отлаживает!",
    "Сколько программистов нужно чтобы поменять лампочку? Ни одного, это аппаратная проблема!",
    "Почему программисты не любят ходить в лес? Потому что там слишком много багов!",
    "Как называется программист, который не умеет кодить? Начальник!",
    "Что говорит программист когда видит ошибку? Это не баг, это фича!",
    "Почему программисты всегда ходят с зонтиком? Потому что у них везде дата-центры!"
]

FACTS_LIST = [
    "Знаешь, у осьминога целых три сердца!",
    "У страуса глаза больше мозга, представляешь?",
    "Волки воют не на луну, а чтобы общаться с другими волками!",
    "У кошек 32 мышцы в каждом ухе!",
    "Дельфины дают друг другу имена, как люди!",
    "Слоны единственные млекопитающие, которые не умеют прыгать!",
    "Гепарды разгоняются до 100 км/ч за 3 секунды!",
    "Пингвины ныряют на глубину до 500 метров!"
]

async def get_reply(text):
    text_lower = text.lower()
    
    for pattern, replies in FRIENDLY_RESPONSES.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            return random.choice(replies)
    
    if random.randint(1, 100) <= data["settings"].get("response_chance", 60):
        return random.choice(RANDOM_REPLIES)
    
    return None

# ============================================================
# ОБРАБОТКА СООБЩЕНИЙ
# ============================================================
async def process_message(message_data):
    try:
        if not isinstance(message_data, dict):
            return
        if "object" not in message_data or "message" not in message_data["object"]:
            return
        
        msg = message_data["object"]["message"]
        peer_id = msg.get("peer_id", 0)
        user_id = msg.get("from_id", 0)
        text = msg.get("text", "")
        
        if user_id < 0:
            return
        
        if is_banned(user_id):
            return
        
        if is_muted(user_id, peer_id):
            return
        
        # Статистика
        data["user_stats"][str(user_id)] = data["user_stats"].get(str(user_id), 0) + 1
        
        # Опыт
        if data["settings"].get("leveling", True):
            if random.random() < 0.15:
                await add_exp(user_id, random.randint(1, 10))
        
        # Антиспам
        if peer_id > 2000000000:
            if check_links(text) and not is_mod(user_id):
                vk.messages_send(peer_id, "Ссылки запрещены! Используй разрешённые домены.")
                return
            if check_spam(user_id, peer_id) and not is_mod(user_id):
                mute_time = data["settings"].get("mute_duration", 5)
                data["muted"][f"{peer_id}_{user_id}"] = time.time() + (mute_time * 60)
                save_data()
                vk.messages_send(peer_id, f"{user_link(user_id)} заглушен на {mute_time} минут за спам!")
                return
        
        # ============================================================
        # ЖИВОЙ ОТВЕТ НА ЛЮБОЕ СООБЩЕНИЕ
        # ============================================================
        if peer_id > 2000000000 and text and not text.startswith("!"):
            reply = await get_reply(text)
            if reply:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                vk.messages_send(peer_id, reply)
                return
        
        # ============================================================
        # КОМАНДЫ
        # ============================================================
        if not text.startswith("!"):
            return
        
        command = text[1:].strip().lower()
        args = text.split()[1:] if len(text.split()) > 1 else []
        
        # help
        if command in ["help", "помощь"]:
            help_text = """Доступные команды:

Мой профиль:
!profile - посмотреть свой профиль
!profile [ID] - посмотреть профиль другого
!level - узнать свой уровень
!stats - моя статистика

Экономика:
!money - сколько денег
!daily - получить ежедневный бонус
!shop - магазин
!buy [ID] - купить товар

Общение:
!rep [ID] - поставить репутацию
!nick [ник] - установить никнейм
!say [текст] - сказать от лица бота

Развлечения:
!joke - услышать шутку
!fact - узнать факт
!roll [число] - бросить кубик
!coin - монетка
!8ball [вопрос] - магический шар

Другое:
!rules - правила чата
!info - информация о боте
!report [ID] [причина] - пожаловаться"""
            vk.messages_send(peer_id, help_text)
            return
        
        # profile
        if command in ["profile", "профиль"]:
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                
                name = get_display_name(target_id)
                level = get_user_level(target_id)
                exp = get_user_exp(target_id)
                money = get_user_money(target_id)
                rep = get_user_rep(target_id)
                warns = get_user_warns(target_id)
                stats = data.get("user_stats", {}).get(str(target_id), 0)
                next_level = get_required_exp(level)
                
                profile_text = f"""Профиль {name}

Уровень: {level}
Опыт: {exp} из {next_level}
Денег: {money}
Репутация: {rep}
Предупреждений: {warns}
Сообщений: {stats}"""
                vk.messages_send(peer_id, profile_text)
            except Exception as e:
                logger.error(f"profile ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка при получении профиля!")
            return
        
        # money
        if command in ["money", "баланс"]:
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                name = get_display_name(target_id)
                money = get_user_money(target_id)
                vk.messages_send(peer_id, f"У {name} {money} монет")
            except Exception as e:
                logger.error(f"money ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка при получении баланса!")
            return
        
        # daily
        if command in ["daily", "ежедневный"]:
            try:
                key = f"{peer_id}_{user_id}"
                now = time.time()
                last_claim = data.get("daily_bonus", {}).get(key, 0)
                
                if now - last_claim < 86400:
                    remaining = int(86400 - (now - last_claim))
                    hours = remaining // 3600
                    minutes = (remaining % 3600) // 60
                    vk.messages_send(peer_id, f"Ты уже получал бонус сегодня! Следующий через {hours} часов {minutes} минут")
                    return
                
                amount = data["settings"].get("daily_amount", 100)
                await add_money(user_id, amount)
                data["daily_bonus"][key] = now
                save_data()
                vk.messages_send(peer_id, f"Ты получил {amount} монет! Заходи завтра ещё!")
            except Exception as e:
                logger.error(f"daily ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка при получении бонуса!")
            return
        
        # shop
        if command in ["shop", "магазин"]:
            try:
                items = data.get("shop", {}).get("items", [])
                if not items:
                    vk.messages_send(peer_id, "Магазин пока пуст, загляни позже!")
                    return
                text = "Магазин:\n"
                for item in items:
                    text += f"{item['name']} - {item['price']} монет (ID: {item['id']})\n"
                    text += f"{item.get('desc', '')}\n\n"
                vk.messages_send(peer_id, text)
            except Exception as e:
                logger.error(f"shop ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка при открытии магазина!")
            return
        
        # buy
        if command in ["buy", "купить"]:
            try:
                if not args:
                    vk.messages_send(peer_id, "Напиши !buy [ID товара]")
                    return
                item_id = args[0]
                items = data.get("shop", {}).get("items", [])
                item = next((i for i in items if i.get("id") == item_id), None)
                if not item:
                    vk.messages_send(peer_id, "Такого товара нет в магазине!")
                    return
                price = item.get("price", 0)
                if await remove_money(user_id, price):
                    vk.messages_send(peer_id, f"Ты купил {item['name']} за {price} монет!")
                else:
                    vk.messages_send(peer_id, f"Не хватает денег! Нужно {price} монет")
            except Exception as e:
                logger.error(f"buy ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка при покупке!")
            return
        
        # rep
        if command in ["rep", "репутация"]:
            try:
                if not args:
                    rep = get_user_rep(user_id)
                    vk.messages_send(peer_id, f"У тебя {rep} репутации")
                    return
                target_id = int(args[0])
                if target_id == user_id:
                    vk.messages_send(peer_id, "Нельзя дать репутацию самому себе!")
                    return
                key = f"rep_{user_id}_{target_id}"
                if key in data.get("rep_history", {}):
                    if time.time() - data["rep_history"][key] < 86400:
                        vk.messages_send(peer_id, "Ты уже давал репутацию этому пользователю сегодня!")
                        return
                data["rep"][str(target_id)] = data["rep"].get(str(target_id), 0) + 1
                data["rep_history"][key] = time.time()
                save_data()
                vk.messages_send(peer_id, f"{user_link(target_id)} получил репутацию!")
            except Exception as e:
                logger.error(f"rep ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # level
        if command in ["level", "уровень"]:
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                name = get_display_name(target_id)
                level = get_user_level(target_id)
                exp = get_user_exp(target_id)
                next_level = get_required_exp(level)
                vk.messages_send(peer_id, f"{name} - уровень {level}\nОпыт: {exp} из {next_level}")
            except Exception as e:
                logger.error(f"level ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # joke
        if command in ["joke", "шутка"]:
            try:
                joke = random.choice(JOKES_LIST)
                vk.messages_send(peer_id, joke)
            except Exception as e:
                logger.error(f"joke ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # fact
        if command in ["fact", "факт"]:
            try:
                fact = random.choice(FACTS_LIST)
                vk.messages_send(peer_id, fact)
            except Exception as e:
                logger.error(f"fact ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # roll
        if command in ["roll", "кубик"]:
            try:
                max_num = int(args[0]) if args and args[0].isdigit() else 6
                if max_num < 2:
                    max_num = 2
                if max_num > 100:
                    max_num = 100
                result = random.randint(1, max_num)
                vk.messages_send(peer_id, f"{user_link(user_id)} выбросил {result} из {max_num}")
            except Exception as e:
                logger.error(f"roll ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # coin
        if command in ["coin", "монетка"]:
            try:
                result = "Орёл" if random.random() < 0.5 else "Решка"
                vk.messages_send(peer_id, f"{user_link(user_id)}: {result}")
            except Exception as e:
                logger.error(f"coin ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # 8ball
        if command in ["8ball", "шар"]:
            try:
                if not args:
                    vk.messages_send(peer_id, "Напиши вопрос после команды")
                    return
                answers = ["Да", "Нет", "Возможно", "Скорее всего", "Спроси позже",
                          "Определённо да", "Определённо нет", "Может быть", "Неизвестно"]
                answer = random.choice(answers)
                vk.messages_send(peer_id, f"Магический шар говорит: {answer}")
            except Exception as e:
                logger.error(f"8ball ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # say
        if command in ["say", "скажи"]:
            try:
                if not args:
                    vk.messages_send(peer_id, "Напиши что сказать")
                    return
                text_to_say = " ".join(args)
                vk.messages_send(peer_id, text_to_say)
            except Exception as e:
                logger.error(f"say ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # nick
        if command in ["nick", "ник"]:
            try:
                if not args:
                    vk.messages_send(peer_id, "Напиши никнейм")
                    return
                nick = " ".join(args)
                data["nicks"][str(user_id)] = nick
                save_data()
                vk.messages_send(peer_id, f"Теперь тебя зовут {nick}!")
            except Exception as e:
                logger.error(f"nick ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # rules
        if command in ["rules", "правила"]:
            rules = data["settings"].get("rules", "Правила не установлены")
            vk.messages_send(peer_id, rules)
            return
        
        # info
        if command in ["info", "инфо"]:
            info_text = f"""Информация о боте

Пользователей: {len(data.get('user_stats', {}))}
Версия API: {API_VERSION}
Режим: дружелюбный"""
            vk.messages_send(peer_id, info_text)
            return
        
        # report
        if command in ["report", "репорт", "жалоба"]:
            try:
                if len(args) < 2:
                    vk.messages_send(peer_id, "Напиши: report [ID] [причина]")
                    return
                target_id = int(args[0])
                reason = " ".join(args[1:])
                
                if "reports" not in data:
                    data["reports"] = {}
                
                report_id = str(int(time.time()))
                data["reports"][report_id] = {
                    "from": user_id,
                    "target": target_id,
                    "reason": reason,
                    "time": time.time(),
                    "peer_id": peer_id,
                    "status": "pending"
                }
                save_data()
                
                name = get_display_name(target_id)
                vk.messages_send(peer_id, f"Жалоба на {name} отправлена модераторам!")
                
                for admin_id in data.get("admins", []):
                    try:
                        vk.messages_send(admin_id, f"Новая жалоба!\nОт: {user_link(user_id)}\nНа: {user_link(target_id)}\nПричина: {reason}")
                    except:
                        pass
            except Exception as e:
                logger.error(f"report ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка при отправке жалобы!")
            return
        
        # stats
        if command in ["stats", "статистика"]:
            try:
                target_id = user_id
                if args:
                    try:
                        target_id = int(args[0])
                    except:
                        pass
                name = get_display_name(target_id)
                messages = data.get("user_stats", {}).get(str(target_id), 0)
                warns = get_user_warns(target_id)
                level = get_user_level(target_id)
                money = get_user_money(target_id)
                rep = get_user_rep(target_id)
                stats_text = f"""Статистика {name}

Сообщений: {messages}
Предупреждений: {warns}
Уровень: {level}
Денег: {money}
Репутация: {rep}"""
                vk.messages_send(peer_id, stats_text)
            except Exception as e:
                logger.error(f"stats ошибка: {e}")
                vk.messages_send(peer_id, "Ошибка!")
            return
        
        # ============================================================
        # КОМАНДЫ МОДЕРАЦИИ
        # ============================================================
        if is_mod(user_id):
            
            if command in ["mute", "мут"]:
                try:
                    if not args:
                        vk.messages_send(peer_id, "Напиши: mute [ID] [минут]")
                        return
                    target_id = int(args[0])
                    minutes = int(args[1]) if len(args) > 1 else data["settings"].get("mute_duration", 5)
                    data["muted"][f"{peer_id}_{target_id}"] = time.time() + (minutes * 60)
                    save_data()
                    vk.messages_send(peer_id, f"{user_link(target_id)} заглушен на {minutes} минут!")
                except Exception as e:
                    logger.error(f"mute ошибка: {e}")
                    vk.messages_send(peer_id, "Ошибка!")
                return
            
            if command in ["unmute", "размут"]:
                try:
                    if not args:
                        vk.messages_send(peer_id, "Напиши: unmute [ID]")
                        return
                    target_id = int(args[0])
                    key = f"{peer_id}_{target_id}"
                    if key in data.get("muted", {}):
                        del data["muted"][key]
                        save_data()
                        vk.messages_send(peer_id, f"{user_link(target_id)} размучен!")
                    else:
                        vk.messages_send(peer_id, "Этот пользователь не заглушен!")
                except Exception as e:
                    logger.error(f"unmute ошибка: {e}")
                    vk.messages_send(peer_id, "Ошибка!")
                return
            
            if command in ["kick", "кик"]:
                try:
                    if not args:
                        vk.messages_send(peer_id, "Напиши: kick [ID]")
                        return
                    target_id = int(args[0])
                    chat_id = peer_id - 2000000000
                    result = vk.messages_remove_chat_user(chat_id, target_id)
                    if "error" not in result:
                        vk.messages_send(peer_id, f"{user_link(target_id)} кикнут из беседы!")
                    else:
                        vk.messages_send(peer_id, "Не удалось кикнуть пользователя!")
                except Exception as e:
                    logger.error(f"kick ошибка: {e}")
                    vk.messages_send(peer_id, "Ошибка!")
                return
            
            if command in ["ban", "бан"]:
                try:
                    if not args:
                        vk.messages_send(peer_id, "Напиши: ban [ID] [дней]")
                        return
                    target_id = int(args[0])
                    days = int(args[1]) if len(args) > 1 else data["settings"].get("ban_duration", 7)
                    data["banned"].append(target_id)
                    save_data()
                    vk.messages_send(peer_id, f"{user_link(target_id)} забанен на {days} дней!")
                    chat_id = peer_id - 2000000000
                    vk.messages_remove_chat_user(chat_id, target_id)
                except Exception as e:
                    logger.error(f"ban ошибка: {e}")
                    vk.messages_send(peer_id, "Ошибка!")
                return
            
            if command in ["unban", "разбан"]:
                try:
                    if not args:
                        vk.messages_send(peer_id, "Напиши: unban [ID]")
                        return
                    target_id = int(args[0])
                    if target_id in data.get("banned", []):
                        data["banned"].remove(target_id)
                        save_data()
                        vk.messages_send(peer_id, f"{user_link(target_id)} разбанен!")
                    else:
                        vk.messages_send(peer_id, "Этот пользователь не забанен!")
                except Exception as e:
                    logger.error(f"unban ошибка: {e}")
                    vk.messages_send(peer_id, "Ошибка!")
                return
            
            if command in ["warn", "варн"]:
                try:
                    if not args:
                        vk.messages_send(peer_id, "Напиши: warn [ID]")
                        return
                    target_id = int(args[0])
                    data["warns"][str(target_id)] = data["warns"].get(str(target_id), 0) + 1
                    warns = data["warns"][str(target_id)]
                    max_warns = data["settings"].get("max_warns", 3)
                    save_data()
                    if warns >= max_warns:
                        data["banned"].append(target_id)
                        save_data()
                        vk.messages_send(peer_id, f"{user_link(target_id)} забанен за {max_warns} предупреждений!")
                    else:
                        vk.messages_send(peer_id, f"{user_link(target_id)} получил предупреждение! {warns} из {max_warns}")
                except Exception as e:
                    logger.error(f"warn ошибка: {e}")
                    vk.messages_send(peer_id, "Ошибка!")
                return

# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================
async def main():
    logger.info("Запуск бота...")
    
    server_data = vk.get_long_poll_server()
    if "error" in server_data:
        logger.error(f"Ошибка подключения: {server_data['error']}")
        return
    
    server = server_data.get("server")
    key = server_data.get("key")
    ts = server_data.get("ts")
    
    if not server or not key or not ts:
        logger.error("Не удалось подключиться к Long Poll")
        return
    
    logger.info("Бот успешно запущен и готов к работе!")
    
    while True:
        try:
            response = vk.long_poll_request(server, key, ts)
            
            if "failed" in response:
                error_code = response.get("failed", 0)
                if error_code in [1, 2, 3]:
                    server_data = vk.get_long_poll_server()
                    if "error" not in server_data:
                        server = server_data.get("server", server)
                        key = server_data.get("key", key)
                        ts = server_data.get("ts", ts)
                    continue
                else:
                    logger.error(f"Ошибка Long Poll: {response}")
                    await asyncio.sleep(5)
                    continue
            
            ts = response.get("ts", ts)
            updates = response.get("updates", [])
            
            for update in updates:
                try:
                    if update.get("type") == "message_new":
                        await process_message(update.get("object", {}))
                except Exception as e:
                    logger.error(f"Ошибка обработки: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка в цикле: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
