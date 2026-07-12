import asyncio
import os
import logging
import json
import time
import requests
from datetime import datetime

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
PREFIX = "!"

class VKAPI:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://api.vk.com/method/"
    
    def _request(self, method, params=None):
        if params is None:
            params = {}
        params["access_token"] = self.token
        params["v"] = API_VERSION
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
    
    def users_get(self, user_id):
        return self._request("users.get", {
            "user_ids": user_id,
            "fields": "city,country,education,status,last_seen,counters,photo_200,sex,bdate,about,activities,books,games,interests,movies,music,occupation,personal,quotes,relatives,schools,universities,career,military,home_town,facebook,twitter,instagram,skype,site"
        })
    
    def wall_get(self, user_id, count=10):
        return self._request("wall.get", {
            "owner_id": user_id,
            "count": count,
            "extended": 1
        })
    
    def friends_get(self, user_id, count=100):
        return self._request("friends.get", {
            "user_id": user_id,
            "count": count,
            "fields": "first_name,last_name,photo_50"
        })
    
    def groups_get(self, user_id, count=50):
        return self._request("groups.get", {
            "user_id": user_id,
            "count": count,
            "extended": 1,
            "fields": "name,photo_50"
        })
    
    def photos_get(self, user_id, count=10):
        return self._request("photos.get", {
            "owner_id": user_id,
            "count": count,
            "extended": 1
        })
    
    def videos_get(self, user_id, count=10):
        return self._request("video.get", {
            "owner_id": user_id,
            "count": count
        })
    
    def audio_get(self, user_id, count=50):
        return self._request("audio.get", {
            "owner_id": user_id,
            "count": count
        })
    
    def docs_get(self, user_id, count=20):
        return self._request("docs.get", {
            "owner_id": user_id,
            "count": count
        })
    
    def messages_get(self, user_id, count=20):
        return self._request("messages.getHistory", {
            "user_id": user_id,
            "count": count
        })
    
    def status_get(self, user_id):
        return self._request("status.get", {"user_id": user_id})
    
    def subscriptions_get(self, user_id, count=50):
        return self._request("users.getSubscriptions", {
            "user_id": user_id,
            "count": count
        })
    
    def followers_get(self, user_id, count=50):
        return self._request("users.getFollowers", {
            "user_id": user_id,
            "count": count
        })
    
    def reports_get(self, user_id):
        return self._request("users.report", {"user_id": user_id})
    
    def messages_send(self, peer_id, message):
        return self._request("messages.send", {
            "peer_id": peer_id,
            "message": message,
            "random_id": int(time.time() * 1000)
        })

vk = VKAPI(TOKEN)

def format_user_info(user_data):
    if not user_data or "error" in user_data:
        return "Пользователь не найден или профиль закрыт"
    
    user = user_data[0]
    
    sex = "Не указан"
    if user.get("sex") == 1:
        sex = "Женский"
    elif user.get("sex") == 2:
        sex = "Мужской"
    
    bdate = user.get("bdate", "Не указана")
    if user.get("bdate_visibility") == 1:
        bdate = "Скрыта (только день и месяц)"
    elif user.get("bdate_visibility") == 0:
        bdate = "Скрыта полностью"
    
    home_town = user.get("home_town", "Не указан")
    
    status = user.get("status", "Нет статуса")
    if len(status) > 200:
        status = status[:200] + "..."
    
    about = user.get("about", "Не указано")
    if len(about) > 200:
        about = about[:200] + "..."
    
    last_seen = "Неизвестно"
    if user.get("last_seen"):
        last_seen = datetime.fromtimestamp(user["last_seen"]["time"]).strftime("%d.%m.%Y %H:%M")
    
    counters = user.get("counters", {})
    
    contacts = []
    if user.get("facebook"):
        contacts.append(f"Facebook: {user['facebook']}")
    if user.get("twitter"):
        contacts.append(f"Twitter: {user['twitter']}")
    if user.get("instagram"):
        contacts.append(f"Instagram: {user['instagram']}")
    if user.get("skype"):
        contacts.append(f"Skype: {user['skype']}")
    if user.get("site"):
        contacts.append(f"Сайт: {user['site']}")
    
    education = []
    if user.get("universities"):
        for uni in user["universities"]:
            education.append(f"{uni.get('name', '')} - {uni.get('faculty_name', '')}")
    if user.get("schools"):
        for school in user["schools"]:
            education.append(f"{school.get('name', '')}")
    
    career = []
    if user.get("career"):
        for job in user["career"]:
            career.append(f"{job.get('position', '')} в {job.get('company', '')}")
    
    interests = []
    for field in ["interests", "music", "movies", "books", "games", "activities", "quotes"]:
        if user.get(field):
            interests.append(f"{field.capitalize()}: {user[field]}")
    
    text = f"""
[ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ ]
----------------------------------------

Основное:
Имя: {user.get('first_name', '')} {user.get('last_name', '')}
ID: {user.get('id', '')}
Пол: {sex}
Дата рождения: {bdate}
Город: {user.get('city', {}).get('title', 'Не указан')}
Страна: {user.get('country', {}).get('title', 'Не указана')}
Родной город: {home_town}
Статус: {status}
О себе: {about}
Последний визит: {last_seen}

Контакты:
{chr(10).join(contacts) if contacts else 'Не указаны'}

Образование:
{chr(10).join(education) if education else 'Не указано'}

Карьера:
{chr(10).join(career) if career else 'Не указана'}

Интересы:
{chr(10).join(interests) if interests else 'Не указаны'}

Статистика:
Друзей: {counters.get('friends', 0)}
Подписчиков: {counters.get('followers', 0)}
Постов на стене: {counters.get('wall', 0)}
Фотографий: {counters.get('photos', 0)}
Видеозаписей: {counters.get('videos', 0)}
Аудиозаписей: {counters.get('audios', 0)}

Ссылка: vk.com/id{user['id']}
Фото: {user.get('photo_200', '')}
"""
    return text

