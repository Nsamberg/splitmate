# splitmate — design

A minimal shared-expense tracker for the Harvard Business Group (8 members): record group/partial-group expenses, see a balance recap, and record reimbursement transfers (settlements).

## Decisions so far

- **Stack**: FastAPI (Python) + HTMX + Jinja2 templates, server-rendered. No JS build step.
- **Storage**: SQLite, file on a Docker volume. Fine for 8 users / low volume; can migrate to Postgres later if needed.
- **Auth**: single shared access code to enter the site, then "pick your name" from the seeded member list. Session via a signed, `HttpOnly`, `Secure`, `SameSite=Lax` cookie. No passwords.
- **Members (seeded at init)**: Ade, Sandro, Vidhya, Mohammed, Atsushi, Huseyin, Sam, Niko.
  - **Niko is admin.** *(Open question below — what admin means in v1.)*
- **Edit/delete permissions**: a member can edit or delete only the expenses/settlements *they* created (attributed by session, not open to everyone).
- **v1 scope**: expenses (amount, free-text description, payer, date, participant subset for split), recap (net balance per member + suggested settling-up transfers), settlements (from/to member, amount, date, optional note). No categories, no multi-currency, no email notifications.
- **Deployment**: Hetzner server, Docker Compose — `app` (uvicorn/FastAPI) + `caddy` (reverse proxy, automatic HTTPS via Let's Encrypt) on `splitmate.samberger.fr`.
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

- `docker-compose.yml`: `app` + `caddy`, SQLite file on a named volume so it survives redeploys.
- `.env` holds `ACCESS_CODE` and `SESSION_SECRET` (not committed).
- Caddy handles automatic Let's Encrypt HTTPS for `splitmate.samberger.fr`.
- `docker compose up -d` on the Hetzner box. Daily cron copies the SQLite file to a backup location.

## Open questions for this design pass

1. **What does "Niko is admin" mean concretely?** e.g.:
   - Can edit/delete *anyone's* expenses/settlements (not just their own)?
   - Can add/remove/rename members?
   - Can regenerate the access code?
   - All of the above / something else?
2. **Equal split only, or per-expense custom shares later?** v1 assumes equal split among selected participants — confirm that's enough for now.
3. **Should a deleted expense/settlement be hard-deleted, or soft-deleted (kept for history but excluded from balances)?** Soft-delete gives you an audit trail if a number ever looks wrong.
4. **Date field**: default to "today" with an optional override (for entering a receipt a few days late), correct?
5. Anything else you want to change in the model, permissions, or deployment plan above before I start building?
