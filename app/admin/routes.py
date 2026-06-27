import csv
from datetime import datetime
from flask import current_app, jsonify, redirect, render_template, url_for
from flask import Blueprint, render_template
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from app import db
from app.models import AdminActivity, Media, OrderItem, User, Product, Order, Coupon, CouponUsage, Message, Category, ProductImage, Chama, ChamaMember, DeliveryArea
from flask import render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
from sqlalchemy.exc import IntegrityError
from app.utils.helpers import generate_unique_slug
import cloudinary.uploader
import uuid
from sqlalchemy.orm import joinedload
from functools import wraps
from werkzeug.security import check_password_hash
from markupsafe import Markup

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("You are not authorized to access the admin panel.", "danger")
            return redirect(url_for("admin.admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------
# Admin Home
# -------------------------------------------------
@admin_bp.route("/")
def admin_home():
    # If already logged in as admin, go to dashboard
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for("admin.admin_dashboard"))

    # Otherwise go to login page
    return redirect(url_for("admin.admin_login"))


# -------------------------------------------------
# Admin Dashboard
# -------------------------------------------------
@admin_bp.route("/dashboard")
@admin_required
def admin_dashboard():
    from sqlalchemy import extract
    from datetime import datetime
    from calendar import month_name

    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 1:
        last_month_start = now.replace(year=now.year - 1, month=12, day=1,
                                       hour=0, minute=0, second=0, microsecond=0)
    else:
        last_month_start = now.replace(month=now.month - 1, day=1,
                                       hour=0, minute=0, second=0, microsecond=0)

    # --- Top Metrics ---
    total_revenue = db.session.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).scalar() or 0

    total_users = User.query.count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    active_coupons = Coupon.query.filter_by(is_active=True).count()

    # --- Growth Calculations ---
    this_month_revenue = db.session.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(
        Order.created_at >= this_month_start,
        Order.status != 'Cancelled'
    ).scalar() or 0

    last_month_revenue = db.session.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(
        Order.created_at >= last_month_start,
        Order.created_at < this_month_start,
        Order.status != 'Cancelled'
    ).scalar() or 0

    revenue_growth = round(
        ((this_month_revenue - last_month_revenue) / last_month_revenue) * 100, 1
    ) if last_month_revenue > 0 else 0.0

    this_month_order_count = db.session.query(func.count(Order.id)).filter(
        Order.created_at >= this_month_start
    ).scalar() or 0

    last_month_order_count = db.session.query(func.count(Order.id)).filter(
        Order.created_at >= last_month_start,
        Order.created_at < this_month_start
    ).scalar() or 0

    orders_growth = round(
        ((this_month_order_count - last_month_order_count) / last_month_order_count) * 100, 1
    ) if last_month_order_count > 0 else 0.0

    # --- Revenue Comparison: Weekly Breakdown ---
    this_month_daily = db.session.query(
        extract('day', Order.created_at).label('day'),
        func.coalesce(func.sum(Order.total_amount), 0).label('revenue')
    ).filter(
        Order.created_at >= this_month_start,
        Order.status != 'Cancelled'
    ).group_by(extract('day', Order.created_at)).all()

    this_month_weeks = [0.0, 0.0, 0.0, 0.0]
    for row in this_month_daily:
        week_idx = min((int(row.day) - 1) // 7, 3)
        this_month_weeks[week_idx] += float(row.revenue)

    last_month_daily = db.session.query(
        extract('day', Order.created_at).label('day'),
        func.coalesce(func.sum(Order.total_amount), 0).label('revenue')
    ).filter(
        Order.created_at >= last_month_start,
        Order.created_at < this_month_start,
        Order.status != 'Cancelled'
    ).group_by(extract('day', Order.created_at)).all()

    last_month_weeks = [0.0, 0.0, 0.0, 0.0]
    for row in last_month_daily:
        week_idx = min((int(row.day) - 1) // 7, 3)
        last_month_weeks[week_idx] += float(row.revenue)

    this_month_label = month_name[now.month]
    last_month_label = month_name[last_month_start.month]

    # --- Sales by Region ---
    # NOTE: Change 'shipping_city' to match your Order model's field name
    # Common alternatives: 'city', 'shipping_county', 'county'
    try:
        region_query = db.session.query(
            Order.shipping_city.label('region'),
            func.count(Order.id).label('order_count'),
            func.coalesce(func.sum(Order.total_amount), 0).label('revenue')
        ).filter(
            Order.shipping_city.isnot(None),
            Order.shipping_city != '',
            Order.status != 'Cancelled'
        ).group_by(Order.shipping_city).order_by(
            func.sum(Order.total_amount).desc()
        ).limit(6).all()

        total_region_revenue = sum(float(r.revenue) for r in region_query) or 1
        bar_colors = ['bg-primary', 'bg-violet-500', 'bg-accent',
                      'bg-amber-500', 'bg-emerald-500', 'bg-slate-400']
        chart_colors = ['#5423E7', '#7C3AED', '#D4AF37',
                        '#F59E0B', '#10B981', '#94A3B8']

        region_percentages = []
        for i, r in enumerate(region_query):
            pct = round((float(r.revenue) / total_region_revenue) * 100, 1)
            region_percentages.append({
                'name': r.region.title(),
                'percentage': pct,
                'revenue': float(r.revenue),
                'orders': r.order_count,
                'bar_color': bar_colors[i % len(bar_colors)],
                'chart_color': chart_colors[i % len(chart_colors)]
            })
    except Exception:
        region_percentages = []

    # --- Product Performance Heatmap (Category × Day of Week) ---
    # NOTE: Change 'OrderItem' to match your model name if different
    try:
        heatmap_raw = db.session.query(
            Product.category,
            extract('dow', Order.created_at).label('dow'),
            func.coalesce(func.sum(OrderItem.quantity), 0).label('sales')
        ).join(
            OrderItem, Product.id == OrderItem.product_id
        ).join(
            Order, OrderItem.order_id == Order.id
        ).filter(
            Order.status != 'Cancelled',
            Product.category.isnot(None)
        ).group_by(
            Product.category,
            extract('dow', Order.created_at)
        ).all()

        cat_totals = {}
        for row in heatmap_raw:
            cat_totals[row.category] = cat_totals.get(row.category, 0) + int(row.sales)
        top_categories = sorted(cat_totals.keys(),
                                key=lambda x: cat_totals[x], reverse=True)[:7]

        # Reorder: Mon(1) Tue(2) ... Sat(6) Sun(0)
        dow_order = [1, 2, 3, 4, 5, 6, 0]
        dow_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

        heatmap_matrix = []
        max_sales = 1
        for cat in top_categories:
            day_map = {}
            for h in heatmap_raw:
                if h.category == cat:
                    val = int(h.sales)
                    day_map[int(h.dow)] = val
                    if val > max_sales:
                        max_sales = val
            heatmap_matrix.append({
                'category': cat,
                'days': [day_map.get(d, 0) for d in dow_order],
                'total': cat_totals[cat]
            })
    except Exception:
        heatmap_matrix = []
        dow_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        max_sales = 1

    # --- Low Stock Products ---
    low_stock_products = Product.query.filter(Product.stock <= 5).all()

    # --- Recent Orders ---
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    # --- Recent Messages ---
    recent_messages = Message.query.order_by(Message.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_revenue=total_revenue,
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        active_coupons=active_coupons,
        low_stock_products=low_stock_products,
        recent_orders=recent_orders,
        recent_messages=recent_messages,
        this_month_weeks=this_month_weeks,
        last_month_weeks=last_month_weeks,
        revenue_growth=revenue_growth,
        orders_growth=orders_growth,
        this_month_label=this_month_label,
        last_month_label=last_month_label,
        region_percentages=region_percentages,
        heatmap_matrix=heatmap_matrix,
        dow_labels=dow_labels,
        max_sales=max_sales,
    )



@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated and current_user.role == "admin":
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        admin = User.query.filter_by(
            email=email,
            role="admin"
        ).first()

        if admin and check_password_hash(admin.password_hash, password):
            login_user(admin)
            return redirect(url_for("admin.admin_dashboard"))

        flash("Invalid admin credentials", "danger")

    return render_template("admin/login.html")    

@admin_bp.route("/logout")
@login_required
def admin_logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin.admin_login"))

@admin_bp.route("/products")
def all_products():
    products = Product.query.options(
        joinedload(Product.images)
    ).order_by(Product.created_at.desc()).all()

    return render_template("admin/products/all_products.html", products=products)


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()

    if request.method == "POST":

        # --- Basic Info ---
        product.name = request.form.get("name")
        product.slug = request.form.get("slug") or generate_unique_slug(product.name)

        if Product.query.filter(
            Product.slug == product.slug,
            Product.id != product.id
        ).first():
            product.slug = generate_unique_slug(product.name)

        category_id = request.form.get("category_id")
        product.category_id = int(category_id) if category_id and category_id.isdigit() else None

        product.sku = request.form.get("sku")
        product.short_description = request.form.get("short_description")
        product.description = request.form.get("description")

        # --- Pricing ---
        product.price = float(request.form.get("price") or 0)
        product.discount_price = float(request.form.get("discount_price") or 0)
        product.cost_price = float(request.form.get("cost_price") or 0)

        offer_percentage = request.form.get("offer_percentage") or 0
        product.offer_percentage = float(offer_percentage)

        # --- NEW OFFER FIELDS ---
        product.is_on_offer = True if float(offer_percentage) > 0 else False

        offer_start = request.form.get("offer_start")
        offer_end = request.form.get("offer_end")

        product.offer_start = (
            datetime.strptime(offer_start, "%Y-%m-%dT%H:%M")
            if offer_start else None
        )

        product.offer_end = (
            datetime.strptime(offer_start, "%Y-%m-%dT%H:%M")
            if offer_end else None
        )

        # --- Inventory ---
        product.stock = request.form.get("stock") or 0
        product.low_stock = request.form.get("low_stock") or 0
        product.stock_status = request.form.get("stock_status") or "in_stock"

        # --- Visibility ---
        status = request.form.get("status") or "draft"
        product.is_active = True if status.lower() == "published" else False

        # --- Special Options ---
        product.is_featured = True if request.form.get("featured") else False
        product.allow_reviews = True if request.form.get("allow_reviews") else False
        product.lipa_pole_pole = True if request.form.get("lipa_pole_pole") else False
        product.chama_eligible = True if request.form.get("chama_eligible") else False
        product.is_trending = True if request.form.get("is_trending") else False

        # --- Shipping ---
        product.weight = request.form.get("weight") or 0
        product.length = request.form.get("length") or 0
        product.width = request.form.get("width") or 0
        product.height = request.form.get("height") or 0
        product.shipping_class = request.form.get("shipping_class")

        # --- SEO ---
        product.meta_title = request.form.get("meta_title")
        product.meta_description = request.form.get("meta_description")
        product.meta_keywords = request.form.get("meta_keywords")

        # --- Apply discount logic ---
        product.apply_discount(float(offer_percentage) if offer_percentage else 0)

        try:
            db.session.commit()
            flash("Product updated successfully!", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Error: Product slug already exists.", "error")
            return redirect(url_for("admin.edit_product", product_id=product.id))

        # --- Handle Main Image ---
        image_file = request.files.get("main_image")
        upload_folder = "app/static/uploads"
        os.makedirs(upload_folder, exist_ok=True)

        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            path = os.path.join(upload_folder, filename)
            image_file.save(path)

            image_file.stream.seek(0)

            result = cloudinary.uploader.upload(
                image_file,
                folder="cliffine/products",
                public_id=str(uuid.uuid4())
            )

            image_url = result.get("secure_url")

            image = ProductImage(
                product_id=product.id,
                image_url=image_url,
                is_main=True
            )
            db.session.add(image)
            db.session.commit()

        # --- Handle Gallery Images ---
        gallery_files = request.files.getlist("images")
        for file in gallery_files:
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                path = os.path.join(upload_folder, filename)
                file.save(path)

                file.stream.seek(0)

                result = cloudinary.uploader.upload(
                    file,
                    folder="cliffine/products/gallery",
                    public_id=str(uuid.uuid4())
                )

                cloud_url = result.get("secure_url")

                gallery_image = ProductImage(
                    product_id=product.id,
                    image_url=cloud_url
                )
                db.session.add(gallery_image)

        db.session.commit()

        return redirect(url_for("admin.edit_product", product_id=product.id))

    return render_template(
        "admin/products/edit_product.html",
        product=product,
        categories=categories
    )


@admin_bp.route("/products/<int:product_id>/delete")
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted successfully!", "success")
    return redirect(url_for("admin.all_products"))

@admin_bp.route("/products/<int:product_id>/view")
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("admin/products/view_product.html", product=product)

def generate_unique_slug(name):
    base_slug = name.lower().replace(" ", "-")
    slug = base_slug
    counter = 1
    while Product.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

@admin_bp.route("/products/add", methods=["GET", "POST"])
def add_product():
    categories = Category.query.all()

    if request.method == "POST":
        # --- Basic Info ---
        name = request.form.get("name")
        slug = request.form.get("slug") or generate_unique_slug(name)
        # Ensure slug is unique if user entered one manually
        if Product.query.filter_by(slug=slug).first():
            slug = generate_unique_slug(name)

        category_id = request.form.get("category_id")
        category_id = int(category_id) if category_id and category_id.isdigit() else None
        sku = request.form.get("sku")
        short_description = request.form.get("short_description")
        description = request.form.get("description")

        # --- Pricing ---
        price = float(request.form.get("price") or 0)
        cost_price = float(request.form.get("cost_price") or 0)

        offer_percentage = float(request.form.get("offer_percentage") or 0)

        # 🆕 OFFER DATES (NEW)
        offer_start = request.form.get("offer_start")
        offer_end = request.form.get("offer_end")

        # convert to datetime if provided
        from datetime import datetime

        offer_start = datetime.strptime(offer_start, "%Y-%m-%d %H:%M") if offer_start else None
        offer_end = datetime.strptime(offer_end, "%Y-%m-%d %H:%M") if offer_end else None

        # --- Inventory ---
        stock = request.form.get("stock") or 0
        low_stock = request.form.get("low_stock") or 0
        stock_status = request.form.get("stock_status") or "in_stock"

        # --- Visibility ---
        status = request.form.get("status") or "draft"
        is_active = True if status.lower() == "published" else False

        # --- Special Options ---
        is_featured = True if request.form.get("featured") else False
        allow_reviews = True if request.form.get("allow_reviews") else False
        lipa_pole_pole = True if request.form.get("lipa_pole_pole") else False
        chama_eligible = True if request.form.get("chama_eligible") else False
        is_trending = True if request.form.get("is_trending") else False

        # --- Shipping ---
        weight = request.form.get("weight") or 0
        length = request.form.get("length") or 0
        width = request.form.get("width") or 0
        height = request.form.get("height") or 0
        shipping_class = request.form.get("shipping_class")

        # --- SEO ---
        meta_title = request.form.get("meta_title")
        meta_description = request.form.get("meta_description")
        meta_keywords = request.form.get("meta_keywords")

        # --- Create Product ---
        product = Product(
            name=name,
            slug=slug,
            description=description,
            short_description=short_description,
            price=price,
            cost_price=cost_price,
            sku=sku,
            category_id=category_id,
            stock=stock,
            low_stock=low_stock,
            stock_status=stock_status,
            is_active=is_active,
            is_featured=is_featured,
            is_trending=is_trending,
            allow_reviews=allow_reviews,
            lipa_pole_pole=lipa_pole_pole,
            chama_eligible=chama_eligible,
            weight=weight,
            length=length,
            width=width,
            height=height,
            shipping_class=shipping_class,
            meta_title=meta_title,
            meta_description=meta_description,
            meta_keywords=meta_keywords,

            # 🆕 OFFER FIELDS ADDED
            offer_percentage=offer_percentage,
            offer_start=offer_start,
            offer_end=offer_end,
            is_on_offer=True if offer_percentage and offer_percentage > 0 else False
        )

        # ✅ Apply discount automatically
        product.apply_discount(offer_percentage)

        db.session.add(product)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Error: Product slug already exists. Try again with a different name.", "error")
            return redirect(url_for("admin.add_product"))

        # --- Handle Main Image ---
        image_file = request.files.get("main_image")
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            upload_folder = "app/static/uploads"
            os.makedirs(upload_folder, exist_ok=True)
            path = os.path.join(upload_folder, filename)
            image_file.save(path)

            # Reset stream pointer before uploading to Cloudinary
            image_file.stream.seek(0)

            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                image_file,
                folder="cliffine/products",
                public_id=str(uuid.uuid4())
            )
            image_url = result.get("secure_url")

            image = ProductImage(
                product_id=product.id,
                image_url=image_url,
                is_main=True
            )

            db.session.add(image)
            db.session.commit()

        # --- Handle Gallery Images (Optional) ---
        gallery_files = request.files.getlist("gallery_images")
        for file in gallery_files:
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                path = os.path.join(upload_folder, filename)
                file.save(path)

                # Reset stream pointer for Cloudinary
                file.stream.seek(0)
                result = cloudinary.uploader.upload(
                    file,
                    folder="cliffine/products/gallery",
                    public_id=str(uuid.uuid4())
                )
                cloud_url = result.get("secure_url")

                gallery_image = ProductImage(
                    product_id=product.id,
                    image_url=cloud_url
                )
                db.session.add(gallery_image)

        db.session.commit()

        flash("Product added successfully!", "success")
        return redirect(url_for("admin.all_products"))

    return render_template(
        "admin/products/add_product.html",
        categories=categories
    )


@admin_bp.route("/categories")
def all_categories():
    categories = Category.query.order_by(Category.created_at.desc()).all()
    return render_template("admin/categories/all_categories.html", categories=categories)


@admin_bp.route("/categories/add", methods=["GET", "POST"])
def add_category():

    if request.method == "POST":

        name = request.form.get("name")
        slug = request.form.get("slug")

        description = request.form.get("description")
        is_active = True if request.form.get("is_active") else False

        # Handle image upload
        image_file = request.files.get("image")
        filename = None
        image_url = None  # ✅ NEW

        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)

            upload_folder = "app/static/uploads/categories"
            os.makedirs(upload_folder, exist_ok=True)

            path = os.path.join(upload_folder, filename)
            image_file.save(path)

            # ✅ VERY IMPORTANT FIX
            image_file.seek(0)

            # 🔥 Upload to Cloudinary
            result = cloudinary.uploader.upload(
                image_file,
                folder="cliffine/categories",
                public_id=str(uuid.uuid4())
            )
            image_url = result.get("secure_url")  # ✅ NEW

        category = Category(
            name=name,
            slug=slug,
            description=description,
            image=image_url if image_url else filename,
            is_active=is_active
        )

        db.session.add(category)
        db.session.commit()

        flash("Category added successfully", "success")
        return redirect(url_for("admin.all_categories"))

    return render_template("admin/categories/add_category.html")



@admin_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
def edit_category(category_id):

    category = Category.query.get_or_404(category_id)

    if request.method == "POST":

        category.name = request.form.get("name")
        category.slug = request.form.get("slug")
        category.description = request.form.get("description")
        category.is_active = True if request.form.get("is_active") else False

        db.session.commit()

        flash("Category updated successfully", "success")
        return redirect(url_for("admin.all_categories"))

    return render_template("admin/categories/edit_category.html", category=category)


@admin_bp.route("/categories/<int:category_id>/delete")
def delete_category(category_id):

    category = Category.query.get_or_404(category_id)

    db.session.delete(category)
    db.session.commit()

    flash("Category deleted successfully", "success")

    return redirect(url_for("admin.all_categories"))


@admin_bp.route("/products/inventory")
def product_inventory():
    return render_template("admin/products/inventory.html")


@admin_bp.route("/products/reviews")
def product_reviews():
    return render_template("admin/products/reviews.html")    



from datetime import datetime

@admin_bp.route("/orders")
def all_orders():

    today = datetime.utcnow().date()

    orders = Order.query.order_by(
        Order.created_at.desc()
    ).all()

    today_revenue = sum(
        order.total_amount
        for order in orders
        if order.created_at and order.created_at.date() == today
    )

    return render_template(
        "admin/orders/all_orders.html",
        orders=orders,
        today=today,
        today_revenue=today_revenue
    )


@admin_bp.route("/orders/pending")
def pending_orders():

    orders = Order.query.filter_by(
        status="pending"
    ).order_by(
        Order.created_at.desc()
    ).all()

    return render_template(
        "admin/orders/pending_orders.html",
        orders=orders
    )


@admin_bp.route("/orders/processing")
def processing_orders():

    orders = Order.query.filter_by(
        status="processing"
    ).order_by(
        Order.created_at.desc()
    ).all()

    return render_template(
        "admin/orders/processing_orders.html",
        orders=orders
        
    )


@admin_bp.route("/orders/delivered")
def delivered_orders():

    today = datetime.utcnow().date()

    orders = Order.query.filter_by(
        status="delivered"
    ).order_by(
        Order.created_at.desc()
    ).all()

    return render_template(
        "admin/orders/delivered_orders.html",
        orders=orders,
        today=today
    )

@admin_bp.route("/orders/<int:order_id>/deliver", methods=["POST"])
def deliver_order(order_id):

    order = Order.query.get_or_404(order_id)

    # safety check
    if order.status == "delivered":
        flash("Order is already delivered.", "warning")
        return redirect(url_for("admin.all_orders"))

    order.status = "delivered"

    # optional but recommended (if you added it)
    order.delivered_at = datetime.utcnow()

    db.session.commit()

    flash(f"Order #{order.id} marked as delivered.", "success")

    return redirect(url_for("admin.delivered_orders"))

@admin_bp.route("/orders/cancelled")
def cancelled_orders():

    orders = Order.query.filter_by(
        status="cancelled"
    ).order_by(
        Order.created_at.desc()
    ).all()

    return render_template(
        "admin/orders/cancelled_orders.html",
        orders=orders
    )

@admin_bp.route("/users/<int:user_id>")
def user_detail(user_id):

    user = User.query.get_or_404(user_id)

    return render_template(
        "admin/users/user_detail.html",
        user=user
    )

@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
def update_order_status(order_id):

    order = Order.query.get_or_404(order_id)

    new_status = request.form.get("status")

    if new_status not in ["pending", "processing", "shipped", "delivered"]:
        flash("Invalid status", "danger")
        return redirect(url_for("admin.all_orders"))

    order.status = new_status

    # optional timestamps
    if new_status == "shipped":
        order.shipped_at = datetime.utcnow()

    if new_status == "delivered":
        order.delivered_at = datetime.utcnow()

    db.session.commit()

    flash("Order status updated.", "success")

    return redirect(url_for("admin.all_orders"))

from datetime import datetime

@admin_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):

    order = Order.query.get_or_404(order_id)

    if order.status == "delivered":
        flash("Delivered orders cannot be cancelled.", "warning")
        return redirect(url_for("admin.all_orders"))

    order.status = "cancelled"

    # Optional if your model has this field
    # order.cancelled_at = datetime.utcnow()

    db.session.commit()

    flash(f"Order #{order.id} has been cancelled.", "success")

    return redirect(url_for("admin.cancelled_orders"))

