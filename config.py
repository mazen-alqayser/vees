import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'A_VERY_SECRET_KEY_THAT_SHOULD_BE_KEPT_SAFE'

    # قراءة رابط قاعدة البيانات من متغير البيئة DATABASE_URL
    database_url = os.getenv("DATABASE_URL", "sqlite:///site.db")
    
    # بعض خدمات الاستضافة (زي Railway/Heroku) بترجع الرابط بصيغة postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpassword123")
