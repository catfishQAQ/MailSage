# MailSage

[English](README.md) | [简体中文](README.zh-CN.md)

Summarize your emails with local AI, without sending inbox data to the cloud.

MailSage is a privacy-first local email assistant for people who want faster inbox triage without sending mail content to a cloud LLM.

It connects multiple mailboxes, syncs messages into one place, and uses [Ollama](https://ollama.com/) to run a local model that summarizes emails and helps draft replies on your own machine.

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
