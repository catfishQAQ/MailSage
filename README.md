# MailSage

[English](README.md) | [简体中文](README.zh-CN.md)

This started as a spontaneous side project with no fancy tech stack or groundbreaking ideas. If your daily emails don't contain anything particularly sensitive, an agent tool like OpenClaw or Claude Code is probably a more convenient way to get email summaries. But if you'd rather keep certain emails off the cloud — and you have a decent PC — this project is for you.

MailSage is a privacy-first local email assistant. It uses a locally running LLM (via [Ollama](https://ollama.com/)) to summarize emails and assess their importance, supports multiple mailboxes in a single app, and keeps the entire AI pipeline on your own machine without sending any mail content to the cloud.

## Why MailSage

- Multi-mailbox workflow: connect and manage multiple email accounts in one app.
- Local AI with Ollama: summarize emails with a local model instead of a remote AI API.
- Privacy by design: email analysis stays on your machine, which helps reduce data exposure risk.
- Faster triage: surface summaries, action items, and reply drafts so you can process inboxes more efficiently.
- Practical setup: common email providers can be configured quickly with built-in server presets.

## Current Scope

- Multi-account email access, currently based on IMAP sync
- Local AI analysis and reply assistance powered by Ollama
- Bilingual interface support: English and Simplified Chinese

## TODO

- ✅ Overall architecture
- ✅ Email receiving and sync (original mailbox ↔ MailSage)
- ✅ Settings UI and prompt customization
- ✅ One-click launch
- ⬜ Reply sending & AI polish feature testing
- ⬜ ……

## Local Model Suggestions

Please choose and download different Ollama models based on your own machine's VRAM and system memory so the app can run smoothly on your hardware.

Examples:

- RTX 2060 6GB: `qwen3:4b-q4`
- RTX 3090 24GB: `qwen3.5:27b-q4`


According to others’ tests, Qwen3 and later models with a size of 4B or larger are capable of generating daily email summaries. However, I haven’t tested them myself. If you’d like, you can try smaller models to see whether they perform well and share your feedback with the community. That said, models larger than 4B seem to be a better overall choice.
## Installation

Installation steps are documented in [install.md](install.md).

## One-Click Launch

MailSage now supports a one-click launch flow for daily use.

- Development mode: keep using the existing frontend and backend workflow at `http://localhost:5173`
- One-click mode: double-click `MailSage.bat` on Windows or run `./start-mailsage.sh` on macOS / Linux, then open `http://127.0.0.1:8000`

The one-click launcher builds the frontend when needed, starts the backend in frontend-serving mode, and opens the app in your browser automatically.

To stop the one-click mode backend later, use `Stop-MailSage.bat` on Windows or `./stop-mailsage.sh` on macOS / Linux.

## ⚠️ Security Notice

This project has had a number of bugs fixed, but serious issues may still exist — including potential injection vulnerabilities. Please make sure to run it in a safe and trusted environment, and use it with caution.