@admin_bp.route("/orders/<int:order_id>/note", methods=["POST"])
def add_order_note(order_id):

    order = Order.query.get_or_404(order_id)

    note = request.form.get("note")

    order.note = note  # or append to a notes table if you have one

    db.session.commit()

    flash("Note added successfully.", "success")

    return redirect(url_for("admin.all_orders"))

@admin_bp.route("/orders/refunds")
def order_refunds():

    orders = Order.query.filter_by(
        status="refund_requested"
    ).order_by(
        Order.created_at.desc()
    ).all()

    return render_template(
        "admin/orders/order_refunds.html",
        orders=orders
    )

@admin_bp.route("/orders/<int:order_id>/process", methods=["POST"])
def process_order(order_id):
    order = Order.query.get_or_404(order_id)

    order.status = "processing"

    db.session.commit()

    flash("Order marked as processing.", "success")

    return redirect(url_for("admin.all_orders"))

@admin_bp.route("/orders/<int:order_id>/ship", methods=["POST"])
def ship_order(order_id):

    order = Order.query.get_or_404(order_id)

    if order.status == "delivered":
        flash("Cannot ship a delivered order.", "warning")
        return redirect(url_for("admin.all_orders"))

    order.status = "shipped"
    order.shipped_at = datetime.utcnow()

    db.session.commit()

    flash(f"Order #{order.id} marked as shipped.", "success")

    return redirect(url_for("admin.shipped_orders"))

@admin_bp.route("/orders/shipped")
def shipped_orders():

    orders = Order.query.filter_by(
        status="shipped"
    ).order_by(
        Order.created_at.desc()
    ).all()

    return render_template(
        "admin/orders/shipped_orders.html",
        orders=orders
    ) 


@admin_bp.route("/orders/<int:order_id>")
def order_details(order_id):

    order = Order.query.get_or_404(order_id)

    return render_template(
        "admin/orders/details.html",
        order=order
    )

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




@admin_bp.route("/chamas")
def all_chamas():
    chamas = Chama.query.order_by(Chama.created_at.desc()).all()

    return render_template(
        "admin/chamas/all_chamas.html",
        chamas=chamas
    )


