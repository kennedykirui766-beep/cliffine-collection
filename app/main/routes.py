from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from datetime import datetime
from flask import session
from flask_login import current_user
from app.models import Category, Chama, ChamaMember, Order, OrderItem, Product
from app import db

from app.models import Product

# Create blueprint
main_bp = Blueprint("main", __name__)

# Home
@main_bp.route("/")
def index():
    categories = Category.query.filter_by(is_active=True).all()

    featured_products = Product.query.filter_by(
        is_featured=True,
        is_active=True
    ).order_by(Product.created_at.desc()).limit(8).all()

    return render_template(
        "index.html",
        categories=categories,
        featured_products=featured_products,
        current_year=datetime.now().year
    )

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
    
@main_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("product_detail.html", product=product)    

# Categories
@main_bp.route("/category/<category_slug>")
def category_products(category_slug):
    # Find category or 404
    category = Category.query.filter_by(slug=category_slug).first_or_404()
    # Get products for this category
    products = Product.query.filter_by(category_id=category.id).all()
    return render_template("category_products.html", category=category, products=products)

# Offers
@main_bp.route("/offers")
def offers():
    return render_template("offers.html", current_year=datetime.now().year)

# Chamas
from datetime import datetime

@main_bp.route("/chama")
def chama():
    now = datetime.utcnow()

    chamas = Chama.query.filter(
        (Chama.deadline == None) | (Chama.deadline > now)
    ).order_by(Chama.created_at.desc()).all()

    return render_template(
        "chama.html",
        chamas=chamas,
        now=now,
        current_year=datetime.now().year
    )
    
@main_bp.route("/chama/<int:chama_id>")
def chama_detail(chama_id):
    chama = Chama.query.get_or_404(chama_id)

    return render_template(
        "chama_detail.html",
        chama=chama,
        current_year=datetime.now().year
    )


@main_bp.route("/chamas/<int:chama_id>/join", methods=["GET", "POST"])
def join_chama(chama_id):
    chama = Chama.query.get_or_404(chama_id)

    # --- HANDLE GET REQUEST (Display the form) ---
    if request.method == "GET":
        # 🚫 Prevent accessing join page if closed/full
        if chama.status != "open":
            flash("This chama is not open for joining.", "error")
            return redirect(url_for("main.chama_details", chama_id=chama.id))

        if len(chama.members) >= chama.max_members:
            flash("This chama is already full.", "error")
            return redirect(url_for("main.chama_details", chama_id=chama.id))

        # Render the join form template
        return render_template("join_chama.html", chama=chama)

    # --- HANDLE POST REQUEST (Process the form) ---
    try:
        # 🚫 Prevent joining closed/full chama (Double check on submit)
        if chama.status != "open":
            flash("This chama is not open for joining.", "error")
            return redirect(url_for("main.chamas"))

        if len(chama.members) >= chama.max_members:
            flash("This chama is already full.", "error")
            return redirect(url_for("main.chamas"))

        # 🔹 Get form data
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        email = request.form.get("email")

        location = request.form.get("location")
        address = request.form.get("address")

        payment_method = request.form.get("payment_method")

        # 🔹 Assign position (queue logic)
        position = len(chama.members) + 1

        # 🔹 Create member
        member = ChamaMember(
            chama_id=chama.id,
            user_id=current_user.id if current_user.is_authenticated else None,

            full_name=full_name,
            phone=phone,
            email=email,

            location=location,
            address=address,

            payment_method=payment_method,

            position=position,
            status="active",
            joined_at=datetime.utcnow()
        )

        db.session.add(member)
        db.session.commit()

        flash("Successfully joined the chama!", "success")
        return redirect(url_for("main.chama_details", chama_id=chama.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Error joining chama: {str(e)}", "error")
        return redirect(url_for("main.chama"))


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
    cart = session.get("cart", {})

    # Standardize cart to dictionary: {product_id: quantity}
    standardized_cart = {}

    if isinstance(cart, dict):
        standardized_cart = {str(k): v for k, v in cart.items()}

    elif isinstance(cart, list):
        # List could be IDs or dicts
        for item in cart:
            if isinstance(item, dict) and "product_id" in item:
                pid = str(item["product_id"])
                qty = item.get("quantity", 1)
                standardized_cart[pid] = qty
            else:
                # assume item is product ID as str/int
                pid = str(item)
                standardized_cart[pid] = standardized_cart.get(pid, 0) + 1

    # Save standardized cart back in session
    session["cart"] = standardized_cart

    products_in_cart = []
    total_price = 0

    for product_id_str, quantity in standardized_cart.items():
        try:
            product_id = int(product_id_str)
        except ValueError:
            continue

        product = Product.query.get(product_id)
        if product:
            item_total = product.price * quantity
            total_price += item_total

            products_in_cart.append({
                "product": product,
                "quantity": quantity,
                "total": item_total
            })

    return render_template(
        "cart.html",
        products=products_in_cart,
        total_price=total_price,
        cart_count=sum(standardized_cart.values()),
        current_year=datetime.now().year
    )

@main_bp.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    from flask import request, jsonify
    from flask_login import current_user
    from app import db
    from app.models import Cart, CartItem, Product

    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Login required"}), 403

    data = request.get_json()
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 1))

    if not product_id:
        return jsonify({"success": False, "message": "No product ID provided"}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"success": False, "message": "Product not found"}), 404

    # Get or create cart for current user
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()  # commit to get cart.id

    # Check if item already in cart
    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=quantity,
            price=product.price
        )
        db.session.add(cart_item)

    db.session.commit()

    # Count total items
    total_items = sum(item.quantity for item in cart.items)

    return jsonify({"success": True, "cart_count": total_items})


