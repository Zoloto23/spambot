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
            ("/alarm",