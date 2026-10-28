# DigitalServices VPN Store

Self-hosted Flask VPN sales application with Docker Compose, configurable 3x-ui servers, admin-managed payment approvals, and a renewal scheduler.

> **Pre-production implementation.** This repository has not passed live 3x-ui integration, full Docker deployment, or external security testing. Do not process real customer payments until you complete these tests and the security checklist below.

## Plans

| Plan | Traffic | Devices | Price |
| --- | --- | --- | --- |
| 1 Month | 100 GB | 1 | 5,000 MMK |
| 3 Months | 350 GB | 2 | 15,000 MMK |
| 6 Months | 700 GB | 3 | 30,000 MMK |

## Install on Ubuntu 24.04

Docker Engine and the Compose plugin must be installed first.

```bash
git clone https://github.com/AungKhantPaing5/Digitalservices.git && cd Digitalservices && bash install.sh
```

On the **first run**, `install.sh` creates `.env` with a random `SECRET_KEY` and exits. Set your admin email, long unique password, local payment details, and Telegram bot credentials:

```bash
nano .env
bash install.sh
docker compose ps
curl -fsS http://127.0.0.1:8095/health
```

This is a private localhost port, `127.0.0.1:8095`. The web container listens on `8000` within Docker.

## HTTPS without taking the VLESS port 443

Use **https://digitalservices.payapi.uk** (a real DNS hostname), not the single-label URL `https://digitalservices`. Create a **Cloudflare Tunnel** with public hostname `digitalservices.payapi.uk`, HTTP service address `http://web:8000` (in the cloudflared Docker container's network). Put the Tunnel token in `.env` as `TUNNEL_TOKEN` and run `bash install.sh` again. Existing VLESS 443 stays unchanged.

## Admin workflow

1. Log in using `ADMIN_EMAIL` and `ADMIN_PASSWORD`. These credentials seed the initial admin user only.
2. Add each 3x-ui server using its HTTPS panel URL, API Bearer token, inbound ID, VPN hostname, and REALITY settings as needed. Database schema does not impose a fixed server count.
3. Import existing 3x-ui clients by server using JSON exports. The importer stores **metadata only**, not VPN passwords or shared secret material.
4. Customers register, choose a package, specify New/Existing, select server, and upload payment proof.
5. Verify screenshot **against the actual bank account** and independently verify ownership of existing usernames before approving orders. Username alone is not proof of ownership.
6. For early renewals, expiry is extended immediately from the existing expiry; the new quota and device allowance take effect after the original period expires. For expired accounts, renewals attempt to update immediately. Both require live 3x-ui validation first.

## Important limitations / do not skip

- **Not production verified.** Test your specific 3x-ui version, Bearer API endpoints, credentials, and transport configuration before any actual approvals.
- **Security review required:** add verified email ownership, login throttling, secure admin account recovery, CSRF/security testing, abuse prevention, and comprehensive audit/backup monitoring.
- **Existing customer ownership:** admin must independently verify the person, even if the username is unique. The current UI does not implement a dedicated identity-verification workflow.
- **IP / device limits:** 3x-ui's `limitIp` does not guarantee single-device enforcement across all versions; test enforcement.
- **Scheduled renewals:** if a 3x-ui API call succeeds but the following update fails, order moves to manual review; inspect live state, never blind-retry.
- **Customer keys:** imported exports do not necessarily contain enough data to reconstruct original connection links.
- **Cloudflare Tunnel:** DNS and tunnel must be configured separately, and host `443` is not changed.
- Back up `data/` and your separately stored `.env` securely. Run only one scheduler.
- Never commit real `.env`, exported client JSON, payment proofs, user databases, API tokens or VPN credentials.

## Subscription URLs and Telegram approvals

Each server must have its own **HTTPS Subscription Base URL** (for example, `https://subscription.example.com/sub`), configured in the Admin server card. This must point to a live 3x-ui subscription service. New customers see **only** a subscription link, not a raw VLESS URL. Existing imported customers continue to use their original subscription links until verified and reconciled.

