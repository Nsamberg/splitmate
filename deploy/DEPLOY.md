# Deploying splitmate on the Hetzner server

The server already runs other sites behind **nginx**. splitmate does not touch
ports 80/443 — it runs as its own Docker container on an internal port, and
we add one more nginx server block alongside the existing sites.

## 1. Get the code onto the server

```bash
git clone https://github.com/Nsamberg/splitmate.git
cd splitmate
git checkout claude/hbg-expense-tracker-design-dy847a   # or main, once merged
```

## 2. Create the .env file

```bash
cp .env.example .env
```

Edit `.env` and set:

- `ACCESS_CODE` — the shared code the 8 members use to log in (this seeds the
  DB on first run only; after that, change it from the in-app Admin page).
- `SESSION_SECRET` — a long random string. Generate one with:
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

**Never commit `.env`** — it's gitignored.

## 3. Check the internal port is free

`docker-compose.yml` binds the app to `127.0.0.1:8090`. Confirm nothing else
on the box is already using it:

```bash
sudo ss -tlnp | grep 8090
```

If it's taken, pick a different port and update it in both
`docker-compose.yml` (the `ports:` line) and
`deploy/nginx-splitmate.samberger.fr.conf` (the `proxy_pass` line).

## 4. Start the app

```bash
docker compose up -d --build
curl -s http://127.0.0.1:8090/healthz   # should print {"status":"ok"}
```

This creates the SQLite database on first run and seeds the 8 members
(Ade, Sandro, Vidhya, Mohammed, Atsushi, Huseyin, Sam, Niko — Niko as admin)
plus the access code from `.env`.

## 5. Add the nginx site

```bash
sudo cp deploy/nginx-splitmate.samberger.fr.conf /etc/nginx/sites-available/splitmate.samberger.fr
sudo ln -s /etc/nginx/sites-available/splitmate.samberger.fr /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 6. Get a TLS certificate

```bash
sudo certbot --nginx -d splitmate.samberger.fr
```

certbot rewrites the site's nginx config to listen on 443 and redirect
80 -> 443. Point `splitmate.samberger.fr`'s DNS A/AAAA record at the server
first if you haven't already.

## 7. Verify

Visit `https://splitmate.samberger.fr`, enter the access code, and pick your
name from the list.

## Redeploying after a code change

```bash
git pull
docker compose up -d --build
```

The SQLite file lives on the `splitmate_data` Docker volume, so it survives
rebuilds/redeploys.

## Backups

Add a daily cron job to copy the SQLite file out of the volume, e.g.:

```bash
# /etc/cron.d/splitmate-backup
0 3 * * * root docker run --rm -v splitmate_splitmate_data:/data -v /root/backups:/backup alpine cp /data/splitmate.db /backup/splitmate-$(date +%F).db
```

(Adjust the volume name if `docker compose` prefixed it differently — check
with `docker volume ls`.)
