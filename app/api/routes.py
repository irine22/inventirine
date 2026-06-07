import jwt
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request, current_app
from functools import wraps
from app.models import User
from app import limiter
import bleach

api_bp = Blueprint('api', __name__)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # JWT is expected in the Authorization header: Bearer <token>
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
                
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 401

        return f(current_user, *args, **kwargs)
    return decorated

@api_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def api_login():
    auth = request.get_json()

    if not auth or not auth.get('email') or not auth.get('password'):
        return jsonify({'message': 'Invalid credentials'}), 401

    user = User.query.filter_by(email=auth.get('email')).first()

    if not user:
        return jsonify({'message': 'Invalid credentials'}), 401

    if user.is_deleted:
        return jsonify({'message': 'Invalid credentials'}), 401

    if user.is_locked:
        return jsonify({'message': 'Invalid credentials'}), 401

    if user.check_password(auth.get('password')):
        user.reset_failed_logins()
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.now(timezone.utc) + timedelta(minutes=30)
        }, current_app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({'token': token})

    user.record_failed_login()
    return jsonify({'message': 'Invalid credentials'}), 401

@api_bp.route('/data', methods=['POST'])
@token_required
def api_data(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Invalid JSON payload'}), 400
    
    raw_input = data.get('comment', '')
    sanitized_input = bleach.clean(raw_input)
    
    return jsonify({
        'message': f'Hello {current_user.username}',
        'sanitized_comment': sanitized_input,
        'status': 'Success'
    })
