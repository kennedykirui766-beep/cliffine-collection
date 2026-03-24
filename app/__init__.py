from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message_category = "info"

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Import models here, after db is initialized
    from app import models

    # user_loader must be after models import
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.main.routes import main_bp
    app.register_blueprint(main_bp)

    # -----------------------------
    # Context processor: cart count
    # -----------------------------
    from flask_login import current_user
    from app.models import Cart

    @app.context_processor
    def inject_cart_count():
        # If user is logged in, get their cart from DB
        if current_user.is_authenticated:
            cart = Cart.query.filter_by(user_id=current_user.id).first()
            if cart and cart.items:
                return dict(cart_count=sum(item.quantity for item in cart.items))
        # Otherwise, use session cart for guest
        else:
            cart = session.get("cart", {})
            return dict(cart_count=sum(cart.values()) if cart else 0)

        # Default fallback
        return dict(cart_count=0)

    return app