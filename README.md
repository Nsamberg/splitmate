# splitmate

A minimal shared-expense tracker for an 8-person group: record what was spent
for the group (or part of it), see a balance recap, and record reimbursement
transfers between members.

See [`DESIGN.md`](./DESIGN.md) for the full design decisions and data model,
and [`deploy/DEPLOY.md`](./deploy/DEPLOY.md) for deploying to the Hetzner
server behind its existing nginx.

## Features

- **Add an expense**: amount, description, who paid, and who it's split with
  (defaults to everyone, but you can narrow it to a subset — split equally
  among whoever's selected).
- **Recap**: each member's current balance, plus a suggested minimal set of
  transfers to settle everyone up.
- **Settle up**: record a transfer between two members (full or partial
  reimbursement).
- **Admin** (Niko): add/rename/deactivate members, and regenerate the shared
  access code.
- Everything soft-deletes (kept for an audit trail, excluded from balances);
  only the creator of an entry (or the admin) can edit/delete it.

## Local development

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env   # edit ACCESS_CODE / SESSION_SECRET for local testing

uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000, enter the access code from `.env`, and pick a
member. On first run the app seeds the 8 members (Ade, Sandro, Vidhya,
Mohammed, Atsushi, Huseyin, Sam, Niko — Niko as admin) and the access code
from `ACCESS_CODE`, into a local SQLite file at `data/splitmate.db`.

## Tests

```bash
python -m pytest
```

Covers the money-handling helpers (cent-based parsing/formatting, equal-split
rounding) and the balance/settlement-suggestion logic.

## Tech stack

FastAPI + Jinja2 templates (server-rendered, minimal JS), SQLite via SQLModel,
a shared access-code + pick-your-name login (no passwords), all packaged as
one Docker container. See `DESIGN.md` for the reasoning.

## Deployment

See [`deploy/DEPLOY.md`](./deploy/DEPLOY.md).
