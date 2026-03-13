from flask import Flask
import flask_migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = flask_migrate.Migrate()  # <-- add this

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    migrate.init_app(app, db)  # <-- initialize migrate with app & db

    from app import models

    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp)

    return app