# MIKEIZU v4.3 — Deriv duration rejection fix

**Problem:** Deriv reports “Trading is not offered for this duration.” Your account can be connected but a chosen asset / Rise-Fall contract / expiry may be unavailable. This does not mean your App ID or PAT is invalid.

## Changes

- The app requests `contracts_for` for your chosen asset using the official authenticated Deriv WebSocket.
- It reads the CALL/PUT offers and `min_contract_duration` / `max_contract_duration` bounds and lists available 1–15-minute expiries for each direction separately.
- It rejects unsupported durations BEFORE requesting a price proposal; there is **no automatic adjustment of duration, symbol, or direction**.
- The demo indicator bot validates both UP and DOWN 1-minute availability before starting. Strategy automation validates UP and DOWN at the configured expiry before starting, and still validates availability at each subsequent quote.
- It translates a duration-specific broker proposal rejection into a clear no-order message. Contract metadata does not guarantee a live quotation.
- All live automated trades remain prohibited; manual live orders remain locked by default.

## Use

1. Fully close the older app, then unzip v4.3 to a new folder and run `START_WINDOWS.bat`.
2. Open `http://127.0.0.1:8765` and press Ctrl+Shift+R to reload the new frontend.
3. Sign in via **Deriv Broker**, select your Deriv Options **demo** account, and choose an asset.
4. Press **Check supported expiries**. Choose a duration shown for your desired UP/CALL or DOWN/PUT direction.
5. Request a quote. If the quote succeeds, verify details and manually confirm a demo purchase.
6. For automation, confirm both directions and the intended expiry are allowed. The bot must not silently change the duration tested in the strategy research.

If no 1–15-minute CALL/PUT contracts are offered, switch to another account-accessible asset or use monitor/paper mode. For durations exceeding 15 minutes, a separate strategy/broker product implementation is required; do not assume minutes, hours, days, and weeks are interchangeable.

## Safety and compatibility

- No Deriv credentials are stored by this app's broker connector; keep your PAT private.
- This package is a **source-based Windows application**, not a compiled installer.
- Actual availability varies by account, instrument, regulation, market hours, and contract type; synthetic and CSV results do not authorize broker trades.
- Supported expiry list is obtained from metadata. The authenticated broker's proposal response remains authoritative; an advertised duration might not be purchasable at the time of quotation.
- A rejected quote never buys or reserves an order.
- Real Deriv connection and orders cannot be verified without your account; tests are local/mocked.

Reference: https://developers.deriv.com/docs/data/contracts-for/ and https://developers.deriv.com/comparison/contracts-for/
