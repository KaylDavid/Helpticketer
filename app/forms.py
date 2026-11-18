from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from .extensions import db
from .models import CATEGORIES, PRIORITIES, User


def strip_text(value):
    """Remove spaces at the start and end of text typed into a field."""
    return value.strip() if isinstance(value, str) else value


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


class TicketForm(FlaskForm):
    title = StringField(
        "Title",
        filters=[strip_text],
        validators=[
            DataRequired(message="Please enter a title."),
            Length(min=3, max=120, message="Title must be 3 to 120 characters."),
        ],
    )
    description = TextAreaField(
        "Description",
        filters=[strip_text],
        validators=[
            DataRequired(message="Please describe the problem."),
            Length(min=10, max=5000, message="Description must be 10 to 5000 characters."),
        ],
    )
    category = SelectField(
        "Category",
        choices=[(c, c) for c in CATEGORIES],
        validators=[DataRequired(message="Please choose a category.")],
    )
    priority = SelectField(
        "Priority",
        choices=[(p, p) for p in PRIORITIES],
        default="Medium",
        validators=[DataRequired(message="Please choose a priority.")],
    )
    submit = SubmitField("Submit ticket")