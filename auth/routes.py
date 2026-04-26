# app/auth/routes.py

from flask import render_template, request, flash, redirect, url_for
from . import auth_bp

@auth_bp.route("/password-reset", methods=["GET", "POST"])
def password_reset():

    if request.method == "POST":
        email = request.form.get("email")

        # TODO: send reset email
        flash("Password reset link sent to your email", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/password_reset.html")