New orders require usernames (3–64 letters/digits/period/underscore/hyphen). Whitespace is removed both in the browser and server-side.

Payment screenshot is delivered through Telegram `sendPhoto`. Telegram action buttons are enabled only when a webhook is registered and both the Telegram sender user ID and chat ID match configured administrator values. A 2-click confirmation is used; **new orders only** may be approved directly in Telegram. Existing-account renewals still require independent ownership verification in web Admin.

Add these to `.env`:

```dotenv
PUBLIC_URL=https://digitalservices.payapi.uk
TELEGRAM_ADMIN_USER_ID=YOUR_PRIVATE_TELEGRAM_NUMERIC_USER_ID
TELEGRAM_WEBHOOK_SECRET=GENERATE_A_RANDOM_32_CHARACTER_SECRET
```

The Bot Token / Chat ID must already be configured. Generate a secret with `python3 -c 'import secrets;print(secrets.token_urlsafe(32))'`, keep it private, and add it to `.env`. Recreate the web service, then register the webhook:

```bash
docker compose up -d --build web scheduler
docker compose exec -T web python scripts/setup_telegram_webhook.py
```

Never use example subscription URLs or payment proof images for real sales. Verify every real payment independently in KPay/Wave/AYA before approving.

## Telegram VPN-server speed tests

The bot supports admin-only `/speedtest`, `/speedtest api1`, `/speedtest apitwo`, `/speedtest api3` (also `/servers`). These return the **latest saved measurements collected on each corresponding VPN VPS**, with the Myanmar-local timestamp and age. The command does not launch an on-demand remote test.

**Install the opt-in agent separately on each VPN VPS.** This uses `speedtest-cli --json --secure`; run sparingly as tests consume bandwidth and may be affected by test-server congestion. It tests the VPS connection, **not** a Myanmar client's route through the VPN. It cannot conclusively detect ISP throttling. Comparing repeated speed/ping results from a client-side probe and a control network is still necessary.

On the DigitalServices **web host**:
1. Generate `SPEED_AGENT_SECRET`: `python3 -c 'import secrets;print(secrets.token_urlsafe(36))'` and add it to `.env`.
2. Restart web: `docker compose up -d --force-recreate web`.
3. Rerun `docker compose exec -T web python scripts/setup_telegram_webhook.py` so the bot receives messages and approval callbacks.
4. Get the server IDs from the Admin server database or `docker compose exec -T web python -c 'from app import conn; c=conn();print([(x["id"],x["name"]) for x in c.execute("SELECT id,name FROM servers")])'`.

On **each** separate VPN VPS, securely copy `scripts/vpn_server_speed_agent.py` from the private repo, and install `speedtest-cli` (Ubuntu: `sudo apt install speedtest-cli`).
Set `DS_MONITOR_URL=https://digitalservices.payapi.uk`, `DS_SERVER_ID=<the database ID for this particular VPN server>`, and `DS_SPEED_SECRET=<same generated secret>` as private process environment values. Run `python3 vpn_server_speed_agent.py` to test. For recurring monitoring schedule it via a protected root-owned systemd timer or cron job, e.g. every six hours, *after* ensuring credentials remain out of shell history, public process arguments, logs and Git.

The reporting API requires HTTPS and the long shared secret and retains only 100 latest measurements per server. If the secret is leaked, rotate it centrally and update all agents. A separate agent secret per server is a future hardening improvement.

No automatic network-wide throttling claim is made from single-run speed results.

## Server configuration edit and encrypted backup

Admin dashboard now supports editing every configured 3x-ui connection (including new API token, inbound, REALITY parameters, hostname, subscription URL, and Active/Disabled). Disabling a server stops **new** automatic assignment. Editing these fields changes the central application pointer, **not** the actual 3x-ui inbound/client setup or customer VPN subscriptions.

