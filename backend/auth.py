from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
import jwt
import datetime
import os
from scraper.db import get_connection

bcrypt = Bcrypt()
auth_bp = Blueprint('auth', __name__)

SECRET_KEY = os.getenv('JWT_SECRET', 'dev_secret')  # Set a strong secret in production

@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, email, pw_hash)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
        return jsonify({'message': 'User registered', 'user_id': user_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Invalid credentials'}), 401
            user_id, pw_hash = row
            if not bcrypt.check_password_hash(pw_hash, password):
                return jsonify({'error': 'Invalid credentials'}), 401
            # Generate JWT
            payload = {
                'user_id': user_id,
                'username': username,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
            return jsonify({'token': token, 'user_id': user_id, 'username': username})
    finally:
        conn.close()

@auth_bp.route('/api/protected', methods=['GET'])
def protected():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid Authorization header'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return jsonify({'message': f'Hello, {payload["username"]}! This is a protected endpoint.'})
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401 