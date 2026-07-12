import asyncio
import os
import logging
import json
import time
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("VK_GROUP_TOKEN")
GROUP_ID = int(os.environ.get("VK_GROUP_ID", 0))

if not TOKEN:
    raise RuntimeError("VK_GROUP_TOKEN not set")

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
        response = requests.post(self.base_url + method, data=params, timeout=10)
        return response.json().get("response", {})
    
    def users_get(self, user_id):
        return self._request("users.get", {
            "user_ids": user_id,
            "fields": "city,country,education,status,last_seen,counters,photo_200"
        })
    
    def wall_get(self, user_id, count=5):
        return self._request("wall.get", {
            "owner_id": user_id,
            "count": count
        })
    
    def friends_get(self, user_id):
        return self._request("friends.get", {"user_id": user_id, "count": 0})
    
    def groups_get(self, user_id):
        return self._request("groups.get", {"user_id": user_id, "count": 0})
    
    def messages_send(self, peer_id, message):
        return self._request("messages.send", {
            "peer_id": peer_id,
            "message": message,
            "random_id": int(time.time() * 1000)
        })

vk = VKAPI(TOKEN)

def format_user_info(user_data):
    """Форматирует ПУБЛИЧНУЮ информацию о пользователе"""
    if not user_data:
        return "❌ Пользователь не найден"
    
    user = user_data[0]
    text = f"👤 **{user.get('first_name', '')} {user.get('last_name', '')}**\n"
    text += f"🆔 ID: {user.get('id', '')}\n"
    
    if user.get('city'):
        text += f"🏙️ Город: {user['city'].get('title', '')}\n"
    if user.get('country'):
        text += f"🌍 Страна: {user['country'].get('title', '')}\n"
    if user.get('education'):
        text += f"🎓 Учеба: {user['education'].get('university_name', '')}\n"
    if user.get('status'):
        text += f"📝 Статус: {user['status']}\n"
    if user.get('last_seen'):
        import datetime
        last_seen = datetime.datetime.fromtimestamp(user['last_seen']['time'])
        text += f"🕐 Последний раз: {last_seen.strftime('%d.%m.%Y %H:%M')}\n"
    if user.get('counters'):
        text += f"👥 Друзей: {user['counters'].get('friends', 0)}\n"
        text += f"📸 Подписчиков: {user['counters'].get('followers', 0)}\n"
        text += f"📝 Постов: {user['counters'].get('wall', 0)}\n"
    
    text += f"🔗 Профиль: vk.com/id{user['id']}"
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
        
        # --- СЕЙЧАС БУДЕТ КОМАНДА ДЛЯ ПРОСМОТРА ПУБЛИЧНЫХ ДАННЫХ ---
        if command == "инфо" or command == "info":
            target_id = user_id
            if len(args) > 1 and args[1].isdigit():
                target_id = int(args[1])
            elif len(args) > 1 and args[1].startswith("id"):
                try:
                    target_id = int(args[1].replace("id", ""))
                except:
                    pass
            
            user_info = vk.users_get(target_id)
            if "error" in user_info:
                await vk.messages_send(peer_id, "❌ Ошибка получения данных")
                return
            
            response_text = format_user_info(user_info)
            await vk.messages_send(peer_id, response_text)
            return
        
        if command == "посты" or command == "posts":
            target_id = user_id
            if len(args) > 1 and args[1].isdigit():
                target_id = int(args[1])
            
            posts = vk.wall_get(target_id, 3)
            if not posts or "error" in posts:
                await vk.messages_send(peer_id, "❌ Нет публичных постов или стена закрыта")
                return
            
            text = f"📝 **Последние посты:**\n\n"
            for post in posts.get("items", [])[:3]:
                if post.get("text"):
                    post_text = post["text"][:200]
                    text += f"• {post_text}...\n\n"
            
            await vk.messages_send(peer_id, text)
            return
        
        if command == "помощь" or command == "help":
            help_text = (
                "🤖 **Бот для просмотра публичных профилей VK**\n\n"
                "!инфо [ID] — Публичная информация\n"
                "!посты [ID] — Последние посты\n"
                "!помощь — Это сообщение\n\n"
                "⚠️ **Только публичная информация!**\n"
                "❌ Бот НЕ показывает:\n"
                "• Номера телефонов\n"
                "• Паспортные данные\n"
                "• Адреса\n"
                "• СНИЛС\n"
                "• Приватные сообщения"
            )
            await vk.messages_send(peer_id, help_text)
            return
        
    except Exception as e:
        logger.error(f"Error: {e}")

async def main():
    logger.info("🚀 Бот запущен!")
    logger.info("📌 Команды: !инфо, !посты, !помощь")
    
    # Получаем Long Poll
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
