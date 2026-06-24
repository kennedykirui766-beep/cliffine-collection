from collections import defaultdict
from operator import and_

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from datetime import datetime
from flask import session
from app.forms import ContactForm, LoginForm, RegistrationForm, ProfileForm
from flask_login import current_user, login_required, login_user, logout_user
from app.models import FAQ, BlogPost, Cart, CartItem, Category, Chama, ChamaMember, ContactMessage, Order, OrderItem, Product, DeliveryArea, User, Wishlist, WishlistItem
from app import db
from flask_login import login_required, current_user

from app.models import Product

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

@main_bp.route("/categories/<slug>")
def category_products(slug):
    category = Category.query.filter_by(slug=slug, is_active=True).first_or_404()

    products = Product.query.filter_by(
        category_id=category.id,
        is_active=True
    ).all()

    return render_template(
        "category_products.html",
        category=category,
        products=products
    )



@main_bp.route("/categories")
def all_categories():
    categories = Category.query.filter_by(is_active=True).all()

    # ✅ Fetch trending electronics
    trending_products = Product.query.join(Category).filter(
        Category.slug == "electronics",
        Product.is_trending == True,
        Product.is_active == True
    ).all()

    return render_template(
        "categories.html",
        categories=categories,
        products=trending_products
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



# Offers

from datetime import datetime

@main_bp.route("/offers")
def offers():
    products = Product.query.all()

    print("TOTAL PRODUCTS:", len(products))

    offer_products = Product.query.filter_by(is_on_offer=True).all()

    print("ON OFFER COUNT:", len(offer_products))

    for p in offer_products:
        print(
            p.name,
            p.is_on_offer,
            p.offer_start,
            p.offer_end,
            p.offer_percentage
        )

    return render_template(
        "offers.html",
        products=offer_products,
        current_year=datetime.now().year
    )

# Chamas
from datetime import datetime

@main_bp.route("/chama")
@main_bp.route("/chamas")
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

    if request.method == "GET":
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
        return redirect(url_for("main.chama_detail", chama_id=chama.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Error joining chama: {str(e)}", "error")
        return redirect(url_for("main.chama"))


# Lipa Pole Pole
@main_bp.route("/lipa-pole-pole")
def lipa_pole_pole():
    products = Product.query.filter_by(
        lipa_pole_pole=True,
        is_active=True
    ).order_by(Product.created_at.desc()).all()

    return render_template(
        "lipa_pole_pole.html",
        products=products,
        current_year=datetime.now().year
    )

# Wishlist
@main_bp.route("/wishlist")
def wishlist():

    wishlist = None

    # ── Logged-in user ─────────────────────────────
    if current_user.is_authenticated:
        wishlist = Wishlist.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).first()

    # ── Guest user (session-based) ─────────────────
    else:
        session_id = session.get("wishlist_session_id")

        if session_id:
            wishlist = Wishlist.query.filter_by(
                session_id=session_id,
                is_active=True
            ).first()

    # ── Extract items safely ───────────────────────
    items = wishlist.items if wishlist else []

    return render_template(
        "wishlist.html",
        wishlist=wishlist,
        items=items,
        current_year=datetime.now().year
    )


@main_bp.route("/wishlist/add/<int:product_id>", methods=["POST"])
def add_to_wishlist(product_id):

    # ── Get product ─────────────────────────────
    product = Product.query.get_or_404(product_id)

    # ── Determine wishlist owner ────────────────
    wishlist = None

    if current_user.is_authenticated:
        wishlist = Wishlist.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).first()

        if not wishlist:
            wishlist = Wishlist(user_id=current_user.id)
            db.session.add(wishlist)

    else:
        # Guest user → use session
        if not session.get("wishlist_session_id"):
            session["wishlist_session_id"] = str(uuid.uuid4())

        wishlist = Wishlist.query.filter_by(
            session_id=session["wishlist_session_id"],
            is_active=True
        ).first()

        if not wishlist:
            wishlist = Wishlist(session_id=session["wishlist_session_id"])
            db.session.add(wishlist)

    db.session.flush() 

    # ── Prevent duplicates ──────────────────────
    existing = WishlistItem.query.filter_by(
        wishlist_id=wishlist.id,
        product_id=product.id
    ).first()

    if existing:
        return jsonify({"status": "exists", "message": "Already in wishlist"})

    # ── Add item ───────────────────────────────
    item = WishlistItem(
        wishlist_id=wishlist.id,
        product_id=product.id
    )

    db.session.add(item)
    db.session.commit()

    return jsonify({"status": "success", "message": "Added to wishlist"})


@main_bp.route("/wishlist/remove/<int:item_id>", methods=["POST"])
def remove_from_wishlist(item_id):

    item = WishlistItem.query.get_or_404(item_id)

    db.session.delete(item)
    db.session.commit()

    flash("Removed from wishlist", "success")
    return redirect(url_for("main.wishlist"))

# Blog list page
@main_bp.route("/blog")
def blog():

    posts = BlogPost.query.filter_by(
        is_published=True
    ).order_by(BlogPost.created_at.desc()).all()

    return render_template(
        "blog/list.html",
        posts=posts,
        current_year=datetime.now().year
    )


# Single blog post
@main_bp.route("/blog/<slug>")
def blog_detail(slug):

    post = BlogPost.query.filter_by(
        slug=slug,
        is_published=True
    ).first()

    if not post:
        abort(404)

    return render_template(
        "blog/detail.html",
        post=post,
        current_year=datetime.now().year
    )

# About
@main_bp.route("/about")
def about():
    return render_template("about.html", current_year=datetime.now().year)

# Contact
@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()

    if form.validate_on_submit():

        contact_message = ContactMessage(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            subject=form.subject.data,
            message=form.message.data
        )

        db.session.add(contact_message)
        db.session.commit()

        flash(
            "Thank you for contacting us. We will get back to you shortly.",
            "success"
        )

        return redirect(url_for("main.contact"))

    return render_template(
        "contact.html",
        form=form,
        current_year=datetime.now().year
    )

# FAQ
@main_bp.route("/faq")
def faq():

    faqs = FAQ.query.filter_by(is_active=True)\
        .order_by(FAQ.category, FAQ.sort_order)\
        .all()

    grouped_faqs = defaultdict(list)

    for faq in faqs:
        grouped_faqs[faq.category or "General"].append(faq)

    return render_template(
        "faq.html",
        grouped_faqs=grouped_faqs
    )


@main_bp.route("/faq/search")
def faq_search():

    query = request.args.get("q", "")

    faqs = FAQ.query.filter(
        FAQ.question.ilike(f"%{query}%"),
        FAQ.is_active == True
    ).all()

    grouped_faqs = defaultdict(list)

    for faq in faqs:
        grouped_faqs[faq.category or "General"].append(faq)

    return render_template(
        "faq_search.html",
        grouped_faqs=grouped_faqs,
        query=query
    )

# Cart
@main_bp.route("/cart")
def cart():
    from flask import session, render_template
    from flask_login import current_user
    from app.models import Cart, Product

    products_in_cart = []
    total_price = 0
    cart_count = 0

    # Get cart (user or session)
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
    else:
        session_id = session.get("cart_session")
        cart = Cart.query.filter_by(session_id=session_id).first() if session_id else None

    if cart and cart.items:
        for item in cart.items:
            product = Product.query.get(item.product_id)

            if product:
                # ✅ Use discount price if available
                unit_price = product.discount_price if product.discount_price else product.price

                item_total = unit_price * item.quantity

                total_price += item_total
                cart_count += item.quantity

                products_in_cart.append({
                    "product": product,
                    "quantity": item.quantity,
                    "total": item_total,
                    "unit_price": unit_price 
                })

    return render_template(
        "cart.html",
        products=products_in_cart,
        total_price=total_price,
        cart_count=cart_count
    )

@main_bp.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    from flask import request, jsonify, session
    from flask_login import current_user
    from app import db
    from app.models import Cart, CartItem, Product
    import uuid

    data = request.get_json()
    product_id = int(data.get("product_id"))
    quantity = int(data.get("quantity", 1))

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"success": False, "message": "Product not found"}), 404

    # --- Determine cart owner ---
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not cart:
            cart = Cart(user_id=current_user.id)
            db.session.add(cart)
    else:
        # Guest cart
        session_id = session.get("cart_session")
        if not session_id:
            session_id = str(uuid.uuid4())
            session["cart_session"] = session_id
        cart = Cart.query.filter_by(session_id=session_id).first()
        if not cart:
            cart = Cart(session_id=session_id)
            db.session.add(cart)

    db.session.commit()  # ensure cart.id exists

    # --- Add or update item ---
    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity, price=product.price)
        db.session.add(cart_item)

    db.session.commit()

    total_items = sum(item.quantity for item in cart.items)
    return jsonify({"success": True, "cart_count": total_items})

