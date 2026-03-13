from flask import redirect, render_template, url_for
from flask import Blueprint, render_template
from app import db
from app.models import User, Product, Order, Coupon, Message
# app/admin/routes.py

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/")
@admin_bp.route("/dashboard")
def admin_dashboard():
    # Top Metrics
    from sqlalchemy import func

    total_revenue = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).scalar()
    total_users = User.query.count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    active_coupons = Coupon.query.filter_by(is_active=True).count()
    
    # Low stock products (e.g., stock <=5)
    low_stock_products = Product.query.filter(Product.stock <= 5).all()
    
    # Recent orders (limit 5)
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    # Recent messages (limit 5)
    recent_messages = Message.query.order_by(Message.created_at.desc()).limit(5).all()
    
    return render_template(
        'admin/dashboard.html',
        total_revenue=total_revenue,
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        active_coupons=active_coupons,
        low_stock_products=low_stock_products,
        recent_orders=recent_orders,
        recent_messages=recent_messages
    )
    
@admin_bp.route("/products")
def all_products():
    return render_template("admin/products/all_products.html")


@admin_bp.route("/products/add")
def add_product():
    return render_template("admin/products/add_product.html")


@admin_bp.route("/products/categories")
def product_categories():
    return render_template("admin/products/categories.html")


@admin_bp.route("/products/inventory")
def product_inventory():
    return render_template("admin/products/inventory.html")


@admin_bp.route("/products/reviews")
def product_reviews():
    return render_template("admin/products/reviews.html")    


@admin_bp.route("/orders")
def all_orders():
    return render_template("admin/orders/all_orders.html")


@admin_bp.route("/orders/pending")
def pending_orders():
    return render_template("admin/orders/pending.html")


@admin_bp.route("/orders/processing")
def processing_orders():
    return render_template("admin/orders/processing.html")


@admin_bp.route("/orders/delivered")
def delivered_orders():
    return render_template("admin/orders/delivered.html")


@admin_bp.route("/orders/cancelled")
def cancelled_orders():
    return render_template("admin/orders/cancelled.html")


@admin_bp.route("/orders/refunds")
def order_refunds():
    return render_template("admin/orders/refunds.html")


@admin_bp.route("/customers")
def all_users():
    return render_template("admin/customers/all_users.html")


@admin_bp.route("/customers/roles")
def user_roles():
    return render_template("admin/customers/roles.html")


@admin_bp.route("/payments/transactions")
def transactions():
    return render_template("admin/payments/transactions.html")


@admin_bp.route("/payments/methods")
def payment_methods():
    return render_template("admin/payments/methods.html")


@admin_bp.route("/payments/refunds")
def payment_refunds():
    return render_template("admin/payments/refunds.html")


@admin_bp.route("/coupons")
def coupons():
    return render_template("admin/coupons/index.html")

@admin_bp.route("/chamas")
def all_chamas():
    return render_template("admin/chamas/all_chamas.html")


@admin_bp.route("/chamas/members")
def chama_members():
    return render_template("admin/chamas/members.html")

@admin_bp.route("/messages")
def messages():
    return render_template("admin/messages/index.html")


@admin_bp.route("/inventory")
def inventory():
    return render_template("admin/inventory/index.html")


@admin_bp.route("/shipping")
def shipping():
    return render_template("admin/shipping/index.html")


@admin_bp.route("/reports")
def reports():
    return render_template("admin/reports/index.html")

@admin_bp.route("/pages")
def pages():
    return render_template("admin/pages/index.html")


@admin_bp.route("/media")
def media():
    return render_template("admin/media/index.html")

@admin_bp.route("/settings")
def settings():
    return render_template("admin/settings/index.html")

@admin_bp.route("/profile")
def admin_profile():
    return render_template("admin/profile.html")

@admin_bp.route("/logout")
def admin_logout():
    # Logic for logout
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/analytics")
def analytics():
    return render_template("admin/analytics/index.html")  