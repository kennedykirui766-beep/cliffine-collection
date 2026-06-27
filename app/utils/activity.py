from app import db
from app.models import AdminActivity
from flask import request


def log_activity(admin_id, action, description="", ip=None, user_agent=None):
    activity = AdminActivity(
        admin_id=admin_id,
        action=action,
        description=description,
        ip_address=ip or (request.remote_addr if request else ""),
        user_agent=user_agent or (request.headers.get("User-Agent", "")[:500] if request else ""),
    )
    db.session.add(activity)
    db.session.commit()
    return activity


def get_activity_colors(action):
    colors = {
        "login": "bg-green-500",
        "profile_update": "bg-blue-500",
        "password_change": "bg-amber-500",
        "photo_update": "bg-purple-500",
        "preferences_update": "bg-indigo-500",
        "logout": "bg-slate-400",
        "account_delete": "bg-red-500",
    }
    return colors.get(action, "bg-slate-400")


def get_action_labels(action):
    labels = {
        "login": "Logged in",
        "profile_update": "Updated profile information",
        "password_change": "Changed password",
        "photo_update": "Updated profile photo",
        "preferences_update": "Updated preferences",
        "logout": "Logged out",
        "account_delete": "Deleted account",
    }
    return labels.get(action, action.replace("_", " ").title())