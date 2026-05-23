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
```

(Ask Josue to send you the SUPABASE_KEY — it's not a secret between us, just shouldn't be in this file.)

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
| Update to latest version | `cd ~/Desktop/ana-lead-tracker && git pull` |
| Problems? | Ask Josue or check the error message in Terminal |
