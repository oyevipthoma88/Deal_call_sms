# Safe Telegram Test Console

An admin-restricted Telegram bot for **local dry-run simulations**. The original repository contained SMS/call/WhatsApp bombing code and third-party dispatch endpoints. Those components have been removed. This version validates a test number and runs a bounded simulation; **it never sends calls, SMS, WhatsApp messages, OTPs, or network requests to the supplied number**.

## Features
- `/start` interactive menu: **Start safe dry-run**, **Stop / cancel**, **Help**
- `/help`, `/status`, `/stop` commands
- Number input in international format and simulation count (default cap: 20)
- Per-user authorization via `ALLOWED_USERS`; safe denial when no IDs configured
- Async progress updates, cancellation, and no storage of the full phone number

## Run locally
1. Create a Telegram bot with [@BotFather](https://t.me/BotFather).
2. Set environment variables (never commit the token):
   ```sh
   export BOT_TOKEN='...'
   export ALLOWED_USERS='123456789'
   python -m pip install -r requirements.txt
   python bot.py
   ```
`ALLOWED_USERS` is a comma-separated allowlist of numeric Telegram user IDs. An empty list denies all users. `MAX_SIMULATIONS` defaults to 20.

## Heroku one-click deploy
Use the Heroku button below, then set `BOT_TOKEN` and `ALLOWED_USERS` in the app's Config Vars if Heroku does not collect them during provisioning. Scale the `worker` process to 1. This is a Telegram polling worker and does not need a web dyno.

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/oyevipthoma88/Deal_call_sms)

Heroku deploy buttons deploy the repository's default branch. For a fork or private deployment, use Heroku Dashboard → **New app → Deploy** and configure the same environment variables.

## Safety
Do not use this project to target real people or contact numbers. This code has no telecom provider integration by design. The entered number is only validated and masked in the interaction; no message is sent. For legitimate messaging, use a provider's documented opt-in APIs and its compliance controls in a separate, reviewed application.
