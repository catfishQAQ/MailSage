# MailSage

[English](README.md) | [简体中文](README.zh-CN.md)

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

## Installation

Installation steps are documented in [install.md](install.md).

## Language Switch on GitHub

GitHub only renders one repository homepage README automatically: `README.md`.

To provide multiple languages:

1. Keep `README.md` as the main landing page.
2. Create a second file such as `README.zh-CN.md`.
3. Add language links at the top of both files.

Example:

```md
[English](README.md) | [简体中文](README.zh-CN.md)
```

In the Chinese file:

```md
[English](README.md) | [简体中文](README.zh-CN.md)
```

When visitors click the language link on GitHub, it opens the corresponding README file in the repo.

## Notes

- MailSage is designed for local processing with Ollama so your email content does not need to be sent to a hosted LLM for summarization.
- If you add POP support later, you can update the README wording from "currently based on IMAP sync" to "supports IMAP and POP".
