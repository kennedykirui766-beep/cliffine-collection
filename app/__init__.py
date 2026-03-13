from flask import Flask
import flask_migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = flask_migrate.Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models

    # Admin routes
    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Main (public) routes
    from app.main.routes import main_bp
    app.register_blueprint(main_bp)

    return app