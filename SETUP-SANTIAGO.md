# Ana Lead Tracker — Setup for Santiago

The app and database are already set up. You just need to run it on your computer so you get the full experience (including AI-generated call scripts from your Claude Max subscription).

---

## What you need before starting

- A Mac
- Your Claude Max account (already have it)
- ~10 minutes

---

## Step 1: Install Claude Code

Open Terminal (press Cmd + Space, type "Terminal", hit Enter) and run:

```bash
npm install -g @anthropic-ai/claude-code
```

If you get a "npm not found" error, install Node.js first from https://nodejs.org (download the LTS version, install it, then retry the command above).

After installing, log in:

```bash
claude login
```

Follow the prompts to sign in with your Claude Max account.

---

## Step 2: Install Python

Check if you have Python:

```bash
python3 --version
```

If you see `Python 3.11` or higher, you're good. If not, install it from https://www.python.org/downloads/ (download the latest version, run the installer).

---

## Step 3: Get the code

```bash
cd ~/Desktop
git clone https://github.com/jzinspire/ana-lead-tracker.git
cd ana-lead-tracker
```

---

## Step 4: Set up the environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 5: Add the credentials

```bash
cp .env.example .env
```

Now open the `.env` file and fill in these values:

```
SUPABASE_URL=https://trthktwtwaoowytaweay.supabase.co
SUPABASE_KEY=ask Josue for this key
APIFY_API_TOKEN=ask Josue for this key
APP_PASSWORD=ask Josue for this password
```

Ask Josue for the `SUPABASE_KEY`, `APIFY_API_TOKEN`, and `APP_PASSWORD` — those are credentials we share between the two of us but don't put in the public repo. He'll send them via Slack/text.

**About the APP_PASSWORD:** It's a simple gate to prevent random people who find our Streamlit Cloud URL from seeing our leads. You enter it once when you open the app each session.

**About the Apify token:** It's our scraping account for Google Maps data. We share one token between both of us. Each "Run Deep Research" uses a tiny amount of our shared $5/month free tier. If you ever hit the limit, just tell Josue and we'll figure it out.

---

## Step 6: Run the app

```bash
streamlit run app.py
```

Your browser will open to `http://localhost:8501` with the full Ana Lead Tracker.

---

## Every time after the first time

Open Terminal and run:

```bash
cd ~/Desktop/ana-lead-tracker
source venv/bin/activate
streamlit run app.py
```

That's it — 3 commands.

---

## How it works with Josue

- You both share the same database. Every lead, call note, status change, and objection encounter syncs instantly.
- If Josue closes a prospect, it shows as "Closed Won" on your end immediately — you won't call them again.
- The Daily Cockpit builds a fresh call list for you each day based on what's current.
- When you use "Generate Script", it uses YOUR Claude Max subscription on YOUR computer. No extra cost.

---

## Quick reference

| What | How |
|------|-----|
| Start the app | `cd ~/Desktop/ana-lead-tracker && source venv/bin/activate && streamlit run app.py` |
| Stop the app | Press Ctrl + C in Terminal |
| Update to latest version | `cd ~/Desktop/ana-lead-tracker && git pull && source venv/bin/activate && pip install -r requirements.txt` |
| Problems? | Ask Josue or check the error message in Terminal |

---

## If something doesn't work

**"ModuleNotFoundError: No module named 'beautifulsoup4'" (or similar)**
You forgot to install dependencies after a `git pull`. Run:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**"Missing SUPABASE_URL or SUPABASE_KEY"**
Your `.env` file is missing or empty. Ask Josue for the values.

**"Claude CLI not on PATH"**
You need to install Claude Code (Step 1) and log in with `claude login`.

**App opens but pages are blank**
The Supabase database might be paused (free tier sleeps after inactivity). Ask Josue to check the Supabase dashboard.
