from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions (without app yet)
db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Config
    app.config['SECRET_KEY'] = 'your-secret-key'  # replace with a secure key
    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://<username>:<password>@<host>:<port>/CliffineCollection"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)

    # Import and register routes
    from app import routes
    app.register_blueprint(routes.main_bp)

    return app