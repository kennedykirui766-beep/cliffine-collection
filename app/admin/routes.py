from flask import render_template
from app import app, db
from app.models import User, Product, Order, Coupon, Message

@app.route('/admin/dashboard')
def admin_dashboard():
    # Top Metrics
    total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    total_users = User.query.count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    active_coupons = Coupon.query.filter_by(active=True).count()
    
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