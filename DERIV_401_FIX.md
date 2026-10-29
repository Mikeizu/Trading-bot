# Deriv HTTP 401 troubleshooting — MIKEIZU TradeLab PRO v4.1

### What was checked
The Get My Deriv Accounts button sends POST to the private localhost app, which makes GET `https://api.derivws.com/trading/v1/options/accounts`, with `Authorization: Bearer <PAT>` and `Deriv-App-ID: <APP_ID>`. Both required headers were already present in v4. A Deriv HTTP 401 means its REST API rejected authentication; the original app sometimes displayed only `HTTP 401` due to an unstructured response. v4.1 provides an actionable error and account setup checklist without printing credentials.

### Reconnect
1. In https://developers.deriv.com, sign in to your developer account.
2. Register a NEW application and choose authentication type **PAT**. Existing legacy Deriv App IDs and OAuth-type App IDs are not suitable for the app's PAT flow.
3. Under API tokens, create a fresh **Personal Access Token** with the `trade` scope for Options account discovery. Never select withdrawal/payment permissions for this purpose.
4. Copy the new PAT and its corresponding App ID carefully. Make sure they are from the correct dashboard. Do not use your normal Deriv password, MT5 password, an OAuth secret, or a short-lived OTP.
5. Run `START_WINDOWS.bat`, browse to `http://127.0.0.1:8765`, open Deriv Broker, paste the new App ID and PAT, then press **Find my Deriv accounts**.
6. Select a DEMO Options account. If you only have an MT5 account, use a separate MT5 connector, not the Options API.

If the response changes to 403, the token may lack the necessary scope or account access. If 401 persists with new matching credentials, check Deriv's developer dashboard, revoke old unused tokens, and contact Deriv support with only the time and generic error code (no secrets).

### Reference
- https://developers.deriv.com/docs/intro/authentication/
- https://developers.deriv.com/docs/options/get-accounts/
- https://developers.deriv.com/docs/workflows/

This patch does not turn on unattended real-money orders; live execution remains locked by default.
