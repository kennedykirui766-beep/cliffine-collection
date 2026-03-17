from flask import Blueprint, render_template
from datetime import datetime

from app.models import Product

# Create blueprint
main_bp = Blueprint("main", __name__)

# Home
@main_bp.route("/")
def index():
    return render_template("index.html", current_year=datetime.now().year)

# Products
from datetime import datetime, timedelta

@main_bp.route("/products")
def products():
    # Fetch active products ordered by newest first
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()

    # Calculate date 30 days ago
    thirty_days_ago = datetime.now() - timedelta(days=30)

    return render_template(
        "products.html",
        products=products,
        thirty_days_ago=thirty_days_ago,   # pass it here!
        current_year=datetime.now().year
    )

# Categories
@main_bp.route("/categories")
def categories():
    return render_template("categories.html", current_year=datetime.now().year)

# Offers
@main_bp.route("/offers")
def offers():
    return render_template("offers.html", current_year=datetime.now().year)

# Chamas
@main_bp.route("/chama")
def chama():
    return render_template("chama_detail.html", current_year=datetime.now().year)

# Lipa Pole Pole
@main_bp.route("/lipa-pole-pole")
def lipa_pole_pole():
    return render_template("offers.html", current_year=datetime.now().year)

# Wishlist
@main_bp.route("/wishlist")
def wishlist():
    return render_template("wishlist.html", current_year=datetime.now().year)

# Blog
@main_bp.route("/blog")
def blog():
    return render_template("blog.html", current_year=datetime.now().year)

# About
@main_bp.route("/about")
def about():
    return render_template("about.html", current_year=datetime.now().year)

# Contact
@main_bp.route("/contact")
def contact():
    return render_template("contact.html", current_year=datetime.now().year)

# FAQ
@main_bp.route("/faq")
def faq():
    return render_template("faq.html", current_year=datetime.now().year)

# Cart
@main_bp.route("/cart")
def cart():
    return render_template("cart.html", current_year=datetime.now().year)

# Account
@main_bp.route("/account")
def account():
    return render_template("login.html", current_year=datetime.now().year)

# Privacy
@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html", current_year=datetime.now().year)

# Terms
@main_bp.route("/terms")
def terms():
    return render_template("terms.html", current_year=datetime.now().year)

# Search
@main_bp.route("/search")
def search():
    return render_template("search.html", current_year=datetime.now().year)

# Checkout
@main_bp.route("/checkout")
def checkout():
    return render_template("checkout.html", current_year=datetime.now().year)

# Orders
@main_bp.route("/orders")
def orders():
    return render_template("orders.html", current_year=datetime.now().year)

# User dashboard
@main_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", current_year=datetime.now().year)