@admin_bp.route("/create", methods=["GET", "POST"])
def create_chama():
    if request.method == "POST":
        # ── Basic Information ───────────────────────────────────────
        name              = request.form.get("name")
        description       = request.form.get("description")
        category          = request.form.get("category")
        target_amount     = request.form.get("target_amount")
        target_product    = request.form.get("target_product")
        deadline_str      = request.form.get("deadline")

        # ── Contribution Plan ──────────────────────────────────────
        contribution_amount = request.form.get("contribution_amount")
        contribution_frequency = request.form.get("frequency")
        max_members       = request.form.get("max_members")

        # ── Privacy & Access ───────────────────────────────────────
        privacy           = request.form.get("privacy")
        invite_code       = request.form.get("invite_code")

        # ── Rules ──────────────────────────────────────────────────
        rules             = request.form.get("rules")

        # ── Payment Methods ────────────────────────────────────────
        accepts_mpesa = True if request.form.get("payment_mpesa") else False
        accepts_card  = True if request.form.get("payment_card") else False
        accepts_bank  = True if request.form.get("payment_bank") else False

        mpesa_type        = request.form.get("mpesa_type")
        mpesa_number      = request.form.get("mpesa_number")
        mpesa_account     = request.form.get("mpesa_account")

        # ── Notifications ──────────────────────────────────────────
        notify_on_join    = bool(request.form.get("notify_join"))
        notify_on_payment = bool(request.form.get("notify_payment"))
        notify_on_goal    = bool(request.form.get("notify_goal"))

        # ── Cover Image Handling (Cloudinary) ──────────────────────
        cover_image = request.files.get("cover_image")
        cover_filename = None

        if cover_image and cover_image.filename:
            try:
                upload_result = cloudinary.uploader.upload(
                    cover_image,
                    folder="chama_covers",
                    resource_type="image"
                )

                cover_filename = upload_result.get("secure_url")

            except Exception as e:
                flash(f"Error uploading image: {str(e)}", "error")

        # ── Start Date Parsing ─────────────────────────────────────
        start_date_str = request.form.get("start_date")
        start_date = None

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                print("Invalid start date format:", start_date_str)

        # ── Deadline Parsing ───────────────────────────────────────
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        # ── Generate Invite Code ───────────────────────────────────
        import uuid
        invite_code = f"CHM-{uuid.uuid4().hex[:6].upper()}"
        existing = Chama.query.filter_by(invite_code=invite_code).first()
        while existing:
            invite_code = f"CHM-{uuid.uuid4().hex[:6].upper()}"
            existing = Chama.query.filter_by(invite_code=invite_code).first()

        # ── Create model instance ──────────────────────────────────
        chama = Chama(
            name                  = name,
            description           = description,
            category              = category,
            target_amount         = float(target_amount) if target_amount else None,
            product_id            = target_product if target_product else None,
            start_date            = start_date,
            deadline              = deadline,
            contribution_amount   = float(contribution_amount) if contribution_amount else None,
            contribution_frequency= contribution_frequency,
            max_members           = int(max_members) if max_members else None,
            privacy               = privacy,
            invite_code           = invite_code,
            rules                 = rules,

            # Payment flags
            accepts_mpesa         = accepts_mpesa,
            accepts_card          = accepts_card,
            accepts_bank          = accepts_bank,
            mpesa_type            = mpesa_type,
            mpesa_number          = mpesa_number,
            mpesa_account         = mpesa_account,

            # Notifications
            notify_on_join        = notify_on_join,
            notify_on_payment     = notify_on_payment,
            notify_on_goal        = notify_on_goal,

            # Image (Cloudinary URL)
            cover_image           = cover_filename,
        )

        try:
            db.session.add(chama)
            db.session.commit()
            flash("Chama created successfully", "success")
            return redirect(url_for('admin.all_chamas'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating Chama: {str(e)}", "error")

    return render_template("admin/chamas/create.html")



@admin_bp.route("/chamas/edit/<int:chama_id>", methods=["GET", "POST"])
def edit_chama(chama_id):

    chama = Chama.query.get_or_404(chama_id)

    if request.method == "POST":
        # ── Basic Info ─────────────────────
        chama.name = request.form.get("name")
        chama.description = request.form.get("description")
        chama.category = request.form.get("category")

        # ── Target / Goal ──────────────────
        chama.product_id = request.form.get("product_id") or None
        chama.target_amount = request.form.get("target_amount") or None

        deadline = request.form.get("deadline")
        chama.deadline = datetime.strptime(deadline, "%Y-%m-%d") if deadline else None

        # ── Contribution Plan ──────────────
        chama.contribution_amount = request.form.get("contribution_amount") or None
        chama.contribution_frequency = request.form.get("contribution_frequency")
        chama.max_members = request.form.get("max_members") or None

        # ── Rules ─────────────────────────
        chama.rules = request.form.get("rules")

        # ── Privacy ───────────────────────
        chama.privacy = request.form.get("privacy")
        chama.invite_code = request.form.get("invite_code")

        # ── Payments ──────────────────────
        chama.accepts_mpesa = bool(request.form.get("accepts_mpesa"))
        chama.accepts_card = bool(request.form.get("accepts_card"))
        chama.accepts_bank = bool(request.form.get("accepts_bank"))

        chama.mpesa_type = request.form.get("mpesa_type")
        chama.mpesa_number = request.form.get("mpesa_number")
        chama.mpesa_account = request.form.get("mpesa_account")

        # ── Notifications ─────────────────
        chama.notify_on_join = bool(request.form.get("notify_on_join"))
        chama.notify_on_payment = bool(request.form.get("notify_on_payment"))
        chama.notify_on_goal = bool(request.form.get("notify_on_goal"))

        # ── Status ────────────────────────
        chama.status = request.form.get("status")

        # ── Dates ─────────────────────────
        start_date = request.form.get("start_date")
        chama.start_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None

        db.session.commit()

        flash("Chama updated successfully", "success")
        return redirect(url_for("admin.all_chamas"))

    return render_template(
        "admin/chamas/edit_chama.html",
        chama=chama
    )

@admin_bp.route("/chamas/delete/<int:chama_id>", methods=["POST"])
def delete_chama(chama_id):

    chama = Chama.query.get_or_404(chama_id)

    try:
        db.session.delete(chama)
        db.session.commit()
        flash("Chama deleted successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting chama: {str(e)}", "error")

    return redirect(url_for("admin.all_chamas"))

@admin_bp.route("/chama-members")
def chama_members():
    members = ChamaMember.query.order_by(ChamaMember.joined_at.desc()).all()
    
    return render_template(
        "admin/chamas/members.html",
        members=members
    )


@admin_bp.route("/messages")
def messages():
    return render_template("admin/messages/index.html")


@admin_bp.route("/inventory")
@admin_required
def inventory():
    from sqlalchemy import func, or_

    # Filters
    search = request.args.get("search", "").strip()
    category_filter = request.args.get("category", "all")
    stock_filter = request.args.get("stock", "all")
    sort_by = request.args.get("sort", "name_asc")
    page = request.args.get("page", 1, type=int)
    per_page = 20

    # Base query
    query = Product.query

    # Search
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            Product.name.ilike(search_term),
            Product.sku.ilike(search_term) if hasattr(Product, 'sku') else False,
        ))

    # Category filter
    if category_filter and category_filter != "all":
        query = query.filter(Product.category_id == int(category_filter))

    # Stock filter
    if stock_filter == "in_stock":
        query = query.filter(Product.stock > 5)
    elif stock_filter == "low_stock":
        query = query.filter(Product.stock.between(1, 5))
    elif stock_filter == "out_of_stock":
        query = query.filter(Product.stock == 0)

    # Sorting
    if sort_by == "name_asc":
        query = query.order_by(Product.name.asc())
    elif sort_by == "name_desc":
        query = query.order_by(Product.name.desc())
    elif sort_by == "stock_asc":
        query = query.order_by(Product.stock.asc())
    elif sort_by == "stock_desc":
        query = query.order_by(Product.stock.desc())
    elif sort_by == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort_by == "newest":
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.name.asc())

    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    products = pagination.items

    # ===================== SUMMARY METRICS =====================
    total_products = Product.query.count()
    total_stock_units = db.session.query(func.coalesce(func.sum(Product.stock), 0)).scalar() or 0

    # Stock value: use cost_price if available, otherwise use price
    cost_field = getattr(Product, 'cost_price', None)
    if cost_field is not None:
        total_stock_value = db.session.query(
            func.coalesce(func.sum(Product.stock * cost_field), 0)
        ).scalar() or 0
    else:
        total_stock_value = db.session.query(
            func.coalesce(func.sum(Product.stock * Product.price), 0)
        ).scalar() or 0

    low_stock_count = Product.query.filter(Product.stock.between(1, 5)).count()
    out_of_stock_count = Product.query.filter(Product.stock == 0).count()

    # Average stock per product
    avg_stock = round(total_stock_units / total_products) if total_products > 0 else 0

    # ===================== CATEGORIES =====================
    categories = []
    try:
        from app.models import Category
        categories = Category.query.order_by(Category.name.asc()).all()
    except Exception:
        pass

    # ===================== STOCK DISTRIBUTION =====================
    stock_distribution = []
    try:
        dist_labels = ["0 (Out)", "1-5 (Low)", "6-20 (Med)", "21-50 (Good)", "50+ (High)"]
        dist_counts = [
            Product.query.filter(Product.stock == 0).count(),
            Product.query.filter(Product.stock.between(1, 5)).count(),
            Product.query.filter(Product.stock.between(6, 20)).count(),
            Product.query.filter(Product.stock.between(21, 50)).count(),
            Product.query.filter(Product.stock > 50).count(),
        ]
        max_dist = max(dist_counts) if dist_counts else 1
        dist_colors = ["#EF4444", "#F59E0B", "#3B82F6", "#10B981", "#5423E7"]
        for i, label in enumerate(dist_labels):
            stock_distribution.append({
                "label": label,
                "count": dist_counts[i],
                "percentage": round((dist_counts[i] / total_products * 100), 1) if total_products > 0 else 0,
                "width": round((dist_counts[i] / max_dist * 100), 1) if max_dist > 0 else 0,
                "color": dist_colors[i],
            })
    except Exception:
        pass

    # ===================== RECENT STOCK CHANGES =====================
    recent_changes = []
    try:
        from app.models import AdminActivity
        changes = AdminActivity.query.filter(
            AdminActivity.action.in_(['stock_adjusted', 'stock_imported']),
        ).order_by(AdminActivity.created_at.desc()).limit(5).all()
        for c in changes:
            recent_changes.append({
                "description": c.description,
                "time": c.created_at,
            })
    except Exception:
        pass

    # Build product list with images
    product_list = []
    for p in products:
        image_url = "https://placehold.co/80x80/F3F4F6/A0A0A0?text=Product"
        if hasattr(p, 'images') and p.images:
            image_url = p.images[0].image_url
        elif hasattr(p, 'image') and p.image:
            image_url = p.image

        selling_price = p.discount_price if p.discount_price else p.price
        stock_value = p.stock * (getattr(p, 'cost_price', None) or p.price)

        product_list.append({
            "id": p.id,
            "name": p.name,
            "slug": getattr(p, 'slug', ''),
            "sku": getattr(p, 'sku', ''),
            "price": float(p.price),
            "discount_price": float(p.discount_price) if p.discount_price else None,
            "selling_price": float(selling_price),
            "cost_price": float(getattr(p, 'cost_price', 0) or 0),
            "stock": p.stock,
            "stock_value": float(stock_value),
            "category": p.category.name if hasattr(p, 'category') and p.category else "Uncategorized",
            "category_id": p.category_id if hasattr(p, 'category_id') else None,
            "image": image_url,
            "is_active": getattr(p, 'is_active', True),
            "lipa_pole_pole": getattr(p, 'lipa_pole_pole', False),
        })

    return render_template(
        "admin/inventory/index.html",
        products=product_list,
        pagination=pagination,
        total_products=total_products,
        total_stock_units=total_stock_units,
        total_stock_value=total_stock_value,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        avg_stock=avg_stock,
        categories=categories,
        stock_distribution=stock_distribution,
        recent_changes=recent_changes,
        search=search,
        category_filter=category_filter,
        stock_filter=stock_filter,
        sort_by=sort_by,
    )


@admin_bp.route("/inventory/adjust", methods=["POST"])
@admin_required
def inventory_adjust():
    from app.utils.activity import log_activity

    data = request.get_json()
    product_id = data.get("product_id")
    adjustment = data.get("adjustment", 0)  # positive or negative integer
    reason = data.get("reason", "").strip()

    if not product_id or adjustment == 0:
        return jsonify(success=False, message="Invalid adjustment."), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify(success=False, message="Product not found."), 404

    old_stock = product.stock
    new_stock = old_stock + adjustment

    if new_stock < 0:
        return jsonify(success=False, message=f"Cannot reduce below 0. Current stock: {old_stock}."), 400

    product.stock = new_stock
    db.session.commit()

    direction = "increased" if adjustment > 0 else "decreased"
    log_activity(
        current_user.id,
        "stock_adjusted",
        f"{product.name}: {old_stock} → {new_stock} ({direction} by {abs(adjustment)}). Reason: {reason or 'Manual adjustment'}"
    )

    return jsonify(
        success=True,
        message=f"Stock {direction} by {abs(adjustment)}. New stock: {new_stock}",
        new_stock=new_stock,
        old_stock=old_stock,
    )


@admin_bp.route("/inventory/bulk-update", methods=["POST"])
@admin_required
def inventory_bulk_update():
    from app.utils.activity import log_activity

    data = request.get_json()
    updates = data.get("updates", [])  # [{product_id: 1, stock: 50}, ...]

    if not updates:
        return jsonify(success=False, message="No updates provided."), 400

    updated = 0
    errors = []

    for item in updates:
        product = Product.query.get(item.get("product_id"))
        if not product:
            errors.append(f"Product ID {item.get('product_id')} not found.")
            continue

        new_stock = item.get("stock")
        if new_stock is None or new_stock < 0:
            errors.append(f"Invalid stock value for {product.name}.")
            continue

        old_stock = product.stock
        product.stock = int(new_stock)
        updated += 1

    if updated > 0:
        db.session.commit()
        log_activity(
            current_user.id,
            "stock_imported",
            f"Bulk stock update: {updated} products adjusted."
        )

    return jsonify(
        success=True,
        message=f"{updated} products updated.",
        updated=updated,
        errors=errors if errors else None,
    )


