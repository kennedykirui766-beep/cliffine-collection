from datetime import datetime
from flask import current_app, jsonify, redirect, render_template, url_for
from flask import Blueprint, render_template
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from app import db
from app.models import AdminActivity, OrderItem, User, Product, Order, Coupon, CouponUsage, Message, Category, ProductImage, Chama, ChamaMember, DeliveryArea
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
    email = request.form["email"].strip().lower()
    password = request.form["password"]

    admin = User.query.filter_by(
        email=email,
        role="admin"
    ).first()

    print("=" * 60)
    print("Email entered:", email)
    print("Admin found:", admin)

    if admin:
        print("Role:", admin.role)
        print("Hash:", admin.password_hash)
        print("Password check:", check_password_hash(admin.password_hash, password))

    if admin and check_password_hash(admin.password_hash, password):
        print("LOGIN SUCCESS")
        login_user(admin)
        return redirect(url_for("admin.admin_dashboard"))

    print("LOGIN FAILED")
    flash("Invalid admin credentials", "danger")    

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
    admin = admin.query.get(current_user.id)
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
    admin = admin.query.get(current_user.id)
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
    admin = admin.query.get(current_user.id)
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
    admin = admin.query.get(current_user.id)
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

    # Delete old photo
    if admin.profile_image:
        old_path = os.path.join(current_app.root_path, admin.profile_image.lstrip("/"))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # Save new photo
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "profiles")
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"admin_{admin.id}_{int(datetime.utcnow().timestamp())}.{ext}")
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    admin.profile_image = f"static/uploads/profiles/{filename}"
    db.session.commit()
    log_activity(admin.id, "photo_update", "Updated profile photo.")

    return jsonify(
        success=True,
        message="Profile photo updated!",
        image_url=admin.profile_image_url,
    )


@admin_bp.route("/profile/preferences", methods=["POST"])
@admin_required
def admin_profile_preferences():
    admin = admin.query.get(current_user.id)
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
    admin = admin.query.get(current_user.id)
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
def analytics():
    return render_template("admin/analytics/index.html")  



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