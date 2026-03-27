from datetime import datetime

from flask import current_app, redirect, render_template, url_for
from flask import Blueprint, render_template
from app import db
from app.models import User, Product, Order, Coupon, Message, Category, ProductImage, Chama, ChamaMember, DeliveryArea
from flask import render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
from sqlalchemy.exc import IntegrityError
from app.utils.helpers import generate_unique_slug
import cloudinary.uploader
import uuid
from sqlalchemy.orm import joinedload


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
    products = Product.query.options(
        joinedload(Product.images)
    ).order_by(Product.created_at.desc()).all()

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
        category_id = int(category_id) if category_id and category_id.isdigit() else None
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
            discount_price=discount_price,
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
                image_url=image_url,  # store Cloudinary URL
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
                    image_url=cloud_url  # store Cloudinary URL
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
        chama.name = request.form.get("name")
        chama.description = request.form.get("description")
        chama.category = request.form.get("category")

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