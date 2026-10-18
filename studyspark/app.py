"""
StudySpark — turn your notes into flashcards, quizzes, and summaries.

Run it:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:3000
"""

import csv
import io
import json
import os
import re
import secrets
from datetime import datetime, time, timedelta

import click
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)

load_dotenv()  # read .env into environment variables

from ai import AIError, MAX_NOTES_LENGTH, generate_study_material, is_demo_mode  # noqa: E402
from models import CardState, Generation, StudySet, User, Waitlist, db  # noqa: E402

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-secret-change-me")

# Database: SQLite on your laptop, PostgreSQL when deployed (DATABASE_URL env var).
db_url = os.getenv("DATABASE_URL", "sqlite:///studyspark.db")
# Hosting providers give URLs starting with "postgres://" but SQLAlchemy wants "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "5"))
MIN_NOTES_LENGTH = 50
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB safety cap for file uploads
VALID_KINDS = ("flashcards", "quiz", "summary")

# XP rewards — tune the game economy here 🎮
XP_GENERATE = 10        # creating a study set
XP_STUDY_FINISH = 5     # finishing a Study Mode run (plus +1 per known card)
XP_QUIZ_PER_CORRECT = 2 # per correct quiz answer

# Spaced repetition intervals (in days)
REVIEW_KNOWN_DAYS = 3
REVIEW_LEARNING_DAYS = 1

# Every new account gets this demo deck so nobody lands on an empty app 🎁
WELCOME_NOTES = """
StudySpark turns your class notes into flashcards in seconds.
You can paste notes directly or upload a PDF file.
Quiz mode tests you with multiple choice questions and saves your best score.
Summaries condense long chapters into key points and key terms.
Study Mode flips one card at a time and tracks which cards you keep missing.
Cards you mark as still learning come back tomorrow for review.
Share links let your classmates study your sets without making an account.
XP and daily streaks reward you for studying a little bit every day.
This welcome deck was generated automatically when you signed up.
"""

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to keep studying. 📚"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()  # create the SQLite tables on first run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generations_today(user_id: int) -> int:
    """How many generations this user already used today (free-plan meter)."""
    start = datetime.combine(datetime.utcnow().date(), time.min)
    return Generation.query.filter(
        Generation.user_id == user_id, Generation.created_at >= start
    ).count()


def remaining_today() -> int | None:
    """None = unlimited (Pro users)."""
    if not current_user.is_authenticated or current_user.is_pro:
        return None
    return max(0, FREE_DAILY_LIMIT - generations_today(current_user.id))


def record_activity(user: User, xp: int) -> None:
    """
    Award XP and update the daily streak.
    Caller is responsible for db.session.commit().
    """
    today = datetime.utcnow().date()
    if user.last_active_date != today:
        user.streak = (
            user.streak + 1
            if user.last_active_date == today - timedelta(days=1)
            else 1
        )
        user.last_active_date = today
    user.xp = (user.xp or 0) + xp


def get_owned_set(set_id: int) -> StudySet:
    """Fetch a set that belongs to the current user, or 404."""
    s = StudySet.query.filter_by(id=set_id, user_id=current_user.id).first()
    if not s:
        abort(404)
    return s


def due_card_states(user_id: int, set_id: int) -> list[CardState]:
    """Cards this user must review TODAY (spaced repetition queue)."""
    today = datetime.utcnow().date()
    return (
        CardState.query.filter(
            CardState.user_id == user_id,
            CardState.set_id == set_id,
            CardState.next_review <= today,
        )
        .order_by(CardState.next_review.asc())
        .all()
    )


def extract_text_from_upload(file_storage) -> str:
    """Read an uploaded .txt/.md/.pdf file and return plain text."""
    raw = file_storage.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AIError("That file is bigger than 5 MB — split it into smaller parts.")
    filename = (file_storage.filename or "").lower()
    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            raise AIError("Could not read that PDF. Try a different file or paste the text.")
    else:
        text = raw.decode("utf-8", errors="ignore")
    return text.strip()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "studyspark"