@admin_bp.route("/inventory/low-stock-api")
@admin_required
def inventory_low_stock_api():
    """API endpoint for dashboard or other pages to get low stock count."""
    low = Product.query.filter(Product.stock.between(1, 5)).count()
    out = Product.query.filter(Product.stock == 0).count()
    return jsonify(low_stock=low, out_of_stock=out, total_alerts=low + out)


@admin_bp.route("/shipping")
def shipping():
    return render_template("admin/shipping/index.html")


@admin_bp.route("/reports")
@admin_required
def reports():
    from sqlalchemy import func, extract, or_
    from datetime import datetime, timedelta
    from calendar import month_name, monthrange
    import csv
    from io import StringIO
    from flask import Response

    now = datetime.utcnow()
    period = request.args.get("period", "month")
    txn_search = request.args.get("txn_search", "").strip()
    txn_status = request.args.get("txn_status", "all")
    txn_page = request.args.get("txn_page", 1, type=int)

    # ===================== DATE RANGES =====================
    if period == "quarter":
        current_quarter = (now.month - 1) // 3
        current_start = datetime(now.year, current_quarter * 3 + 1, 1)
        prev_start = current_start - timedelta(days=90)
        period_label = f"Q{current_quarter + 1} {now.year}"
    elif period == "year":
        current_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = current_start.replace(year=now.year - 1)
        period_label = str(now.year)
    else:
        current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = (current_start - timedelta(days=1)).replace(day=1)
        period_label = f"{month_name[now.month]} {now.year}"

    current_end = now
    prev_end = current_start

    # ===================== HELPER =====================
    def q_sum(field, start, end, status_exclude=None):
        q = db.session.query(func.coalesce(func.sum(field), 0)).filter(
            Order.created_at >= start,
            Order.created_at < end,
        )
        if status_exclude:
            q = q.filter(Order.status.notin_(status_exclude))
        return q.scalar() or 0

    # ===================== SUMMARY CARDS =====================
    total_revenue = q_sum(Order.total_amount, current_start, current_end, ['Cancelled'])

    # Tax — use tax_amount if available, otherwise estimate 16% VAT
    tax_amount_field = getattr(Order, 'tax_amount', None)
    if tax_amount_field is not None:
        total_tax = q_sum(tax_amount_field, current_start, current_end, ['Cancelled', 'Refunded'])
    else:
        total_tax = round(total_revenue * 0.16 / 1.16, 0)

    # Refunds
    refunded_orders = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        Order.created_at >= current_start,
        Order.created_at < current_end,
        Order.status == 'Refunded',
    ).scalar() or 0
    refund_count = db.session.query(func.count(Order.id)).filter(
        Order.created_at >= current_start,
        Order.created_at < current_end,
        Order.status == 'Refunded',
    ).scalar() or 0

    # Shipping Revenue
    shipping_field = getattr(Order, 'shipping_fee', None)
    if shipping_field is not None:
        shipping_revenue = q_sum(shipping_field, current_start, current_end, ['Cancelled', 'Refunded'])
    else:
        shipping_revenue = 0

    # Net Profit (Revenue - Refunds - Tax - Shipping)
    net_profit = total_revenue - refunded_orders - total_tax

    # ===================== TOP PRODUCTS =====================
    top_products_raw = db.session.query(
        Product.id,
        Product.name,
        Product.price,
        Product.slug,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('units_sold'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label('revenue'),
    ).join(
        OrderItem, Product.id == OrderItem.product_id
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Order.created_at >= current_start,
        Order.created_at < current_end,
        Order.status.notin_(['Cancelled', 'Refunded']),
    ).group_by(
        Product.id, Product.name, Product.price, Product.slug
    ).order_by(
        func.sum(OrderItem.quantity * OrderItem.unit_price).desc()
    ).limit(8).all()

    top_products = []
    for p in top_products_raw:
        image_url = "https://placehold.co/80x80/F3F4F6/A0A0A0?text=Product"
        if hasattr(p, 'images') and p.images:
            image_url = p.images[0].image_url
        elif hasattr(p, 'image') and p.image:
            image_url = p.image
        top_products.append({
            "id": p.id,
            "name": p.name,
            "price": float(p.price),
            "units_sold": int(p.units_sold),
            "revenue": float(p.revenue),
            "image": image_url,
            "slug": getattr(p, 'slug', ''),
        })

    # ===================== LOW STOCK =====================
    low_stock_threshold = 10
    low_stock = Product.query.filter(
        Product.stock <= low_stock_threshold
    ).order_by(Product.stock.asc()).limit(10).all()

    # ===================== TRANSACTION LOG =====================
    txn_query = Order.query.order_by(Order.created_at.desc())

    if txn_search:
        search_term = f"%{txn_search}%"
        txn_query = txn_query.filter(or_(
            Order.id.cast(db.String).ilike(search_term),
            Order.customer_name.ilike(search_term),
            Order.payment_method.ilike(search_term),
        ))

    if txn_status and txn_status != "all":
        txn_query = txn_query.filter(Order.status == txn_status)

    txn_pagination = txn_query.paginate(page=txn_page, per_page=15, error_out=False)
    transactions = txn_pagination.items

    # ===================== PERIOD GROWTH =====================
    prev_revenue = q_sum(Order.total_amount, prev_start, prev_end, ['Cancelled'])
    revenue_change = round(((total_revenue - prev_revenue) / prev_revenue * 100), 1) if prev_revenue > 0 else None

    return render_template(
        "admin/reports/index.html",
        period=period,
        period_label=period_label,
        total_revenue=total_revenue,
        total_tax=total_tax,
        refunded_amount=refunded_orders,
        refund_count=refund_count,
        shipping_revenue=shipping_revenue,
        net_profit=net_profit,
        revenue_change=revenue_change,
        top_products=top_products,
        low_stock=low_stock,
        low_stock_threshold=low_stock_threshold,
        transactions=transactions,
        txn_pagination=txn_pagination,
        txn_search=txn_search,
        txn_status=txn_status,
    )


@admin_bp.route("/reports/export")
@admin_required
def reports_export():
    """Export transactions as CSV."""
    from io import StringIO
    from flask import Response

    status_filter = request.args.get("status", "all")

    query = Order.query.order_by(Order.created_at.desc())
    if status_filter and status_filter != "all":
        query = query.filter(Order.status == status_filter)

    orders = query.limit(5000).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID", "Date", "Customer", "Payment Method", "Amount", "Status"])

    for o in orders:
        writer.writerow([
            f"#{o.id}",
            o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
            getattr(o, 'customer_name', '') or (o.user.full_name if hasattr(o, 'user') and o.user else ''),
            getattr(o, 'payment_method', '') or '',
            float(o.total_amount) if o.total_amount else 0,
            o.status,
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions_report.csv"},
    )


@admin_bp.route("/reports/print")
@admin_required
def reports_print():
    """Print-friendly report view."""
    from sqlalchemy import func
    from datetime import datetime

    now = datetime.utcnow()
    current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_revenue = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        Order.created_at >= current_start,
        Order.status != 'Cancelled',
    ).scalar() or 0

    total_orders = db.session.query(func.count(Order.id)).filter(
        Order.created_at >= current_start,
    ).scalar() or 0

    refunded = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        Order.created_at >= current_start,
        Order.status == 'Refunded',
    ).scalar() or 0

    tax_field = getattr(Order, 'tax_amount', None)
    if tax_field is not None:
        total_tax = db.session.query(func.coalesce(func.sum(tax_field), 0)).filter(
            Order.created_at >= current_start,
            Order.status.notin_(['Cancelled', 'Refunded']),
        ).scalar() or 0
    else:
        total_tax = round(total_revenue * 0.16 / 1.16, 0)

    top_products = db.session.query(
        Product.name,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('units'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label('rev'),
    ).join(OrderItem, Product.id == OrderItem.product_id).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Order.created_at >= current_start,
        Order.status.notin_(['Cancelled', 'Refunded']),
    ).group_by(Product.name).order_by(
        func.sum(OrderItem.quantity * OrderItem.unit_price).desc()
    ).limit(10).all()

    recent = Order.query.order_by(Order.created_at.desc()).limit(30).all()

    return render_template(
        "admin/reports/print_report.html",
        generated_at=now.strftime("%d %B %Y, %H:%M"),
        period_label=f"{now.strftime('%B %Y')}",
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_tax=total_tax,
        refunded=refunded,
        net_profit=total_revenue - refunded - total_tax,
        top_products=top_products,
        recent_orders=recent,
    )

import re
from flask import request, redirect, url_for, jsonify, flash
from app.models import Page, db
from app.utils.activity import log_activity
from functools import wraps


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text


@admin_bp.route("/pages")
@admin_required
def pages():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "all")
    page = request.args.get("page", 1, type=int)
    per_page = 15

    query = Page.query.order_by(Page.sort_order.asc(), Page.title.asc())

    if search:
        query = query.filter(Page.title.ilike(f"%{search}%"))

    if status_filter and status_filter != "all":
        query = query.filter(Page.status == status_filter)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    all_pages = pagination.items

    total_published = Page.query.filter_by(status="published").count()
    total_drafts = Page.query.filter_by(status="draft").count()

    page_list = []
    for p in all_pages:
        page_list.append({
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "status": p.status,
            "is_homepage": p.is_homepage,
            "sort_order": p.sort_order,
            "meta_description": p.meta_description or "",
            "content_preview": (p.content[:120] + "...") if p.content and len(p.content) > 120 else (p.content or ""),
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })

    return render_template(
        "admin/pages/index.html",
        pages=page_list,
        pagination=pagination,
        total_published=total_published,
        total_drafts=total_drafts,
        search=search,
        status_filter=status_filter,
    )


@admin_bp.route("/pages/create", methods=["POST"])
@admin_required
def create_page():
    data = request.get_json()

    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    content = data.get("content") or ""
    meta_description = (data.get("meta_description") or "").strip()
    meta_keywords = (data.get("meta_keywords") or "").strip()
    status = data.get("status", "draft")
    sort_order = data.get("sort_order", 0)

    errors = []
    if not title:
        errors.append("Title is required.")
    if not slug:
        slug = _slugify(title)
    if not slug:
        errors.append("Slug could not be generated from title.")

    if not errors:
        existing = Page.query.filter_by(slug=slug).first()
        if existing:
            errors.append(f"A page with slug '{slug}' already exists.")

    if errors:
        return jsonify(success=False, message="; ".join(errors)), 400

    try:
        sort_order = int(sort_order)
    except (TypeError, ValueError):
        sort_order = 0

    page = Page(
        title=title,
        slug=slug,
        content=content,
        meta_description=meta_description[:500],
        meta_keywords=meta_keywords[:500],
        status=status,
        sort_order=sort_order,
    )
    db.session.add(page)
    db.session.commit()

    log_activity(
        current_user.id, "page_created",
        f"Created page: {title} ({slug})"
    )

    return jsonify(
        success=True,
        message=f"Page '{title}' created successfully!",
        redirect=url_for("admin.pages"),
    )


@admin_bp.route("/pages/<int:page_id>", methods=["GET"])
@admin_required
def get_page(page_id):
    page = Page.query.get_or_404(page_id)
    return jsonify({
        "success": True,
        "page": {
            "id": page.id,
            "title": page.title,
            "slug": page.slug,
            "content": page.content or "",
            "meta_description": page.meta_description or "",
            "meta_keywords": page.meta_keywords or "",
            "status": page.status,
            "is_homepage": page.is_homepage,
            "sort_order": page.sort_order,
            "created_at": page.created_at.isoformat() if page.created_at else "",
            "updated_at": page.updated_at.isoformat() if page.updated_at else "",
        }
    })


@admin_bp.route("/pages/<int:page_id>/update", methods=["POST"])
@admin_required
def update_page(page_id):
    page = Page.query.get_or_404(page_id)
    data = request.get_json()

    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    content = data.get("content") or ""
    meta_description = (data.get("meta_description") or "").strip()
    meta_keywords = (data.get("meta_keywords") or "").strip()
    status = data.get("status", page.status)
    sort_order = data.get("sort_order", page.sort_order)
    is_homepage = data.get("is_homepage", page.is_homepage)

    errors = []
    if not title:
        errors.append("Title is required.")
    if not slug:
        slug = _slugify(title)
    if not slug:
        errors.append("Slug could not be generated from title.")

    if not errors:
        existing = Page.query.filter(Page.slug == slug, Page.id != page_id).first()
        if existing:
            errors.append(f"Another page with slug '{slug}' already exists.")

    if errors:
        return jsonify(success=False, message="; ".join(errors)), 400

    page.title = title
    page.slug = slug
    page.content = content
    page.meta_description = meta_description[:500]
    page.meta_keywords = meta_keywords[:500]
    page.status = status
    page.is_homepage = bool(is_homepage)

    try:
        page.sort_order = int(sort_order)
    except (TypeError, ValueError):
        pass

    db.session.commit()

    log_activity(
        current_user.id, "page_updated",
        f"Updated page: {title} ({slug})"
    )

    # If homepage was set, unset others
    if page.is_homepage:
        Page.query.filter(Page.id != page.id, Page.is_homepage == True).update({"is_homepage": False})
        db.session.commit()

    return jsonify(
        success=True,
        message=f"Page '{title}' updated successfully!",
    )


