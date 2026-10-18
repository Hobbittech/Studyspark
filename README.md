# ⚡ StudySpark

**Turn your class notes into flashcards, quizzes, and summaries — in seconds.**

Built with Python (Flask) + HTML + CSS + a little JavaScript. No frameworks, no magic —
every line is readable and commented so you can learn exactly how a real product works.

---

## 🧰 What's inside

| Feature | Where it lives | Status |
|---|---|---|
| Landing page | `templates/index.html` | ✅ done |
| Accounts (sign up / log in, secure password hashing) | `app.py` + `models.py` | ✅ done |
| Dashboard + personal study library | `templates/dashboard.html` | ✅ done |
| AI generation: flashcards / quiz / summary | `ai.py` | ✅ done |
| Free plan with daily limits (5/day) + Pro flag | `app.py` | ✅ done |
| Pricing page + **Pro waitlist (collects customer emails!)** | `templates/pricing.html` | ✅ done |
| 🎯 **Study Mode** — one-card trainer, keyboard shortcuts, shuffle | `templates/study.html` + `app.js` | ✅ done |
| 🔗 **Share links** — public pages, no account needed (growth engine!) | `/s/<token>` route | ✅ done |
| 🔥 **XP + daily streaks** — gamified retention | `record_activity()` in `app.py` | ✅ done |
| 📄 **PDF / txt file upload** (textbook chapters!) | `extract_text_from_upload()` | ✅ done |
| 📊 Quiz best scores saved + XP rewards | `/api/quiz-score` route | ✅ done |
| 🌙 **Dark mode** (saved per visitor) | `style.css` + `app.js` | ✅ done |
| 📥 CSV export for Anki/Quizlet | `/set/<id>/export.csv` | ✅ done |
| 🔁 **Spaced repetition** — remembers cards you miss, builds "Review due" decks | `CardState` model + Study Mode | ✅ done |
| 🌍 **Explore page** — browse & clone community sets | `/explore` + `/clone/<token>` | ✅ done |
| 🏆 **Leaderboard** — top students by XP | `/leaderboard` | ✅ done |
| 🔊 **Text-to-speech** — cards read aloud (browser-native, free) | `app.js` `speak()` | ✅ done |
| 🎉 Confetti celebrations | `app.js` `fireConfetti()` | ✅ done |
| 🔎 Library search | dashboard + `app.js` | ✅ done |
| 🎁 Welcome deck for every new signup | `register` route | ✅ done |
| ⚙️ Settings — change password / delete account | `/settings` | ✅ done |
| 🖼️ Rich link previews (Open Graph) on shared sets | `public_set.html` | ✅ done |
| Privacy + Terms pages (real products need these) | `templates/` | ✅ done |
| Live preview in demo mode (works with **zero** API keys) | `ai.py` | ✅ done |
| Online payments (Stripe) | roadmap below | 🔜 v2 |
| Deploy to the real internet with your own domain | roadmap below | 🔜 v2 |

---

## 🚀 Step 1 — Run it on your computer

```bash
# 1. Go into the project folder
cd studyspark

# 2. Create a virtual environment (a private box for this project's libraries)
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install the libraries
pip install -r requirements.txt

# 4. Run the server
python app.py
```

Then open **http://localhost:3000** in your browser. 🎉

It already works in **demo mode** (offline AI) so you can test everything for free.

## 🔑 Step 2 — Connect a real AI (free, no credit card!)

