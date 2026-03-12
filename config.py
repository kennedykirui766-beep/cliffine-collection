import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"sqlite:///{os.path.join(BASE_DIR, 'cliffine_collection.db')}"  # <- changed here

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail settings (example)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.sendgrid.net'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'apikey'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'your-sendgrid-api-key'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'no-reply@cliffine.com'

    ITEMS_PER_PAGE = 12