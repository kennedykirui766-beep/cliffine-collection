import json
from app import db
from app.models import Notification


def notify(category, type_, title, message="", link=None, metadata=None, admin_id=None):
    """Quickly create a notification.

    Usage examples:
        notify('order', 'new', 'New Order #1254',
               'Kennedy Kirui placed an order worth KSh 4,800.',
               '/admin/orders/1254')

        notify('inventory', 'low', 'Low Stock',
               'Classic Hoodie — Only 3 items remaining.',
               '/admin/inventory')

        notify('payment', 'failed', 'Payment Failed',
               'Order #1254 payment via M-Pesa failed.',
               '/admin/orders/1254')

        notify('milestone', 'sales_milestone',
               "Today's sales exceeded KSh 100,000!",
               '/admin/reports')

        notify('coupon', 'coupon_expiring', 'Coupon WELCOME10 Expiring Soon',
               'Expires in 2 days. Used 95 of 100 times.',
               '/admin/coupons')
    """
    notif = Notification(
        category=category,
        type=type_,
        title=title,
        message=message,
        link=link or "",
        metadata_json=json.dumps(metadata) if metadata else None,
        admin_id=admin_id,
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def notify_bulk(notifications_list):
    """Create multiple notifications in one commit.
    Each item is a dict with keys: category, type, title, message, link, metadata.
    """
    for n in notifications_list:
        notif = Notification(
            category=n.get("category", "system"),
            type=n.get("type", "info"),
            title=n.get("title", ""),
            message=n.get("message", ""),
            link=n.get("link", ""),
            metadata_json=json.dumps(n["metadata"]) if n.get("metadata") else None,
        )
        db.session.add(notif)
    db.session.commit()


def cleanup_old_notifications(days=30, keep_unread=True):
    """Delete read notifications older than N days. Keeps unread ones."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = Notification.query.filter(
        Notification.is_read == True,
        Notification.created_at < cutoff,
    )
    count = query.count()
    query.delete(synchronize_session=False)
    db.session.commit()
    return count