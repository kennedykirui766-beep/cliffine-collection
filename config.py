# app/config.py

import os

class Config:
    # Secret key for sessions and forms
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

    # Database settings (example with SQLite)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail settings (example for SendGrid)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.sendgrid.net'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'apikey'  # literally 'apikey'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'your-sendgrid-api-key'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'no-reply@cliffine.com'

    # Other settings
    ITEMS_PER_PAGE = 12