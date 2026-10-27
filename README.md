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
