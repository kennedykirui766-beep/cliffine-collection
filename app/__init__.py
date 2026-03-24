from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions (no circular imports here)
db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import blueprints **inside the function**, after db is ready
    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.main.routes import main_bp
    app.register_blueprint(main_bp)

    # Import models here if needed for Alembic to detect them
    from app import models  # <-- ensures models are loaded for migrations

    # Context processor example
    @app.context_processor
    def inject_cart_count():
        cart = session.get("cart", {})
        return dict(cart_count=sum(cart.values()) if cart else 0)

    return app