@app.context_processor
def inject_globals():
    """Variables available in EVERY template."""
    return {
        "demo_mode": is_demo_mode(),
        "free_daily_limit": FREE_DAILY_LIMIT,
        "current_year": datetime.utcnow().year,
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    sets = (
        StudySet.query.filter_by(user_id=current_user.id)
        .order_by(StudySet.created_at.desc())
        .limit(20)
        .all()
    )
    sets_view = [
        {
            "id": s.id,
            "title": s.title,
            "kind": s.kind,
            "created_at": s.created_at,
            "best_score": s.best_score,
            "is_shared": bool(s.share_token),
        }
        for s in sets
    ]
    return render_template(
        "dashboard.html",
        sets=sets_view,
        used_today=generations_today(current_user.id),
        remaining=remaining_today(),
    )


@app.route("/create", methods=["GET", "POST"])
@login_required
def create_set():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        kind = request.form.get("kind", "")
        notes = (request.form.get("notes") or "").strip()

        # Bonus input: an uploaded notes file (txt/md/pdf) merged into the notes
        upload = request.files.get("notes_file")
        upload_error = None
        if upload and upload.filename:
            try:
                file_text = extract_text_from_upload(upload)
                notes = (notes + "\n\n" + file_text).strip() if notes else file_text
            except AIError as exc:
                upload_error = str(exc)

        # --- validation (always validate user input!) ---
        if upload_error:
            flash(upload_error, "error")
        elif kind not in VALID_KINDS:
            flash("Pick what you want to create: flashcards, quiz, or summary.", "error")
        elif len(notes) < MIN_NOTES_LENGTH:
            flash(f"Your notes are too short — paste text or upload a file (at least {MIN_NOTES_LENGTH} characters).", "error")
        elif len(notes) > MAX_NOTES_LENGTH:
            flash(f"Notes are limited to {MAX_NOTES_LENGTH:,} characters. Split long chapters into parts.", "error")
        elif remaining_today() == 0:
            flash("You've used all your free generations for today. Come back tomorrow — or go Pro for unlimited! ⚡", "error")
            return redirect(url_for("pricing"))
        else:
            try:
                content = generate_study_material(kind, notes)
            except AIError as exc:
                flash(str(exc), "error")
            else:
                if not title:
                    title = notes.splitlines()[0][:60].strip() or "Untitled study set"
                s = StudySet(
                    user_id=current_user.id,
                    title=title,
                    kind=kind,
                    content=json.dumps(content),
                )
                record_activity(current_user, XP_GENERATE)
                db.session.add(s)
                db.session.add(Generation(user_id=current_user.id, kind=kind))
                db.session.commit()
                flash(f"Your study set is ready! +{XP_GENERATE} XP ⚡", "success")
                return redirect(url_for("view_set", set_id=s.id))

        return render_template("create.html", form=request.form, remaining=remaining_today())

    return render_template("create.html", form={}, remaining=remaining_today())


@app.route("/set/<int:set_id>")
@login_required
def view_set(set_id: int):
    s = get_owned_set(set_id)
    share_url = url_for("public_set", token=s.share_token, _external=True) if s.share_token else None
    due_count = len(due_card_states(current_user.id, s.id)) if s.kind == "flashcards" else 0
    return render_template(
        "set.html",
        study_set=s,
        data=json.loads(s.content),
        share_url=share_url,
        due_count=due_count,
    )


@app.route("/set/<int:set_id>/delete", methods=["POST"])
@login_required
def delete_set(set_id: int):
    s = get_owned_set(set_id)
    db.session.delete(s)
    db.session.commit()
    flash("Study set deleted.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# 🎯 Study Mode + 🔁 spaced repetition (the brain-training engine)
# ---------------------------------------------------------------------------

@app.route("/set/<int:set_id>/study")
@login_required
def study_set(set_id: int):
    s = get_owned_set(set_id)
    if s.kind != "flashcards":
        flash("Study Mode works with flashcard sets!", "error")
        return redirect(url_for("view_set", set_id=s.id))

    content = json.loads(s.content)
    deck_mode = request.args.get("deck", "all")
    flashcards = content.get("flashcards", [])

    if deck_mode == "due":
        due_fronts = {cs.card_front for cs in due_card_states(current_user.id, s.id)}
        flashcards = [c for c in flashcards if c.get("front") in due_fronts]
        if not flashcards:
            flash("🎉 Nothing due for review — come back tomorrow!", "success")
            return redirect(url_for("view_set", set_id=s.id))
        content = {"flashcards": flashcards}

    return render_template("study.html", study_set=s, data=content, deck_mode=deck_mode)


@app.route("/set/<int:set_id>/finish-study", methods=["POST"])
@login_required
def finish_study(set_id: int):
    """
    Save per-card results for spaced repetition:
      "known"    -> review again in ~3 days
      "learning" -> review again tomorrow
    Body: {"results": [{"front": "...", "state": "known"|"learning"}, ...]}
    """
    s = get_owned_set(set_id)
    payload = request.get_json(silent=True) or {}
    results = payload.get("results", [])[:200]
    today = datetime.utcnow().date()

    known = 0
    for r in results:
        front = str(r.get("front", "")).strip()[:500]
        state = "known" if r.get("state") == "known" else "learning"
        if not front:
            continue
        if state == "known":
            known += 1

        cs = CardState.query.filter_by(
            user_id=current_user.id, set_id=s.id, card_front=front
        ).first()
        if not cs:
            cs = CardState(user_id=current_user.id, set_id=s.id, card_front=front, state=state,
                           next_review=today)
            db.session.add(cs)
        cs.state = state
        # NOTE: column defaults only apply at INSERT time, so a brand-new
        # object has None here — always coerce with `or 0` before +=.
        if state == "known":
            cs.times_known = (cs.times_known or 0) + 1
            cs.next_review = today + timedelta(days=REVIEW_KNOWN_DAYS)
        else:
            cs.times_again = (cs.times_again or 0) + 1
            cs.next_review = today + timedelta(days=REVIEW_LEARNING_DAYS)

    xp_earned = XP_STUDY_FINISH + known
    record_activity(current_user, xp_earned)
    db.session.commit()

    due_remaining = len(due_card_states(current_user.id, s.id))
    return jsonify(xp_earned=xp_earned, total_xp=current_user.xp,
                   streak=current_user.streak, due_remaining=due_remaining)


# ---------------------------------------------------------------------------
# 🔗 Share links + 🌍 Explore + clone (your built-in growth engine)
# ---------------------------------------------------------------------------

@app.route("/set/<int:set_id>/share", methods=["POST"])
@login_required
def share_set(set_id: int):
    s = get_owned_set(set_id)
    if not s.share_token:
        s.share_token = secrets.token_urlsafe(8)
        db.session.commit()
    flash("Share link created! Anyone with the link can study it 🔗", "success")
    return redirect(url_for("view_set", set_id=s.id))


@app.route("/set/<int:set_id>/unshare", methods=["POST"])
@login_required
def unshare_set(set_id: int):
    s = get_owned_set(set_id)
    s.share_token = None
    db.session.commit()
    flash("Share link turned off. The set is private again.", "success")
    return redirect(url_for("view_set", set_id=s.id))


@app.route("/s/<token>")
def public_set(token: str):
    """The public page — works WITHOUT an account (perfect for class group chats)."""
    s = StudySet.query.filter_by(share_token=token).first()
    if not s:
        abort(404)
    return render_template("public_set.html", study_set=s, data=json.loads(s.content))


@app.route("/explore")
def explore():
    """A gallery of every publicly shared set — free content grows the app 🌍"""
    shared = (
        StudySet.query.filter(StudySet.share_token.isnot(None))
        .order_by(StudySet.created_at.desc())
        .limit(30)
        .all()
    )
    return render_template(
        "explore.html",
        sets=shared,
        total_users=User.query.count(),
        total_sets=StudySet.query.count(),
    )


@app.route("/clone/<token>", methods=["POST"])
@login_required
def clone_set(token: str):
    """Save someone else's shared set into YOUR library."""
    s = StudySet.query.filter_by(share_token=token).first()
    if not s:
        abort(404)
    if s.user_id == current_user.id:
        flash("That's your own set — it's already in your library 😄", "error")
        return redirect(url_for("public_set", token=token))
    copy = StudySet(
        user_id=current_user.id,
        title=s.title,
        kind=s.kind,
        content=s.content,  # shared content becomes your own copy (share/private state resets)
    )
    db.session.add(copy)
    db.session.commit()
    flash("Saved to your library! 📚", "success")
    return redirect(url_for("view_set", set_id=copy.id))


# ---------------------------------------------------------------------------
# 🏆 Leaderboard — friendly competition = retention
# ---------------------------------------------------------------------------

@app.route("/leaderboard")
def leaderboard():
    top = User.query.order_by(User.xp.desc(), User.streak.desc()).limit(20).all()
    your_rank = None
    if current_user.is_authenticated:
        higher = User.query.filter(User.xp > current_user.xp).count()
        your_rank = higher + 1
    return render_template(
        "leaderboard.html",
        top=top,
        your_rank=your_rank,
        total_users=User.query.count(),
        total_sets=StudySet.query.count(),
    )


# ---------------------------------------------------------------------------
# 📊 Quiz scores — save best results & reward XP
# ---------------------------------------------------------------------------

@app.route("/api/quiz-score", methods=["POST"])
def quiz_score():
    if not current_user.is_authenticated:
        return jsonify(error="Log in to save your score."), 401
    payload = request.get_json(silent=True) or {}
    set_id = int(payload.get("set_id", 0))
    total = int(payload.get("total", 0))
    correct = max(0, int(payload.get("correct", 0)))
    s = StudySet.query.filter_by(id=set_id, user_id=current_user.id).first()
    if not s or s.kind != "quiz" or total <= 0:
        return jsonify(error="Invalid quiz result."), 400

    correct = min(correct, total)
    pct = round(correct / total * 100)
    new_best = s.best_score is None or pct > s.best_score
    if new_best:
        s.best_score = pct
    xp_earned = correct * XP_QUIZ_PER_CORRECT
    record_activity(current_user, xp_earned)
    db.session.commit()
    return jsonify(
        xp_earned=xp_earned,
        total_xp=current_user.xp,
        streak=current_user.streak,
        best_score=s.best_score,
        new_best=new_best,
    )


# ---------------------------------------------------------------------------
# 📥 Export flashcards to CSV (importable into Anki / Quizlet)
# ---------------------------------------------------------------------------

@app.route("/set/<int:set_id>/export.csv")
@login_required
def export_csv(set_id: int):
    s = get_owned_set(set_id)
    if s.kind != "flashcards":
        abort(404)
    buf = io.StringIO()
    writer = csv.writer(buf)
    for card in json.loads(s.content).get("flashcards", []):
        writer.writerow([card.get("front", ""), card.get("back", "")])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{slugify(s.title)}.csv"'},
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not (3 <= len(username) <= 30) or not username.replace("_", "").isalnum():
            flash("Username must be 3–30 characters (letters, numbers, underscores).", "error")
        elif "@" not in email or "." not in email:
            flash("Please enter a valid email address.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            flash("That username or email is already taken.", "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            record_activity(user, 0)  # day 1 of the streak starts now!
            db.session.add(user)
            db.session.commit()

            # 🎁 Welcome deck: instant value the second you land. Never block
            # registration if generation hiccups.
            try:
                content = generate_study_material("flashcards", WELCOME_NOTES)
                db.session.add(StudySet(
                    user_id=user.id,
                    title="👋 How StudySpark works",
                    kind="flashcards",
                    content=json.dumps(content),
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

            login_user(user)
            flash(f"Welcome to StudySpark, {username}! ⚡ We made you a starter deck — check it out.", "success")
            return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.username}! 👋", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out. See you soon! 👋", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# ⚙️ Settings — change password & delete account (trust = signups)
# ---------------------------------------------------------------------------

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current") or ""
    new = request.form.get("new") or ""
    confirm = request.form.get("confirm") or ""
    if not current_user.check_password(current):
        flash("Your current password is wrong.", "error")
    elif len(new) < 6:
        flash("New password must be at least 6 characters.", "error")
    elif new != confirm:
        flash("New passwords do not match.", "error")
    else:
        current_user.set_password(new)
        db.session.commit()
        flash("Password updated! 🔒", "success")
    return redirect(url_for("settings"))


@app.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password") or ""
    if not current_user.check_password(password):
        flash("Wrong password — account NOT deleted.", "error")
        return redirect(url_for("settings"))
    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)  # cascades wipe sets, generations & card memory
    db.session.commit()
    flash("Your account and all its data were deleted. We'll miss you! 👋", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Money pages 💸
# ---------------------------------------------------------------------------

@app.route("/pricing")
def pricing():
    return render_template("pricing.html", remaining=remaining_today())


@app.route("/waitlist", methods=["POST"])
def join_waitlist():
    """Collect emails of people interested in Pro = future customers."""
    email = (request.form.get("email") or "").strip().lower()
    if "@" not in email or "." not in email:
        flash("Please enter a valid email address.", "error")
    elif Waitlist.query.filter_by(email=email).first():
        flash("You're already on the list! 🎉", "success")
    else:
        db.session.add(Waitlist(email=email))
        db.session.commit()
        flash("You're on the Pro waitlist! We'll email you when Pro launches. 🚀", "success")
    return redirect(url_for("pricing"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


# ---------------------------------------------------------------------------
# Admin CLI — grant Pro to a user (real payments come later, see README)
# ---------------------------------------------------------------------------

@app.cli.command("make-pro")
@click.argument("username")
def make_pro(username: str):
    """Grant Pro to a user:  flask make-pro some_username"""
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f"No user named '{username}'.")
        return
    user.is_pro = True
    db.session.commit()
    click.echo(f"⚡ {username} is now Pro!")


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    # host 0.0.0.0 makes it reachable from outside this machine (needed for the preview)
    app.run(host="0.0.0.0", port=3000, debug=True)
