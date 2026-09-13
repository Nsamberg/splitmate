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
- **Deployment**: Hetzner server, `splitmate.samberger.fr`. **The server already hosts other websites, so deployment must slot in alongside them rather than assume splitmate owns ports 80/443** — exact approach (join an existing reverse proxy vs. run alongside on an internal port) is pending confirmation of what's currently fronting those other sites. See "Open questions" below.
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
  Caddyfile
  README.md
```

## Deployment plan

Two candidate approaches, to be finalized once we know what fronts the server's other sites (see "Open questions"):

- **A — existing reverse proxy present** (Caddy/Nginx/Traefik/nginx-proxy-manager, as a system service or container): splitmate ships as its own `app` container (uvicorn/FastAPI) on an internal-only port, with a site/vhost block added to the *existing* proxy for `splitmate.samberger.fr` — no new Caddy/Nginx of our own, no port 80/443 contention.
- **B — no shared proxy, each site on its own host port**: splitmate's `app` container binds to a free host port (e.g. `127.0.0.1:8090:8000`), and either we add a lightweight Caddy just for splitmate (on a free port range, or taking 80/443 if genuinely free) or DNS/manual port-forwarding points `splitmate.samberger.fr` at that port.

Common to both:
- `docker-compose.yml` for the `app` service; SQLite file on a named volume so it survives redeploys.
- `.env` holds `ACCESS_CODE` and `SESSION_SECRET` (not committed).
- Daily cron copies the SQLite file to a backup location.

## Open questions for this design pass

1. **What's currently fronting the other websites on the Hetzner server** (reverse proxy already running vs. per-site ports, per approach A/B above)? Check with:
   ```bash
   sudo ss -tlnp | grep -E ':80|:443'
   sudo systemctl status nginx caddy traefik apache2 2>&1 | grep -E "Active|Unit"
   docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
   ```
2. Anything else you want to change in the model, permissions, or deployment plan above before you give the go-ahead to build?