@main_bp.route("/cart/update", methods=["POST"])
def update_cart():
    from flask import request, jsonify, session
    from flask_login import current_user
    from app.models import Cart, CartItem

    data = request.get_json()
    updates = data.get("updates", [])

    # Get cart
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
    else:
        session_id = session.get("cart_session")
        cart = Cart.query.filter_by(session_id=session_id).first()

    if not cart:
        return jsonify({"success": False, "message": "Cart not found"}), 404

    for update in updates:
        product_id = int(update.get("product_id"))
        quantity = int(update.get("quantity"))

        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()

        if item:
            if quantity <= 0:
                # Remove item
                db.session.delete(item)
            else:
                item.quantity = quantity

    db.session.commit()

    return jsonify({"success": True})

@main_bp.route("/cart/coupon/apply", methods=["POST"])
def apply_coupon():
    from flask import request, jsonify

    data = request.get_json()
    code = data.get("code")

    # Example logic (replace with DB later)
    if code == "SAVE10":
        return jsonify({
            "success": True,
            "message": "Coupon applied!",
            "discount_amount": 100,
            "new_total": 900  # you should calculate this dynamically
        })

    return jsonify({
        "success": False,
        "message": "Invalid coupon"
    }), 400


@main_bp.route("/cart/remove", methods=["POST"])
def remove_from_cart():
    from flask import request, redirect, url_for, session, flash
    from flask_login import current_user
    from app.models import Cart, CartItem
    from app import db

    product_id = request.form.get("product_id")

    # Get correct cart
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
    else:
        session_id = session.get("cart_session")
        cart = Cart.query.filter_by(session_id=session_id).first()

    if not cart:
        flash("Cart not found", "error")
        return redirect(url_for("main.cart"))

    # Find item
    item = CartItem.query.filter_by(
        cart_id=cart.id,
        product_id=product_id
    ).first()

    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Item removed from cart", "success")
    else:
        flash("Item not found in cart", "error")

    return redirect(url_for("main.cart"))


