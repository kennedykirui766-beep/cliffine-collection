from flask import redirect, render_template, url_for
from flask import Blueprint, render_template
from app import db
from app.models import User, Product, Order, Coupon, Message, Category, ProductImage
from flask import render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
from sqlalchemy.exc import IntegrityError
from app.utils.helpers import generate_unique_slug
from app.models import Chama


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
    # Load all products and their categories
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products/all_products.html", products=products)

@admin_bp.route("/products/<int:product_id>/edit")
def edit_product(product_id):
    # Fetch product by ID
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()
    return render_template("admin/products/edit_product.html", product=product, categories=categories)


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
        sku = request.form.get("sku")
        short_description = request.form.get("short_description")
        description = request.form.get("description")

        # --- Pricing ---
        price = request.form.get("price") or 0
        discount_price = request.form.get("discount_price") or 0
        cost_price = request.form.get("cost_price") or 0

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
            discount_price=discount_price,
            cost_price=cost_price,
            sku=sku,
            category_id=category_id,
            stock=stock,
            low_stock=low_stock,
            stock_status=stock_status,
            is_active=is_active,
            is_featured=is_featured,
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
            meta_keywords=meta_keywords
        )

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

            image = ProductImage(
                product_id=product.id,
                image_url=filename,
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

                gallery_image = ProductImage(
                    product_id=product.id,
                    image_url=filename
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

        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)

            upload_folder = "app/static/uploads/categories"
            os.makedirs(upload_folder, exist_ok=True)

            path = os.path.join(upload_folder, filename)
            image_file.save(path)

        category = Category(
            name=name,
            slug=slug,
            description=description,
            image=filename,
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


@admin_bp.route("/")
def chamas():
    all_chamas = Chama.query.all()
    return render_template("admin/chamas.html", chamas=all_chamas)


@admin_bp.route("/create", methods=["POST"])
def create_chama():
    name = request.form.get("name")
    description = request.form.get("description")
    category = request.form.get("category")
    target_amount = request.form.get("target_amount")
    contribution_amount = request.form.get("contribution_amount")
    frequency = request.form.get("frequency")
    max_members = request.form.get("max_members")
    privacy = request.form.get("privacy")

    chama = Chama(
        name=name,
        description=description,
        category=category,
        target_amount=target_amount,
        contribution_amount=contribution_amount,
        frequency=frequency,
        max_members=max_members,
        privacy=privacy
    )

    db.session.add(chama)
    db.session.commit()

    flash("Chama created successfully", "success")
    return redirect(url_for("chamas.chamas"))


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