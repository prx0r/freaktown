# emails/ — Ella's inbox scanner

Zoho Mail API over OAuth (EU region). Tracks seen state so repeated scans
only surface **new** mail.

## Setup (one-time, done)

- `ella@freak.town` is an alias on `tom@egoic.ai` (single-license org —
  a separate mailbox needs a paid license).
- OAuth scopes required: `ZohoMail.folders.READ`, `ZohoMail.messages.READ`
  (+ org scopes for setup).
- Creds live in agent-vault (`ZOHO_CLIENT_ID/SECRET`) and
  `/root/.zohomail/store.json` (refresh token, rotation-safe: the scanner
  persists rotated refresh tokens back to the store).

## Use

```bash
python emails/scan.py            # new mail since last scan
python emails/scan.py --all      # latest 10 regardless
python emails/scan.py --show ID  # full content of one message
```

State: `emails/.state.json` (seen IDs, gitignored).

## Domain status (freak.town @ Zoho EU, org `egoic`)

- Domain added + CNAME-verified (`zmverify.zoho.com` target — note: the
  `.com` target in old docs fails here; EU needs no regional variant,
  just patience for resolver cache).
- Mail hosting enabled. MX + SPF + DKIM TXT all published via Cloudflare.
- DKIM verification pending DNS propagation at time of writing — re-run
  `verifyDkimPublicKey` if the admin panel still shows unverified.
