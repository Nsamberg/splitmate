# splitmate — design

A minimal shared-expense tracker for the Harvard Business Group (8 members): record group/partial-group expenses, see a balance recap, and record reimbursement transfers (settlements).

## Decisions so far

- **Stack**: FastAPI (Python) + HTMX + Jinja2 templates, server-rendered. No JS build step.
- **Storage**: SQLite, file on a Docker volume. Fine for 8 users / low volume; can migrate to Postgres later if needed.
- **Auth**: single shared access code to enter the site, then "pick your name" from the seeded member list. Session via a signed, `HttpOnly`, `Secure`, `SameSite=Lax` cookie. No passwords.
- **Members (seeded at init)**: Ade, Sandro, Vidhya, Mohammed, Atsushi, Huseyin, Sam, Niko.
  - **Niko is admin, with full admin rights**: can edit/delete *anyone's* expenses/settlements (not just their own), add/remove/rename members, and regenerate the shared access code.
- **Edit/delete permissions**: a non-admin member can edit or delete only the expenses/settlements *they* created (attributed by session). Niko (admin) can edit/delete anyone's.
- **Soft-delete**: deleting an expense or settlement marks it `deleted` (with who/when) rather than removing the row. Deleted entries are excluded from balance calculations and from the normal list views, but stay queryable for an audit trail. Nothing is hard-deleted in v1.
- **Splitting**: every expense defaults to an equal split across the whole group, but the creator can select a subset of members to split it with instead (e.g. only 3 people at a lunch) — still split equally among whoever is selected. No unequal/custom-weight shares in v1.
- **v1 scope**: expenses (amount, free-text description, payer, date, participant subset for split), recap (net balance per member + suggested settling-up transfers), settlements (from/to member, amount, date, optional note). No categories, no multi-currency, no email notifications.
- **Expense date**: defaults to today, editable to backdate a late-entered receipt.
- **Deployment**: Hetzner server, `splitmate.samberger.fr`. The server already hosts other websites fronted by **nginx** (confirmed) — splitmate does not run its own reverse proxy or touch ports 80/443 directly; it ships as its own app container on an internal-only port, and we add a new nginx server block + certbot cert for `splitmate.samberger.fr` alongside the existing sites (see "Deployment plan").
- **Repo**: https://github.com/Nsamberg/splitmate, this branch (`claude/hbg-expense-tracker-design-dy847a`).

## Data model

- **Member**: `id, name`
- **Expense**: `id, description, amount, paid_by (member_id), date, created_by (member_id), created_at`
- **ExpenseParticipant**: `expense_id, member_id, share_amount` — the subset of members this expense is split across (equal split for v1; defaults to the whole group but a subset can be picked, e.g. only 3 people at a lunch)
- **Settlement**: `id, from_member, to_member, amount, date, note, created_by (member_id)`

## Balance logic

For each member:

```
balance = Σ(amount they paid on expenses)
        − Σ(their share owed across expenses they participated in)
        + Σ(settlements received)
        − Σ(settlements paid)
```

- Positive balance → the group owes them. Negative → they owe the group.
- **Recap page** shows each member's current balance, plus a suggested list of transfers (greedy match: largest debtor pays largest creditor, repeat) to zero everyone out in the fewest transfers.
- Settlements are recorded between two specific members, so partial reimbursements between any pair net out correctly — not just "pay into a pot."

## App structure (planned)

```
splitmate/
  app/
    main.py            # FastAPI app, routes
    models.py          # SQLAlchemy/SQLModel models
    db.py              # SQLite engine/session
    auth.py            # access-code check + "pick your name" session cookie
    balances.py        # balance + settlement-suggestion calculations
    templates/         # Jinja2 + HTMX partials
      login.html
      dashboard.html   # add expense form + recent expenses
      recap.html       # balances + suggested transfers
      settle.html      # record a transfer
    static/
  tests/
  Dockerfile
  docker-compose.yml
  deploy/
    nginx-splitmate.samberger.fr.conf   # nginx server block for this site, copied onto the server
  README.md
```

## Deployment plan (finalized: nginx is the existing reverse proxy)

- `docker-compose.yml` runs just the `app` service (uvicorn/FastAPI), bound only to localhost on an internal port not used by anything else, e.g. `127.0.0.1:8090:8000`. No Caddy, no port 80/443 in the compose file — nginx already owns those.
- SQLite file on a named Docker volume so it survives container rebuilds/redeploys.
- `.env` (not committed) holds `ACCESS_CODE` and `SESSION_SECRET`.
- A new nginx server block is added alongside the existing sites' configs (e.g. `/etc/nginx/sites-available/splitmate.samberger.fr`, symlinked into `sites-enabled`), proxying `splitmate.samberger.fr` → `127.0.0.1:8090`:
  ```nginx
  server {
      listen 80;
      server_name splitmate.samberger.fr;

      location / {
          proxy_pass http://127.0.0.1:8090;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
      }
  }
  ```
- TLS via `certbot --nginx -d splitmate.samberger.fr` (same tool likely already used for the other sites) — issues the cert and rewrites the block to redirect 80→443 automatically.
- `docker compose up -d --build` on the box to (re)deploy; `nginx -t && systemctl reload nginx` after any config change.
- Daily cron copies the SQLite file to a backup location.

## Remaining open item

- Confirm the internal port (`8090` above is just a placeholder) doesn't collide with anything else already running — worth a quick `sudo ss -tlnp | grep 8090` before first deploy.
- Anything else you want to change in the model, permissions, or deployment plan above before you give the go-ahead to build?
