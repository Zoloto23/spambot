from flask import Flask, render_template, request, jsonify, session
import requests
import os
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Файл для хранения токенов
TOKENS_FILE = "tokens.json"

def save_token(user_id, token):
    """Сохраняет токен пользователя"""
    try:
        with open(TOKENS_FILE, "r") as f:
            tokens = json.load(f)
    except:
        tokens = {}
    
    tokens[str(user_id)] = token
    
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f)

def get_token(user_id):
    """Получает сохранённый токен"""
    try:
        with open(TOKENS_FILE, "r") as f:
            tokens = json.load(f)
            return tokens.get(str(user_id))
    except:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/connect', methods=['POST'])
def connect():
    """Подключение бота через токен"""
    data = request.json
    token = data.get('token')
    user_id = data.get('user_id')
    
    if not token:
        return jsonify({'error': 'Токен не указан'}), 400
    
    # Проверяем токен через VK API
    try:
        response = requests.get(
            'https://api.vk.com/method/users.get',
            params={
                'access_token': token,
                'v': '5.199'
            },
            timeout=10
        )
        result = response.json()
        
        if 'error' in result:
            return jsonify({'error': 'Неверный токен'}), 400
        
        user = result.get('response', [{}])[0]
        user_id = user.get('id')
        
        # Сохраняем токен
        save_token(user_id, token)
        
        return jsonify({
            'success': True,
            'user': user,
            'message': 'Бот успешно подключен!'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    """Проверка статуса бота"""
    token = session.get('token')
    if not token:
        return jsonify({'connected': False})
    
    try:
        response = requests.get(
            'https://api.vk.com/method/account.getInfo',
            params={'access_token': token, 'v': '5.199'}
        )
        return jsonify({'connected': True, 'data': response.json()})
    except:
        return jsonify({'connected': False})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
