
import os
from dotenv import load_dotenv
from extensions import db


if os.environ.get("FLASK_ENV") != "production":
    load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:

    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY must be set in production")
    
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    
    _database_url = os.getenv("DATABASE_URL")
    if not _database_url:
        _database_url = f"sqlite:///{os.path.join(basedir, 'instance', 'super_kash_db')}"
    
  
    if _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    db.session.expire_on_commit = False
  
    SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 20,
            "max_overflow": 40,
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_use_lifo": True,
            "pool_timeout": 30,
        }
 
    MARZ_API_KEY = os.getenv("MARZ_API_KEY")
    MARZ_API_SECRET = os.getenv("MARZ_API_SECRET")
    MARZ_BASE_URL = os.getenv("MARZ_BASE_URL", "https://wallet.wearemarz.com/api/v1")
    MARZ_AUTH_HEADER = os.getenv("MARZ_AUTH_HEADER")
    

    APP_BASE_URL = os.getenv("APP_BASE_URL", "https://finicashi-app.onrender.com")

