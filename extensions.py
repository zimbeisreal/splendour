# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import TooManyRequests
from flask import request, jsonify, render_template, session
import hashlib
import os
import redis

db = SQLAlchemy()
login_manager = LoginManager()
_limiter = None
def get_session_or_user_key():
    """Get a unique identifier for rate limiting"""
    # 1. Logged-in user: use their ID (most specific)
    if current_user and current_user.is_authenticated:
        return f"user:{current_user.id}"
    
    # 2. Has session cookie: use session ID
    session_id = session.get('_id') or session.get('session_id')
    if session_id:
        # Hash session ID for consistency
        hashed = hashlib.md5(session_id.encode()).hexdigest()
        return f"session:{hashed}"
    
    # 3. Fallback to IP address
    return get_remote_address()
    # Auto-clear Redis on strategy change
def clear_redis_for_new_strategy():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return
    
    try:
        r = redis.from_url(redis_url)
        
        # Check for old rate limiter keys
        keys = r.keys('*limiter*')
        if keys:
            print(f"⚠️ Found {len(keys)} old keys. Clearing Redis for new strategy...")
            r.flushdb()
            print("✅ Redis cleared successfully!")
        else:
            print("✅ No old keys found, Redis is clean")
    except Exception as e:
        print(f"⚠️ Could not clear Redis: {e}")
def init_extensions(app):
    """Initialize Flask extensions with app context"""
    global _limiter
    
    db.init_app(app)

    redis_url = os.getenv("REDIS_URL")
    is_production = os.getenv("FLASK_ENV") == "production"
    
    # Enforce Redis in production
    if is_production and not redis_url:
        #pass
        raise ValueError("REDIS_URL must be set in production for rate limiting")
    
    # Configure storage options for Upstash
    storage_options = {}
    if redis_url and redis_url.startswith("rediss://"):
        storage_options = {
            "socket_connect_timeout": 30,
            "socket_timeout": 30,
            "retry_on_timeout": True,
            "health_check_interval": 30,
            "socket_keepalive": True, 
        }

    if not app.debug:
       # Call this BEFORE initializing limiter
       clear_redis_for_new_strategy()
    else:
        print("🔍 Skipping Redis clear (debug mode)")
    # Initialize limiter correctly (app passed directly)
    _limiter = Limiter(
        get_session_or_user_key,
        app=app, 
       # default_limits=["2000 per day", "200 per hour"],
        default_limits=["50000 per day", "5000 per hour"],
        storage_uri="memory://",
        storage_options=storage_options,
        #strategy="fixed-window",
        strategy="fixed-window",
        headers_enabled=True,
        retry_after="http-date"

    )
    
    # Custom rate limit error handler
    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.path.startswith('/api/'):
            return jsonify({
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Please try again later.",
                "retry_after": str(e.description) if e.description else "unknown"
            }), 429
        else:
            return render_template('errors/429.html', error=e.description), 429
    
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"
    
    # Store limiter on app for easy access
    app.extensions['limiter'] = _limiter
    
    return app

def get_limiter():
    """Safely get limiter - raises clear error if not initialized"""
    if _limiter is None:
        raise RuntimeError(
            "Rate limiter not initialized. "
            "Make sure init_extensions(app) is called before accessing limiter."
        )
    return _limiter

__all__ = ['db', 'login_manager', 'init_extensions', 'get_limiter']




