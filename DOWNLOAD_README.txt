MIKEIZU TRADELAB PRO - MULTI-STRATEGY RESEARCH TERMINAL

This download contains the editable application, local browser interface,
Windows/macOS/Linux launchers, documentation, tests, and the verified offline
WebSocket dependency wheel. It is not a signed Windows .exe or installer.

WINDOWS QUICK START
1. Install Python 3.10 or newer from https://www.python.org/downloads/ if needed.
   Enable the Python launcher or Add Python to PATH during installation.
2. Extract the entire ZIP into a private local folder. Do not run inside the ZIP.
3. Double-click START_WINDOWS.bat. Keep that terminal window open while using
   the app. The launcher creates .venv and uses the bundled dependency offline.
4. The browser should open automatically. If it does not, open the localhost
   address printed in the terminal (default port 8765) on the same computer.
5. Start with synthetic research in the technical-strategy library. Read each
   rule, warm-up and validation result. Real-money orders are disabled.

MACOS / LINUX
Install Python 3.10+ including venv support. From the extracted folder run:
    bash START_MAC_LINUX.sh
The launcher uses the bundled wheel when vendor/wheels is present.

STOPPING
Press Ctrl+C in the server terminal. Closing only the browser does not stop the
backend. The Stop trading control blocks new entries but does not close broker
contracts. Restarting the app does not erase persisted risk limits or journals.

BROKER CONNECTIONS
Synthetic research needs no broker account or network. Deriv monitoring/demo
requires an authorized account, matching PAT-type App ID and personal access
token, available contracts, working HTTPS/WebSocket connectivity, current data
and risk approval. Enter credentials only in the local Broker panel. Never put
them in chat, source files, reports or startup scripts. Real accounts are read-
only; MT5/CFD position execution is not implemented.

WHAT HAS AND HAS NOT BEEN VERIFIED
Read docs/CONTROL_AUDIT.md and docs/VALIDATION.md for the actual test
results and limitations accompanying this package. Passing mocked integrations
does not prove real broker compatibility, predictive accuracy or profitability. No application can
honestly promise perfect operation in every broker, market or system condition.

TROUBLESHOOTING
- Python not found: install Python and reopen the launcher. Do not rename a
  downloaded file to .exe; that does not create a Windows executable.
- Port already in use: close only another TradeLab instance you started, or run
  START_WINDOWS.bat --port 8766 (bash START_MAC_LINUX.sh --port 8766 on Unix).
- Startup failure: read the terminal message. The complete vendor/wheels folder
  and requirements.lock must remain alongside the launcher.
- Broker errors: use docs/OPERATIONS.md. Do not delete databases or relax limits
  to force a purchase after an unknown order outcome.
- Browser stale after upgrade: refresh the app; preserve existing private state
  and back up the consistent set of databases before upgrading.

INTEGRITY
SHA256SUMS.txt covers every package member except itself. RELEASE_INFO.json
records the source commit and dependency hashes. A separate ZIP.sha256 file
allows checking the download; local hashes are not a publisher digital signature.
From the extracted folder, you can verify a retained ZIP with:
    python packaging/build_bundle.py --verify-only PATH_TO_DOWNLOADED_ZIP
For an isolated fresh-install check (not an existing trading session):
    python packaging/verify_install.py PATH_TO_DOWNLOADED_ZIP
The latter creates temporary state, uses only synthetic local data, and tests
the launcher for the OS where it runs; it does not certify other operating systems.

UPGRADING
The previous book-pattern workspace has been removed from this app. Original
state files and historical records are preserved during the filename migration;
back up the complete database set before upgrading. Old records do not enable
removed strategies. See docs/RELEASE_NOTES.md and docs/OPERATIONS.md.

LICENSE
The application is MIT licensed; see LICENSE. The bundled websocket-client
wheel retains its Apache 2.0 license at its dist-info/licenses/LICENSE path;
the application's MIT license does not replace that dependency license.
See README.md and docs/ for source details and limitations.