@admin_bp.route("/pages/<int:page_id>/delete", methods=["POST"])
@admin_required
def delete_page(page_id):
    page = Page.query.get_or_404(page_id)

    confirm_text = (request.get_json() or {}).get("confirm", "")
    if confirm_text != page.title:
        return jsonify(
            success=False,
            message=f'Type "{page.title}" to confirm deletion.',
        ), 400

    log_activity(
        current_user.id, "page_deleted",
        f"Deleted page: {page.title} ({page.slug})"
    )

    db.session.delete(page)
    db.session.commit()

    return jsonify(
        success=True,
        message=f"Page '{page.title}' deleted successfully.",
    )


@admin_bp.route("/pages/<int:page_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_page_status(page_id):
    page = Page.query.get_or_404(page_id)
    page.status = "published" if page.status == "draft" else "draft"
    db.session.commit()

    log_activity(
        current_user.id, "page_updated",
        f"Toggled page '{page.title}' to {page.status}"
    )

    return jsonify(
        success=True,
        status=page.status,
        message=f"Page is now {page.status}.",
    )


@admin_bp.route("/pages/reorder", methods=["POST"])
@admin_required
def reorder_pages():
    data = request.get_json()
    items = data.get("items", [])

    for item in items:
        page = Page.query.get(item.get("id"))
        if page:
            page.sort_order = item.get("sort_order", 0)

    db.session.commit()
    return jsonify(success=True, message="Page order updated.")


@admin_bp.route("/pages/check-slug", methods=["GET"])
@admin_required
def check_slug():
    slug = request.args.get("slug", "").strip()
    exclude = request.args.get("exclude", type=int)

    if not slug:
        return jsonify(available=True, slug="")

    slug = _slugify(slug)
    if not slug:
        return jsonify(available=False, slug="")

    query = Page.query.filter_by(slug=slug)
    if exclude:
        query = query.filter(Page.id != exclude)

    exists = query.first() is not None
    return jsonify(available=not exists, slug=slug)


import os
from flask import request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename


def _get_upload_dir():
    d = os.path.join(current_app.root_path, "static", "uploads", "media")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "thumbnails"), exist_ok=True)
    return d


def _generate_thumbnail(file_path, max_size=(300, 300)):
    """Generate a thumbnail. Returns True if successful."""
    try:
        from PIL import Image as PILImage
        img = PILImage.open(file_path)
        img.thumbnail(max_size, PILImage.LANCZOS)
        thumb_dir = os.path.dirname(file_path) + "/thumbnails/"
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_name = "thumb_" + os.path.basename(file_path)
        thumb_path = thumb_dir + thumb_name
        img.save(thumb_path, "WEBP", quality=80)
        return True
    except Exception:
        return False


def _get_file_type(mime_type):
    if not mime_type:
        return "other"
    m = mime_type.lower()
    if m.startswith("image/"):
        return "image"
    elif m.startswith("video/"):
        return "video"
    elif m.startswith("audio/"):
        return "audio"
    elif m in ("application/pdf",):
        return "document"
    elif m.startswith("text/") or m in ("application/json", "application/xml", "application/javascript", "application/zip"):
        return "document"
    return "other"


@admin_bp.route("/media")
@admin_required
def media():
    search = request.args.get("search", "").strip()
    file_type = request.args.get("type", "all")
    page = request.args.get("page", 1, type=int)
    per_page = 24

    query = Media.query.order_by(Media.created_at.desc())

    if search:
        query = query.filter(Media.filename.ilike(f"%{search}%"))

    if file_type and file_type != "all":
        query = query.filter_by(file_type=file_type)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    media_list = []
    for m in pagination.items:
        media_list.append({
            "id": m.id,
            "filename": m.filename,
            "file_url": m.file_url,
            "thumbnail_url": m.thumbnail_url,
            "file_type": m.file_type,
            "mime_type": m.mime_type or "",
            "file_size": m.file_size,
            "width": m.width,
            "height": m.height,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        })

    # Counts per type
    type_counts = {}
    for t in ["image", "video", "document", "audio", "other"]:
        type_counts[t] = Media.query.filter_by(file_type=t).count()

    total_size = db.session.query(
        func.coalesce(func.sum(Media.file_size), 0)
    ).scalar() or 0

    return render_template(
        "admin/media/index.html",
        media=media_list,
        pagination=pagination,
        search=search,
        file_type=file_type,
        type_counts=type_counts,
        total_size=total_size,
    )


@admin_bp.route("/media/upload", methods=["POST"])
@admin_required
def media_upload():
    if "file" not in request.files:
        return jsonify(success=False, message="No file selected."), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(success=False, message="No file selected."), 400

    upload_dir = _get_upload_dir()

    # Generate unique filename to avoid overwrites
    name, ext = os.path.splitext(file.filename)
    timestamp = int(datetime.utcnow().timestamp())
    stored_name = secure_filename(f"{name}_{timestamp}{ext}")
    stored_path = os.path.join(upload_dir, stored_name)

    # Save file
    file.save(stored_path)

    # Generate thumbnail for images
    if _get_file_type(file.mimetype) == "image":
        _generate_thumbnail(stored_path)

    file_type = _get_file_type(file.mimetype)
    file_size = os.path.getsize(stored_path)
    width, height = None, None
    if file_type == "image":
        try:
            from PIL import Image as PILImage
            with PILImage.open(stored_path) as img:
                width, height = img.size
        except Exception:
            pass

    media = Media(
        filename=file.filename,
        stored_name=stored_name,
        file_path=f"uploads/media/{stored_name}",
        file_type=file_type,
        mime_type=file.mimetype,
        file_size=file_size,
        width=width,
        height=height,
        uploaded_by=current_user.id,
    )
    db.session.add(media)
    db.session.commit()

    return jsonify(
        success=True,
        media={
            "id": media.id,
            "filename": media.filename,
            "file_url": media.file_url,
            "thumbnail_url": media.thumbnail_url,
            "file_type": media.file_type,
            "mime_type": media.mime_type or "",
            "file_size": media.file_size,
            "width": media.width,
            "height": media.height,
            "created_at": media.created_at.isoformat(),
        },
    )


@admin_bp.route("/media/<int:media_id>", methods=["DELETE"])
@admin_required
def media_delete(media_id):
    media = Media.query.get_or_404(media_id)

    # Delete files from disk
    try:
        fpath = os.path.join(current_app.root_path, media.file_path)
        if os.path.exists(fpath):
            os.remove(fpath)
    except OSError:
        pass

    # Delete thumbnail
    if media.file_type == "image":
        try:
            thumb_dir = os.path.dirname(media.file_path) + "/thumbnails/"
            thumb_path = os.path.join(current_app.root_path, thumb_dir, "thumb_" + media.stored_name)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        except OSError:
            pass

    from app.utils.activity import log_activity
    log_activity(
        current_user.id, "media_deleted",
        f"Deleted file: {media.filename} ({media.file_type}, {media.file_size} bytes)"
    )

    db.session.delete(media)
    db.session.commit()

    return jsonify(success=True, message=f"'{media.filename}' deleted.")


@admin_bp.route("/media/files/<path:filename>")
@admin_required
def serve_media(filename):
    upload_dir = _get_upload_dir()
    return send_from_directory(upload_dir, filename)

@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    import json
    import os
    
    settings_file = "settings_data.json"
    default_settings = {
        "general": {
            "store_name": "Cliffine Collection",
            "contact_email": "support@cliffine.co.ke",
            "phone_number": "+254 700 000 000",
            "default_currency": "KES",
            "store_address": "",
        },
        "payments": {
            "mpesa_enabled": False,
            "paybill_number": "",
            "account_number": "",
            "tax_rate": 16,
            "default_payment_method": "M-Pesa",
        },
        "shipping": {
            "zones": [
                {"region": "Nairobi", "method": "Pickup / Courier", "cost": 200},
                {"region": "Major Towns", "method": "Standard", "cost": 350},
            ],
            "free_shipping_threshold": "",
            "estimated_delivery": "1-3 Business Days",
        },
        "emails": {
            "smtp_host": "",
            "smtp_port": "",
            "smtp_username": "",
            "smtp_password": "",
            "notify_new_order": True,
            "notify_payment_receipts": True,
            "notify_chama_updates": False,
            "notify_newsletters": False,
        },
        "coupons": {
            "enabled": True,
            "default_discount_type": "Percentage",
            "expiry_reminder": "3 Days Before",
        },
        "security": {
            "two_factor_enabled": False,
            "session_timeout": 60,
        },
        "advanced": {
            "maintenance_mode": False,
            "google_analytics_id": "",
            "custom_css": "",
        },
    }

    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Build settings from form data
        saved_settings = default_settings.copy()
        
        # General
        saved_settings["general"]["store_name"] = data.get("store_name", "")
        saved_settings["general"]["contact_email"] = data.get("contact_email", "")
        saved_settings["general"]["phone_number"] = data.get("phone_number", "")
        saved_settings["general"]["default_currency"] = data.get("default_currency", "KES")
        saved_settings["general"]["store_address"] = data.get("store_address", "")
        
        # Payments
        saved_settings["payments"]["mpesa_enabled"] = data.get("mpesa_enabled") == "true"
        saved_settings["payments"]["paybill_number"] = data.get("paybill_number", "")
        saved_settings["payments"]["account_number"] = data.get("account_number", "")
        saved_settings["payments"]["tax_rate"] = int(data.get("tax_rate", 16) or 16)
        saved_settings["payments"]["default_payment_method"] = data.get("default_payment_method", "M-Pesa")
        
        # Shipping
        shipping_zones = []
        zones_data = data.get("shipping_zones", "[]")
        if isinstance(zones_data, str):
            try:
                import json
                zones_data = json.loads(zones_data)
            except:
                zones_data = []
        saved_settings["shipping"]["zones"] = zones_data
        saved_settings["shipping"]["free_shipping_threshold"] = data.get("free_shipping_threshold", "")
        saved_settings["shipping"]["estimated_delivery"] = data.get("estimated_delivery", "")
        
        # Emails
        saved_settings["emails"]["smtp_host"] = data.get("smtp_host", "")
        saved_settings["emails"]["smtp_port"] = data.get("smtp_port", "")
        saved_settings["emails"]["smtp_username"] = data.get("smtp_username", "")
        saved_settings["emails"]["smtp_password"] = data.get("smtp_password", "")
        saved_settings["emails"]["notify_new_order"] = data.get("notify_new_order") == "true"
        saved_settings["emails"]["notify_payment_receipts"] = data.get("notify_payment_receipts") == "true"
        saved_settings["emails"]["notify_chama_updates"] = data.get("notify_chama_updates") == "true"
        saved_settings["emails"]["notify_newsletters"] = data.get("notify_newsletters") == "true"
        
        # Coupons
        saved_settings["coupons"]["enabled"] = data.get("coupons_enabled") == "true"
        saved_settings["coupons"]["default_discount_type"] = data.get("default_discount_type", "Percentage")
        saved_settings["coupons"]["expiry_reminder"] = data.get("expiry_reminder", "3 Days Before")
        
        # Security
        saved_settings["security"]["two_factor_enabled"] = data.get("two_factor_enabled") == "true"
        saved_settings["security"]["session_timeout"] = int(data.get("session_timeout", 60) or 60)
        
        # Handle password change separately
        new_password = data.get("new_password", "")
        if new_password:
            # Hash and update password logic here
            pass
        
        # Advanced
        saved_settings["advanced"]["maintenance_mode"] = data.get("maintenance_mode") == "true"
        saved_settings["advanced"]["google_analytics_id"] = data.get("google_analytics_id", "")
        saved_settings["advanced"]["custom_css"] = data.get("custom_css", "")
        
        # Save to file (in production, use database)
        try:
            with open(settings_file, "w") as f:
                json.dump(saved_settings, f, indent=2)
        except Exception as e:
            pass
        
        return jsonify({"success": True, "message": "Settings saved successfully!"})
    
    # Load settings
    current_settings = default_settings.copy()
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                loaded = json.load(f)
                # Deep merge
                for section in default_settings:
                    if section in loaded:
                        if isinstance(default_settings[section], dict):
                            current_settings[section].update(loaded[section])
                        else:
                            current_settings[section] = loaded[section]
    except Exception as e:
        pass
    
    return render_template("admin/settings/index.html", settings=current_settings)

import os
from flask import (
    render_template, request, redirect, url_for,
    flash, jsonify, current_app
)
from werkzeug.utils import secure_filename
from app.utils.activity import log_activity, get_activity_colors, get_action_labels