# Account

@main_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():

        email = form.email.data.strip().lower()

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered", "danger")
            return redirect(url_for("main.register"))

        # safer name splitting
        name_parts = form.name.data.strip().split()

        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=form.phone.data  # if your form has it
        )

        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", form=form)


@main_bp.route("/login", methods=["GET", "POST"])
def login():

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)

            flash("Login successful", "success")
            return redirect(url_for("main.index"))

        flash("Invalid email or password", "danger")

    return render_template(
        "login.html",
        form=form
    )

@main_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.login"))

@main_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():

    user = current_user

    # Profile form
    form = ProfileForm(obj=user)

    if form.validate_on_submit():

        existing_user = User.query.filter(
            User.email == form.email.data.lower().strip(),
            User.id != user.id
        ).first()

        if existing_user:
            flash("Email already in use.", "danger")
            return redirect(url_for("main.account"))

        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.email = form.email.data.lower().strip()
        user.phone = form.phone.data
        user.address = form.address.data
        user.city = form.city.data
        user.country = form.country.data

        db.session.commit()

        flash("Profile updated successfully.", "success")

        return redirect(url_for("main.account"))

    # Wishlist
    wishlist = Wishlist.query.filter_by(
        user_id=user.id,
        is_active=True
    ).first()

    wishlist_items = wishlist.items if wishlist else []

    return render_template(
        "account.html",
        user=user,
        form=form,
        wishlist_items=wishlist_items,
        current_year=datetime.now().year
    )
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
    from flask_login import current_user
    from flask import session, render_template
    from app.models import Cart, Product, DeliveryArea
    from datetime import datetime

    products_in_cart = []
    subtotal = 0
    cart_count = 0

    # Get cart
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
    else:
        session_id = session.get("cart_session")
        cart = Cart.query.filter_by(session_id=session_id).first() if session_id else None

    # Build cart items
    if cart and cart.items:
        for item in cart.items:
            product = Product.query.get(item.product_id)
            if product:
                unit_price = product.discount_price if product.discount_price else product.price
                item_total = unit_price * item.quantity

                subtotal += item_total
                cart_count += item.quantity

                products_in_cart.append({
                    "product": product,
                    "quantity": item.quantity,
                    "total": item_total,
                    "unit_price": unit_price
                })

    # ✅ Fetch delivery areas
    areas = DeliveryArea.query.filter_by(is_active=True).all()

    return render_template(
        "checkout.html",
        products=products_in_cart,
        subtotal=subtotal,
        cart_count=cart_count,
        areas=areas,
        current_year=datetime.now().year
    )

