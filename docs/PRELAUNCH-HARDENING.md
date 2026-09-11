# Pre-launch hardening — freak.town edge (audited 2026-09-08, read-only)

Zone `freak.town` (`b79e62…`) is healthy: tunnel origin, proxied, valid cert,
mail (Zoho MX/SPF/2× DKIM) correct. Gaps below, ordered by risk/benefit.
Nothing here has been applied — each fix is one idempotent API call.

> **2026-09-09: P0 items 1–3 APPLIED + verified live** (301 redirect,
> HSTS + nosniff headers present, min TLS 1.2, `/api/health` ok).

## P0 — before accounts go live

1. **HTTP → HTTPS redirect** (`always_use_https` is `off`; `http://` serves 200).
   ```bash
   curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/b79e62aa91cee4c12ca23df3626c8bf7/settings/always_use_https" \
     -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
     -H 'Content-Type: application/json' -d '{"value":"on"}'
   ```
2. **HSTS** (currently fully disabled). After (1) is verified:
   ```bash
   curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/b79e62aa91cee4c12ca23df3626c8bf7/settings/security_header" \
     -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
     -H 'Content-Type: application/json' -d '{"value":{"strict_transport_security":{"enabled":true,"max_age":15552000,"include_subdomains":true,"preload":false,"nosniff":true}}}'
   ```
   Preload only after 6 months of stable HTTPS.
3. **Minimum TLS 1.2** (currently 1.0):
   ```bash
   curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/b79e62aa91cee4c12ca23df3626c8bf7/settings/min_tls_version" \
     -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
     -H 'Content-Type: application/json' -d '{"value":"1.2"}'
   ```

## P1 — soon after

4. **SSL mode `full` → `strict`** (origin cert validation; origin is a
   Cloudflare Tunnel so this should be safe — verify tunnel cert first).
5. **Security headers at origin** (`X-Frame-Options`/`CSP` can't come from
   these settings; add in Flask `app.py` after-action or a Worker):
   same-origin framing, `frame-ancestors 'self'`, minimal CSP for the
   single-file Black Room page.
6. **Backup/restore drill**: tunnel host DB (`freaks/`, `*.jsonl`) → R2 on a
   schedule; test a restore. (Code already mirrors shares to R2; scheduled
   full-state backup is the gap.)
7. **pog.town is not in this Cloudflare account** (7 zones, none is pog.town).
   `api/game.pog.town` can't work until that zone exists here or elsewhere
   with A/CNAME + proxied records pointing at the deploy host.

## Verify after each change

```bash
curl -s -o /dev/null -w "http: %{http_code} -> %{redirect_url}\n" http://freak.town/
curl -s -D - -o /dev/null https://freak.town/ | grep -iE "strict|x-content|location"
curl -s https://freak.town/api/health
```