def _allowed_file(filename):
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route("/profile", methods=["GET", "POST"])
@admin_required
def admin_profile():
    admin = User.query.get(current_user.id)
    if not admin:
        flash("Admin account not found.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    # Pre-fill username from email if empty (migration fallback)
    if not admin.username:
        admin.username = admin.email.split("@")[0]
        db.session.commit()

    # Fetch recent activity
    recent_activity = (
        AdminActivity.query
        .filter_by(admin_id=admin.id)
        .order_by(AdminActivity.created_at.desc())
        .limit(10)
        .all()
    )

    activity_data = []
    for act in recent_activity:
        activity_data.append({
            "color": get_activity_colors(act.action),
            "label": get_action_labels(act.action),
            "description": act.description,
            "ip": act.ip_address,
            "time": act.created_at,
        })

    prefs = admin.get_preferences()

    # Count other admins for danger zone
    other_admins_count = admin.query.filter(
        admin.id != admin.id,
        admin.role == "admin",
        admin.is_active == True,
    ).count()

    return render_template(
        "admin/profile.html",
        admin=admin,
        prefs=prefs,
        activity_data=activity_data,
        other_admins_count=other_admins_count,
    )


@admin_bp.route("/profile/update", methods=["POST"])
@admin_required
def admin_profile_update():
    admin = User.query.get(current_user.id)
    if not admin:
        return jsonify(success=False, message="Admin not found."), 404

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    # Validation
    errors = []
    if not first_name:
        errors.append("First name is required.")
    if not email:
        errors.append("Email is required.")
    if username and len(username) < 3:
        errors.append("Username must be at least 3 characters.")

    # Check uniqueness
    if email != admin.email:
        existing = admin.query.filter_by(email=email).first()
        if existing:
            errors.append("This email is already in use.")
    if username and username != admin.username:
        existing = admin.query.filter_by(username=username).first()
        if existing:
            errors.append("This username is already taken.")

    if errors:
        return jsonify(success=False, message="; ".join(errors))

    # Update
    admin.first_name = first_name
    admin.last_name = last_name or None
    admin.username = username or admin.email.split("@")[0]
    admin.email = email
    admin.phone = phone or None

    db.session.commit()
    log_activity(
        admin.id, "profile_update",
        f"Updated profile: {admin.full_name} ({admin.email})"
    )

    return jsonify(
        success=True,
        message="Profile updated successfully!",
        data={
            "full_name": admin.full_name,
            "display_name": admin.display_name,
            "email": admin.email,
        }
    )


@admin_bp.route("/profile/password", methods=["POST"])
@admin_required
def admin_profile_password():
    admin = User.query.get(current_user.id)
    if not admin:
        return jsonify(success=False, message="Admin not found."), 404

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    # Validation
    if not current_password:
        return jsonify(success=False, message="Current password is required.")
    if not new_password:
        return jsonify(success=False, message="New password is required.")
    if len(new_password) < 8:
        return jsonify(success=False, message="New password must be at least 8 characters.")
    if new_password != confirm_password:
        return jsonify(success=False, message="New passwords do not match.")
    if current_password == new_password:
        return jsonify(success=False, message="New password must be different from current password.")
    if not admin.check_password(current_password):
        return jsonify(success=False, message="Current password is incorrect.")

    admin.set_password(new_password)
    db.session.commit()
    log_activity(admin.id, "password_change", "Password was changed.")

    return jsonify(success=True, message="Password changed successfully!")


@admin_bp.route("/profile/photo", methods=["POST"])
@admin_required
def admin_profile_photo():
    import cloudinary
    from cloudinary.uploader import upload as cloudinary_upload, destroy as cloudinary_destroy

    admin = User.query.get(current_user.id)
    if not admin:
        return jsonify(success=False, message="Admin not found."), 404

    if "photo" not in request.files:
        return jsonify(success=False, message="No file selected.")

    file = request.files["photo"]
    if file.filename == "":
        return jsonify(success=False, message="No file selected.")

    if not _allowed_file(file.filename):
        return jsonify(success=False, message="Invalid file type. Use PNG, JPG, or WebP.")

    # Check file size (max 2MB)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 2 * 1024 * 1024:
        return jsonify(success=False, message="File too large. Maximum size is 2MB.")

    public_id = f"admin_profiles/{admin.id}"

    # Delete old photo from Cloudinary
    if admin.profile_image:
        # If the stored URL is a Cloudinary URL, extract public_id and destroy it
        if "cloudinary.com" in admin.profile_image:
            try:
                cloudinary_destroy(public_id, invalidate=True)
            except Exception:
                pass
        else:
            # Legacy local file — remove from disk
            old_path = os.path.join(current_app.root_path, admin.profile_image.lstrip("/"))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

    # Upload to Cloudinary
    try:
        upload_result = cloudinary_upload(
            file,
            public_id=public_id,
            folder="admin_profiles",
            overwrite=True,
            width=400,
            height=400,
            crop="limit",
            quality="auto:good",
            fetch_format="auto",
            resource_type="image",
        )
    except Exception as e:
        return jsonify(success=False, message=f"Upload failed: {str(e)}"), 500

    # Use the secure URL
    image_url = upload_result.get("secure_url", "")

    if not image_url:
        return jsonify(success=False, message="Upload returned no image URL."), 500

    admin.profile_image = image_url
    db.session.commit()
    log_activity(admin.id, "photo_update", "Updated profile photo via Cloudinary.")

    return jsonify(
        success=True,
        message="Profile photo updated!",
        image_url=image_url,
    )


@admin_bp.route("/profile/preferences", methods=["POST"])
@admin_required
def admin_profile_preferences():
    admin = User.query.get(current_user.id)
    if not admin:
        return jsonify(success=False, message="Admin not found."), 404

    data = request.get_json() or {}

    prefs = admin.get_preferences()
    prefs["language"] = data.get("language", prefs["language"])
    prefs["timezone"] = data.get("timezone", prefs["timezone"])
    prefs["email_notifications"] = bool(data.get("email_notifications", prefs["email_notifications"]))
    prefs["sms_notifications"] = bool(data.get("sms_notifications", prefs["sms_notifications"]))
    prefs["two_factor"] = bool(data.get("two_factor", prefs["two_factor"]))

    admin.preferences = prefs
    db.session.commit()
    log_activity(admin.id, "preferences_update", "Updated notification preferences.")

    return jsonify(success=True, message="Preferences saved!")


@admin_bp.route("/profile/delete", methods=["POST"])
@admin_required
def admin_profile_delete():
    admin = User.query.get(current_user.id)
    if not admin:
        return jsonify(success=False, message="Admin not found."), 404

    # Safety: check if there are other active admins
    other_admins = admin.query.filter(
        admin.id != admin.id,
        admin.role == "admin",
        admin.is_active == True,
    ).count()

    if other_admins == 0:
        return jsonify(
            success=False,
            message="Cannot delete the only admin account. Create another admin first."
        )

    confirm_text = (request.get_json() or {}).get("confirm", "")
    if confirm_text != "DELETE":
        return jsonify(success=False, message='Type "DELETE" to confirm.')

    log_activity(admin.id, "account_delete", f"Account {admin.email} deleted by self.")

    # Delete profile image
    if admin.profile_image:
        old_path = os.path.join(current_app.root_path, admin.profile_image.lstrip("/"))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # Deactivate rather than hard delete (safer)
    admin.is_active = False
    admin.email = f"deleted_{admin.id}_{admin.email}"
    admin.profile_image = None
    db.session.commit()

    from flask_login import logout_user
    logout_user()

    return jsonify(success=True, message="Account deleted. Redirecting...", redirect=url_for("main.home"))


@admin_bp.route("/analytics")
@admin_required
def analytics():
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta
    from calendar import month_name, monthrange
    import json

    period = request.args.get("period", "month")
    now = datetime.utcnow()

    # ===================== DATE RANGES =====================
    if period == "today":
        current_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        prev_start = current_start - timedelta(days=1)
        prev_end = current_start
        period_label = f"Today, {now.strftime('%d %b %Y')}"
        prev_period_label = "Yesterday"
    elif period == "year":
        current_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        prev_start = current_start.replace(year=now.year - 1)
        prev_end = current_start
        period_label = str(now.year)
        prev_period_label = str(now.year - 1)
    else:
        current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        prev_start = (current_start - timedelta(days=1)).replace(day=1)
        prev_end = current_start
        period_label = f"{month_name[now.month]} {now.year}"
        prev_period_label = f"{month_name[prev_start.month]} {prev_start.year}"

    # ===================== HELPERS =====================
    def calc_growth(curr, prev):
        if not prev or prev == 0:
            return None
        return round(((curr - prev) / prev) * 100, 1)

    def query_revenue(start, end):
        return db.session.query(
            func.coalesce(func.sum(Order.total_amount), 0)
        ).filter(
            Order.created_at >= start,
            Order.created_at < end,
            Order.status != 'Cancelled'
        ).scalar() or 0

    def query_order_count(start, end):
        return db.session.query(func.count(Order.id)).filter(
            Order.created_at >= start,
            Order.created_at < end,
        ).scalar() or 0

    # ===================== TOP METRICS =====================
    current_revenue = query_revenue(current_start, current_end)
    prev_revenue = query_revenue(prev_start, prev_end)
    revenue_growth = calc_growth(current_revenue, prev_revenue)

    current_orders = query_order_count(current_start, current_end)
    prev_orders = query_order_count(prev_start, prev_end)
    orders_growth = calc_growth(current_orders, prev_orders)

    # Products Sold (units)
    products_sold = db.session.query(
        func.coalesce(func.sum(OrderItem.quantity), 0)
    ).join(Order, OrderItem.order_id == Order.id).filter(
        Order.created_at >= current_start,
        Order.created_at < current_end,
        Order.status != 'Cancelled'
    ).scalar() or 0

    # Average Order Value
    avg_order_value = round(current_revenue / current_orders) if current_orders > 0 else 0

    # ===================== CHART DATA =====================
    def build_chart_data(p_start, p_end, p_type, ref_now=None):
        if p_type == "today":
            data = db.session.query(
                extract('hour', Order.created_at).label('key'),
                func.coalesce(func.sum(Order.total_amount), 0).label('val')
            ).filter(
                Order.created_at >= p_start,
                Order.created_at < p_end,
                Order.status != 'Cancelled'
            ).group_by(extract('hour', Order.created_at)).all()

            n = (ref_now.hour + 1) if ref_now else 24
            labels = [f"{h}:00" for h in range(n)]
            values = [0.0] * n
            for row in data:
                idx = int(row.key)
                if idx < n:
                    values[idx] = float(row.val)

        elif p_type == "year":
            data = db.session.query(
                extract('month', Order.created_at).label('key'),
                func.coalesce(func.sum(Order.total_amount), 0).label('val')
            ).filter(
                Order.created_at >= p_start,
                Order.created_at < p_end,
                Order.status != 'Cancelled'
            ).group_by(extract('month', Order.created_at)).all()

            n = ref_now.month if ref_now else 12
            labels = [month_name[m][:3] for m in range(1, n + 1)]
            values = [0.0] * n
            for row in data:
                idx = int(row.key) - 1
                if idx < n:
                    values[idx] = float(row.val)

        else:  # month
            if ref_now:
                days = ref_now.day
            else:
                days = monthrange(p_start.year, p_start.month)[1]

            data = db.session.query(
                extract('day', Order.created_at).label('key'),
                func.coalesce(func.sum(Order.total_amount), 0).label('val')
            ).filter(
                Order.created_at >= p_start,
                Order.created_at < p_end,
                Order.status != 'Cancelled'
            ).group_by(extract('day', Order.created_at)).all()

            labels = [str(d) for d in range(1, days + 1)]
            values = [0.0] * days
            for row in data:
                idx = int(row.key) - 1
                if idx < days:
                    values[idx] = float(row.val)

        return labels, values

    chart_labels, chart_values = build_chart_data(current_start, current_end, period, now)

    if period == "today":
        _, prev_chart_values = build_chart_data(prev_start, prev_end, "today", now - timedelta(days=1))
    elif period == "year":
        _, prev_chart_values = build_chart_data(prev_start, prev_end, "year", prev_start.replace(month=12, day=31))
    else:
        _, prev_chart_values = build_chart_data(prev_start, prev_end, "month", prev_end - timedelta(days=1))

    while len(prev_chart_values) < len(chart_values):
        prev_chart_values.append(0.0)

    # ===================== PAYMENT METHODS =====================
    payment_methods = []
    payment_colors = ['#16A34A', '#5423E7', '#D4AF37', '#EC4899', '#F97316', '#06B6D4']
    try:
        pay_data = db.session.query(
            Order.payment_method,
            func.count(Order.id).label('cnt'),
            func.coalesce(func.sum(Order.total_amount), 0).label('rev')
        ).filter(
            Order.created_at >= current_start,
            Order.created_at < current_end,
            Order.status != 'Cancelled',
            Order.payment_method.isnot(None),
            Order.payment_method != ''
        ).group_by(Order.payment_method).order_by(func.count(Order.id).desc()).all()

        total_pay = sum(p.cnt for p in pay_data) or 1
        for i, p in enumerate(pay_data):
            payment_methods.append({
                "name": (p.payment_method or "Other").title(),
                "count": p.cnt,
                "revenue": float(p.rev),
                "percentage": round((p.cnt / total_pay) * 100, 1),
                "color": payment_colors[i % len(payment_colors)]
            })
    except Exception:
        pass

    # ===================== ORDER STATUS =====================
    status_colors = {
        'Completed': 'bg-green-500', 'Delivered': 'bg-green-500',
        'Processing': 'bg-blue-500', 'Pending': 'bg-yellow-500',
        'Shipped': 'bg-indigo-500', 'Cancelled': 'bg-red-400',
        'Refunded': 'bg-red-500', 'Returned': 'bg-orange-400',
    }
    status_data = db.session.query(
        Order.status, func.count(Order.id).label('cnt')
    ).filter(
        Order.created_at >= current_start,
        Order.created_at < current_end,
    ).group_by(Order.status).all()

    total_status = sum(s.cnt for s in status_data) or 1
    order_statuses = sorted([
        {
            "status": s.status,
            "count": s.cnt,
            "percentage": round((s.cnt / total_status) * 100, 1),
            "color": status_colors.get(s.status, 'bg-slate-400')
        }
        for s in status_data
    ], key=lambda x: x['count'], reverse=True)

    # ===================== CUSTOMER STATS =====================
    total_customers = User.query.filter_by(role='customer').count()
    new_customers = db.session.query(func.count(User.id)).filter(
        User.role == 'customer',
        User.created_at >= current_start,
        User.created_at < current_end,
    ).scalar() or 0

    returning_customers = db.session.query(
        func.count(func.distinct(Order.user_id))
    ).filter(
        Order.user_id.isnot(None),
        Order.status != 'Cancelled'
    ).group_by(Order.user_id).having(func.count(Order.id) > 1).count()

    # ===================== CHAMA =====================
    active_chamas = 0
    chama_members = 0
    try:
        active_chamas = Chama.query.filter_by(is_active=True).count()
        chama_members = ChamaMember.query.count()
    except Exception:
        pass

    # ===================== COUPON STATS =====================
    coupon_usage = 0
    total_discount = 0
    try:
        coupon_usage = db.session.query(func.count(Order.id)).filter(
            Order.created_at >= current_start,
            Order.created_at < current_end,
            Order.coupon_id.isnot(None),
            Order.status != 'Cancelled'
        ).scalar() or 0

        total_discount = db.session.query(
            func.coalesce(func.sum(Order.discount_amount), 0)
        ).filter(
            Order.created_at >= current_start,
            Order.created_at < current_end,
            Order.coupon_id.isnot(None),
            Order.status != 'Cancelled'
        ).scalar() or 0
    except Exception:
        pass

    return render_template(
        "admin/analytics/index.html",
        period=period,
        period_label=period_label,
        prev_period_label=prev_period_label,
        current_revenue=current_revenue,
        revenue_growth=revenue_growth,
        current_orders=current_orders,
        orders_growth=orders_growth,
        products_sold=products_sold,
        avg_order_value=avg_order_value,
        chart_labels=json.dumps(chart_labels),
        chart_values=json.dumps(chart_values),
        prev_chart_values=json.dumps(prev_chart_values),
        payment_methods=payment_methods,
        order_statuses=order_statuses,
        total_customers=total_customers,
        new_customers=new_customers,
        returning_customers=returning_customers,
        active_chamas=active_chamas,
        chama_members=chama_members,
        coupon_usage=coupon_usage,
        total_discount=total_discount,
    ) 



# ===============================
# VIEW ALL DELIVERY AREAS
# ===============================
@admin_bp.route("/delivery-areas")
def delivery_areas():
    areas = DeliveryArea.query.order_by(DeliveryArea.id.desc()).all()
    return render_template("admin/delivery_areas/all.html", areas=areas)


# ===============================
# ADD DELIVERY AREA
# ===============================
@admin_bp.route("/delivery-areas/add", methods=["GET", "POST"])
def add_delivery_area():
    if request.method == "POST":
        name = request.form.get("name")
        fee = request.form.get("fee")

        # validation
        if not name or not fee:
            flash("All fields are required", "error")
            return redirect(url_for("admin.add_delivery_area"))

        # check duplicate
        existing = DeliveryArea.query.filter_by(name=name).first()
        if existing:
            flash("Area already exists", "error")
            return redirect(url_for("admin.add_delivery_area"))

        area = DeliveryArea(
            name=name,
            fee=float(fee)
        )

        db.session.add(area)
        db.session.commit()

        flash("Delivery area added successfully", "success")
        return redirect(url_for("admin.delivery_areas"))

    return render_template("admin/delivery_areas/add.html")


# ===============================
# EDIT DELIVERY AREA
# ===============================
@admin_bp.route("/delivery-areas/edit/<int:id>", methods=["GET", "POST"])
def edit_delivery_area(id):
    area = DeliveryArea.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name")
        fee = request.form.get("fee")
        is_active = request.form.get("is_active")

        area.name = name
        area.fee = float(fee)
        area.is_active = True if is_active == "on" else False

        db.session.commit()

        flash("Delivery area updated", "success")
        return redirect(url_for("admin.delivery_areas"))

    return render_template("admin/delivery_areas/edit.html", area=area)


# ===============================
# DELETE DELIVERY AREA
# ===============================
@admin_bp.route("/delivery-areas/delete/<int:id>", methods=["POST"])
def delete_delivery_area(id):
    area = DeliveryArea.query.get_or_404(id)

    db.session.delete(area)
    db.session.commit()

    flash("Delivery area deleted", "success")
    return redirect(url_for("admin.delivery_areas"))


# ═══════════════════════════════════════════════════════════════
# ... YOUR EXISTING IMPORTS STAY ABOVE ...
# ═══════════════════════════════════════════════════════════════

# Make sure these are imported (add any that are missing):
from datetime import datetime, timedelta
from functools import wraps
import json    # ← adjust if you import differently


# ╔═══════════════════════════════════════════════════════════════╗
# ║  COUPON EVENT DEFINITIONS — PASTE INTO routes.py             ║
# ╚═══════════════════════════════════════════════════════════════╝

COUPON_EVENTS = {
    'account': {
        'label': 'Customer Account Events',
        'icon': 'user-plus',
        'color': 'blue',
        'events': [
            {
                'key': 'new_registration',
                'label': 'New Account Registration',
                'description': 'Encourage first purchase when a user creates an account.',
                'example_code': 'WELCOME10',
                'default_discount_type': 'percentage',
                'default_discount_value': 10,
                'default_validity_days': 30,
                'default_total_uses': 1000,
            },
            {
                'key': 'email_verification',
                'label': 'Email Verification',
                'description': 'Small discount or free shipping when user verifies their email.',
                'example_code': 'VERIFYFREESHIP',
                'default_discount_type': 'free_shipping',
                'default_discount_value': 0,
                'default_validity_days': 14,
                'default_total_uses': 500,
            },
            {
                'key': 'profile_completion',
                'label': 'Profile Completion',
                'description': 'Discount coupon when user fills in all profile details.',
                'example_code': 'PROFILE15',
                'default_discount_type': 'percentage',
                'default_discount_value': 15,
                'default_validity_days': 21,
                'default_total_uses': 500,
            },
        ]
    },
    'purchase': {
        'label': 'Purchase Events',
        'icon': 'shopping-bag',
        'color': 'green',
        'events': [
            {
                'key': 'first_order',
                'label': 'First Order',
                'description': 'Coupon for second purchase after user places their first order.',
                'example_code': 'THANKYOU10',
                'default_discount_type': 'percentage',
                'default_discount_value': 10,
                'default_validity_days': 30,
                'default_total_uses': 1000,
            },
            {
                'key': 'order_completion',
                'label': 'Order Completion',
                'description': 'Loyalty coupon when an order is delivered successfully.',
                'example_code': 'LOYAL5',
                'default_discount_type': 'percentage',
                'default_discount_value': 5,
                'default_validity_days': 45,
                'default_total_uses': 2000,
            },
            {
                'key': 'high_value_purchase',
                'label': 'High-Value Purchase',
                'description': 'Special discount for next order when order exceeds KSh 10,000.',
                'example_code': 'BIGSPENDER15',
                'default_discount_type': 'percentage',
                'default_discount_value': 15,
                'default_validity_days': 60,
                'default_total_uses': 500,
                'trigger_min_amount': 10000,
            },
            {
                'key': 'repeat_customer',
                'label': 'Repeat Customer',
                'description': 'VIP coupon when customer reaches 5th, 10th, or 20th order.',
                'example_code': 'VIP20',
                'default_discount_type': 'percentage',
                'default_discount_value': 20,
                'default_validity_days': 90,
                'default_total_uses': 200,
                'trigger_order_milestone': [5, 10, 20],
            },
        ]
    },
    'cart': {
        'label': 'Cart Events',
        'icon': 'shopping-cart',
        'color': 'orange',
        'events': [
            {
                'key': 'abandoned_cart',
                'label': 'Abandoned Cart',
                'description': "Coupon sent by email or SMS when customer adds items but doesn't check out after a set period.",
                'example_code': 'COMEBACK10',
                'default_discount_type': 'percentage',
                'default_discount_value': 10,
                'default_validity_days': 3,
                'default_total_uses': 5000,
            },
            {
                'key': 'large_cart_value',
                'label': 'Large Cart Value',
                'description': 'Discount encouraging checkout when cart exceeds a target amount.',
                'example_code': 'BIGCART8',
                'default_discount_type': 'percentage',
                'default_discount_value': 8,
                'default_validity_days': 2,
                'default_total_uses': 3000,
                'trigger_min_cart_amount': 5000,
            },
        ]
    },
    'loyalty': {
        'label': 'Loyalty Events',
        'icon': 'award',
        'color': 'purple',
        'events': [
            {
                'key': 'points_milestone',
                'label': 'Points Milestone',
                'description': 'Coupon when customer earns a certain number of loyalty points.',
                'example_code': 'POINTS500',
                'default_discount_type': 'fixed',
                'default_discount_value': 500,
                'default_validity_days': 30,
                'default_total_uses': 300,
                'trigger_min_points': 500,
            },
            {
                'key': 'vip_status',
                'label': 'VIP Status',
                'description': 'Exclusive coupons when customer reaches VIP tier.',
                'example_code': 'VIPEXCLUSIVE25',
                'default_discount_type': 'percentage',
                'default_discount_value': 25,
                'default_validity_days': 60,
                'default_total_uses': 100,
            },
        ]
    },
    'referral': {
        'label': 'Referral Events',
        'icon': 'users',
        'color': 'teal',
        'events': [
            {
                'key': 'successful_referral',
                'label': 'Successful Referral',
                'description': 'Coupon for referrer when a friend signs up or makes a purchase.',
                'example_code': 'REFERRAL10',
                'default_discount_type': 'percentage',
                'default_discount_value': 10,
                'default_validity_days': 45,
                'default_total_uses': 5000,
            },
            {
                'key': 'friend_first_purchase',
                'label': "Friend's First Purchase",
                'description': 'Larger coupon for the referred customer on their first buy.',
                'example_code': 'FRIEND15',
                'default_discount_type': 'percentage',
                'default_discount_value': 15,
                'default_validity_days': 30,
                'default_total_uses': 5000,
            },
        ]
    },
    'birthday': {
        'label': 'Birthday & Anniversary Events',
        'icon': 'gift',
        'color': 'pink',
        'events': [
            {
                'key': 'customer_birthday',
                'label': 'Customer Birthday',
                'description': "Birthday discount sent on the customer's birthday date.",
                'example_code': 'BIRTHDAY20',
                'default_discount_type': 'percentage',
                'default_discount_value': 20,
                'default_validity_days': 7,
                'default_total_uses': 5000,
            },
            {
                'key': 'account_anniversary',
                'label': 'Account Anniversary',
                'description': 'Special reward one year since registration.',
                'example_code': 'ANNIV12',
                'default_discount_type': 'percentage',
                'default_discount_value': 12,
                'default_validity_days': 14,
                'default_total_uses': 3000,
            },
        ]
    },
}

COLOR_MAP = {
    'blue':   {'bg': 'bg-blue-50',      'border': 'border-blue-200',      'text': 'text-blue-600',      'dot': 'bg-blue-500',      'ring': 'ring-blue-500/30',  'badge': 'bg-blue-100 text-blue-700'},
    'green':  {'bg': 'bg-emerald-50',   'border': 'border-emerald-200',   'text': 'text-emerald-600',  'dot': 'bg-emerald-500',  'ring': 'ring-emerald-500/30', 'badge': 'bg-emerald-100 text-emerald-700'},
    'orange': {'bg': 'bg-orange-50',    'border': 'border-orange-200',    'text': 'text-orange-600',   'dot': 'bg-orange-500',   'ring': 'ring-orange-500/30',  'badge': 'bg-orange-100 text-orange-700'},
    'purple': {'bg': 'bg-purple-50',    'border': 'border-purple-200',    'text': 'text-purple-600',   'dot': 'bg-purple-500',   'ring': 'ring-purple-500/30',  'badge': 'bg-purple-100 text-purple-700'},
    'teal':   {'bg': 'bg-teal-50',      'border': 'border-teal-200',      'text': 'text-teal-600',     'dot': 'bg-teal-500',     'ring': 'ring-teal-500/30',    'badge': 'bg-teal-100 text-teal-700'},
    'pink':   {'bg': 'bg-pink-50',      'border': 'border-pink-200',      'text': 'text-pink-600',     'dot': 'bg-pink-500',     'ring': 'ring-pink-500/30',    'badge': 'bg-pink-100 text-pink-700'},
}


# ╔═══════════════════════════════════════════════════════════════╗
# ║  COUPON ROUTES — PASTE INTO routes.py                        ║
# ╚═══════════════════════════════════════════════════════════════╝

# ─── If you already have an admin_required decorator, remove this one ───
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for("main.home"))
        return f(*args, **kwargs)
    return decorated_function