def format_posts(posts_data):
    if not posts_data or "error" in posts_data:
        return "Нет публичных постов или стена закрыта"
    
    items = posts_data.get("items", [])
    if not items:
        return "Нет постов на стене"
    
    text = "[ ПОСЛЕДНИЕ ПОСТЫ ]\n----------------------------------------\n"
    for i, post in enumerate(items[:5], 1):
        post_text = post.get("text", "")
        if len(post_text) > 300:
            post_text = post_text[:300] + "..."
        
        date = datetime.fromtimestamp(post.get("date", 0)).strftime("%d.%m.%Y %H:%M")
        likes = post.get("likes", {}).get("count", 0)
        comments = post.get("comments", {}).get("count", 0)
        reposts = post.get("reposts", {}).get("count", 0)
        
        text += f"""
{post_text}

Дата: {date}
Лайков: {likes} | Комментариев: {comments} | Репостов: {reposts}
----------------------------------------
"""
    return text

def format_friends(friends_data):
    if not friends_data or "error" in friends_data:
        return "Список друзей закрыт"
    
    items = friends_data.get("items", [])
    if not items:
        return "Нет друзей"
    
    text = "[ ДРУЗЬЯ ]\n----------------------------------------\n"
    for friend in items[:20]:
        text += f"{friend.get('first_name', '')} {friend.get('last_name', '')} (id{friend.get('id', '')})\n"
    
    if len(items) > 20:
        text += f"... и еще {len(items) - 20} друзей"
    
    return text

def format_groups(groups_data):
    if not groups_data or "error" in groups_data:
        return "Список групп закрыт"
    
    items = groups_data.get("items", [])
    if not items:
        return "Не состоит в группах"
    
    text = "[ ГРУППЫ ]\n----------------------------------------\n"
    for group in items[:15]:
        text += f"{group.get('name', '')} (id{group.get('id', '')})\n"
    
    if len(items) > 15:
        text += f"... и еще {len(items) - 15} групп"
    
    return text

