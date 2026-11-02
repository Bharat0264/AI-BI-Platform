# Render deployment and cache recovery

## Temporary public demo (current setting)

At the owner's explicit request, login is paused. Render defaults AURA_PUBLIC_DEMO=true, so the existing service does not need to remove its older AURA_AUTH_REQUIRED=true variable to open the demo. The blueprint also sets AURA_AUTH_REQUIRED=false for clarity. The login dialog and sign-out controls stay hidden; a shared-workspace notice is displayed.

Anonymous requests use a dedicated public-demo database namespace, not the legacy shared cache or any existing private account's database. All visitors to the demo can read/change its uploaded sample data and settings. Existing private sessions are ignored in demo mode, but their data is preserved. The server-side file connector remains unavailable. Keep the existing AURA_SECRET_KEY, AURA_COOKIE_SECURE=true and MongoDB configuration: the key also signs stored dataset blobs even while login is disabled.

After the latest source is deployed, refresh the browser to open the demo directly. To restore accounts, set AURA_PUBLIC_DEMO=false and AURA_AUTH_REQUIRED=true, then redeploy. The authenticated-mode instructions below apply when restoring accounts.

## Failure diagnosed from the supplied log

The build successfully installed Python 3.12 packages and ran `python start.py`. The old launcher then listened on localhost. Render reported that it found only localhost ports and timed out because a public web service must bind to 0.0.0.0 on PORT. The previous source blueprint also used an offline release-check command instead of a server. Those two startup paths are corrected.

Separately, startup tried to restore an old shared GridFS pickle and pandas 2.3.3 raised NotImplementedError for StringDtype. That restore exception was caught, so the supplied log does not establish it as the port-timeout cause. The hosted profile now requires account mode, which skips the shared legacy cache entirely. Existing blobs are preserved. An incompatible signed account snapshot returns a 409 response asking for original-source re-import rather than deleting data or attempting an unsafe migration.

## Existing Render service: Settings

Set:

- Build Command: `python -m pip install -r requirements.txt`
- Start Command: `python start.py`
- Python version: 3.12.16 (.python-version is included in the repository)
- Health Check Path: `/api/health`

Do not use `python app/main.py`, a Streamlit command, the Flask development server, or `python scripts/release_check.py --target public` as the hosted Start Command.

## Existing Render service: Environment

Required settings:

| Variable | Value |
|---|---|
| AURA_AUTH_REQUIRED | true |
| AURA_COOKIE_SECURE | true |
| AURA_SECRET_KEY | A private, randomly generated secret of at least 32 characters; keep it stable across deploys |
| MONGODB_URI | Your existing secret-managed TLS MongoDB connection URI |
| MONGODB_DATABASE | Your existing account database base, using 1–24 letters/digits/underscores |

Render automatically supplies RENDER=true, PORT and RENDER_EXTERNAL_HOSTNAME. The launcher uses 0.0.0.0 and PORT even if an old HOST=127.0.0.1 setting remains. Do not disable authentication or secure cookies to bypass a startup error. A missing/invalid configuration now fails with its variable name instead of waiting for a localhost port scan.

For custom domains, add their bare hostnames to AURA_TRUSTED_HOSTS, comma-separated, without scheme/path/wildcards. The service's Render hostname and local health-check hostnames are allowed automatically. Waitress uses the known external HTTPS scheme because Render terminates TLS and forwards HTTP. It does not trust arbitrary forwarded headers. The native platform HTTPS redirect/TLS behavior is assumed only in the Render profile.

The blueprint generates AURA_SECRET_KEY only when it creates/manages that missing environment variable. An existing manually configured service must add missing variables in its Environment panel; merely pushing render.yaml does not apply all service settings. Do not rotate an existing key accidentally: rotation invalidates sessions and snapshot signatures and requires dataset re-import.

## Redeploy and first sign-in

After configuring the service, manually deploy the latest commit. Expected startup logs include `Starting AURA-BI on 0.0.0.0:<PORT>`. Health returns ready only if MongoDB is reachable. The browser displays the account sign-in screen. Accounts are explicitly provisioned by an operator; no default production password exists.

Run `python scripts/manage_user.py --username your-account-name` in a private operator environment configured with the same MONGODB_URI and MONGODB_DATABASE. Enter the password at the private prompt. This writes the auth/account databases and initializes indexes; the MongoDB credential must have the corresponding database permissions. Do not put passwords in source control, command arguments or chat. See ACCOUNT_SECURITY.md for disable/reset behavior.

Upload the original CSV/Excel/JSON after sign-in. Legacy shared uploads are not assigned automatically to any account and are not deleted by this fix.

## Verification and limits

Tests cover platform port/host selection, stale local HOST override, rejection of anonymous/insecure/missing-secret hosting, trusted hosts, real Waitress HTTP forwarding with HTTPS Origin and secure-session login, no legacy cache restore in account mode, and preserved incompatible snapshot recovery. MongoDB transport is mocked; these checks are not proof of a successful live deployment, actual database permissions or production scalability. The private operator must still verify deployed health, login, upload and storage/backup policy.

## Primary references

Render, Web Services — Port binding and TLS termination: https://render.com/docs/web-services#port-binding

Render, Default Environment Variables: https://render.com/docs/environment-variables

Render, Blueprint YAML Reference — secret generation and existing-service sync limitations: https://render.com/docs/blueprint-spec

Pylons Project, Waitress arguments — host, port and url_scheme: https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html

Documentation checked 2 November 2026.