@main_bp.route("/cart/remove", methods=["POST"])
def remove_from_cart():
    product_id = request.form.get("product_id")

    cart = session.get("cart", [])

    # remove item (simple list)
    cart = [item for item in cart if str(item) != str(product_id)]

    session["cart"] = cart

    flash("Item removed from cart", "success")
    return redirect(url_for("main.cart"))


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

@main_bp.route("/checkout", methods=["GET"])
def checkout():
    cart_ids = session.get("cart", [])

    # Fetch products from DB using IDs
    products_in_cart = Product.query.filter(
        Product.id.in_(cart_ids)
    ).all() if cart_ids else []

    # Calculate subtotal
    subtotal = sum(p.price for p in products_in_cart)

    return render_template(
        "checkout.html",
        products=products_in_cart,
        subtotal=subtotal,
        cart_count=len(cart_ids),
        current_year=datetime.now().year
    )

import uuid

@main_bp.route("/checkout/process", methods=["POST"])
def checkout_process():
    from flask import request, redirect, url_for, flash
    from flask_login import current_user
    from app import db
    from app.models import Cart, CartItem, Order, OrderItem
    import uuid
    from datetime import datetime

    if not current_user.is_authenticated:
        flash("Login required to checkout.", "danger")
        return redirect(url_for("auth.login"))

    # Get user's cart
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart or not cart.items:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("main.cart"))

    # --- Form data ---
    full_name = request.form.get("full_name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    address = request.form.get("address")
    city = request.form.get("city")
    delivery_method = request.form.get("delivery_method")
    delivery_location = request.form.get("delivery_location")
    notes = request.form.get("notes")

    # --- Calculate subtotal and total ---
    subtotal = sum(item.price * item.quantity for item in cart.items)

    delivery_fee = 0
    if delivery_method == "local":
        delivery_fee = 300
    elif delivery_method == "countrywide":
        delivery_fee = 500

    total_amount = subtotal + delivery_fee

    # --- Create order ---
    order = Order(
        user_id=current_user.id,
        order_number=str(uuid.uuid4())[:8],
        full_name=full_name,
        email=email,
        phone=phone,
        shipping_address=address,
        city=city,
        country="Kenya",
        delivery_method=delivery_method,
        delivery_location=delivery_location,
        notes=notes,
        total_amount=total_amount,
        delivery_fee=delivery_fee,
        status="pending",
        payment_status="pending",
        created_at=datetime.utcnow()
    )
    db.session.add(order)
    db.session.commit()  # commit to get order.id

    # --- Add order items ---
    for item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price=item.price,
            total_price=item.price * item.quantity
        )
        db.session.add(order_item)

    db.session.commit()

    # --- Clear cart ---
    db.session.delete(cart)
    db.session.commit()

    flash("Order placed successfully!", "success")
    return redirect(url_for("main.index"))

# Orders
@main_bp.route("/orders")
def orders():
    return render_template("orders.html", current_year=datetime.now().year)

# User dashboard
@main_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", current_year=datetime.now().year)