async def process_message(message_data):
    try:
        if "object" in message_data and "message" in message_data["object"]:
            msg = message_data["object"]["message"]
            peer_id = msg.get("peer_id", 0)
            user_id = msg.get("from_id", 0)
            text = msg.get("text", "")
        else:
            peer_id = message_data.get("peer_id", 0)
            user_id = message_data.get("from_id", 0)
            text = message_data.get("text", "")
        
        if user_id < 0:
            return
        
        if not text.startswith(PREFIX):
            return
        
        text = text[1:].strip()
        args = text.split()
        if not args:
            return
        
        command = args[0].lower()
        
        def get_target_id():
            if len(args) > 1 and args[1].isdigit():
                return int(args[1])
            elif len(args) > 1 and args[1].startswith("id"):
                try:
                    return int(args[1].replace("id", ""))
                except:
                    return user_id
            return user_id
        
        if command == "инфо" or command == "info":
            target_id = get_target_id()
            user_info = vk.users_get(target_id)
            response_text = format_user_info(user_info)
            await vk.messages_send(peer_id, response_text)
            return
        
        if command == "посты" or command == "posts" or command == "wall":
            target_id = get_target_id()
            posts = vk.wall_get(target_id, 10)
            response_text = format_posts(posts)
            await vk.messages_send(peer_id, response_text)
            return
        
        if command == "друзья" or command == "friends":
            target_id = get_target_id()
            friends = vk.friends_get(target_id, 50)
            response_text = format_friends(friends)
            await vk.messages_send(peer_id, response_text)
            return
        
        if command == "группы" or command == "groups":
            target_id = get_target_id()
            groups = vk.groups_get(target_id, 50)
            response_text = format_groups(groups)
            await vk.messages_send(peer_id, response_text)
            return
        
        if command == "фото" or command == "photos":
            target_id = get_target_id()
            photos = vk.photos_get(target_id, 10)
            if "error" not in photos and photos.get("items"):
                text = "[ ФОТОГРАФИИ ]\n----------------------------------------\n"
                for photo in photos["items"][:5]:
                    text += f"{photo.get('text', 'Без описания')}\n"
                    text += f"Ссылка: {photo.get('sizes', [{}])[-1].get('url', '')}\n"
                    text += "----------------------------------------\n"
                await vk.messages_send(peer_id, text)
            else:
                await vk.messages_send(peer_id, "Нет публичных фотографий")
            return
        
        if command == "видео" or command == "videos":
            target_id = get_target_id()
            videos = vk.videos_get(target_id, 10)
            if "error" not in videos and videos.get("items"):
                text = "[ ВИДЕОЗАПИСИ ]\n----------------------------------------\n"
                for video in videos["items"][:5]:
                    text += f"{video.get('title', 'Без названия')}\n"
                    text += f"Просмотров: {video.get('views', 0)}\n"
                    text += "----------------------------------------\n"
                await vk.messages_send(peer_id, text)
            else:
                await vk.messages_send(peer_id, "Нет публичных видеозаписей")
            return
        
        if command == "аудио" or command == "audio":
            target_id = get_target_id()
            audio = vk.audio_get(target_id, 20)
            if "error" not in audio and audio.get("items"):
                text = "[ АУДИОЗАПИСИ ]\n----------------------------------------\n"
                for track in audio["items"][:10]:
                    text += f"{track.get('artist', '')} - {track.get('title', '')}\n"
                await vk.messages_send(peer_id, text)
            else:
                await vk.messages_send(peer_id, "Нет публичных аудиозаписей")
            return
        
        if command == "помощь" or command == "help":
            help_text = """
[ БОТ ДЛЯ ПРОСМОТРА ПУБЛИЧНЫХ ПРОФИЛЕЙ ]

Команды:
!инфо [ID] — Полная информация о пользователе
!посты [ID] — Последние посты на стене
!друзья [ID] — Список друзей
!группы [ID] — Список групп
!фото [ID] — Фотографии
!видео [ID] — Видеозаписи
!аудио [ID] — Аудиозаписи
!помощь — Это сообщение

ВСЕ ДАННЫЕ — ПУБЛИЧНЫЕ ИЗ ПРОФИЛЯ
Бот НЕ показывает приватную информацию:
• Номера телефонов
• Паспортные данные
• Адреса
• СНИЛС
• Личные сообщения
"""
            await vk.messages_send(peer_id, help_text)
            return
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await vk.messages_send(peer_id, f"Ошибка: {e}")

async def main():
    logger.info("Бот запущен")
    logger.info("Команды: !инфо, !посты, !друзья, !группы, !фото, !видео, !аудио, !помощь")
    
    response = requests.post(
        f"https://api.vk.com/method/groups.getLongPollServer",
        data={"group_id": GROUP_ID, "access_token": TOKEN, "v": API_VERSION}
    ).json()
    
    if "error" in response:
        logger.error(f"Error: {response['error']}")
        return
    
    server = response["response"]["server"]
    key = response["response"]["key"]
    ts = response["response"]["ts"]
    
    if not server.startswith(('http://', 'https://')):
        server = 'https://' + server
    
    while True:
        try:
            url = f"{server}?act=a_check&key={key}&ts={ts}&wait=25&mode=2&version=2"
            r = requests.get(url, timeout=30).json()
            
            if "failed" in r:
                ts = r.get("ts", ts)
                continue
            
            ts = r.get("ts", ts)
            for update in r.get("updates", []):
                if update.get("type") == "message_new":
                    await process_message(update)
                    
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
