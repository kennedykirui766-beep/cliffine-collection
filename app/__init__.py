from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
import os

from markupsafe import Markup

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message_category = "info"

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    print("\n" + "="*60)
    print("DATABASE URI:", app.config["SQLALCHEMY_DATABASE_URI"])
    print("="*60 + "\n")

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
        from flask_login import current_user
        from flask import session
        from app.models import Cart

        cart_count = 0

        if current_user.is_authenticated:
            cart = Cart.query.filter_by(user_id=current_user.id).first()
        else:
            session_id = session.get("cart_session")
            cart = Cart.query.filter_by(session_id=session_id).first() if session_id else None

        if cart and cart.items:
            cart_count = sum(item.quantity for item in cart.items)

        return dict(cart_count=cart_count)
    
    from markupsafe import Markup

    @app.context_processor
    def utility_processor():

        def status_badge(status):
            status = (status or "").lower()

            colors = {
                "pending": "bg-yellow-100 text-yellow-800",
                "processing": "bg-blue-100 text-blue-800",
                "shipped": "bg-indigo-100 text-indigo-800",
                "delivered": "bg-green-100 text-green-800",
                "cancelled": "bg-red-100 text-red-800",
            }

            css = colors.get(status, "bg-gray-100 text-gray-800")

            return Markup(
                f'<span class="px-2 py-1 rounded-full text-xs font-semibold {css}">'
                f'{status.title()}'
                f'</span>'
            )

        return dict(status_badge=status_badge)

    return app