import uuid

import requests
import base64
from datetime import datetime
from flask import jsonify, request, session, url_for, current_app

@main_bp.route("/checkout/initiate-stk", methods=["POST"])
def initiate_stk_push():
    """Initiate M-Pesa STK Push"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
            
        phone = data.get("phone")
        amount = data.get("amount")
        
        if not phone or not amount:
            return jsonify({"success": False, "message": "Phone and amount are required"}), 400
        
        # Format phone number (remove leading 0 or +254)
        phone = phone.replace(" ", "").replace("-", "")
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif phone.startswith("+"):
            phone = phone[1:]
        
        # Ensure phone starts with 254
        if not phone.startswith("254"):
            phone = "254" + phone
        
        # M-Pesa credentials from config
        consumer_key = current_app.config.get("MPESA_CONSUMER_KEY")
        consumer_secret = current_app.config.get("MPESA_CONSUMER_SECRET")
        passkey = current_app.config.get("MPESA_PASSKEY")
        business_short_code = current_app.config.get("MPESA_BUSINESS_SHORT_CODE", "174379")
        
        # Check if credentials are configured
        if not consumer_key or not consumer_secret or not passkey:
            current_app.logger.error("M-Pesa credentials not configured")
            return jsonify({
                "success": False, 
                "message": "Payment system not configured. Please contact support."
            }), 500
        
        # Get access token
        try:
            api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            response = requests.get(
                api_url, 
                auth=(consumer_key, consumer_secret),
                timeout=30
            )
            
            if response.status_code != 200:
                current_app.logger.error(f"M-Pesa auth failed: {response.status_code} - {response.text}")
                return jsonify({
                    "success": False, 
                    "message": "Failed to connect to M-Pesa. Please try again."
                }), 503
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                current_app.logger.error(f"No access token in response: {token_data}")
                return jsonify({
                    "success": False, 
                    "message": "Failed to get M-Pesa access token."
                }), 503
                
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"M-Pesa auth request error: {str(e)}")
            return jsonify({
                "success": False, 
                "message": "Network error connecting to M-Pesa. Please try again."
            }), 503
        
        # Generate password
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_str = f"{business_short_code}{passkey}{timestamp}"
        password = base64.b64encode(password_str.encode()).decode()
        
        # STK Push request
        stk_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "BusinessShortCode": business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(round(amount)),
            "PartyA": int(phone),
            "PartyB": int(business_short_code),
            "PhoneNumber": int(phone),
            "CallBackURL": url_for("main.mpesa_callback", _external=True),
            "AccountReference": "Cliffine",
            "TransactionDesc": f"Order {int(round(amount))}"
        }
        
        try:
            response = requests.post(stk_url, json=payload, headers=headers, timeout=30)
            result = response.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"STK Push request error: {str(e)}")
            return jsonify({
                "success": False, 
                "message": "Network error sending STK Push. Please try again."
            }), 503
        
        if result.get("ResponseCode") == "0":
            checkout_request_id = result.get("CheckoutRequestID")
            merchant_request_id = result.get("MerchantRequestID")

            # ----------------------------------------------------------
            # Save to database instead of session.
            # 
            # The callback from Safaricom comes from Safaricom's servers,
            # NOT from the customer's browser. So session storage is
            # useless — the callback cannot read or write the customer's
            # session. The database is the only shared medium.
            # 
            # order_id is set to None here because the order hasn't been
            # placed yet (it's placed AFTER payment is confirmed).
            # Your Payment model needs: order_id = db.Column(..., nullable=True)
            # ----------------------------------------------------------
            payment = Payment(
                order_id=None,
                user_id=current_user.id if current_user.is_authenticated else None,
                checkout_request_id=checkout_request_id,
                merchant_request_id=merchant_request_id,
                phone_number=phone,
                amount=float(amount),
                mpesa_receipt=None,
                status="pending",
                result_code=None,
                result_desc=None
            )

            db.session.add(payment)

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to save payment record: {str(e)}", exc_info=True)
                # Don't block the user — the STK was already sent.
                # The callback can still arrive and we can handle it.
                # But log it loudly so you know.

            return jsonify({
                "success": True,
                "message": "STK Push sent successfully. Check your phone.",
                "checkout_request_id": checkout_request_id
            })
        else:
            error_code = result.get("errorCode", "Unknown")
            error_desc = result.get("errorMessage", result.get("ResponseDescription", "Failed to initiate STK Push"))
            
            current_app.logger.error(f"STK Push failed: {error_code} - {error_desc}")
            
            # Provide user-friendly error messages
            if "Invalid" in error_desc and "Phone" in error_desc:
                error_desc = "Invalid phone number. Please check and try again."
            elif "Invalid" in error_desc and "Amount" in error_desc:
                error_desc = "Invalid amount. Please contact support."
            elif "insufficient" in error_desc.lower():
                error_desc = "Insufficient balance in your M-Pesa account."
            
            return jsonify({
                "success": False,
                "message": error_desc
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Unexpected error in initiate_stk_push: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "An unexpected error occurred. Please try again."
        }), 500


@main_bp.route("/checkout/check-stk-status", methods=["GET"])
def check_stk_status():
    """Check STK Push status - reads from DATABASE, not session.

    Flow:
      1. Query the Payment table by checkout_request_id
      2. If callback already updated status to "paid" → return success immediately
      3. If callback already updated status to "failed"/"cancelled" → return failure
      4. If still "pending" → fall back to querying M-Pesa STK Query API directly
         (handles the case where callback was delayed or never arrived)
      5. If M-Pesa query returns a result → update the database with it
    """
    try:
        checkout_request_id = request.args.get("checkout_request_id")
        
        if not checkout_request_id:
            return jsonify({"success": False, "message": "No checkout request ID"}), 400
        
        # ----------------------------------------------------------
        # Step 1: Ask the DATABASE first (callback may have updated it)
        # ----------------------------------------------------------
        payment = Payment.query.filter_by(checkout_request_id=checkout_request_id).first()
        
        if not payment:
            return jsonify({"success": False, "message": "Payment record not found"}), 404
        
        # Callback already confirmed it — return immediately, no need to query M-Pesa
        if payment.status == "paid":
            # Store in browser session so checkout_process can find this record.
            # This is safe because THIS route runs in the customer's browser session,
            # unlike the callback which runs on Safaricom's servers.
            session["confirmed_checkout_request_id"] = checkout_request_id
            
            return jsonify({
                "success": True,
                "status": "success",
                "message": "Payment confirmed",
                "receipt": payment.mpesa_receipt or ""
            })
        
        # Callback already marked it failed or cancelled
        if payment.status in ("failed", "cancelled"):
            return jsonify({
                "success": True,
                "status": "failed",
                "message": payment.result_desc or "Payment failed or cancelled"
            })
        
        # ----------------------------------------------------------
        # Step 2: DB still says "pending" — ask M-Pesa directly as fallback
        # ----------------------------------------------------------
        consumer_key = current_app.config.get("MPESA_CONSUMER_KEY")
        consumer_secret = current_app.config.get("MPESA_CONSUMER_SECRET")
        passkey = current_app.config.get("MPESA_PASSKEY")
        business_short_code = current_app.config.get("MPESA_BUSINESS_SHORT_CODE", "174379")
        
        if not consumer_key or not consumer_secret or not passkey:
            return jsonify({"success": False, "message": "Payment system not configured"}), 500
        
        # Get access token
        try:
            api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            response = requests.get(
                api_url, 
                auth=(consumer_key, consumer_secret),
                timeout=30
            )
            access_token = response.json().get("access_token")
            
            if not access_token:
                return jsonify({"success": False, "message": "Failed to get M-Pesa access token"}), 503
        except requests.exceptions.RequestException:
            return jsonify({"success": False, "message": "Network error"}), 503
        
        # Generate password
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{business_short_code}{passkey}{timestamp}".encode()).decode()
        
        # Query M-Pesa
        status_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "BusinessShortCode": business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        try:
            response = requests.post(status_url, json=payload, headers=headers, timeout=30)
            result = response.json()
        except requests.exceptions.RequestException:
            return jsonify({"success": False, "message": "Network error"}), 503
        
        result_code = result.get("ResultCode")
        
        if result_code == "0":
            # M-Pesa confirms paid — update the DATABASE
            metadata_items = result.get("CallbackMetadata", {}).get("Item", []) if result.get("CallbackMetadata") else []
            mpesa_receipt = ""
            for item in metadata_items:
                if item.get("Name") == "MpesaReceiptNumber":
                    mpesa_receipt = item.get("Value", "")
            
            # Prefer the receipt from M-Pesa query; fall back to whatever callback may have set
            payment.status = "paid"
            payment.mpesa_receipt = mpesa_receipt or payment.mpesa_receipt
            payment.result_code = str(result_code)
            payment.result_desc = result.get("ResultDesc", "")
            payment.paid_at = datetime.utcnow()
            db.session.commit()
            
            # Store in browser session for checkout_process
            session["confirmed_checkout_request_id"] = checkout_request_id
            
            return jsonify({
                "success": True,
                "status": "success",
                "message": "Payment confirmed",
                "receipt": mpesa_receipt or payment.mpesa_receipt or ""
            })
        
        elif result_code is not None and result_code != "0":
            # M-Pesa says failed — update the DATABASE
            payment.status = "failed"
            payment.result_code = str(result_code)
            payment.result_desc = result.get("ResultDesc", "Payment failed or cancelled")
            db.session.commit()
            
            return jsonify({
                "success": True,
                "status": "failed",
                "message": result.get("ResultDesc", "Payment failed or cancelled")
            })
        
        else:
            # M-Pesa also says pending — keep polling
            return jsonify({
                "success": True,
                "status": "pending",
                "message": result.get("ResultDesc", "Waiting for confirmation")
            })
            
    except Exception as e:
        current_app.logger.error(f"Error in check_stk_status: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


@main_bp.route("/mpesa/callback", methods=["POST"])
def mpesa_callback():
    """Handle M-Pesa STK Push callback - saves to DATABASE.

    IMPORTANT: This route is called by Safaricom's servers, NOT by the
    customer's browser. Therefore you CANNOT use session[] here — the
    callback has no access to the customer's session cookie.
    
    The only reliable way to pass data from callback → customer is
    through the database.
    """
    try:
        data = request.get_json(force=True)
        
        current_app.logger.info(f"M-Pesa callback received: {data}")
        
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        result_code = str(stk_callback.get("ResultCode"))
        result_desc = stk_callback.get("ResultDesc")
        
        current_app.logger.info(
            f"STK Callback - RequestID: {checkout_request_id}, "
            f"Code: {result_code}, Desc: {result_desc}"
        )
        
        if not checkout_request_id:
            current_app.logger.warning("M-Pesa callback missing CheckoutRequestID")
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200
        
        # ----------------------------------------------------------
        # Find the payment record created by initiate_stk_push()
        # ----------------------------------------------------------
        payment = Payment.query.filter_by(checkout_request_id=checkout_request_id).first()
        
        if not payment:
            current_app.logger.warning(
                f"No payment record found for CheckoutRequestID: {checkout_request_id}"
            )
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200
        
        # Don't overwrite if callback already processed this one
        if payment.status in ("paid", "failed", "cancelled"):
            current_app.logger.info(
                f"Payment {checkout_request_id} already processed, status: {payment.status}"
            )
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200
        
        # ----------------------------------------------------------
        # Update the database record
        # ----------------------------------------------------------
        payment.result_code = result_code
        payment.result_desc = result_desc
        
        if result_code == "0":
            # Payment successful — extract receipt from metadata
            metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
            for item in metadata:
                if item.get("Name") == "MpesaReceiptNumber":
                    payment.mpesa_receipt = item.get("Value")
            
            payment.status = "paid"
            payment.paid_at = datetime.utcnow()
            
            current_app.logger.info(
                f"Payment confirmed in DB - Receipt: {payment.mpesa_receipt}, "
                f"Amount: {payment.amount}"
            )
        else:
            # Payment failed or cancelled
            if "cancelled" in (result_desc or "").lower() or result_code in ("1032", "1037"):
                payment.status = "cancelled"
            else:
                payment.status = "failed"
            
            current_app.logger.info(
                f"Payment {payment.status} in DB - Code: {result_code}, Desc: {result_desc}"
            )
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in mpesa_callback: {str(e)}", exc_info=True)
    
    # Always return 200 to M-Pesa — never return errors to Safaricom
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200


@main_bp.route("/checkout/process", methods=["POST"])
def checkout_process():
    """Process the order — verifies payment from DATABASE, not session."""
    
    payment_method = request.form.get("payment_method")
    payment = None
    
    if payment_method == "stk_push":
        # STK Push: the browser session has the checkout_request_id
        # (set by check_stk_status, which runs in the browser session)
        checkout_request_id = session.get("confirmed_checkout_request_id")
        if checkout_request_id:
            payment = Payment.query.filter_by(
                checkout_request_id=checkout_request_id,
                status="paid"
            ).first()
    
    elif payment_method == "manual":
        # Manual Paybill: the hidden form field has the M-Pesa reference
        manual_ref = request.form.get("manual_payment_ref")
        if manual_ref:
            payment = Payment.query.filter_by(
                mpesa_receipt=manual_ref,
                status="paid"
            ).first()
            
            # Fallback: if verify_manual_payment didn't create a DB record yet,
            # create one now so we have a clean payment record linked to the order
            if not payment:
                payment = Payment(
                    order_id=None,
                    user_id=current_user.id if current_user.is_authenticated else None,
                    checkout_request_id=None,
                    phone_number=request.form.get("phone"),
                    amount=0,  # will be set below
                    mpesa_receipt=manual_ref,
                    status="paid",
                    result_code="0",
                    result_desc="Manual verification",
                    paid_at=datetime.utcnow()
                )
                db.session.add(payment)
                db.session.commit()
    
    # ----------------------------------------------------------
    # Reject if no confirmed payment found in the database
    # ----------------------------------------------------------
    if not payment:
        flash("Please complete payment before placing your order.", "danger")
        return redirect(url_for("main.checkout"))
    
    mpesa_receipt = payment.mpesa_receipt

    # --- Determine cart ---
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
    else:
        session_id = session.get("cart_session")
        cart = Cart.query.filter_by(session_id=session_id).first() if session_id else None

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

    subtotal = sum(item.price * item.quantity for item in cart.items)

    delivery_fee = 0
    if delivery_method == "local":
        delivery_fee = 300
    elif delivery_method == "countrywide":
        delivery_fee = 500

    total_amount = subtotal + delivery_fee

    # --- Create order ---
    order = Order(
        user_id=current_user.id if current_user.is_authenticated else None,
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
        payment_status="paid",
        mpesa_receipt=mpesa_receipt,
        created_at=datetime.utcnow()
    )
    db.session.add(order)
    db.session.commit()

    # --- Link the payment record to this order ---
    if payment:
        payment.order_id = order.id
        # For manual payments created as fallback above, set the correct amount
        if not payment.amount or payment.amount == 0:
            payment.amount = total_amount
    db.session.commit()

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
    session.pop("cart_session", None)
    
    # --- Clear only the browser-session pointer (not payment data — that lives in DB now) ---
    session.pop("confirmed_checkout_request_id", None)

    flash("Order placed successfully!", "success")
    return redirect(url_for("main.index"))


# Orders
@main_bp.route("/orders")
@login_required
def orders():
    user_id=current_user.id

    orders = Order.query.filter_by(user_id=current_user.id)\
        .order_by(Order.created_at.desc())\
        .all()

    return render_template(
        "orders.html",
        orders=orders,
        current_year=datetime.now().year
    )

# User dashboard
@main_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", current_year=datetime.now().year)

# app/main/routes.py


@main_bp.route("/password-reset", methods=["GET", "POST"])
def password_reset():

    if request.method == "POST":
        email = request.form.get("email")

        # TODO: send reset email later
        flash("Password reset link sent to your email", "info")
        return redirect(url_for("main.login"))

    return render_template("password_reset.html")