# ───────────────────────────────────────────────────────────────
# Generate Page (event selector)
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons/generate')
@admin_required
def coupon_generate():
    return render_template('admin/coupons/generate.html',
                           coupon_events=COUPON_EVENTS,
                           color_map=COLOR_MAP)


# ───────────────────────────────────────────────────────────────
# Event Details (AJAX — returns form HTML for selected event)
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons/event-details/<category>/<event_key>')
@admin_required
def coupon_event_details(category, event_key):
    if category not in COUPON_EVENTS:
        return jsonify({'error': 'Invalid category'}), 404

    event = None
    for e in COUPON_EVENTS[category]['events']:
        if e['key'] == event_key:
            event = e
            break
    if not event:
        return jsonify({'error': 'Invalid event'}), 404

    colors = COLOR_MAP.get(COUPON_EVENTS[category]['color'], COLOR_MAP['blue'])

    html = render_template('admin/coupons/partials/event_form.html',
                           event=event,
                           category=category,
                           category_label=COUPON_EVENTS[category]['label'],
                           colors=colors,
                           coupon_events=COUPON_EVENTS)

    return jsonify({'html': html, 'event': event, 'colors': colors})


# ───────────────────────────────────────────────────────────────
# Generate Coupon (POST)
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons/generate', methods=['POST'])
@admin_required
def coupon_generate_post():
    category = request.form.get('category', '')
    event_key = request.form.get('event_key', '')

    # Validate category + event
    if category not in COUPON_EVENTS:
        flash('Invalid coupon category.', 'error')
        return redirect(url_for('admin.coupon_generate'))

    event = None
    for e in COUPON_EVENTS[category]['events']:
        if e['key'] == event_key:
            event = e
            break
    if not event:
        flash('Invalid coupon event.', 'error')
        return redirect(url_for('admin.coupon_generate'))

    # Gather form values
    code            = request.form.get('code', '').strip().upper()
    code_prefix     = request.form.get('code_prefix', '').strip().upper()
    auto_generate   = request.form.get('auto_generate', 'off') == 'on'
    bulk_count      = int(request.form.get('bulk_count', 1))
    discount_type   = request.form.get('discount_type', 'percentage')
    discount_value  = float(request.form.get('discount_value', 0))
    min_order_amount = float(request.form.get('min_order_amount', 0))
    max_discount_amount = float(request.form.get('max_discount_amount', 0)) or None
    total_uses      = int(request.form.get('total_uses', 100))
    uses_per_customer = int(request.form.get('uses_per_customer', 1))
    validity_days   = int(request.form.get('validity_days', 30))
    description     = request.form.get('description', '')
    is_active       = request.form.get('is_active', 'on') == 'on'

    # Trigger settings
    trigger_settings = {}
    if 'trigger_min_amount' in request.form:
        trigger_settings['trigger_min_amount'] = float(request.form.get('trigger_min_amount', 0))
    if 'trigger_min_cart_amount' in request.form:
        trigger_settings['trigger_min_cart_amount'] = float(request.form.get('trigger_min_cart_amount', 0))
    if 'trigger_min_points' in request.form:
        trigger_settings['trigger_min_points'] = int(request.form.get('trigger_min_points', 0))
    if 'trigger_order_milestone' in request.form:
        trigger_settings['trigger_order_milestone'] = request.form.getlist('trigger_order_milestone')

    # ── Validation ──
    if discount_type in ('percentage', 'fixed') and discount_value <= 0:
        flash('Discount value must be greater than 0.', 'error')
        return redirect(url_for('admin.coupon_generate'))

    if discount_type == 'percentage' and discount_value > 100:
        flash('Percentage discount cannot exceed 100%.', 'error')
        return redirect(url_for('admin.coupon_generate'))

    if bulk_count < 1 or bulk_count > 100:
        flash('Bulk count must be between 1 and 100.', 'error')
        return redirect(url_for('admin.coupon_generate'))

    # ── Create coupon(s) ──
    generated = []
    valid_from  = datetime.utcnow()
    valid_until = valid_from + timedelta(days=validity_days)

    # Build description JSON if there are triggers
    desc_json = None
    if trigger_settings:
        desc_json = json.dumps({'text': description, 'triggers': trigger_settings})

    for i in range(bulk_count):
        if auto_generate or bulk_count > 1:
            length = 6 if bulk_count > 1 else 8
            coupon_code = Coupon.generate_code(prefix=code_prefix, length=length)
        else:
            coupon_code = code

        # Uniqueness check
        existing = Coupon.query.filter_by(code=coupon_code).first()
        if existing:
            if bulk_count == 1 and not auto_generate:
                flash(f'Code "{coupon_code}" already exists. Choose a different one.', 'error')
                return redirect(url_for('admin.coupon_generate'))
            coupon_code = Coupon.generate_code(prefix=code_prefix, length=10)

        coupon = Coupon(
            code=coupon_code,
            event_category=category,
            event_type=event_key,
            event_label=event['label'],
            discount_type=discount_type,
            discount_value=discount_value,
            min_order_amount=min_order_amount,
            max_discount_amount=max_discount_amount,
            total_uses=total_uses,
            used_count=0,
            uses_per_customer=uses_per_customer,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=is_active,
            description=desc_json if desc_json else description,
            created_by=current_user.id,
        )
        db.session.add(coupon)
        generated.append(coupon_code)

    db.session.commit()

    if bulk_count == 1:
        flash(
            Markup(f'Coupon <strong>{generated[0]}</strong> created successfully!'),
            "success"
        )
    else:
        flash(
            Markup(f'<strong>{len(generated)}</strong> coupons generated successfully!'),
            "success"
        )

    return redirect(url_for('admin.coupon_list'))


