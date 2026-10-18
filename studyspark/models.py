"""
Database models for StudySpark.

We use SQLite through Flask-SQLAlchemy. SQLite is a real database stored in
one file (studyspark.db) next to this project — perfect for launch, easy to
upgrade to PostgreSQL later when you have thousands of users.
"""

from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """A registered student. Passwords are always stored hashed, never in plain text."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_pro = db.Column(db.Boolean, default=False, nullable=False)  # paying member flag
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # --- Gamification: keeps students coming back (this drives retention AND revenue)
    xp = db.Column(db.Integer, default=0, nullable=False)           # total experience points
    streak = db.Column(db.Integer, default=0, nullable=False)       # consecutive active days
    last_active_date = db.Column(db.Date, nullable=True)            # used to compute the streak

    study_sets = db.relationship(
        "StudySet", backref="owner", lazy=True, cascade="all, delete-orphan"
    )
    generations = db.relationship(
        "Generation", backref="owner", lazy=True, cascade="all, delete-orphan"
    )
    card_states = db.relationship(
        "CardState", backref="owner", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        # Werkzeug uses pbkdf2 hashing with salt — industry standard.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class StudySet(db.Model):
    """One finished study resource (a deck of flashcards, a quiz, or a summary)."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # "flashcards" | "quiz" | "summary"
    content = db.Column(db.Text, nullable=False)  # JSON string with the generated material
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # --- Growth features
    share_token = db.Column(db.String(32), unique=True, nullable=True)  # public link when set
    best_score = db.Column(db.Integer, nullable=True)  # best quiz score in % (quizzes only)

    card_states = db.relationship(
        "CardState", backref="study_set", lazy=True, cascade="all, delete-orphan"
    )


class CardState(db.Model):
    """
    🔁 Spaced repetition memory: how well a user knows ONE flashcard.

    Rule of the game:
      - mark "Know it"       -> card goes away for ~3 days
      - mark "Still learning" -> card comes back tomorrow
    Studying only the cards that are DUE is how top students memorize anything
    (this is the same idea that made Anki and Duolingo famous).
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    set_id = db.Column(db.Integer, db.ForeignKey("study_set.id"), nullable=False)
    card_front = db.Column(db.String(500), nullable=False)  # key: the question text
    state = db.Column(db.String(10), nullable=False)        # "known" | "learning"
    times_known = db.Column(db.Integer, default=0, nullable=False)
    times_again = db.Column(db.Integer, default=0, nullable=False)
    next_review = db.Column(db.Date, nullable=False)         # card is DUE on/after this day
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Generation(db.Model):
    """
    A log row for every generation run. We count these per day to enforce the
    free plan limit (this is how freemium apps control costs!).
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Waitlist(db.Model):
    """Emails of people who want to join Pro — this IS your future customer list."""

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