Use **Download Encrypted Server Backup** and **Restore Server Settings** to preserve/restore the configured server registry. Encryption uses a password of at least 12 characters with scrypt-derived Fernet; the backup includes sensitive decrypted 3x-ui API tokens *inside the encrypted archive*. Keep both backup and password secure and separate. Restore is an atomic upsert keyed by original server database IDs, protecting customer foreign keys, but it **does not** remove extra servers and does not migrate clients between 3x-ui installations. Take a full backup before restore.

### Full application data backup (separate from server-settings export)
In `~/Digitalservices` on host `q`, back up the `.env` file (including its SECRET_KEY), `data/app.sqlite3`, its WAL if any, payment proof directory, and any other files under `data/`. The safest simple complete backup requires a short maintenance window:

```bash
cd ~/Digitalservices
docker compose stop web scheduler
sudo tar --numeric-owner -czf "/root/digitalservices-full-$(date +%Y%m%d-%H%M%S).tar.gz" .env data
docker compose start web scheduler
```

The tarball contains **payment receipts, password hashes, customer details and credential secrets**. Restrict it to root, encrypt it before moving off-host and never upload it to public repositories or group chats. To restore, stop web/scheduler, back up the current files first, restore the saved `.env` and `data/` from the archive using a secure offline procedure, then restart the services and verify site health. Do **not** casually restore stale snapshots: recent orders and client links could diverge from 3x-ui. Always reconcile 3x-ui actual state.

Changing provider or endpoint during throttling: a new empty 3x-ui server is **not** an automatic replacement for an old server. Subscription client IDs, REALITY and existing links must be migrated/maintained explicitly. Disabling the old server for new sales is safer than overwriting its settings until migration is validated.

## api3 hosting: server edit, password reset, full encrypted backup/restore

The DigitalServices application may run on the same VPS as api3 3x-ui. They are distinct installations: app configuration backup does **not** back up 3x-ui clients, certificates, or Xray configuration. Before migration back up both installations independently.

**Admin panel**
- Edit Server Configuration: change URL, inbound, token (optional), host, REALITY settings, subscription URL; disable server for new orders without deleting client references.
- Encrypted Server Configuration Backup / Restore: only application server-connection registry, not database/orders/customers.
- Customer Password Reset: select customer by email and set a new 12–128 character password; saved as a salted password hash and reset action logged. Does not change VPN keys. Arrange private delivery to customer.

**Complete site backup (host CLI, encrypted):** first put the site into a maintenance window and stop web/scheduler so SQLite and filesystem snapshots agree. Execute from the DigitalServices directory:
```bash
cd ~/Digitalservices
docker compose stop web scheduler
python3 -m pip show cryptography >/dev/null || echo 'Install python3-cryptography for the HOST Python environment'
python3 scripts/full_backup.py backup "/root/digitalservices-$(date +%Y%m%d-%H%M).enc"
docker compose start web scheduler
```
This encrypted backup includes `.env`, `data/app.sqlite3`, payment images and chat history. Store backup password separately. Never put the backup in public GitHub. Store an off-site copy after encrypting.

**Restore:** back up existing state first, then **stop** web and scheduler:
```bash
cd ~/Digitalservices
docker compose stop web scheduler
python3 scripts/full_backup.py restore /root/path-to-backup.enc
docker compose start web scheduler
```
The script validates the archive and requires the operator to type RESTORE. It overwrites application files; restore is not safe while web/scheduler are running. Verify customer orders and 3x-ui client state afterward. The current restore process runs on the host, not through browser upload, to avoid mutating the live SQLite database.

For Ubuntu, if host Python lacks cryptography: `sudo apt install python3-cryptography`. Ensure system disk has room for a complete backup.

**Do not mistake a server connection edit for VPN client migration.** Existing customers must be migrated or the existing subscription endpoint and client IDs retained. A disabled server can still have old customers.