# ───────────────────────────────────────────────────────────────
# Coupons List
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons')
@admin_required
def coupon_list():
    page      = request.args.get('page', 1, type=int)
    per_page  = request.args.get('per_page', 20, type=int)
    search    = request.args.get('search', '').strip()
    category  = request.args.get('category', '').strip()
    status    = request.args.get('status', '').strip()
    discount_type_filter = request.args.get('discount_type', '').strip()

    query = Coupon.query

    if search:
        query = query.filter(
            db.or_(
                Coupon.code.ilike(f'%{search}%'),
                Coupon.event_label.ilike(f'%{search}%'),
                Coupon.description.ilike(f'%{search}%'),
            )
        )
    if category:
        query = query.filter_by(event_category=category)
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    elif status == 'expired':
        query = query.filter(Coupon.valid_until < datetime.utcnow())
    elif status == 'exhausted':
        query = query.filter(db.and_(
            Coupon.total_uses > 0,
            Coupon.used_count >= Coupon.total_uses
        ))
    if discount_type_filter:
        query = query.filter_by(discount_type=discount_type_filter)

    query = query.order_by(Coupon.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/coupons/list.html',
                           coupons=pagination.items,
                           pagination=pagination,
                           coupon_events=COUPON_EVENTS,
                           color_map=COLOR_MAP,
                           search=search,
                           category=category,
                           status=status,
                           discount_type=discount_type_filter)


# ───────────────────────────────────────────────────────────────
# Toggle Active (AJAX POST)
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons/<int:coupon_id>/toggle', methods=['POST'])
@admin_required
def coupon_toggle(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    coupon.is_active = not coupon.is_active
    db.session.commit()
    status_text = 'activated' if coupon.is_active else 'deactivated'
    return jsonify({'success': True, 'is_active': coupon.is_active,
                    'message': f'Coupon {status_text} successfully.'})


# ───────────────────────────────────────────────────────────────
# Delete Coupon (AJAX POST)
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons/<int:coupon_id>/delete', methods=['POST'])
@admin_required
def coupon_delete(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    code = coupon.code

    if coupon.used_count > 0:
        coupon.is_active = False
        db.session.commit()
        return jsonify({
            'success': True, 'soft_deleted': True,
            'message': f'"{code}" has {coupon.used_count} use(s). Deactivated instead of deleted.'
        })

    db.session.delete(coupon)
    db.session.commit()
    return jsonify({
        'success': True, 'soft_deleted': False,
        'message': f'Coupon "{code}" deleted successfully.'
    })


# ───────────────────────────────────────────────────────────────
# Coupon Detail (AJAX)
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons/<int:coupon_id>/details')
@admin_required
def coupon_details(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    usages = coupon.usages.order_by(CouponUsage.used_at.desc()).limit(20).all()
    colors = COLOR_MAP.get(
        COUPON_EVENTS.get(coupon.event_category, {}).get('color', 'blue'),
        COLOR_MAP['blue']
    )
    html = render_template('admin/coupons/partials/coupon_detail.html',
                           coupon=coupon, usages=usages, colors=colors)
    return jsonify({'html': html})


# ───────────────────────────────────────────────────────────────
# Stats (AJAX)
# ───────────────────────────────────────────────────────────────
@admin_bp.route('/coupons/stats')
@admin_required
def coupon_stats():
    total_coupons  = Coupon.query.count()
    active_coupons = Coupon.query.filter_by(is_active=True).count()
    total_redeemed = db.session.query(db.func.sum(Coupon.used_count)).scalar() or 0
    expired_coupons = Coupon.query.filter(
        Coupon.valid_until < datetime.utcnow(),
        Coupon.is_active == True
    ).count()

    category_stats = db.session.query(
        Coupon.event_category,
        db.func.count(Coupon.id),
        db.func.sum(Coupon.used_count)
    ).group_by(Coupon.event_category).all()

    return jsonify({
        'total':    total_coupons,
        'active':   active_coupons,
        'redeemed': int(total_redeemed),
        'expired':  expired_coupons,
        'by_category': [
            {'category': cat, 'count': cnt, 'used': int(used or 0)}
            for cat, cnt, used in category_stats
        ]
    })


# ╔═══════════════════════════════════════════════════════════════╗
# ║  END COUPON ROUTES                                            ║
# ╚═══════════════════════════════════════════════════════════════╝

# ═══════════════════════════════════════════════════════════════
# ... YOUR EXISTING ROUTES CONTINUE BELOW ...
# ═══════════════════════════════════════════════════════════════


from flask import request, jsonify, render_template
from app.models import Notification, db
from functools import wraps


# --- API Endpoints ---

@admin_bp.route("/notifications/api")
@admin_required
def get_notifications_api():
    """Return latest 15 notifications + unread count for the dropdown."""
    category = request.args.get("category", "all")

    query = Notification.query.order_by(Notification.created_at.desc())

    if category != "all":
        query = query.filter_by(category=category)

    notifications = query.limit(15).all()
    unread_count = Notification.query.filter_by(is_read=False).count()

    return jsonify({
        "notifications": [n.to_dict() for n in notifications],
        "unread_count": unread_count,
    })


@admin_bp.route("/notifications/api/<int:notif_id>/read", methods=["POST"])
@admin_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if not notif.is_read:
        notif.is_read = True
        db.session.commit()
    unread_count = Notification.query.filter_by(is_read=False).count()
    return jsonify({"success": True, "unread_count": unread_count})


@admin_bp.route("/notifications/api/read-all", methods=["POST"])
@admin_required
def mark_all_notifications_read():
    Notification.query.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True, "unread_count": 0})


# --- Full Notifications Page ---

@admin_bp.route("/notifications")
@admin_required
def notifications_page():
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "all")

    query = Notification.query.order_by(Notification.created_at.desc())

    if category != "all":
        query = query.filter_by(category=category)

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    notifications = pagination.items
    unread_count = Notification.query.filter_by(is_read=False).count()

    categories = [
        {"key": "all", "label": "All", "icon": "bell"},
        {"key": "order", "label": "Orders", "icon": "shopping-bag"},
        {"key": "customer", "label": "Customers", "icon": "users"},
        {"key": "inventory", "label": "Inventory", "icon": "package"},
        {"key": "payment", "label": "Payments", "icon": "credit-card"},
        {"key": "coupon", "label": "Coupons", "icon": "tag"},
        {"key": "review", "label": "Reviews", "icon": "star"},
        {"key": "message", "label": "Messages", "icon": "mail"},
        {"key": "system", "label": "System", "icon": "settings"},
        {"key": "milestone", "label": "Milestones", "icon": "trending-up"},
    ]

    # Count per category
    cat_counts = {}
    for cat in categories:
        if cat["key"] == "all":
            cat_counts["all"] = Notification.query.count()
        else:
            cat_counts[cat["key"]] = Notification.query.filter_by(category=cat["key"]).count()

    return render_template(
        "admin/notifications.html",
        notifications=notifications,
        pagination=pagination,
        unread_count=unread_count,
        categories=categories,
        cat_counts=cat_counts,
        current_category=category,
    )


@admin_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@admin_required
def read_notification_page(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    notif.is_read = True
    db.session.commit()
    if notif.link:
        from flask import redirect
        return redirect(notif.link)
    from flask import redirect, url_for
    return redirect(url_for("admin.notifications_page"))