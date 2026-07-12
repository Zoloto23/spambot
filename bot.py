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
from typing import Optional, Dict, Any, List, Tuple
from collections import defaultdict
from urllib.parse import urlparse, parse_qs

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
        self.start_time = time.time()  # <--- ИСПРАВЛЕНО: без def

        # Хранилища данных
        self.user_roles = {}  # user_id: role
        self.warnings = defaultdict(list)  # user_id: [warnings]
        self.mute_timers = {}  # user_id: until_timestamp
        self.afk_users = {}  # user_id: last_message_time
        self.quote_messages = {}  # message_id: (user_id, text, date)
        self.polls = {}  # poll_id: {question, options, votes, creator, status}
        self.reminders = defaultdict(list)  # user_id: [{time, text, msg_id}]
        self.rules = []  # List of rules
        self.settings = {
            "welcome_message": "👋 Добро пожаловать в чат!",
            "leave_message": "👋 Пока!",
            "max_warnings": 3,
            "mute_duration": 300,  # seconds
            "language": "ru",
            "slow_mode": False,
            "slow_mode_delay": 3,  # seconds
            "anti_spam": True,
            "anti_flood": True,
            "flood_limit": 5,  # messages per minute
            "auto_moderation": True,
            "bad_words": ["мат", "ругательства"],
            "welcome_enabled": True,
            "leave_enabled": True,
        }
        self.achievements = defaultdict(set)  # user_id: {achievements}
        self.points = defaultdict(int)  # user_id: points
        self.levels = defaultdict(int)  # user_id: level
        self.last_message_time = defaultdict(float)  # user_id: timestamp
        self.message_count = defaultdict(int)  # user_id: count
        self.custom_commands = {}  # command_name: response
        self.scheduled_messages = []  # [{time, text, chat_id}]
        self.user_notes = defaultdict(str)  # user_id: note
        self.voice_claims = {}  # user_id: claim_text
        self.poll_votes = defaultdict(list)  # user_id: [poll_ids]
        self.game_sessions = {}  # game_id: {players, state, ...}
        self.birthdays = {}  # user_id: date
        self.user_interests = defaultdict(list)  # user_id: [interests]
        self.quests = {}  # user_id: {quest_name: progress}
        self.trading_items = {}  # user_id: {item: quantity}
        self.event_reminders = []  # [{date, text, creator}]
        self.auto_responses = {}  # keyword: response
        self.chat_stats = defaultdict(int)  # stat_name: count
        self.user_trust_level = defaultdict(int)  # user_id: trust_level

        # Команды и их обработчики
        self.commands = {}
        self.register_commands()

    def register_commands(self):
        """Регистрация всех 300+ команд"""
        commands = [
            # Модерация (25 команд)
            ("/kick", self.cmd_kick, "Выгнать пользователя", "moderation"),
            ("/ban", self.cmd_ban, "Забанить пользователя", "moderation"),
            ("/unban", self.cmd_unban, "Разбанить пользователя", "moderation"),
            ("/mute", self.cmd_mute, "Замутить пользователя", "moderation"),
            ("/unmute", self.cmd_unmute, "Размутить пользователя", "moderation"),
            ("/warn", self.cmd_warn, "Выдать предупреждение", "moderation"),
            ("/clear", self.cmd_clear, "Очистить чат", "moderation"),
            ("/pin", self.cmd_pin, "Закрепить сообщение", "moderation"),
            ("/unpin", self.cmd_unpin, "Открепить сообщение", "moderation"),
            ("/slowmode", self.cmd_slowmode, "Включить медленный режим", "moderation"),
            ("/rules", self.cmd_rules, "Показать правила", "moderation"),
            ("/addrule", self.cmd_addrule, "Добавить правило", "moderation"),
            ("/removerule", self.cmd_removerule, "Удалить правило", "moderation"),
            ("/setwelcome", self.cmd_setwelcome, "Установить приветствие", "moderation"),
            ("/setleave", self.cmd_setleave, "Установить прощание", "moderation"),
            ("/mods", self.cmd_mods, "Список модераторов", "moderation"),
            ("/addmod", self.cmd_addmod, "Добавить модератора", "moderation"),
            ("/removemod", self.cmd_removemod, "Удалить модератора", "moderation"),
            ("/lock", self.cmd_lock, "Заблокировать чат", "moderation"),
            ("/unlock", self.cmd_unlock, "Разблокировать чат", "moderation"),
            ("/filter", self.cmd_filter, "Настроить фильтр слов", "moderation"),
            ("/antispam", self.cmd_antispam, "Настройка антиспама", "moderation"),
            ("/report", self.cmd_report, "Пожаловаться на пользователя", "moderation"),
            ("/adminlog", self.cmd_adminlog, "Лог действий администрации", "moderation"),
            ("/cleanup", self.cmd_cleanup, "Очистка истории", "moderation"),

            # Информационные (30 команд)
            ("/help", self.cmd_help, "Помощь по командам", "info"),
            ("/info", self.cmd_info, "Информация о пользователе", "info"),
            ("/chat", self.cmd_chat, "Информация о чате", "info"),
            ("/stats", self.cmd_stats, "Статистика чата", "info"),
            ("/users", self.cmd_users, "Список пользователей", "info"),
            ("/online", self.cmd_online, "Онлайн пользователи", "info"),
            ("/time", self.cmd_time, "Текущее время", "info"),
            ("/date", self.cmd_date, "Текущая дата", "info"),
            ("/weather", self.cmd_weather, "Погода", "info"),
            ("/news", self.cmd_news, "Новости", "info"),
            ("/ping", self.cmd_ping, "Пинг", "info"),
            ("/uptime", self.cmd_uptime, "Время работы", "info"),
            ("/version", self.cmd_version, "Версия бота", "info"),
            ("/about", self.cmd_about, "О боте", "info"),
            ("/commands", self.cmd_commands, "Список команд", "info"),
            ("/permissions", self.cmd_permissions, "Ваши права", "info"),
            ("/rank", self.cmd_rank, "Ваш ранг", "info"),
            ("/top", self.cmd_top, "Топ пользователей", "info"),
            ("/levels", self.cmd_levels, "Уровни пользователей", "info"),
            ("/achivements", self.cmd_achievements, "Достижения", "info"),
            ("/profile", self.cmd_profile, "Ваш профиль", "info"),
            ("/whois", self.cmd_whois, "Кто это?", "info"),
            ("/id", self.cmd_id, "ID пользователя", "info"),
            ("/group", self.cmd_group, "Информация о группе", "info"),
            ("/invite", self.cmd_invite, "Пригласить в чат", "info"),
            ("/settings", self.cmd_settings, "Настройки чата", "info"),
            ("/banned", self.cmd_banned, "Список забаненных", "info"),
            ("/muted", self.cmd_muted, "Список замученных", "info"),
            ("/warnings", self.cmd_warnings, "Ваши предупреждения", "info"),
            ("/trust", self.cmd_trust, "Уровень доверия", "info"),

            # Развлечения (40 команд)
            ("/roll", self.cmd_roll, "Бросок кубика", "fun"),
            ("/coin", self.cmd_coin, "Орёл или решка", "fun"),
            ("/8ball", self.cmd_8ball, "Магический шар", "fun"),
            ("/quote", self.cmd_quote, "Цитата дня", "fun"),
            ("/joke", self.cmd_joke, "Шутка", "fun"),
            ("/meme", self.cmd_meme, "Мем", "fun"),
            ("/rps", self.cmd_rps, "Камень-ножницы-бумага", "fun"),
            ("/guess", self.cmd_guess, "Угадай число", "fun"),
            ("/trivia", self.cmd_trivia, "Викторина", "fun"),
            ("/quiz", self.cmd_quiz, "Опрос", "fun"),
            ("/poll", self.cmd_poll, "Создать опрос", "fun"),
            ("/vote", self.cmd_vote, "Голосовать", "fun"),
            ("/result", self.cmd_result, "Результаты опроса", "fun"),
            ("/dice", self.cmd_dice, "Бросить кости", "fun"),
            ("/slots", self.cmd_slots, "Игровой автомат", "fun"),
            ("/blackjack", self.cmd_blackjack, "Блэкджек", "fun"),
            ("/roulette", self.cmd_roulette, "Русская рулетка", "fun"),
            ("/battle", self.cmd_battle, "Битва", "fun"),
            ("/duel", self.cmd_duel, "Дуэль", "fun"),
            ("/race", self.cmd_race, "Гонка", "fun"),
            ("/shop", self.cmd_shop, "Магазин", "fun"),
            ("/buy", self.cmd_buy, "Купить", "fun"),
            ("/sell", self.cmd_sell, "Продать", "fun"),
            ("/inventory", self.cmd_inventory, "Инвентарь", "fun"),
            ("/daily", self.cmd_daily, "Ежедневный бонус", "fun"),
            ("/weekly", self.cmd_weekly, "Еженедельный бонус", "fun"),
            ("/guessword", self.cmd_guessword, "Угадай слово", "fun"),
            ("/hangman", self.cmd_hangman, "Виселица", "fun"),
            ("/tictac", self.cmd_tictac, "Крестики-нолики", "fun"),
            ("/chess", self.cmd_chess, "Шахматы", "fun"),
            ("/checkers", self.cmd_checkers, "Шашки", "fun"),
            ("/cards", self.cmd_cards, "Карты", "fun"),
            ("/bingo", self.cmd_bingo, "Бинго", "fun"),
            ("/lottery", self.cmd_lottery, "Лотерея", "fun"),
            ("/gamble", self.cmd_gamble, "Сделать ставку", "fun"),
            ("/casino", self.cmd_casino, "Казино", "fun"),
            ("/horoscope", self.cmd_horoscope, "Гороскоп", "fun"),
            ("/zodiac", self.cmd_zodiac, "Знак зодиака", "fun"),
            ("/tarot", self.cmd_tarot, "Карты Таро", "fun"),
            ("/fortune", self.cmd_fortune, "Предсказание", "fun"),

            # Утилиты (35 команд)
            ("/calc", self.cmd_calc, "Калькулятор", "utils"),
            ("/convert", self.cmd_convert, "Конвертер валют", "utils"),
            ("/translate", self.cmd_translate, "Переводчик", "utils"),
            ("/qr", self.cmd_qr, "Создать QR-код", "utils"),
            ("/shorten", self.cmd_shorten, "Сократить ссылку", "utils"),
            ("/weather", self.cmd_weather, "Погода", "utils"),
            ("/currency", self.cmd_currency, "Курс валют", "utils"),
            ("/math", self.cmd_math, "Математика", "utils"),
            ("/random", self.cmd_random, "Случайное число", "utils"),
            ("/pick", self.cmd_pick, "Выбрать из списка", "utils"),
            ("/shuffle", self.cmd_shuffle, "Перемешать", "utils"),
            ("/sort", self.cmd_sort, "Отсортировать", "utils"),
            ("/reverse", self.cmd_reverse, "Перевернуть текст", "utils"),
            ("/uppercase", self.cmd_uppercase, "В верхний регистр", "utils"),
            ("/lowercase", self.cmd_lowercase, "В нижний регистр", "utils"),
            ("/capitalize", self.cmd_capitalize, "С большой буквы", "utils"),
            ("/count", self.cmd_count, "Подсчитать символы", "utils"),
            ("/wordcount", self.cmd_wordcount, "Подсчитать слова", "utils"),
            ("/timer", self.cmd_timer, "Таймер", "utils"),
            ("/stopwatch", self.cmd_stopwatch, "Секундомер", "utils"),
            ("/remind", self.cmd_remind, "Напомнить", "utils"),
            ("/todo", self.cmd_todo, "Список дел", "utils"),
            ("/note", self.cmd_note, "Заметка", "utils"),
            ("/poll", self.cmd_poll, "Опрос", "utils"),
            ("/feedback", self.cmd_feedback, "Обратная связь", "utils"),
            ("/suggest", self.cmd_suggest, "Предложение", "utils"),
            ("/bug", self.cmd_bug, "Сообщить об ошибке", "utils"),
            ("/idea", self.cmd_idea, "Идея", "utils"),
            ("/support", self.cmd_support, "Поддержка", "utils"),
            ("/faq", self.cmd_faq, "Частые вопросы", "utils"),
            ("/url", self.cmd_url, "Проверить ссылку", "utils"),
            ("/hash", self.cmd_hash, "Хешировать текст", "utils"),
            ("/encode", self.cmd_encode, "Кодировать", "utils"),
            ("/decode", self.cmd_decode, "Декодировать", "utils"),
            ("/password", self.cmd_password, "Сгенерировать пароль", "utils"),

            # Социальные (25 команд)
            ("/hello", self.cmd_hello, "Поздороваться", "social"),
            ("/hi", self.cmd_hi, "Сказать привет", "social"),
            ("/bye", self.cmd_bye, "Попрощаться", "social"),
            ("/thanks", self.cmd_thanks, "Поблагодарить", "social"),
            ("/sorry", self.cmd_sorry, "Извиниться", "social"),
            ("/congrats", self.cmd_congrats, "Поздравить", "social"),
            ("/welcome", self.cmd_welcome, "Приветствовать", "social"),
            ("/hug", self.cmd_hug, "Обнять", "social"),
            ("/kiss", self.cmd_kiss, "Поцеловать", "social"),
            ("/pat", self.cmd_pat, "Погладить", "social"),
            ("/poke", self.cmd_poke, "Ткнуть", "social"),
            ("/slap", self.cmd_slap, "Дать пощёчину", "social"),
            ("/highfive", self.cmd_highfive, "Дай пять", "social"),
            ("/fistbump", self.cmd_fistbump, "Кулак", "social"),
            ("/bro", self.cmd_bro, "Бро", "social"),
            ("/sister", self.cmd_sister, "Сестра", "social"),
            ("/friend", self.cmd_friend, "Друг", "social"),
            ("/love", self.cmd_love, "Любовь", "social"),
            ("/hate", self.cmd_hate, "Ненависть", "social"),
            ("/angry", self.cmd_angry, "Злой", "social"),
            ("/happy", self.cmd_happy, "Счастливый", "social"),
            ("/sad", self.cmd_sad, "Грустный", "social"),
            ("/tired", self.cmd_tired, "Уставший", "social"),
            ("/bored", self.cmd_bored, "Скучающий", "social"),
            ("/excited", self.cmd_excited, "Взволнованный", "social"),

            # Медиа (20 команд)
            ("/image", self.cmd_image, "Поиск картинки", "media"),
            ("/gif", self.cmd_gif, "Поиск гифки", "media"),
            ("/video", self.cmd_video, "Поиск видео", "media"),
            ("/music", self.cmd_music, "Поиск музыки", "media"),
            ("/youtube", self.cmd_youtube, "YouTube видео", "media"),
            ("/instagram", self.cmd_instagram, "Instagram", "media"),
            ("/twitter", self.cmd_twitter, "Twitter", "media"),
            ("/reddit", self.cmd_reddit, "Reddit", "media"),
            ("/pinterest", self.cmd_pinterest, "Pinterest", "media"),
            ("/soundcloud", self.cmd_soundcloud, "SoundCloud", "media"),
            ("/spotify", self.cmd_spotify, "Spotify", "media"),
            ("/netflix", self.cmd_netflix, "Netflix", "media"),
            ("/prime", self.cmd_prime, "Amazon Prime", "media"),
            ("/hulu", self.cmd_hulu, "Hulu", "media"),
            ("/disney", self.cmd_disney, "Disney+", "media"),
            ("/hbo", self.cmd_hbo, "HBO Max", "media"),
            ("/peacock", self.cmd_peacock, "Peacock", "media"),
            ("/paramount", self.cmd_paramount, "Paramount+", "media"),
            ("/apple", self.cmd_apple, "Apple TV+", "media"),
            ("/crunchyroll", self.cmd_crunchyroll, "Crunchyroll", "media"),

            # Игры (25 команд)
            ("/game", self.cmd_game, "Начать игру", "games"),
            ("/join", self.cmd_join, "Присоединиться к игре", "games"),
            ("/leave", self.cmd_leave, "Покинуть игру", "games"),
            ("/start", self.cmd_start, "Начать", "games"),
            ("/stop", self.cmd_stop, "Остановить", "games"),
            ("/pause", self.cmd_pause, "Пауза", "games"),
            ("/resume", self.cmd_resume, "Продолжить", "games"),
            ("/move", self.cmd_move, "Сделать ход", "games"),
            ("/roll", self.cmd_roll, "Бросить кости", "games"),
            ("/score", self.cmd_score, "Счёт", "games"),
            ("/winner", self.cmd_winner, "Победитель", "games"),
            ("/leaderboard", self.cmd_leaderboard, "Таблица лидеров", "games"),
            ("/achievement", self.cmd_achievement, "Достижения", "games"),
            ("/quest", self.cmd_quest, "Квест", "games"),
            ("/daily", self.cmd_daily, "Ежедневное задание", "games"),
            ("/weekly", self.cmd_weekly, "Еженедельное задание", "games"),
            ("/challenge", self.cmd_challenge, "Вызов", "games"),
            ("/accept", self.cmd_accept, "Принять вызов", "games"),
            ("/decline", self.cmd_decline, "Отклонить вызов", "games"),
            ("/team", self.cmd_team, "Команда", "games"),
            ("/teams", self.cmd_teams, "Список команд", "games"),
            ("/captain", self.cmd_captain, "Капитан", "games"),
            ("/strategy", self.cmd_strategy, "Стратегия", "games"),
            ("/tactics", self.cmd_tactics, "Тактика", "games"),
            ("/gg", self.cmd_gg, "Хорошая игра", "games"),

            # Экономика (20 команд)
            ("/balance", self.cmd_balance, "Баланс", "economy"),
            ("/money", self.cmd_money, "Деньги", "economy"),
            ("/earn", self.cmd_earn, "Заработать", "economy"),
            ("/pay", self.cmd_pay, "Перевести", "economy"),
            ("/bank", self.cmd_bank, "Банк", "economy"),
            ("/deposit", self.cmd_deposit, "Внести", "economy"),
            ("/withdraw", self.cmd_withdraw, "Снять", "economy"),
            ("/interest", self.cmd_interest, "Проценты", "economy"),
            ("/loan", self.cmd_loan, "Кредит", "economy"),
            ("/invest", self.cmd_invest, "Инвестировать", "economy"),
            ("/stock", self.cmd_stock, "Акции", "economy"),
            ("/trade", self.cmd_trade, "Торговать", "economy"),
            ("/market", self.cmd_market, "Рынок", "economy"),
            ("/price", self.cmd_price, "Цена", "economy"),
            ("/buy", self.cmd_buy, "Купить", "economy"),
            ("/sell", self.cmd_sell, "Продать", "economy"),
            ("/auction", self.cmd_auction, "Аукцион", "economy"),
            ("/bid", self.cmd_bid, "Ставка", "economy"),
            ("/wallet", self.cmd_wallet, "Кошелёк", "economy"),
            ("/transaction", self.cmd_transaction, "Транзакция", "economy"),

            # Системные (20 команд)
            ("/reload", self.cmd_reload, "Перезагрузить бота", "system"),
            ("/restart", self.cmd_restart, "Перезапустить", "system"),
            ("/update", self.cmd_update, "Обновить", "system"),
            ("/backup", self.cmd_backup, "Создать бэкап", "system"),
            ("/restore", self.cmd_restore, "Восстановить", "system"),
            ("/sync", self.cmd_sync, "Синхронизировать", "system"),
            ("/status", self.cmd_status, "Статус", "system"),
            ("/health", self.cmd_health, "Здоровье", "system"),
            ("/memory", self.cmd_memory, "Память", "system"),
            ("/cpu", self.cmd_cpu, "CPU", "system"),
            ("/info", self.cmd_info, "Информация", "system"),
            ("/logs", self.cmd_logs, "Логи", "system"),
            ("/errors", self.cmd_errors, "Ошибки", "system"),
            ("/warnings", self.cmd_warnings, "Предупреждения", "system"),
            ("/debug", self.cmd_debug, "Отладка", "system"),
            ("/test", self.cmd_test, "Тест", "system"),
            ("/benchmark", self.cmd_benchmark, "Тест производительности", "system"),
            ("/config", self.cmd_config, "Конфигурация", "system"),
            ("/env", self.cmd_env, "Переменные окружения", "system"),
            ("/secret", self.cmd_secret, "Секреты", "system"),

            # Дополнительные (35 команд)
            ("/alarm", self.cmd_alarm, "Будильник", "extra"),
            ("/calendar", self.cmd_calendar, "Календарь", "extra"),
            ("/schedule", self.cmd_schedule, "Расписание", "extra"),
            ("/reminder", self.cmd_reminder, "Напоминание", "extra"),
            ("/birthday", self.cmd_birthday, "День рождения", "extra"),
            ("/age", self.cmd_age, "Возраст", "extra"),
            ("/zodiac", self.cmd_zodiac, "Знак зодиака", "extra"),
            ("/horoscope", self.cmd_horoscope, "Гороскоп", "extra"),
            ("/tarot", self.cmd_tarot, "Таро", "extra"),
            ("/numerology", self.cmd_numerology, "Нумерология", "extra"),
            ("/astrology", self.cmd_astrology, "Астрология", "extra"),
            ("/mbti", self.cmd_mbti, "Тест MBTI", "extra"),
            ("/iq", self.cmd_iq, "Тест IQ", "extra"),
            ("/personality", self.cmd_personality, "Тест личности", "extra"),
            ("/compatibility", self.cmd_compatibility, "Совместимость", "extra"),
            ("/lovecalc", self.cmd_lovecalc, "Калькулятор любви", "extra"),
            ("/relationship", self.cmd_relationship, "Отношения", "extra"),
            ("/friendship", self.cmd_friendship, "Дружба", "extra"),
            ("/enemy", self.cmd_enemy, "Враг", "extra"),
            ("/rival", self.cmd_rival, "Соперник", "extra"),
            ("/mentor", self.cmd_mentor, "Наставник", "extra"),
            ("/student", self.cmd_student, "Ученик", "extra"),
            ("/teacher", self.cmd_teacher, "Учитель", "extra"),
            ("/colleague", self.cmd_colleague, "Коллега", "extra"),
            ("/partner", self.cmd_partner, "Партнер", "extra"),
            ("/family", self.cmd_family, "Семья", "extra"),
            ("/pet", self.cmd_pet, "Питомец", "extra"),
            ("/plant", self.cmd_plant, "Растение", "extra"),
            ("/food", self.cmd_food, "Еда", "extra"),
            ("/drink", self.cmd_drink, "Напиток", "extra"),
            ("/recipe", self.cmd_recipe, "Рецепт", "extra"),
            ("/restaurant", self.cmd_restaurant, "Ресторан", "extra"),
            ("/travel", self.cmd_travel, "Путешествие", "extra"),
            ("/hotel", self.cmd_hotel, "Отель", "extra"),
            ("/flight", self.cmd_flight, "Авиарейс", "extra"),
        ]

        for cmd, handler, desc, category in commands:
            self.commands[cmd] = {"handler": handler, "desc": desc, "category": category}

    # ----- Вспомогательные методы -----
    def is_admin(self, user_id: int) -> bool:
        return self.user_roles.get(user_id) in ["admin", "owner"]

    def is_mod(self, user_id: int) -> bool:
        return self.user_roles.get(user_id) in ["mod", "admin", "owner"]

    def is_owner(self, user_id: int) -> bool:
        return self.user_roles.get(user_id) == "owner"

    def is_muted(self, user_id: int) -> bool:
        if user_id in self.mute_timers:
            if time.time() < self.mute_timers[user_id]:
                return True
            else:
                del self.mute_timers[user_id]
        return False

    def add_points(self, user_id: int, points: int):
        self.points[user_id] += points
        new_level = self.calculate_level(self.points[user_id])
        if new_level > self.levels[user_id]:
            self.levels[user_id] = new_level
            return True
        return False

    def calculate_level(self, points: int) -> int:
        return int(points / 100) + 1

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

    def get_user_info(self, user_id: int) -> Dict[str, Any]:
        response = self.api_request(
            "users.get",
            user_ids=user_id,
            fields="photo_100,online,last_seen,sex,bdate,city,country,status"
        )
        if response and "error" not in response:
            return response[0]
        return {}

    # ----- Обработчики команд (выборочно, для примера) -----
    def cmd_help(self, args: List[str], user_id: int, chat_id: int) -> str:
        categories = defaultdict(list)
        for cmd, info in self.commands.items():
            categories[info["category"]].append(f"{cmd} - {info['desc']}")
        help_text = "📚 *Список команд*\n\n"
        for category, cmds in categories.items():
            help_text += f"*{category.upper()}*\n"
            for cmd in cmds[:5]:
                help_text += f"  {cmd}\n"
            help_text += f"  ... и еще {len(cmds)-5} команд\n\n"
        help_text += "Введите /commands {категория} для полного списка"
        return help_text

    def cmd_commands(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Укажите категорию: moderation, info, fun, utils, social, media, games, economy, system, extra"
        category = args[0].lower()
        cmds = [f"{cmd} - {info['desc']}" for cmd, info in self.commands.items() if info["category"] == category]
        if not cmds:
            return f"Категория '{category}' не найдена"
        return f"*{category.upper()}* команды:\n" + "\n".join(cmds)

    def cmd_roll(self, args: List[str], user_id: int, chat_id: int) -> str:
        sides = 6
        if args and args[0].isdigit():
            sides = int(args[0])
        if sides < 2:
            sides = 2
        if sides > 100:
            sides = 100
        result = random.randint(1, sides)
        return f"🎲 Бросок кубика (1-{sides}): **{result}**"

    def cmd_coin(self, args: List[str], user_id: int, chat_id: int) -> str:
        result = random.choice(["🦅 Орёл", "🪙 Решка"])
        return f"Монетка упала: {result}"

    def cmd_8ball(self, args: List[str], user_id: int, chat_id: int) -> str:
        answers = ["Определённо да", "Без сомнения", "Вероятно", "Да",
                   "Нет", "Не сейчас", "Возможно", "Спроси позже",
                   "Туманно", "Абсолютно нет", "Точно да", "Очень сомнительно"]
        return f"🔮 Магический шар говорит: {random.choice(answers)}"

    def cmd_joke(self, args: List[str], user_id: int, chat_id: int) -> str:
        jokes = ["Почему программисты путают Хэллоуин и Рождество? 31 OCT = 25 DEC",
                 "Сколько программистов нужно, чтобы заменить лампочку? Ни одного",
                 "Почему компьютеры не могут пить кофе? Боятся Java-атаки"]
        return f"😂 {random.choice(jokes)}"

    def cmd_quote(self, args: List[str], user_id: int, chat_id: int) -> str:
        quotes = ["Жизнь - это то, что происходит с тобой, пока ты строишь планы",
                  "Будь изменением, которое хочешь видеть в мире",
                  "Великие умы обсуждают идеи, средние - события, маленькие - людей"]
        return f"📝 *Цитата дня:*\n{random.choice(quotes)}"

    def cmd_calc(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Введите выражение: /calc 2 + 2"
        expression = " ".join(args)
        try:
            allowed = set("0123456789+-*/() .")
            if not set(expression).issubset(allowed):
                return "❌ Недопустимые символы"
            result = eval(expression)
            return f"🧮 {expression} = {result}"
        except Exception:
            return "❌ Ошибка в выражении"

    def cmd_random(self, args: List[str], user_id: int, chat_id: int) -> str:
        if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
            start = int(args[0])
            end = int(args[1])
            if start <= end:
                return f"🎲 Случайное число: {random.randint(start, end)}"
        return "🎲 Случайное число: " + str(random.randint(1, 100))

    def cmd_time(self, args: List[str], user_id: int, chat_id: int) -> str:
        now = datetime.now()
        return f"🕐 Текущее время: {now.strftime('%H:%M:%S')}\nДата: {now.strftime('%d.%m.%Y')}"

    def cmd_weather(self, args: List[str], user_id: int, chat_id: int) -> str:
        city = " ".join(args) if args else "Москва"
        return f"🌤 Погода в {city}:\nТемпература: +22°C\nВлажность: 65%\nВетер: 5 м/с\n\n(Данные демонстрационные)"

    def cmd_ping(self, args: List[str], user_id: int, chat_id: int) -> str:
        start = time.time()
        self.api_request("messages.get", count=1)
        end = time.time()
        return f"🏓 Понг! Задержка: {round((end - start) * 1000)} мс"

    def cmd_uptime(self, args: List[str], user_id: int, chat_id: int) -> str:
        uptime_seconds = time.time() - self.start_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"⏱ Бот работает: {days}д {hours}ч {minutes}м"

    def cmd_balance(self, args: List[str], user_id: int, chat_id: int) -> str:
        return f"💰 Ваш баланс: {self.points[user_id]} монет"

    def cmd_daily(self, args: List[str], user_id: int, chat_id: int) -> str:
        bonus = random.randint(50, 150)
        self.add_points(user_id, bonus)
        return f"🎁 Ежедневный бонус: {bonus} монет"

    def cmd_profile(self, args: List[str], user_id: int, chat_id: int) -> str:
        profile = f"👤 *Ваш профиль*\nID: {user_id}\nРоль: {self.user_roles.get(user_id, 'Пользователь')}\nУровень: {self.levels[user_id]}\nОчков: {self.points[user_id]}\nСообщений: {self.message_count[user_id]}"
        return profile

    def cmd_info(self, args: List[str], user_id: int, chat_id: int) -> str:
        target = args[0] if args else str(user_id)
        target_id = int(target) if target.isdigit() else user_id
        user_info = self.get_user_info(target_id)
        if not user_info:
            return "❌ Не удалось получить информацию"
        info_text = f"👤 *Информация о пользователе*\nИмя: {user_info.get('first_name', '')} {user_info.get('last_name', '')}\nID: {user_info.get('id', '')}\nСтатус: {'Онлайн' if user_info.get('online', 0) else 'Офлайн'}"
        return info_text

    def cmd_rank(self, args: List[str], user_id: int, chat_id: int) -> str:
        role = self.user_roles.get(user_id, "user")
        points = self.points[user_id]
        level = self.levels[user_id]
        ranks = {"owner": "👑 Владелец", "admin": "🛡 Администратор", "mod": "🔰 Модератор", "user": "👤 Пользователь"}
        return f"Ваш ранг: {ranks.get(role, 'Пользователь')}\nУровень: {level}\nОчков: {points}"

    def cmd_hi(self, args: List[str], user_id: int, chat_id: int) -> str:
        return "👋 Привет!"

    def cmd_bye(self, args: List[str], user_id: int, chat_id: int) -> str:
        return "👋 Пока! Заходи ещё!"

    def cmd_thanks(self, args: List[str], user_id: int, chat_id: int) -> str:
        return "🙏 Пожалуйста! Всегда рад помочь!"

    def cmd_sorry(self, args: List[str], user_id: int, chat_id: int) -> str:
        return "🙇‍♂️ Ничего страшного! Всё бывает."

    def cmd_hug(self, args: List[str], user_id: int, chat_id: int) -> str:
        if args:
            return f"🤗 Обнимаю {args[0]}"
        return "🤗 Отправляю виртуальные объятия!"

    def cmd_kick(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите пользователя: /kick [id|@] [причина]"
        return "✅ Пользователь выгнан (демонстрация)"

    def cmd_mute(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите пользователя: /mute [id|@] [время]"
        return "✅ Пользователь замучен (демонстрация)"

    def cmd_warn(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите пользователя: /warn [id|@] [причина]"
        return "⚠️ Предупреждение выдано (демонстрация)"

    def cmd_clear(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        count = 20
        if args and args[0].isdigit():
            count = min(int(args[0]), 100)
        return f"🧹 Очищено {count} сообщений (демонстрация)"

    def cmd_rules(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.rules:
            return "ℹ️ Правила не установлены"
        text = "📜 *Правила чата:*\n\n"
        for i, rule in enumerate(self.rules, 1):
            text += f"{i}. {rule}\n"
        return text

    def cmd_addrule(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите правило"
        rule = " ".join(args)
        self.rules.append(rule)
        return f"✅ Правило добавлено: {rule}"

    def cmd_removerule(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if not args or not args[0].isdigit():
            return "Укажите номер правила: /removerule [номер]"
        idx = int(args[0]) - 1
        if idx < 0 or idx >= len(self.rules):
            return "❌ Неверный номер правила"
        removed = self.rules.pop(idx)
        return f"✅ Правило удалено: {removed}"

    def cmd_setwelcome(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите текст приветствия"
        text = " ".join(args)
        self.settings["welcome_message"] = text
        return f"✅ Приветствие установлено:\n{text}"

    def cmd_setleave(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите текст прощания"
        text = " ".join(args)
        self.settings["leave_message"] = text
        return f"✅ Прощание установлено:\n{text}"

    def cmd_slowmode(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if args and args[0].lower() == "off":
            self.settings["slow_mode"] = False
            return "✅ Медленный режим отключен"
        delay = 3
        if args and args[0].isdigit():
            delay = int(args[0])
        self.settings["slow_mode"] = True
        self.settings["slow_mode_delay"] = delay
        return f"✅ Медленный режим включен (задержка {delay} сек)"

    def cmd_online(self, args: List[str], user_id: int, chat_id: int) -> str:
        return "👥 Онлайн: 15 пользователей (демонстрационные данные)"

    def cmd_stats(self, args: List[str], user_id: int, chat_id: int) -> str:
        stats = f"📊 *Статистика чата*\nСообщений: {self.message_count[user_id]}\nОчков: {self.points[user_id]}\nУровень: {self.levels[user_id]}\nДостижений: {len(self.achievements[user_id])}"
        return stats

    def cmd_lovecalc(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Укажите имя: /lovecalc [имя]"
        name = " ".join(args)
        love_percent = random.randint(0, 100)
        text = f"❤️ *Калькулятор любви*\n\nВас и {name} связывает {love_percent}% любви\n"
        if love_percent >= 80:
            text += "🔥 Искренняя и сильная любовь!"
        elif love_percent >= 60:
            text += "💕 Взаимная симпатия!"
        elif love_percent >= 40:
            text += "💭 Вы можете стать хорошими друзьями"
        else:
            text += "😅 Вам стоит узнать друг друга лучше"
        return text

    def cmd_horoscope(self, args: List[str], user_id: int, chat_id: int) -> str:
        zodiacs = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
                   "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
        zodiac = args[0] if args else random.choice(zodiacs)
        fortunes = ["🌟 Сегодня звёзды благоволят вам!",
                    "🌙 День будет удачным для новых начинаний",
                    "⭐ Ожидайте приятных сюрпризов"]
        return f"♈ *Гороскоп для {zodiac}*\n\n{random.choice(fortunes)}"

    def cmd_birthday(self, args: List[str], user_id: int, chat_id: int) -> str:
        if args:
            return f"🎂 С днём рождения, {args[0]}!"
        return "🎂 Когда у вас день рождения? Напишите /birthday [дата]"

    def cmd_game(self, args: List[str], user_id: int, chat_id: int) -> str:
        game_id = f"game_{int(time.time())}"
        self.game_sessions[game_id] = {
            "players": [user_id],
            "state": "waiting",
            "max_players": 10,
            "chat_id": chat_id
        }
        return f"🎮 Игра создана! ID: {game_id}\nПрисоединяйтесь: /join {game_id}"

    def cmd_join(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Укажите ID игры: /join [game_id]"
        game_id = args[0]
        if game_id not in self.game_sessions:
            return "❌ Игра не найдена"
        game = self.game_sessions[game_id]
        if user_id in game["players"]:
            return "ℹ️ Вы уже в игре"
        if len(game["players"]) >= game["max_players"]:
            return "❌ Игра заполнена"
        game["players"].append(user_id)
        return f"✅ Вы присоединились к игре! ({len(game['players'])}/{game['max_players']})"

    def cmd_leaderboard(self, args: List[str], user_id: int, chat_id: int) -> str:
        sorted_users = sorted(self.points.items(), key=lambda x: x[1], reverse=True)[:10]
        if not sorted_users:
            return "ℹ️ Нет данных для таблицы лидеров"
        text = "🏆 *Таблица лидеров*\n\n"
        for i, (uid, points) in enumerate(sorted_users, 1):
            user_info = self.get_user_info(uid)
            name = user_info.get('first_name', f'User{uid}') if user_info else f'User{uid}'
            text += f"{i}. {name} - {points} очков\n"
        return text

    def cmd_pay(self, args: List[str], user_id: int, chat_id: int) -> str:
        if len(args) < 2:
            return "Использование: /pay [пользователь] [сумма]"
        target = args[0]
        amount = int(args[1])
        if not target.isdigit():
            return "❌ Укажите ID пользователя"
        target_id = int(target)
        if target_id == user_id:
            return "❌ Нельзя перевести себе"
        if amount <= 0:
            return "❌ Сумма должна быть положительной"
        if self.points[user_id] < amount:
            return f"❌ Недостаточно монет. У вас: {self.points[user_id]}"
        self.points[user_id] -= amount
        self.points[target_id] += amount
        return f"✅ Переведено {amount} монет пользователю"

    def cmd_gamble(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args or not args[0].isdigit():
            return "Укажите сумму: /gamble [сумма]"
        amount = int(args[0])
        if self.points[user_id] < amount:
            return f"❌ Недостаточно монет. У вас: {self.points[user_id]}"
        multiplier = random.choice([0, 0.5, 1, 2])
        result = int(amount * multiplier)
        self.points[user_id] += result - amount
        if result > amount:
            return f"🎉 Вы выиграли! {result} монет (+{result-amount})"
        elif result == amount:
            return "🤝 Ваша ставка вернулась"
        else:
            return f"😢 Вы проиграли {amount-result} монет"

    def cmd_afk(self, args: List[str], user_id: int, chat_id: int) -> str:
        if args:
            self.afk_users[user_id] = {"time": time.time(), "reason": " ".join(args)}
            return f"🔇 Вы AFK: {self.afk_users[user_id]['reason']}"
        self.afk_users[user_id] = {"time": time.time(), "reason": "Не беспокоить"}
        return "🔇 Вы AFK"

    def cmd_notafk(self, args: List[str], user_id: int, chat_id: int) -> str:
        if user_id in self.afk_users:
            del self.afk_users[user_id]
            return "🔊 Вы снова активны"
        return "ℹ️ Вы не были AFK"

    def cmd_echo(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Напишите что-то для повтора"
        return " ".join(args)

    def cmd_reverse(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Введите текст для переворота"
        text = " ".join(args)
        return text[::-1]

    def cmd_uppercase(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Введите текст"
        return " ".join(args).upper()

    def cmd_lowercase(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Введите текст"
        return " ".join(args).lower()

    def cmd_count(self, args: List[str], user_id: int, chat_id: int) -> str:
        if not args:
            return "Введите текст"
        text = " ".join(args)
        return f"Символов: {len(text)}\nСлов: {len(text.split())}"

    # ----- Заглушки для всех остальных команд (чтобы не было AttributeError) -----
    def __getattr__(self, name):
        # Если вызывается метод, начинающийся с cmd_, но не найден, возвращаем заглушку
        if name.startswith("cmd_"):
            return lambda args, user_id, chat_id: f"Команда {name[4:]} в разработке (демонстрация)"
        raise AttributeError(f"{name} not found")

    # ----- Основной цикл обработки сообщений -----
    def process_message(self, message: Dict[str, Any]) -> Optional[str]:
        if "text" not in message:
            return None
        text = message["text"].strip()
        user_id = message.get("from_id", 0)
        chat_id = message.get("peer_id", 0)
        if not text or not user_id:
            return None

        # Mute check
        if self.is_muted(user_id):
            return None

        # Slow mode
        if self.settings["slow_mode"]:
            current_time = time.time()
            if user_id in self.last_message_time:
                if current_time - self.last_message_time[user_id] < self.settings["slow_mode_delay"]:
                    return None
            self.last_message_time[user_id] = current_time

        # Command handling
        if text.startswith('/'):
            parts = text.split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            if command in self.commands:
                handler = self.commands[command]["handler"]
                if callable(handler):
                    try:
                        result = handler(args, user_id, chat_id)
                        if result:
                            self.send_message(chat_id, result)
                    except Exception as e:
                        logger.error(f"Error executing command {command}: {e}")
                        self.send_message(chat_id, f"❌ Ошибка выполнения команды")
                return None

        # Points for activity
        if len(text) > 3 and random.random() < 0.1:
            points = random.randint(1, 3)
            self.add_points(user_id, points)
            self.message_count[user_id] += 1

        return None

    def run(self):
        logger.info("Бот запущен и готов к работе")
        while True:
            try:
                response = self.api_request("messages.get", count=20)
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
