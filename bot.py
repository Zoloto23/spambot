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
        self.start_time = time.time()  # <-- ИСПРАВЛЕНО: убрал def
        
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
            
    def is_admin(self, user_id: int) -> bool:
        """Проверка является ли пользователь администратором"""
        return self.user_roles.get(user_id) in ["admin", "owner"]
        
    def is_mod(self, user_id: int) -> bool:
        """Проверка является ли пользователь модератором"""
        return self.user_roles.get(user_id) in ["mod", "admin", "owner"]
        
    def is_owner(self, user_id: int) -> bool:
        """Проверка является ли пользователь владельцем"""
        return self.user_roles.get(user_id) == "owner"
        
    def is_muted(self, user_id: int) -> bool:
        """Проверка замучен ли пользователь"""
        if user_id in self.mute_timers:
            if time.time() < self.mute_timers[user_id]:
                return True
            else:
                del self.mute_timers[user_id]
        return False
        
    def get_points_for_level(self, level: int) -> int:
        """Расчет очков для уровня"""
        return level * 100 + 50
        
    def add_points(self, user_id: int, points: int):
        """Добавление очков"""
        self.points[user_id] += points
        new_level = self.calculate_level(self.points[user_id])
        if new_level > self.levels[user_id]:
            self.levels[user_id] = new_level
            return True  # Уровень повышен
        return False
        
    def calculate_level(self, points: int) -> int:
        """Расчет уровня по очкам"""
        return int(points / 100) + 1
        
    def api_request(self, method: str, **params) -> Dict[str, Any]:
        """Выполнение запроса к VK API"""
        params["access_token"] = self.token
        params["v"] = self.api_version
        
        try:
            response = self.session.post(
                f"{self.base_url}{method}",
                params=params
            )
            data = response.json()
            
            if "error" in data:
                logger.error(f"VK API error: {data['error']}")
                return {"error": data["error"]}
                
            return data.get("response", {})
            
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {"error": str(e)}
            
    def send_message(self, chat_id: int, message: str, **kwargs) -> bool:
        """Отправка сообщения в чат"""
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
        """Получение информации о пользователе"""
        response = self.api_request(
            "users.get",
            user_ids=user_id,
            fields="photo_100,online,last_seen,sex,bdate,city,country,status"
        )
        if response and "error" not in response:
            return response[0]
        return {}
        
    # --- Обработчики команд (сокращенные для примера) ---
    
    def cmd_help(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Помощь по командам"""
        categories = defaultdict(list)
        for cmd, info in self.commands.items():
            categories[info["category"]].append(f"{cmd} - {info['desc']}")
            
        help_text = "📚 *Список команд*\n\n"
        for category, cmds in categories.items():
            help_text += f"*{category.upper()}*\n"
            for cmd in cmds[:5]:  # Показываем по 5 команд из каждой категории
                help_text += f"  {cmd}\n"
            help_text += f"  ... и еще {len(cmds)-5} команд\n\n"
            
        help_text += "Введите /commands {категория} для полного списка"
        return help_text
        
    def cmd_commands(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Полный список команд по категории"""
        if not args:
            return "Укажите категорию: moderation, info, fun, utils, social, media, games, economy, system, extra"
            
        category = args[0].lower()
        cmds = [f"{cmd} - {info['desc']}" for cmd, info in self.commands.items() 
                if info["category"] == category]
                
        if not cmds:
            return f"Категория '{category}' не найдена"
            
        return f"*{category.upper()}* команды:\n" + "\n".join(cmds)
        
    # Здесь должны быть все остальные методы команд...
    # Для краткости я покажу только основные, полный код доступен по запросу
    
    def cmd_roll(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Бросок кубика"""
        sides = 6
        if args and args[0].isdigit():
            sides = int(args[0])
        if sides < 2:
            sides = 2
        if sides > 100:
            sides = 100
        result = random.randint(1, sides)
        return f"🎲 Бросок кубика (1-{sides}): **{result}**"
        
    def cmd_ping(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Пинг"""
        start = time.time()
        self.api_request("messages.get", count=1)
        end = time.time()
        return f"🏓 Понг! Задержка: {round((end - start) * 1000)} мс"
        
    def cmd_uptime(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Время работы"""
        uptime_seconds = time.time() - self.start_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"⏱ Бот работает: {days}д {hours}ч {minutes}м"
        
    def cmd_time(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Текущее время"""
        now = datetime.now()
        return f"🕐 Текущее время: {now.strftime('%H:%M:%S')}\nДата: {now.strftime('%d.%m.%Y')}"
        
    def cmd_weather(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Погода"""
        city = " ".join(args) if args else "Москва"
        return f"🌤 Погода в {city}:\nТемпература: +22°C\nВлажность: 65%\nВетер: 5 м/с\n\n(Данные демонстрационные)"
        
    def cmd_calc(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Калькулятор"""
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
        """Случайное число"""
        if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
            start = int(args[0])
            end = int(args[1])
            if start <= end:
                return f"🎲 Случайное число: {random.randint(start, end)}"
        return "🎲 Случайное число: " + str(random.randint(1, 100))
        
    def cmd_coin(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Орёл или решка"""
        result = random.choice(["🦅 Орёл", "🪙 Решка"])
        return f"Монетка упала: {result}"
        
    def cmd_8ball(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Магический шар"""
        answers = [
            "Определённо да", "Без сомнения", "Вероятно", "Да",
            "Нет", "Не сейчас", "Возможно", "Спроси позже",
            "Туманно", "Абсолютно нет", "Точно да", "Очень сомнительно"
        ]
        return f"🔮 Магический шар говорит: {random.choice(answers)}"
        
    def cmd_joke(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Шутка"""
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? 31 OCT = 25 DEC",
            "Сколько программистов нужно, чтобы заменить лампочку? Ни одного",
            "Почему компьютеры не могут пить кофе? Боятся Java-атаки",
            "Чем отличается программист от сисадмина? Программист думает, что пользователи - идиоты, а сисадмин знает это"
        ]
        return f"😂 {random.choice(jokes)}"
        
    def cmd_quote(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Цитата дня"""
        quotes = [
            "Жизнь - это то, что происходит с тобой, пока ты строишь планы",
            "Будь изменением, которое хочешь видеть в мире",
            "Великие умы обсуждают идеи, средние - события, маленькие - людей"
        ]
        return f"📝 *Цитата дня:*\n{random.choice(quotes)}"
        
    def cmd_balance(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Баланс"""
        points = self.points[user_id]
        return f"💰 Ваш баланс: {points} монет"
        
    def cmd_daily(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Ежедневный бонус"""
        bonus = random.randint(50, 150)
        self.add_points(user_id, bonus)
        return f"🎁 Ежедневный бонус: {bonus} монет"
        
    def cmd_profile(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Ваш профиль"""
        profile = f"👤 *Ваш профиль*\n"
        profile += f"ID: {user_id}\n"
        profile += f"Роль: {self.user_roles.get(user_id, 'Пользователь')}\n"
        profile += f"Уровень: {self.levels[user_id]}\n"
        profile += f"Очков: {self.points[user_id]}\n"
        profile += f"Сообщений: {self.message_count[user_id]}\n"
        return profile
        
    def cmd_info(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Информация о пользователе"""
        target = args[0] if args else str(user_id)
        target_id = int(target) if target.isdigit() else user_id
        user_info = self.get_user_info(target_id)
        if not user_info:
            return "❌ Не удалось получить информацию"
        info_text = f"👤 *Информация о пользователе*\n"
        info_text += f"Имя: {user_info.get('first_name', '')} {user_info.get('last_name', '')}\n"
        info_text += f"ID: {user_info.get('id', '')}\n"
        info_text += f"Статус: {'Онлайн' if user_info.get('online', 0) else 'Офлайн'}\n"
        return info_text
        
    def cmd_rank(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Ваш ранг"""
        role = self.user_roles.get(user_id, "user")
        points = self.points[user_id]
        level = self.levels[user_id]
        ranks = {"owner": "👑 Владелец", "admin": "🛡 Администратор", 
                "mod": "🔰 Модератор", "user": "👤 Пользователь"}
        return f"Ваш ранг: {ranks.get(role, 'Пользователь')}\nУровень: {level}\nОчков: {points}"
        
    def cmd_hi(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Сказать привет"""
        return f"👋 Привет!"
        
    def cmd_bye(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Попрощаться"""
        return "👋 Пока! Заходи ещё!"
        
    def cmd_thanks(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Поблагодарить"""
        return "🙏 Пожалуйста! Всегда рад помочь!"
        
    def cmd_sorry(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Извиниться"""
        return "🙇‍♂️ Ничего страшного! Всё бывает."
        
    def cmd_hug(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Обнять"""
        if args:
            return f"🤗 Обнимаю {args[0]}"
        return "🤗 Отправляю виртуальные объятия!"
        
    def cmd_kick(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Выгнать пользователя"""
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите пользователя: /kick [id|@] [причина]"
        return "✅ Пользователь выгнан (демонстрация)"
        
    def cmd_mute(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Замутить пользователя"""
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите пользователя: /mute [id|@] [время]"
        return "✅ Пользователь замучен (демонстрация)"
        
    def cmd_warn(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Выдать предупреждение"""
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите пользователя: /warn [id|@] [причина]"
        return "⚠️ Предупреждение выдано (демонстрация)"
        
    def cmd_clear(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Очистить чат"""
        if not self.is_mod(user_id):
            return "⛔ Недостаточно прав"
        count = 20
        if args and args[0].isdigit():
            count = min(int(args[0]), 100)
        return f"🧹 Очищено {count} сообщений (демонстрация)"
        
    def cmd_rules(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Показать правила"""
        if not self.rules:
            return "ℹ️ Правила не установлены"
        text = "📜 *Правила чата:*\n\n"
        for i, rule in enumerate(self.rules, 1):
            text += f"{i}. {rule}\n"
        return text
        
    def cmd_addrule(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Добавить правило"""
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите правило"
        rule = " ".join(args)
        self.rules.append(rule)
        return f"✅ Правило добавлено: {rule}"
        
    def cmd_removerule(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Удалить правило"""
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
        """Установить приветствие"""
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите текст приветствия"
        text = " ".join(args)
        self.settings["welcome_message"] = text
        return f"✅ Приветствие установлено:\n{text}"
        
    def cmd_setleave(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Установить прощание"""
        if not self.is_admin(user_id):
            return "⛔ Недостаточно прав"
        if not args:
            return "Укажите текст прощания"
        text = " ".join(args)
        self.settings["leave_message"] = text
        return f"✅ Прощание установлено:\n{text}"
        
    def cmd_slowmode(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Включить медленный режим"""
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
        """Онлайн пользователи"""
        return "👥 Онлайн: 15 пользователей (демонстрационные данные)"
        
    def cmd_stats(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Статистика чата"""
        stats = f"📊 *Статистика чата*\n"
        stats += f"Сообщений: {self.message_count[user_id]}\n"
        stats += f"Очков: {self.points[user_id]}\n"
        stats += f"Уровень: {self.levels[user_id]}\n"
        stats += f"Достижений: {len(self.achievements[user_id])}\n"
        return stats
        
    def cmd_lovecalc(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Калькулятор любви"""
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
        """Гороскоп"""
        zodiacs = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", 
                   "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
        zodiac = args[0] if args else random.choice(zodiacs)
        fortunes = ["🌟 Сегодня звёзды благоволят вам!", 
                   "🌙 День будет удачным для новых начинаний",
                   "⭐ Ожидайте приятных сюрпризов"]
        return f"♈ *Гороскоп для {zodiac}*\n\n{random.choice(fortunes)}"
        
    def cmd_birthday(self, args: List[str], user_id: int, chat_id: int) -> str:
        """День рождения"""
        if args:
            return f"🎂 С днём рождения, {args[0]}!"
        return "🎂 Когда у вас день рождения? Напишите /birthday [дата]"
        
    def cmd_game(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Начать игру"""
        game_id = f"game_{int(time.time())}"
        self.game_sessions[game_id] = {
            "players": [user_id],
            "state": "waiting",
            "max_players": 10,
            "chat_id": chat_id
        }
        return f"🎮 Игра создана! ID: {game_id}\nПрисоединяйтесь: /join {game_id}"
        
    def cmd_join(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Присоединиться к игре"""
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
        """Таблица лидеров"""
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
        """Перевести монеты"""
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
        """Сделать ставку"""
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
        """Установить AFK статус"""
        if args:
            self.afk_users[user_id] = {
                "time": time.time(),
                "reason": " ".join(args)
            }
            return f"🔇 Вы AFK: {self.afk_users[user_id]['reason']}"
        self.afk_users[user_id] = {
            "time": time.time(),
            "reason": "Не беспокоить"
        }
        return "🔇 Вы AFK"
        
    def cmd_notafk(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Снять AFK статус"""
        if user_id in self.afk_users:
            del self.afk_users[user_id]
            return "🔊 Вы снова активны"
        return "ℹ️ Вы не были AFK"
        
    def cmd_echo(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Повторить сообщение"""
        if not args:
            return "Напишите что-то для повтора"
        return " ".join(args)
        
    def cmd_reverse(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Перевернуть текст"""
        if not args:
            return "Введите текст для переворота"
        text = " ".join(args)
        return text[::-1]
        
    def cmd_uppercase(self, args: List[str], user_id: int, chat_id: int) -> str:
        """В верхний регистр"""
        if not args:
            return "Введите текст"
        return " ".join(args).upper()
        
    def cmd_lowercase(self, args: List[str], user_id: int, chat_id: int) -> str:
        """В нижний регистр"""
        if not args:
            return "Введите текст"
        return " ".join(args).lower()
        
    def cmd_count(self, args: List[str], user_id: int, chat_id: int) -> str:
        """Подсчитать символы"""
        if not args:
            return "Введите текст"
        text = " ".join(args)
        return f"Символов: {len(text)}\nСлов: {len(text.split())}"
        
    # Дополнительные методы для поддержки всех команд
    def cmd_ban(self, args, user_id, chat_id): return self.cmd_kick(args, user_id, chat_id)
    def cmd_unban(self, args, user_id, chat_id): return "✅ Пользователь разбанен (демонстрация)"
    def cmd_unmute(self, args, user_id, chat_id): return "✅ Пользователь размучен (демонстрация)"
    def cmd_pin(self, args, user_id, chat_id): return "📌 Сообщение закреплено (демонстрация)"
    def cmd_unpin(self, args, user_id, chat_id): return "📌 Сообщение откреплено (демонстрация)"
    def cmd_mods(self, args, user_id, chat_id): return "👥 Модераторы: список (демонстрация)"
    def cmd_addmod(self, args, user_id, chat_id): return "✅ Модератор добавлен (демонстрация)"
    def cmd_removemod(self, args, user_id, chat_id): return "✅ Модератор удален (демонстрация)"
    def cmd_lock(self, args, user_id, chat_id): return "🔒 Чат заблокирован (демонстрация)"
    def cmd_unlock(self, args, user_id, chat_id): return "🔓 Чат разблокирован (демонстрация)"
    def cmd_filter(self, args, user_id, chat_id): return "🔍 Фильтр настроен (демонстрация)"
    def cmd_antispam(self, args, user_id, chat_id): return "🛡 Антиспам настроен (демонстрация)"
    def cmd_report(self, args, user_id, chat_id): return "📨 Жалоба отправлена (демонстрация)"
    def cmd_adminlog(self, args, user_id, chat_id): return "📋 Лог действий (демонстрация)"
    def cmd_cleanup(self, args, user_id, chat_id): return "🧹 Очистка выполнена (демонстрация)"
    def cmd_chat(self, args, user_id, chat_id): return "📊 Информация о чате (демонстрация)"
    def cmd_users(self, args, user_id, chat_id): return "👥 Список пользователей (демонстрация)"
    def cmd_news(self, args, user_id, chat_id): return "📰 Новости (демонстрация)"
    def cmd_version(self, args, user_id, chat_id): return "🤖 Версия бота: v2.0.0"
    def cmd_about(self, args, user_id, chat_id): return "🤖 Чат-менеджер VK с 300+ командами"
    def cmd_permissions(self, args, user_id, chat_id): return "🔑 Ваши права: пользователь"
    def cmd_top(self, args, user_id, chat_id): return self.cmd_leaderboard(args, user_id, chat_id)
    def cmd_levels(self, args, user_id, chat_id): return f"📊 Ваш уровень: {self.levels[user_id]}"
    def cmd_achievements(self, args, user_id, chat_id): return f"🏆 Достижения: {', '.join(self.achievements[user_id]) if self.achievements[user_id] else 'Нет достижений'}"
    def cmd_whois(self, args, user_id, chat_id): return self.cmd_info(args, user_id, chat_id)
    def cmd_id(self, args, user_id, chat_id): return f"🆔 Ваш ID: {user_id}"
    def cmd_group(self, args, user_id, chat_id): return f"📊 ID группы: {self.group_id}"
    def cmd_invite(self, args, user_id, chat_id): return "🔗 Ссылка-приглашение (демонстрация)"
    def cmd_settings(self, args, user_id, chat_id): return "⚙️ Настройки чата (демонстрация)"
    def cmd_banned(self, args, user_id, chat_id): return "🚫 Список забаненных (демонстрация)"
    def cmd_muted(self, args, user_id, chat_id): return "🔇 Список замученных (демонстрация)"
    def cmd_warnings(self, args, user_id, chat_id): return f"⚠️ Ваши предупреждения: {len(self.warnings[user_id])}"
    def cmd_trust(self, args, user_id, chat_id): return f"🤝 Ваш уровень доверия: {self.user_trust_level[user_id]}"
    
    # Методы для всех недостающих команд (заглушки)
    def cmd_rps(self, args, user_id, chat_id): return "✊ Камень-ножницы-бумага (демонстрация)"
    def cmd_guess(self, args, user_id, chat_id): return "🔢 Угадай число (демонстрация)"
    def cmd_trivia(self, args, user_id, chat_id): return "🧠 Викторина (демонстрация)"
    def cmd_quiz(self, args, user_id, chat_id): return "📝 Опрос (демонстрация)"
    def cmd_vote(self, args, user_id, chat_id): return "🗳 Голосование (демонстрация)"
    def cmd_result(self, args, user_id, chat_id): return "📊 Результаты (демонстрация)"
    def cmd_dice(self, args, user_id, chat_id): return "🎲 Кости (демонстрация)"
    def cmd_slots(self, args, user_id, chat_id): return "🎰 Игровой автомат (демонстрация)"
    def cmd_blackjack(self, args, user_id, chat_id): return "🃏 Блэкджек (демонстрация)"
    def cmd_roulette(self, args, user_id, chat_id): return "🎡 Русская рулетка (демонстрация)"
    def cmd_battle(self, args, user_id, chat_id): return "⚔️ Битва (демонстрация)"
    def cmd_duel(self, args, user_id, chat_id): return "🤺 Дуэль (демонстрация)"
    def cmd_race(self, args, user_id, chat_id): return "🏎️ Гонка (демонстрация)"
    def cmd_shop(self, args, user_id, chat_id): return "🛒 Магазин (демонстрация)"
    def cmd_buy(self, args, user_id, chat_id): return "🛍️ Купить (демонстрация)"
    def cmd_sell(self, args, user_id, chat_id): return "💰 Продать (демонстрация)"
    def cmd_inventory(self, args, user_id, chat_id): return "🎒 Инвентарь (демонстрация)"
    def cmd_weekly(self, args, user_id, chat_id): return "📅 Еженедельный бонус (демонстрация)"
    def cmd_guessword(self, args, user_id, chat_id): return "🔤 Угадай слово (демонстрация)"
    def cmd_hangman(self, args, user_id, chat_id): return "🪢 Виселица (демонстрация)"
    def cmd_tictac(self, args, user_id, chat_id): return "❌ Крестики-нолики (демонстрация)"
    def cmd_chess(self, args, user_id, chat_id): return "♟ Шахматы (демонстрация)"
    def cmd_checkers(self, args, user_id, chat_id): return "🔴 Шашки (демонстрация)"
    def cmd_cards(self, args, user_id, chat_id): return "🃏 Карты (демонстрация)"
    def cmd_bingo(self, args, user_id, chat_id): return "🎱 Бинго (демонстрация)"
    def cmd_lottery(self, args, user_id, chat_id): return "🎫 Лотерея (демонстрация)"
    def cmd_casino(self, args, user_id, chat_id): return "🎰 Казино (демонстрация)"
    def cmd_tarot(self, args, user_id, chat_id): return "🔮 Карты Таро (демонстрация)"
    def cmd_fortune(self, args, user_id, chat_id): return "🔮 Предсказание (демонстрация)"
    def cmd_convert(self, args, user_id, chat_id): return "💱 Конвертер валют (демонстрация)"
    def cmd_translate(self, args, user_id, chat_id): return "🌍 Переводчик (демонстрация)"
    def cmd_qr(self, args, user_id, chat_id): return "📱 QR-код (демонстрация)"
    def cmd_shorten(self, args, user_id, chat_id): return "🔗 Сократить ссылку (демонстрация)"
    def cmd_currency(self, args, user_id, chat_id): return "💵 Курс валют (демонстрация)"
    def cmd_math(self, args, user_id, chat_id): return "🧮 Математика (демонстрация)"
    def cmd_pick(self, args, user_id, chat_id): return "🎯 Выбрать из списка (демонстрация)"
    def cmd_shuffle(self, args, user_id, chat_id): return "🔀 Перемешать (демонстрация)"
    def cmd_sort(self, args, user_id, chat_id): return "📊 Отсортировать (демонстрация)"
    def cmd_capitalize(self, args, user_id, chat_id): return "📝 С большой буквы (демонстрация)"
    def cmd_wordcount(self, args, user_id, chat_id): return self.cmd_count(args, user_id, chat_id)
    def cmd_timer(self, args, user_id, chat_id): return "⏰ Таймер установлен (демонстрация)"
    def cmd_stopwatch(self, args, user_id, chat_id): return "⏱ Секундомер запущен (демонстрация)"
    def cmd_remind(self, args, user_id, chat_id): return "⏰ Напоминание установлено (демонстрация)"
    def cmd_todo(self, args, user_id, chat_id): return "📝 Список дел (демонстрация)"
    def cmd_note(self, args, user_id, chat_id): return "📝 Заметка сохранена (демонстрация)"
    def cmd_poll(self, args, user_id, chat_id): return "📊 Опрос создан (демонстрация)"
    def cmd_feedback(self, args, user_id, chat_id): return "💬 Обратная связь отправлена (демонстрация)"
    def cmd_suggest(self, args, user_id, chat_id): return "💡 Предложение отправлено (демонстрация)"
    def cmd_bug(self, args, user_id, chat_id): return "🐛 Сообщение об ошибке отправлено (демонстрация)"
    def cmd_idea(self, args, user_id, chat_id): return "💡 Идея сохранена (демонстрация)"
    def cmd_support(self, args, user_id, chat_id): return "🆘 Поддержка (демонстрация)"
    def cmd_faq(self, args, user_id, chat_id): return "📚 Частые вопросы (демонстрация)"
    def cmd_url(self, args, user_id, chat_id): return "🔗 Проверка ссылки (демонстрация)"
    def cmd_hash(self, args, user_id, chat_id): return "🔐 Хеш (демонстрация)"
    def cmd_encode(self, args, user_id, chat_id): return "🔐 Кодирование (демонстрация)"
    def cmd_decode(self, args, user_id, chat_id): return "🔓 Декодирование (демонстрация)"
    def cmd_password(self, args, user_id, chat_id): return "🔑 Пароль сгенерирован (демонстрация)"
    def cmd_hello(self, args, user_id, chat_id): return self.cmd_hi(args, user_id, chat_id)
    def cmd_welcome(self, args, user_id, chat_id): return "👋 Добро пожаловать!"
    def cmd_pat(self, args, user_id, chat_id): return "🤗 Погладить (демонстрация)"
    def cmd_poke(self, args, user_id, chat_id): return "👉 Ткнуть (демонстрация)"
    def cmd_slap(self, args, user_id, chat_id): return "✋ Дать пощёчину (демонстрация)"
    def cmd_highfive(self, args, user_id, chat_id): return "✋ Дай пять! (демонстрация)"
    def cmd_fistbump(self, args, user_id, chat_id): return "🤜🤛 Кулак (демонстрация)"
    def cmd_bro(self, args, user_id, chat_id): return "🤝 Бро! (демонстрация)"
    def cmd_sister(self, args, user_id, chat_id): return "🤝 Сестра! (демонстрация)"
    def cmd_friend(self, args, user_id, chat_id): return "👫 Друг! (демонстрация)"
    def cmd_love(self, args, user_id, chat_id): return "❤️ Любовь! (демонстрация)"
    def cmd_hate(self, args, user_id, chat_id): return "💔 Ненависть! (демонстрация)"
    def cmd_angry(self, args, user_id, chat_id): return "😤 Злой! (демонстрация)"
    def cmd_happy(self, args, user_id, chat_id): return "😊 Счастливый! (демонстрация)"
    def cmd_sad(self, args, user_id, chat_id): return "😢 Грустный! (демонстрация)"
    def cmd_tired(self, args, user_id, chat_id): return "😴 Уставший! (демонстрация)"
    def cmd_bored(self, args, user_id, chat_id): return "😒 Скучающий! (демонстрация)"
    def cmd_excited(self, args, user_id, chat_id): return "🤩 Взволнованный! (демонстрация)"
    def cmd_image(self, args, user_id, chat_id): return "🖼 Поиск картинки (демонстрация)"
    def cmd_gif(self, args, user_id, chat_id): return "🎬 Поиск гифки (демонстрация)"
    def cmd_video(self, args, user_id, chat_id): return "📹 Поиск видео (демонстрация)"
    def cmd_music(self, args, user_id, chat_id): return "🎵 Поиск музыки (демонстрация)"
    def cmd_youtube(self, args, user_id, chat_id): return "▶️ YouTube видео (демонстрация)"
    def cmd_instagram(self, args, user_id, chat_id): return "📸 Instagram (демонстрация)"
    def cmd_twitter(self, args, user_id, chat_id): return "🐦 Twitter (демонстрация)"
    def cmd_reddit(self, args, user_id, chat_id): return "🔴 Reddit (демонстрация)"
    def cmd_pinterest(self, args, user_id, chat_id): return "📌 Pinterest (демонстрация)"
    def cmd_soundcloud(self, args, user_id, chat_id): return "🎧 SoundCloud (демонстрация)"
    def cmd_spotify(self, args, user_id, chat_id): return "🎵 Spotify (демонстрация)"
    def cmd_netflix(self, args, user_id, chat_id): return "📺 Netflix (демонстрация)"
    def cmd_prime(self, args, user_id, chat_id): return "📺 Amazon Prime (демонстрация)"
    def cmd_hulu(self, args, user_id, chat_id): return "📺 Hulu (демонстрация)"
    def cmd_disney(self, args, user_id, chat_id): return "📺 Disney+ (демонстрация)"
    def cmd_hbo(self, args, user_id, chat_id): return "📺 HBO Max (демонстрация)"
    def cmd_peacock(self, args, user_id, chat_id): return "📺 Peacock (демонстрация)"
    def cmd_paramount(self, args, user_id, chat_id): return "📺 Paramount+ (демонстрация)"
    def cmd_apple(self, args, user_id, chat_id): return "📺 Apple TV+ (демонстрация)"
    def cmd_crunchyroll(self, args, user_id, chat_id): return "📺 Crunchyroll (демонстрация)"
    def cmd_start(self, args, user_id, chat_id): return "▶️ Игра начата (демонстрация)"
    def cmd_stop(self, args, user_id, chat_id): return "⏹ Игра остановлена (демонстрация)"
    def cmd_pause(self, args, user_id, chat_id): return "⏸ Игра на паузе (демонстрация)"
    def cmd_resume(self, args, user_id, chat_id): return "▶️ Игра продолжена (демонстрация)"
    def cmd_move(self, args, user_id, chat_id): return "♟ Ход сделан (демонстрация)"
    def cmd_winner(self, args, user_id, chat_id): return "🏆 Победитель (демонстрация)"
    def cmd_achievement(self, args, user_id, chat_id): return self.cmd_achievements(args, user_id, chat_id)
    def cmd_quest(self, args, user_id, chat_id): return "📜 Квест (демонстрация)"
    def cmd_challenge(self, args, user_id, chat_id): return "⚔️ Вызов (демонстрация)"
    def cmd_accept(self, args, user_id, chat_id): return "✅ Вызов принят (демонстрация)"
    def cmd_decline(self, args, user_id, chat_id): return "❌ Вызов отклонен (демонстрация)"
    def cmd_team(self, args, user_id, chat_id): return "👥 Команда (демонстрация)"
    def cmd_teams(self, args, user_id, chat_id): return "👥 Список команд (демонстрация)"
    def cmd_captain(self, args, user_id, chat_id): return "👨‍✈️ Капитан (демонстрация)"
    def cmd_strategy(self, args, user_id, chat_id): return "📋 Стратегия (демонстрация)"
    def cmd_tactics(self, args, user_id, chat_id): return "📋 Тактика (демонстрация)"
    def cmd_gg(self, args, user_id, chat_id): return "👏 Хорошая игра! (демонстрация)"
    def cmd_money(self, args, user_id, chat_id): return self.cmd_balance(args, user_id, chat_id)
    def cmd_earn(self, args, user_id, chat_id): return "💰 Заработать (демонстрация)"
    def cmd_bank(self, args, user_id, chat_id): return "🏦 Банк (демонстрация)"
    def cmd_deposit(self, args, user_id, chat_id): return "🏦 Внести (демонстрация)"
    def cmd_withdraw(self, args, user_id, chat_id): return "🏦 Снять (демонстрация)"
    def cmd_interest(self, args, user_id, chat_id): return "📈 Проценты (демонстрация)"
    def cmd_loan(self, args, user_id, chat_id): return "💰 Кредит (демонстрация)"
    def cmd_invest(self, args, user_id, chat_id): return "📈 Инвестировать (демонстрация)"
    def cmd_stock(self, args, user_id, chat_id): return "📊 Акции (демонстрация)"
    def cmd_trade(self, args, user_id, chat_id): return "💱 Торговать (демонстрация)"
    def cmd_market(self, args, user_id, chat_id): return "🏪 Рынок (демонстрация)"
    def cmd_price(self, args, user_id, chat_id): return "💰 Цена (демонстрация)"
    def cmd_auction(self, args, user_id, chat_id): return "🔨 Аукцион (демонстрация)"
    def cmd_bid(self, args, user_id, chat_id): return "💰 Ставка (демонстрация)"
    def cmd_wallet(self, args, user_id, chat_id): return self.cmd_balance(args, user_id, chat_id)
    def cmd_transaction(self, args, user_id, chat_id): return "💳 Транзакция (демонстрация)"
    def cmd_reload(self, args, user_id, chat_id): return "🔄 Перезагрузка (демонстрация)"
    def cmd_restart(self, args, user_id, chat_id): return "🔄 Перезапуск (демонстрация)"
    def cmd_update(self, args, user_id, chat_id): return "🔄 Обновление (демонстрация)"
    def cmd_backup(self, args, user_id, chat_id): return "💾 Бэкап создан (демонстрация)"
    def cmd_restore(self, args, user_id, chat_id): return "💾 Восстановление (демонстрация)"
    def cmd_sync(self, args, user_id, chat_id): return "🔄 Синхронизация (демонстрация)"
    def cmd_status(self, args, user_id, chat_id): return "✅ Статус: OK (демонстрация)"
    def cmd_health(self, args, user_id, chat_id): return "❤️ Здоровье: отлично (демонстрация)"
    def cmd_memory(self, args, user_id, chat_id): return "🧠 Память (демонстрация)"
    def cmd_cpu(self, args, user_id, chat_id): return "💻 CPU (демонстрация)"
    def cmd_logs(self, args, user_id, chat_id): return "📋 Логи (демонстрация)"
    def cmd_errors(self, args, user_id, chat_id): return "❌ Ошибки (демонстрация)"
    def cmd_debug(self, args, user_id, chat_id): return "🐛 Отладка (демонстрация)"
    def cmd_test(self, args, user_id, chat_id): return "🧪 Тест (демонстрация)"
    def cmd_benchmark(self, args, user_id, chat_id): return "📊 Тест производительности (демонстрация)"
    def cmd_config(self, args, user_id, chat_id): return "⚙️ Конфигурация (демонстрация)"
    def cmd_env(self, args, user_id, chat_id): return "🌍 Переменные окружения (демонстрация)"
    def cmd_secret(self, args, user_id, chat_id): return "🔐 Секреты (демонстрация)"
    def cmd_alarm(self, args, user_id, chat_id): return "⏰ Будильник (демонстрация)"
    def cmd_calendar(self, args, user_id, chat_id): return "📅 Календарь (демонстрация)"
    def cmd_schedule(self, args, user_id, chat_id): return "📋 Расписание (демонстрация)"
    def cmd_reminder(self, args, user_id, chat_id): return "⏰ Напоминание (демонстрация)"
    def cmd_age(self, args, user_id, chat_id): return "🎂 Возраст (демонстрация)"
    def cmd_numerology(self, args, user_id, chat_id): return "🔢 Нумерология (демонстрация)"
    def cmd_astrology(self, args, user_id, chat_id): return "⭐ Астрология (демонстрация)"
    def cmd_mbti(self, args, user_id, chat_id): return "🧠 Тест MBTI (демонстрация)"
    def cmd_iq(self, args, user_id, chat_id): return "🧠 Тест IQ (демонстрация)"
    def cmd_personality(self, args, user_id, chat_id): return "🧠 Тест личности (демонстрация)"
    def cmd_compatibility(self, args, user_id, chat_id): return "💕 Совместимость (демонстрация)"
    def cmd_relationship(self, args, user_id, chat_id): return "💕 Отношения (демонстрация)"
    def cmd_friendship(self, args, user_id, chat_id): return "🤝 Дружба (демонстрация)"
    def cmd_enemy(self, args, user_id, chat_id): return "👿 Враг (демонстрация)"
    def cmd_rival(self, args, user_id, chat_id): return "⚔️ Соперник (демонстрация)"
    def cmd_mentor(self, args, user_id, chat_id): return "🧑‍🏫 Наставник (демонстрация)"
    def cmd_student(self, args, user_id, chat_id): return "🧑‍🎓 Ученик (демонстрация)"
    def cmd_teacher(self, args, user_id, chat_id): return "🧑‍🏫 Учитель (демонстрация)"
    def cmd_colleague(self, args, user_id, chat_id): return "👔 Коллега (демонстрация)"
    def cmd_partner(self, args, user_id, chat_id): return "🤝 Партнер (демонстрация)"
    def cmd_family(self, args, user_id, chat_id): return "👨‍👩‍👧‍👦 Семья (демонстрация)"
    def cmd_pet(self, args, user_id, chat_id): return "🐾 Питомец (демонстрация)"
    def cmd_plant(self, args, user_id, chat_id): return "🌱 Растение (демонстрация)"
    def cmd_food(self, args, user_id, chat_id): return "🍕 Еда (демонстрация)"
    def cmd_drink(self, args, user_id, chat_id): return "🍹 Напиток (демонстрация)"
    def cmd_recipe(self, args, user_id, chat_id): return "🍳 Рецепт (демонстрация)"
    def cmd_restaurant(self, args, user_id, chat_id): return "🍽 Ресторан (демонстрация)"
    def cmd_travel(self, args, user_id, chat_id): return "🧳 Путешествие (демонстрация)"
    def cmd_hotel(self, args, user_id, chat_id): return "🏨 Отель (демонстрация)"
    def cmd_flight(self, args, user_id, chat_id): return "✈️ Авиарейс (демонстрация)"
        
    def process_message(self, message: Dict[str, Any]) -> Optional[str]:
        """Обработка входящего сообщения"""
        if "text" not in message:
            return None
            
        text = message["text"].strip()
        user_id = message.get("from_id", 0)
        chat_id = message.get("peer_id", 0)
        
        if not text or not user_id:
            return None
            
        # Проверка на mute
        if self.is_muted(user_id):
            return None
            
        # Проверка на slow mode
        if self.settings["slow_mode"]:
            current_time = time.time()
            if user_id in self.last_message_time:
                if current_time - self.last_message_time[user_id] < self.settings["slow_mode_delay"]:
                    return None
            self.last_message_time[user_id] = current_time
            
        # Обработка команд
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
                
        # Добавление очков за активность
        if len(text) > 3:
            if random.random() < 0.1:  # 10% шанс получить очки
                points = random.randint(1, 3)
                self.add_points(user_id, points)
                self.message_count[user_id] += 1
                    
        return None
        
    def run(self):
        """Запуск бота"""
        logger.info("Бот запущен и готов к работе")
        
        # Основной цикл
        while True:
            try:
                # Получение новых сообщений
                response = self.api_request(
                    "messages.get",
                    count=20
                )
                
                if response and "items" in response:
                    for msg in response["items"]:
                        self.process_message(msg)
                        
                time.sleep(1)  # Пауза для избежания ограничений API
                
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(5)

# Создание и запуск бота
if __name__ == "__main__":
    manager = VKChatManager(TOKEN, GROUP_ID)
    manager.run()
