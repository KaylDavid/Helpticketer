from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from .extensions import db
from .models import User


class RegistrationForm(FlaskForm):
    name = StringField(
        "Full name",
        validators=[
            DataRequired(message="Please enter your name."),
            Length(max=80, message="Name must be 80 characters or fewer."),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Please enter your email."),
            Email(message="Please enter a valid email address."),
            Length(max=120, message="Email must be 120 characters or fewer."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Please choose a password."),
            Length(min=8, max=128, message="Password must be 8 to 128 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords do not match."),
        ],
    )
    submit = SubmitField("Create account")

    def validate_email(self, field):
        """Runs automatically: reject emails that are already registered."""
        email = field.data.strip().lower()
        existing = db.session.scalar(db.select(User).filter_by(email=email))
        if existing:
            raise ValidationError("That email is already registered.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(message="Please enter your email.")],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Please enter your password.")],
    )
    submit = SubmitField("Log in")