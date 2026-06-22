# app/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, EmailField
from wtforms.validators import DataRequired, Email, Length, EqualTo

# Contact Form
class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired(), Length(min=2, max=200)])
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Send Message')

# Login Form
class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

# Registration Form
class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[
        DataRequired(), Length(min=2, max=100)
    ])

    email = EmailField('Email', validators=[
        DataRequired(), Email()
    ])

    phone = StringField('Phone Number', validators=[
        Length(max=20)
    ])

    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=6)
    ])

    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password')
    ])

    submit = SubmitField('Register')

# Optional: Newsletter / Subscription Form
class SubscribeForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Subscribe')

class ContactForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=150)]
    )

    email = EmailField(
        "Email",
        validators=[DataRequired(), Email()]
    )

    phone = StringField(
        "Phone",
        validators=[Length(max=30)]
    )

    subject = StringField(
        "Subject",
        validators=[DataRequired(), Length(max=200)]
    )

    message = TextAreaField(
        "Message",
        validators=[DataRequired()]
    )

    submit = SubmitField("Send Message")

class ProfileForm(FlaskForm):
    first_name = StringField(
        "First Name",
        validators=[DataRequired(), Length(max=100)]
    )

    last_name = StringField(
        "Last Name",
        validators=[Length(max=100)]
    )

    email = EmailField(
        "Email",
        validators=[DataRequired(), Email()]
    )

    phone = StringField(
        "Phone",
        validators=[Length(max=50)]
    )

    address = StringField(
        "Address",
        validators=[Length(max=500)]
    )

    city = StringField(
        "City",
        validators=[Length(max=100)]
    )

    country = StringField(
        "Country",
        validators=[Length(max=100)]
    )

    submit = SubmitField("Save Changes")