1. Go to [console.groq.com/keys](https://console.groq.com/keys) and make a free account.
2. Create an API key and copy it.
3. Copy `.env.example` to a file named `.env` and paste your key:

```env
AI_PROVIDER=groq
GROQ_API_KEY=gsk_paste_your_key_here
SECRET_KEY=any-long-random-string
```

4. Restart the server (`Ctrl+C`, then `python app.py`).

The yellow demo banner disappears = you're running real AI. 🤖

> **Golden rule:** NEVER put your `.env` file on GitHub or share it. Keys = money.

## 🗂️ Step 3 — Understand your own code (10 minutes)

```
studyspark/
├── app.py            ← the brain: every page/route lives here
├── ai.py             ← the AI engine: prompts, providers, validation
├── models.py         ← the database: users, study sets, waitlist
├── templates/        ← every HTML page (Jinja2: {% %} injects Python data)
├── static/css/       ← the entire design, hand-written
├── static/js/        ← flashcard flips + quiz scoring (only ~100 lines!)
├── requirements.txt  ← the libraries this project needs
└── .env              ← your secret keys (never share!)
```

Read `app.py` top to bottom once — it's ~250 lines and it's the whole app.

---

## 📅 Your 12-week roadmap to a real product

### Phase 1 — Make it great (Weeks 1–4)
- [ ] Week 1: Run it locally, connect the Groq key, make 10 study sets from your real school notes. Find what sucks. Fix it.
- [ ] Week 2: Polish. Better titles on sets, "regenerate" button, maybe a dark mode. Show 3 friends and *watch* them use it (don't explain anything — confusion = a bug to fix).
- [ ] Week 3: Learn the `app.js` file and add one feature yourself (e.g. keyboard arrows to flip flashcards). **This is where you become a real full-stack dev.**
- [ ] Week 4: Add rate-limit safety + better error messages. Ask a teacher to try it.

### Phase 2 — Launch it (Weeks 5–8)
- [ ] Deploy: **Render.com** (free tier) — push your code to GitHub, connect Render, done. (Full guide: render.com/docs/deploy-flask)
- [ ] Production tweaks: switch to a production server (`pip install gunicorn`, run `gunicorn -w 2 -b 0.0.0.0:8000 app:app`), set a strong `SECRET_KEY`.
- [ ] Buy a domain (~$10/yr — studyspark.app? sparkstudy.io? check namecheap.com).
- [ ] Launch at school: demo to your class, put the link in your Discord/insta bio, make one fun TikTok/Short showing "I pasted my notes and THIS happened". Students trust student-built tools.
- [ ] Goal: **100 signups + 50 waitlist emails** for Pro.

### Phase 3 — Money 💸 (Weeks 9–12)
- [ ] **The important legal bit:** Stripe, the standard payment service, requires you to be **18**. The normal path for teen founders: a parent/guardian creates the Stripe account (it's their name, your business). Alternatives while you wait: Gumroad (parent account), Ko-fi, or just keep growing free users + waitlist — a big waitlist *is* money in the bank when you launch Pro.
- [ ] Wire the Pro button to Stripe Checkout (I'll help you code this part — it's ~40 lines).
- [ ] Email the waitlist: "Pro is live — founding members get 3 months free, then $4/mo."
- [ ] Do the math: 1,000 users → 3% go Pro → 30 × $4 = **$120/month**, growing. That's how indie apps start. 📈

---

## 🔒 Safety rules (important for young founders)

1. **Never** commit `.env` or API keys to GitHub (it's already in `.gitignore`).
2. **Never** share your database file — it contains user emails.
3. Don't put personal info (your real school, address) in the Privacy/Terms pages. Use a contact email.
4. Involve a parent/guardian for anything with money or accounts on payment platforms — it's the law, and also they're often happy to help.
5. Be skeptical of "business partners" DMing you. Real ones will happily talk to your parent too.

## 🧠 Level-up ideas (when you're ready for more)

- 🔁 Smarter intervals: grow the review gap the more times you know a card (3d → 7d → 14d) — 10 lines in `finish_study`
- 📧 Email the waitlist from your admin panel (starts with a simple `flask send-launch-email` command)
- 🌍 A second language (French? Dutch?) — most of your classmates could test it!
- 📚 "Collections": group several sets into one study pack for exam season
- ✏️ Edit individual flashcards after generation (fix AI slip-ups)

## ❓ Stuck?

1. Read the error in the terminal — the last line tells you the file and line number.
2. `Ctrl+F` the error message — it's usually a typo.
3. Ask me (your AI coding buddy) — show me the error and I'll fix it *with* you.

---

*Built by a 14-year-old who ships. Now go make it yours.* ⚡
