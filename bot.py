import os
import logging
import time
import random
import requests
from datetime import datetime
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

class VKChatManager:
    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.api_version = "5.131"
        self.base_url = "https://api.vk.com/method/"
        self.session = requests.Session()
        self.start_time = time.time()

        # Хранилища данных (кратко для примера)
        self.user_roles = {}
        self.warnings = defaultdict(list)
        self.mute_timers = {}
        self.points = defaultdict(int)
        self.levels = defaultdict(int)
        self.message_count = defaultdict(int)
        self.achievements = defaultdict(set)
        self.rules = []
        self.settings = {
            "welcome_message": "👋 Добро пожаловать!",
            "leave_message": "👋 Пока!",
            "max_warnings": 3,
            "slow_mode": False,
            "slow_mode_delay": 3,
        }
        self.last_message_time = defaultdict(float)
        self.game_sessions = {}
        self.afk_users = {}
        self.reminders = defaultdict(list)
        self.polls = {}
        self.commands = {}
        self.register_commands()

    def register_commands(self):
        # Регистрируем команды (сокращённо для примера)
        commands = [
            ("/help", self.cmd_help, "Помощь", "info"),
            ("/ping", self.cmd_ping, "Пинг", "info"),
            ("/uptime", self.cmd_uptime, "Время работы", "info"),
            ("/roll", self.cmd_roll, "Бросок кубика", "fun"),
            ("/coin", self.cmd_coin, "Орёл/решка", "fun"),
            ("/joke", self.cmd_joke, "Шутка", "fun"),
            ("/quote", self.cmd_quote, "Цитата", "fun"),
            ("/calc", self.cmd_calc, "Калькулятор", "utils"),
            ("/time", self.cmd_time, "Время", "info"),
            ("/weather", self.cmd_weather, "Погода", "info"),
            ("/balance", self.cmd_balance, "Баланс", "economy"),
            ("/daily", self.cmd_daily, "Бонус", "economy"),
            ("/profile", self.cmd_profile, "Профиль", "info"),
            ("/rank", self.cmd_rank, "Ранг", "info"),
            ("/hi", self.cmd_hi, "Привет", "social"),
            ("/hug", self.cmd_hug, "Обнять", "social"),
            ("/kick", self.cmd_kick, "Выгнать", "moderation"),
            ("/mute", self.cmd_mute, "Мут", "moderation"),
            ("/warn", self.cmd_warn, "Предупреждение", "moderation"),
            ("/clear", self.cmd_clear, "Очистить", "moderation"),
            ("/rules", self.cmd_rules, "Правила", "moderation"),
            ("/addrule", self.cmd_addrule, "Добавить правило", "moderation"),
            ("/removerule", self.cmd_removerule, "Удалить правило", "moderation"),
            ("/setwelcome", self.cmd_setwelcome, "Приветствие", "moderation"),
            ("/slowmode", self.cmd_slowmode, "Медленный режим", "moderation"),
            ("/online", self.cmd_online, "Онлайн", "info"),
            ("/stats", self.cmd_stats, "Статистика", "info"),
            ("/lovecalc", self.cmd_lovecalc, "Любовь", "fun"),
            ("/horoscope", self.cmd_horoscope, "Гороскоп", "fun"),
            ("/game", self.cmd_game, "Игра", "games"),
            ("/join", self.cmd_join, "Присоединиться", "games"),
            ("/leaderboard", self.cmd_leaderboard, "Лидеры", "games"),
            ("/pay", self.cmd_pay, "Перевод", "economy"),
            ("/gamble", self.cmd_gamble, "Риск", "fun"),
            ("/afk", self.cmd_afk, "AFK", "utils"),
            ("/echo", self.cmd_echo, "Эхо", "utils"),
            ("/reverse", self.cmd_reverse, "Реверс", "utils"),
        ]
        for cmd, handler, desc, category in commands:
            self.commands[cmd] = {"handler": handler, "desc": desc, "category": category}

    # Вспомогательные методы
    def is_mod(self, user_id): return self.user_roles.get(user_id) in ["mod", "admin", "owner"]
    def is_admin(self, user_id): return self.user_roles.get(user_id) in ["admin", "owner"]

    def is_muted(self, user_id):
        if user_id in self.mute_timers and time.time() < self.mute_timers[user_id]:
            return True
        return False

    def add_points(self, user_id, points):
        self.points[user_id] += points
        new_level = int(self.points[user_id] / 100) + 1
        if new_level > self.levels[user_id]:
            self.levels[user_id] = new_level
            return True
        return False

    def api_request(self, method: str, **params) -> Dict[str, Any]:
        params["access_token"] = self.token
        params["v"] = self.api_version
        try:
            response = self.session.post(f"{self.base_url}{method}", params=params)
            data = response.json()
            if "error" in data:
                logger.error(f"VK API error: {data['error']}")
                return {"error": data["error"]}
            return data.get("response", {})
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {"error": str(e)}

    def send_message(self, chat_id: int, message: str, **kwargs) -> bool:
        if not message:
            return False
        params = {
            "peer_id": chat_id,
            "message": message,
            "random_id": random.randint(1, 1000000)
        }
        params.update(kwargs)
        response = self.api_request("messages.send", **params)
        return "error" not in response

    def get_user_info(self, user_id):
        response = self.api_request("users.get", user_ids=user_id, fields="photo_100,online,first_name,last_name")
        if response and "error" not in response:
            return response[0]
        return {}

    # ----- Обработчики команд (выборочно) -----
    def cmd_help(self, args, user_id, chat_id):
        return "📚 Доступные команды: /ping, /roll, /joke, /time, /weather, /balance, /daily, /profile, /rank, /hi, /hug, /rules, /game, /join, /leaderboard, /pay, /gamble, /afk, /echo, /reverse и другие."

    def cmd_ping(self, args, user_id, chat_id):
        start = time.time()
        self.api_request("messages.get", count=1, filter=8)  # <-- исправлено
        end = time.time()
        return f"🏓 Понг! Задержка: {round((end - start) * 1000)} мс"

    def cmd_uptime(self, args, user_id, chat_id):
        uptime_seconds = time.time() - self.start_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"⏱ Бот работает: {days}д {hours}ч {minutes}м"

    def cmd_roll(self, args, user_id, chat_id):
        sides = 6
        if args and args[0].isdigit():
            sides = int(args[0])
            if sides < 2: sides = 2
            if sides > 100: sides = 100
        return f"🎲 Бросок кубика (1-{sides}): {random.randint(1, sides)}"

    def cmd_coin(self, args, user_id, chat_id):
        return f"🪙 {random.choice(['Орёл', 'Решка'])}"

    def cmd_joke(self, args, user_id, chat_id):
        jokes = ["Почему программисты путают Хэллоуин и Рождество? 31 OCT = 25 DEC",
                 "Сколько программистов нужно, чтобы заменить лампочку? Ни одного"]
        return f"😂 {random.choice(jokes)}"

    def cmd_quote(self, args, user_id, chat_id):
        quotes = ["Жизнь - это то, что происходит, пока ты строишь планы",
                  "Будь изменением, которое хочешь видеть в мире"]
        return f"📝 {random.choice(quotes)}"

    def cmd_calc(self, args, user_id, chat_id):
        if not args: return "Введите выражение: /calc 2+2"
        expr = " ".join(args)
        try:
            if not set(expr).issubset("0123456789+-*/() ."):
                return "❌ Недопустимые символы"
            return f"🧮 {expr} = {eval(expr)}"
        except:
            return "❌ Ошибка в выражении"

    def cmd_time(self, args, user_id, chat_id):
        now = datetime.now()
        return f"🕐 {now.strftime('%H:%M:%S')}  📅 {now.strftime('%d.%m.%Y')}"

    def cmd_weather(self, args, user_id, chat_id):
        city = " ".join(args) if args else "Москва"
        return f"🌤 Погода в {city}: +22°C, ветер 5 м/с (демо)"

    def cmd_balance(self, args, user_id, chat_id):
        return f"💰 Ваш баланс: {self.points[user_id]} монет"

    def cmd_daily(self, args, user_id, chat_id):
        bonus = random.randint(50, 150)
        self.add_points(user_id, bonus)
        return f"🎁 Ежедневный бонус: +{bonus} монет"

    def cmd_profile(self, args, user_id, chat_id):
        role = self.user_roles.get(user_id, "Пользователь")
        return f"👤 Профиль\nID: {user_id}\nРоль: {role}\nУровень: {self.levels[user_id]}\nОчков: {self.points[user_id]}\nСообщений: {self.message_count[user_id]}"

    def cmd_rank(self, args, user_id, chat_id):
        ranks = {"owner": "👑 Владелец", "admin": "🛡 Админ", "mod": "🔰 Модератор", "user": "👤 Пользователь"}
        role = self.user_roles.get(user_id, "user")
        return f"Ваш ранг: {ranks.get(role, 'Пользователь')}\nУровень: {self.levels[user_id]}\nОчков: {self.points[user_id]}"

    def cmd_hi(self, args, user_id, chat_id):
        return "👋 Привет!"

    def cmd_hug(self, args, user_id, chat_id):
        if args:
            return f"🤗 Обнимаю {args[0]}"
        return "🤗 Отправляю виртуальные объятия!"

    def cmd_kick(self, args, user_id, chat_id):
        if not self.is_mod(user_id): return "⛔ Недостаточно прав"
        if not args: return "Укажите пользователя: /kick [id]"
        return "✅ Пользователь выгнан (демо)"

    def cmd_mute(self, args, user_id, chat_id):
        if not self.is_mod(user_id): return "⛔ Недостаточно прав"
        if not args: return "Укажите пользователя: /mute [id]"
        return "✅ Пользователь замучен (демо)"

    def cmd_warn(self, args, user_id, chat_id):
        if not self.is_mod(user_id): return "⛔ Недостаточно прав"
        if not args: return "Укажите пользователя: /warn [id]"
        return "⚠️ Предупреждение выдано (демо)"

    def cmd_clear(self, args, user_id, chat_id):
        if not self.is_mod(user_id): return "⛔ Недостаточно прав"
        count = 20
        if args and args[0].isdigit():
            count = min(int(args[0]), 100)
        return f"🧹 Очищено {count} сообщений (демо)"

    def cmd_rules(self, args, user_id, chat_id):
        if not self.rules:
            return "ℹ️ Правила не установлены"
        return "📜 Правила:\n" + "\n".join(f"{i+1}. {r}" for i, r in enumerate(self.rules))

    def cmd_addrule(self, args, user_id, chat_id):
        if not self.is_admin(user_id): return "⛔ Недостаточно прав"
        if not args: return "Укажите правило"
        self.rules.append(" ".join(args))
        return "✅ Правило добавлено"

    def cmd_removerule(self, args, user_id, chat_id):
        if not self.is_admin(user_id): return "⛔ Недостаточно прав"
        if not args or not args[0].isdigit(): return "Укажите номер"
        idx = int(args[0]) - 1
        if 0 <= idx < len(self.rules):
            removed = self.rules.pop(idx)
            return f"✅ Правило удалено: {removed}"
        return "❌ Неверный номер"

    def cmd_setwelcome(self, args, user_id, chat_id):
        if not self.is_admin(user_id): return "⛔ Недостаточно прав"
        if not args: return "Укажите текст"
        self.settings["welcome_message"] = " ".join(args)
        return "✅ Приветствие установлено"

    def cmd_slowmode(self, args, user_id, chat_id):
        if not self.is_admin(user_id): return "⛔ Недостаточно прав"
        if args and args[0].lower() == "off":
            self.settings["slow_mode"] = False
            return "✅ Медленный режим выключен"
        delay = 3
        if args and args[0].isdigit():
            delay = int(args[0])
        self.settings["slow_mode"] = True
        self.settings["slow_mode_delay"] = delay
        return f"✅ Медленный режим включен (задержка {delay} сек)"

    def cmd_online(self, args, user_id, chat_id):
        return "👥 Онлайн: 15 (демо)"

    def cmd_stats(self, args, user_id, chat_id):
        return f"📊 Сообщений: {self.message_count[user_id]}\nОчков: {self.points[user_id]}\nУровень: {self.levels[user_id]}\nДостижений: {len(self.achievements[user_id])}"

    def cmd_lovecalc(self, args, user_id, chat_id):
        if not args: return "Укажите имя: /lovecalc Имя"
        name = " ".join(args)
        p = random.randint(0, 100)
        return f"❤️ {name} – {p}% любви"

    def cmd_horoscope(self, args, user_id, chat_id):
        zodiac = args[0] if args else random.choice(["Овен","Телец","Близнецы","Рак","Лев","Дева","Весы","Скорпион","Стрелец","Козерог","Водолей","Рыбы"])
        return f"♈ Гороскоп для {zodiac}: {random.choice(['Сегодня удачный день!', 'Будьте осторожны', 'Вас ждёт сюрприз'])}"

    def cmd_game(self, args, user_id, chat_id):
        gid = f"game_{int(time.time())}"
        self.game_sessions[gid] = {"players": [user_id], "state": "waiting", "max_players": 10}
        return f"🎮 Игра создана! ID: {gid}. Присоединяйтесь: /join {gid}"

    def cmd_join(self, args, user_id, chat_id):
        if not args: return "Укажите ID игры"
        gid = args[0]
        if gid not in self.game_sessions: return "❌ Игра не найдена"
        game = self.game_sessions[gid]
        if user_id in game["players"]: return "ℹ️ Вы уже в игре"
        if len(game["players"]) >= game["max_players"]: return "❌ Игра заполнена"
        game["players"].append(user_id)
        return f"✅ Вы присоединились! ({len(game['players'])}/{game['max_players']})"

    def cmd_leaderboard(self, args, user_id, chat_id):
        sorted_users = sorted(self.points.items(), key=lambda x: x[1], reverse=True)[:10]
        if not sorted_users: return "ℹ️ Нет данных"
        text = "🏆 Таблица лидеров:\n"
        for i, (uid, pts) in enumerate(sorted_users, 1):
            user_info = self.get_user_info(uid)
            name = user_info.get('first_name', f'User{uid}') if user_info else f'User{uid}'
            text += f"{i}. {name} – {pts}\n"
        return text

    def cmd_pay(self, args, user_id, chat_id):
        if len(args) < 2: return "Использование: /pay [id] [сумма]"
        target = int(args[0])
        amount = int(args[1])
        if target == user_id: return "❌ Себе нельзя"
        if amount <= 0: return "❌ Сумма >0"
        if self.points[user_id] < amount: return f"❌ Недостаточно (у вас {self.points[user_id]})"
        self.points[user_id] -= amount
        self.points[target] += amount
        return f"✅ Переведено {amount} монет"

    def cmd_gamble(self, args, user_id, chat_id):
        if not args or not args[0].isdigit(): return "Укажите сумму: /gamble [сумма]"
        amount = int(args[0])
        if self.points[user_id] < amount: return f"❌ Недостаточно (у вас {self.points[user_id]})"
        mult = random.choice([0, 0.5, 1, 2])
        win = int(amount * mult)
        self.points[user_id] += win - amount
        if win > amount: return f"🎉 Выигрыш! +{win-amount} монет"
        elif win == amount: return "🤝 Ставка вернулась"
        else: return f"😢 Проигрыш -{amount-win} монет"

    def cmd_afk(self, args, user_id, chat_id):
        reason = " ".join(args) if args else "Не беспокоить"
        self.afk_users[user_id] = {"time": time.time(), "reason": reason}
        return f"🔇 AFK: {reason}"

    def cmd_echo(self, args, user_id, chat_id):
        return " ".join(args) if args else "Напишите что-то"

    def cmd_reverse(self, args, user_id, chat_id):
        return " ".join(args)[::-1] if args else "Введите текст"

    # Если команда не найдена, заглушка
    def __getattr__(self, name):
        if name.startswith("cmd_"):
            return lambda args, uid, cid: f"Команда {name[4:]} в разработке"
        raise AttributeError(name)

    # ----- Обработка сообщений -----
    def process_message(self, message: Dict[str, Any]) -> Optional[str]:
        text = message.get("text", "").strip()
        user_id = message.get("from_id", 0)
        chat_id = message.get("peer_id", 0)
        if not text or not user_id:
            return None

        if self.is_muted(user_id):
            return None

        if self.settings["slow_mode"]:
            now = time.time()
            if user_id in self.last_message_time and now - self.last_message_time[user_id] < self.settings["slow_mode_delay"]:
                return None
            self.last_message_time[user_id] = now

        if text.startswith('/'):
            parts = text.split()
            cmd = parts[0].lower()
            args = parts[1:]
            if cmd in self.commands:
                handler = self.commands[cmd]["handler"]
                if callable(handler):
                    try:
                        result = handler(args, user_id, chat_id)
                        if result:
                            self.send_message(chat_id, result)
                    except Exception as e:
                        logger.error(f"Error in {cmd}: {e}")
                        self.send_message(chat_id, "❌ Ошибка")
                return None

        # Начисление очков за активность
        if len(text) > 3 and random.random() < 0.1:
            self.add_points(user_id, random.randint(1, 3))
            self.message_count[user_id] += 1
        return None

    def run(self):
        logger.info("Бот запущен и готов к работе")
        while True:
            try:
                # Исправлено: добавлен filter=8
                response = self.api_request("messages.get", count=20, filter=8)
                if response and "items" in response:
                    for msg in response["items"]:
                        self.process_message(msg)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(5)

if __name__ == "__main__":
    manager = VKChatManager(TOKEN, GROUP_ID)
    manager.run()
