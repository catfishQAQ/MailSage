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

## Installation

Installation steps are documented in [install.md](install.md).
