# Deriv market-list connection fix — MIKEIZU TradeLab PRO v4.2

## What was wrong

MIKEIZU v4.1 correctly listed an authorized Deriv account using the official REST API, then fetched its balance over an OTP-authenticated WebSocket. At the next step, the application requested `{"active_symbols":"brief"}` and **parsed the obsolete `symbol`/`display_name` keys**. Deriv's current API returns `underlying_symbol`/`underlying_symbol_name`, so MIKEIZU wrongly filtered every response entry out, reported **"Deriv returned no available markets"**, and disconnected.

Deriv's official API comparison confirms the new response field names:
https://developers.deriv.com/comparison/active-symbols/

## Changes in v4.2

- Uses `underlying_symbol` and `underlying_symbol_name` from the current Deriv API.
- Accepts legacy keys for compatibility without preferring them over the new keys.
- Rejects unexpected or malformed market payloads with a specific error, rather than displaying a misleading empty-market message.
- Distinguishes a legitimately empty `active_symbols` list from an incompatible response. An authorized account remains **connected but unable to trade** if the broker really returns no active markets.
- Adds a **Refresh balance & markets** button that re-fetches symbols with the existing authenticated session, without a new token or login.
- Keeps the account mode restrictions, one-open-position protection, trade journal, and default-live-trading lock.

## Install on Windows 11

1. Exit the existing MIKEIZU application **and close its running command window**, so port 8765 is freed.
2. Extract the v4.2 ZIP to a **fresh directory** (do not double-click the ZIP contents without extracting).
3. To preserve trade history/settings from your old MIKEIZU installation, copy only your data files (`*.db` and any SQLite `-wal`/`-shm` companions) from the old app directory to the new one **after stopping the old app**, without overwriting the updated Python or JavaScript source files.
4. Double-click `START_WINDOWS.bat` in the extracted folder. Python 3.10–3.14 is supported. Internet access is required for the Deriv API and the initial Python dependency installation.
5. Open `http://127.0.0.1:8765` and perform a hard refresh (`Ctrl+Shift+R`) to avoid older browser scripts.
6. Open **Deriv Broker**. Enter your **existing valid PAT App ID and PAT**, click **Find my Deriv accounts**, choose the DEMO account, then **Connect selected account**.
7. The green/connected state should show a market selector containing symbols such as Volatility indices *only if Deriv actually returns them for your session*. Optionally click **Refresh balance & markets**.

**Never share PAT, WebSocket OTP URLs, broker passwords, or screenshots that expose them.** This application binds to localhost and is not designed to be exposed as an internet-facing web server.

## If you still see an error

- **Account lookup works but connect fails with WebSocket error:** this is a *different* issue. Check internet access and the OTP/account authorization. Report the exact sanitized on-screen error.
- **Connected, 0 active markets:** Deriv returned a genuinely empty `active_symbols` list. The app stays connected in read-only mode; choose an eligible Deriv Options account or retry when markets are available. No orders are permitted until symbols become available.
- **Unexpected market response format:** the Deriv API schema may have changed again; report the non-sensitive message. Do not fabricate symbol IDs or bypass order safeguards.
- **Still seeing “Deriv returned no available markets”:** an old v4.1 server is probably still running. Exit all older launcher windows and ensure you're using the extracted v4.2 folder. Hard refresh the page.
- **Uses Deriv MT5:** this connector is for **Deriv Options**, not the MT5 terminal. MT5 requires a different integration.

## What was tested

Regression tests use realistic, mocked new Deriv WebSocket responses, a simulated account, symbol catalogue refresh, empty-list trade block, error handling, and all existing unit tests. Tests **do not** authenticate to a real user account or submit trades. Demo broker verification on your machine remains required before relying on automatic trading.

Run locally: `python -m unittest discover -s tests -v`.
