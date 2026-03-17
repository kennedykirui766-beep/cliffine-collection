from datetime import datetime
from app import db
from flask_login import UserMixin


# ===============================
# USERS TABLE
# ===============================
class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))

    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(50))

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(50), default="customer")  # admin, customer

    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100), default="Kenya")

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship("Order", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)


# ===============================
# CATEGORIES
# ===============================
class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True)

    description = db.Column(db.Text)
    image = db.Column(db.String(255))

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("Product", backref="category", lazy=True)


# ===============================
# PRODUCTS
# ===============================
class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True)

    short_description = db.Column(db.String(500))
    description = db.Column(db.Text)

    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float)
    cost_price = db.Column(db.Float)

    sku = db.Column(db.String(100))
    brand = db.Column(db.String(100))

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))

    stock = db.Column(db.Integer, default=0)
    low_stock = db.Column(db.Integer)

    stock_status = db.Column(db.String(50), default="in_stock")

    is_featured = db.Column(db.Boolean, default=False)
    is_trending = db.Column(db.Boolean, default=False)

    allow_reviews = db.Column(db.Boolean, default=True)

    lipa_pole_pole = db.Column(db.Boolean, default=False)
    chama_eligible = db.Column(db.Boolean, default=False)

    weight = db.Column(db.Float)
    length = db.Column(db.Float)
    width = db.Column(db.Float)
    height = db.Column(db.Float)

    shipping_class = db.Column(db.String(50))

    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.Text)
    meta_keywords = db.Column(db.String(255))

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = db.relationship("ProductImage", backref="product", lazy=True)
    reviews = db.relationship("Review", backref="product", lazy=True)


# ===============================
# PRODUCT IMAGES
# ===============================
class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))

    image_url = db.Column(db.String(255), nullable=False)

    is_main = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===============================
# INVENTORY
# ===============================
class Inventory(db.Model):
    __tablename__ = "inventory"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))

    stock_quantity = db.Column(db.Integer, default=0)

    low_stock_threshold = db.Column(db.Integer, default=5)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===============================
# ORDERS
# ===============================
class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    order_number = db.Column(db.String(100), unique=True)

    total_amount = db.Column(db.Float)

    status = db.Column(db.String(50), default="pending")
    # pending, processing, shipped, delivered, cancelled

    payment_status = db.Column(db.String(50), default="pending")

    shipping_address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True)
    payments = db.relationship("Payment", backref="order", lazy=True)


# ===============================
# ORDER ITEMS
# ===============================
class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"))

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))

    quantity = db.Column(db.Integer, nullable=False)

    price = db.Column(db.Float, nullable=False)

    total_price = db.Column(db.Float)


# ===============================
# PAYMENTS
# ===============================
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"))

    payment_method = db.Column(db.String(100))  
    # mpesa, card, paypal, cash

    transaction_id = db.Column(db.String(255))

    amount = db.Column(db.Float)

    status = db.Column(db.String(50), default="pending")

    paid_at = db.Column(db.DateTime)


# ===============================
# COUPONS
# ===============================
class Coupon(db.Model):
    __tablename__ = "coupons"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(50), unique=True)

    discount_type = db.Column(db.String(50))  
    # percentage or fixed

    discount_value = db.Column(db.Float)

    minimum_order = db.Column(db.Float)

    usage_limit = db.Column(db.Integer)

    expires_at = db.Column(db.DateTime)

    is_active = db.Column(db.Boolean, default=True)


# ===============================
# REVIEWS
# ===============================
class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))

    rating = db.Column(db.Integer)

    comment = db.Column(db.Text)

    is_approved = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===============================
# CONTACT MESSAGES
# ===============================
class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(50))

    subject = db.Column(db.String(200))

    message = db.Column(db.Text)

    is_read = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===============================
# CHAMAS
# ===============================

class Chama(db.Model):
    __tablename__ = "chamas"

    id = db.Column(db.Integer, primary_key=True)

    name                = db.Column(db.String(200), nullable=False)
    description         = db.Column(db.Text, nullable=True)
    category            = db.Column(db.String(100), nullable=True)

    # ── Target / Goal ────────────────────────────────────────────────────
    product_id          = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    target_amount       = db.Column(db.Numeric(12, 2), nullable=True)     # better precision than Float
    deadline            = db.Column(db.Date, nullable=True)               # contribution/purchase deadline

    # ── Contribution Plan ────────────────────────────────────────────────
    contribution_amount    = db.Column(db.Numeric(12, 2), nullable=True)
    contribution_frequency = db.Column(db.String(50), nullable=True)      # Daily / Weekly / Monthly
    max_members            = db.Column(db.Integer, nullable=True)

    # ── Rules & Guidelines ───────────────────────────────────────────────
    rules               = db.Column(db.Text, nullable=True)

    # ── Privacy & Access ─────────────────────────────────────────────────
    privacy             = db.Column(db.String(20), default="public", nullable=False)  # public / private
    invite_code         = db.Column(db.String(50), nullable=True, unique=True)

    # ── Payment Methods ──────────────────────────────────────────────────
    accepts_mpesa       = db.Column(db.Boolean, default=False)
    accepts_card        = db.Column(db.Boolean, default=False)
    accepts_bank        = db.Column(db.Boolean, default=False)

    # M-Pesa specific (only relevant when accepts_mpesa = True)
    mpesa_type          = db.Column(db.String(30), nullable=True)     # Paybill / TillNumber / ...
    mpesa_number        = db.Column(db.String(50), nullable=True)     # Business/Paybill number
    mpesa_account       = db.Column(db.String(100), nullable=True)    # Account name/number

    # ── Notifications ────────────────────────────────────────────────────
    notify_on_join      = db.Column(db.Boolean, default=True)
    notify_on_payment   = db.Column(db.Boolean, default=True)
    notify_on_goal      = db.Column(db.Boolean, default=True)

    # ── Media ────────────────────────────────────────────────────────────
    cover_image         = db.Column(db.String(255), nullable=True)    # path e.g. /uploads/chama_covers/xxx.jpg

    # ── Status & Audit ───────────────────────────────────────────────────
    status              = db.Column(db.String(50), default="open", nullable=False)
    created_by          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    start_date          = db.Column(db.DateTime, nullable=True)       # when chama actually starts (optional)

    # ── Relationships ────────────────────────────────────────────────────
    members = db.relationship("ChamaMember", backref="chama", lazy=True)
    product = db.relationship("Product", backref="chamas", lazy=True)


# ===============================
# CHAMA MEMBERS
# ===============================
class ChamaMember(db.Model):
    __tablename__ = "chama_members"

    id = db.Column(db.Integer, primary_key=True)

    chama_id = db.Column(db.Integer, db.ForeignKey("chamas.id"))

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    payment_status = db.Column(db.String(50), default="pending")


# ===============================
# SETTINGS
# ===============================
class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)

    site_name = db.Column(db.String(200))
    site_logo = db.Column(db.String(255))

    contact_email = db.Column(db.String(150))
    contact_phone = db.Column(db.String(50))

    address = db.Column(db.Text)

    currency = db.Column(db.String(10), default="KES")

    mpesa_number = db.Column(db.String(50))

    facebook = db.Column(db.String(255))
    instagram = db.Column(db.String(255))
    twitter = db.Column(db.String(255))

    updated_at = db.Column(db.DateTime, default=datetime.utcnow)