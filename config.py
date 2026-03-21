import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # --- SECURITY ---
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")

    # --- DATABASE ---
    db_uri = os.getenv("DATABASE_URL")

    # Fix for Render / Neon URL format
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)

    # Use PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = db_uri  # no SQLite fallback here
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- MAIL (SendGrid) ---
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.sendgrid.net")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "apikey")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")  # no fallback for security
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@cliffine.com")

    # --- APP SETTINGS ---
    ITEMS_PER_PAGE = 12