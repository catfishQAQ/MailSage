# MailSage Installation Guide

## Requirements

| Tool | Minimum Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build tooling |
| Ollama | Latest | Local AI runtime |

---

## Startup Modes

MailSage now supports two startup modes:

- Development mode: start the backend and frontend separately, then visit `http://localhost:5173`
- One-click mode: use the launcher and visit `http://127.0.0.1:8000`

Use development mode when you are actively changing the frontend. Use one-click mode for normal daily usage.

---

## Step 1: Install Ollama and Download a Model

### 1.1 Install Ollama

Download the installer for your operating system from [https://ollama.com/download](https://ollama.com/download) and complete the installation.

After installation, Ollama usually runs in the background and listens on `http://localhost:11434` by default.

### 1.2 Download the `qwen3:4b` model

Run this command in your terminal:

```bash
ollama pull qwen3:4b
```

> The model is about 2.6 GB. Download time depends on your network speed. You can verify it with `ollama list` after the download finishes.

---

## Step 2: Install the Backend

> Run the following commands from the project root, the directory that contains both `backend/` and `frontend/`.

### 2.1 Enter the backend directory

```bash
cd backend
```

### 2.2 Create and activate a virtual environment

**Windows**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

> Once activated, your terminal prompt should include `(.venv)`.

### 2.3 Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2.4 Start the backend server

```bash
uvicorn main:app --reload --port 8000
```

If startup succeeds, you should see output similar to:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     AI queue worker started
INFO:     Scheduler started (every 2 hours)
```

**Verify:** open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to check the API docs.

---

## Step 3: Install the Frontend

Open another terminal window and keep the backend running.

### 3.1 Enter the frontend directory

```bash
cd frontend
```

### 3.2 Install Node.js dependencies

```bash
npm install
```

### 3.3 Start the frontend development server

```bash
npm run dev
```

If startup succeeds, you should see output similar to:

```text
VITE v6.x.x  ready in xxx ms
➜  Local:   http://localhost:5173/
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Step 4: First-Time Setup

### 4.1 Add an email account

Open [http://localhost:5173](http://localhost:5173), then click the **+ Add Account** button at the bottom of the left sidebar.

Fill in the following fields:

| Field | Description |
|---|---|
| Email address | Your full email address, for example `your@163.com` |
| Display name | Optional, used only in the UI |
| Authorization code / app password | **Not your login password**. Generate it in your mailbox security settings |
| IMAP server / port | Auto-filled for common providers after you finish entering the email address |
| SMTP server / port | Auto-filled the same way |

After clicking **Add**, MailSage will start the first sync automatically and fetch the latest 200 emails.

> **Built-in presets:** 163, 126, yeah.net, QQ, Foxmail, Gmail, Outlook, Hotmail, Live

#### How to get an app password

**QQ Mail**
1. Open QQ Mail on the web, then go to Settings -> Accounts.
2. Find the mail services section for POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV.
3. Enable IMAP/SMTP and complete the SMS verification if required.
4. Generate and copy the authorization code.

**163 Mail**
1. Open 163 Mail, then go to Settings -> POP3/SMTP/IMAP.
2. Enable IMAP/SMTP and create an authorization password.

**Gmail**
1. Enable 2-Step Verification in your Google account security settings.
2. Search for "App Passwords" and create a 16-character password for MailSage.

### 4.2 Set your persona

Click **Settings / Persona** in the lower-left area of the app and fill in your profile information:

- **Role:** for example, `Computer vision researcher`
- **Focus:** for example, `Adversarial attacks on autonomous driving models, VAE architecture debugging`
- **Tone preference:** for example, `Professional, objective, direct`

These fields are used as AI context so summaries and reply drafts better match your real workflow.

### 4.3 Run AI batch processing

Make sure Ollama is running, then click **Batch process unread emails** in the **AI Console** section of the left sidebar.

- 🟢 means Ollama is running and ready
- 🟡 means the queue is currently processing
- ⚪️ means Ollama is not running yet

After processing finishes, important emails will show a ⚡ marker in the list. Open an email to view the AI summary card and ghost reply suggestions.

---

## Common Commands

```bash
# Start Ollama if it is not already running
ollama serve

# Start the backend from backend/
uvicorn main:app --reload --port 8000

# Start the frontend from frontend/
npm run dev

# One-click launch from the project root
python scripts/start_mailsage.py
```

## One-Click Launch

From the project root:

**Windows**
```bat
MailSage.bat
```

**macOS / Linux**
```bash
chmod +x start-mailsage.sh
./start-mailsage.sh
```

The launcher will:

1. Build the frontend if needed
2. Start the backend in frontend-serving mode
3. Open `http://127.0.0.1:8000` automatically

If you are developing UI changes and want hot reload, keep using `npm run dev` and open `http://localhost:5173` instead.

To stop the one-click mode backend later:

**Windows**
```bat
Stop-MailSage.bat
```

**macOS / Linux**
```bash
chmod +x stop-mailsage.sh
./stop-mailsage.sh
```

---

## Troubleshooting

**Q: The frontend shows "Ollama is not running"**
- Run `ollama list` in a terminal to check whether Ollama is available
- If Ollama is not running, start it with `ollama serve`

**Q: Email sync failed**
- Make sure IMAP is enabled in your mailbox settings
- Make sure you entered an app password or authorization code, not the normal login password
- QQ Mail may require a newly generated authorization code after some time

**Q: AI processing keeps ending in `failed`**
- Confirm that `qwen3:4b` has been downloaded with `ollama list`
- Check the backend terminal logs for the actual error
- Make sure your machine has enough available RAM / VRAM

**Q: The one-click launcher starts but the page does not open**
- Open `http://127.0.0.1:8000` manually in your browser
- Check `backend/mailsage-backend.log` for startup errors

**Q: Port 8000 is already in use**
- Stop the other process using port 8000, then try again
- If MailSage is already running, the launcher should reuse the existing instance

**Q: `pip install` fails**
- Check that your Python version is 3.11 or newer with `python --version`
- Try upgrading pip with `pip install --upgrade pip`

**Q: The backend reports a database error on first start**
- Delete `backend/omnimail.db` and start the backend again so the database can be recreated automatically
