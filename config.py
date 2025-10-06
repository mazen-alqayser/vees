import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'A_VERY_SECRET_KEY_THAT_SHOULD_BE_KEPT_SAFE'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'  # استخدام قاعدة بيانات SQLite بسيطة
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_EMAIL = "admin@example.com"  # البريد الإلكتروني الخاص بالمدير
    ADMIN_PASSWORD = "adminpassword123"  # كلمة المرور الخاصة بالمدير
