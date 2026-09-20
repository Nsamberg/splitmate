from collections import defaultdict

from sqlmodel import Session, select

from .models import Expense, ExpenseParticipant, Member, Settlement


def compute_balances(db: Session) -> dict[int, int]:
    """Net balance per member, in cents. Positive = the group owes them."""
    balances: dict[int, int] = defaultdict(int)

    members = db.exec(select(Member)).all()
    for m in members:
        balances[m.id] = 0

    expenses = db.exec(select(Expense).where(Expense.deleted_at.is_(None))).all()
    for expense in expenses:
        balances[expense.paid_by_id] += expense.amount_cents
        shares = db.exec(
            select(ExpenseParticipant).where(ExpenseParticipant.expense_id == expense.id)
        ).all()
        for share in shares:
            balances[share.member_id] -= share.share_cents

    settlements = db.exec(select(Settlement).where(Settlement.deleted_at.is_(None))).all()
    for s in settlements:
        # from_member paid to_member: this discharges what from_member owed
        # (their balance moves toward/above zero) and reduces what the group
        # still owes to_member (their balance moves toward/below zero).
        balances[s.from_member_id] += s.amount_cents
        balances[s.to_member_id] -= s.amount_cents

    return dict(balances)


def member_ledger(db: Session, member_id: int) -> list[dict]:
    """Itemized entries behind a member's balance: every expense they paid or
    had a share in, and every settlement they sent or received. Each entry's
    `cents` is signed the same way as compute_balances (positive = increases
    what the group owes them) — this is the "why" behind a recap balance or
    suggested transfer."""
    entries: list[dict] = []

    paid_expenses = db.exec(
        select(Expense).where(Expense.deleted_at.is_(None), Expense.paid_by_id == member_id)
    ).all()
    for e in paid_expenses:
        entries.append(
            {
                "date": e.expense_date,
                "description": f'Paid for "{e.description}"',
                "cents": e.amount_cents,
            }
        )

    shares = db.exec(select(ExpenseParticipant).where(ExpenseParticipant.member_id == member_id)).all()
    for share in shares:
        expense = db.get(Expense, share.expense_id)
        if not expense or expense.deleted_at is not None:
            continue
        entries.append(
            {
                "date": expense.expense_date,
                "description": f'Your share of "{expense.description}"',
                "cents": -share.share_cents,
            }
        )

    sent = db.exec(
        select(Settlement).where(
            Settlement.deleted_at.is_(None), Settlement.from_member_id == member_id
        )
    ).all()
    for s in sent:
        to_member = db.get(Member, s.to_member_id)
        label = f"You paid {to_member.name if to_member else 'someone'}"
        if s.note:
            label += f" ({s.note})"
        entries.append({"date": s.settlement_date, "description": label, "cents": s.amount_cents})

    received = db.exec(
        select(Settlement).where(Settlement.deleted_at.is_(None), Settlement.to_member_id == member_id)
    ).all()
    for s in received:
        from_member = db.get(Member, s.from_member_id)
        label = f"{from_member.name if from_member else 'Someone'} paid you"
        if s.note:
            label += f" ({s.note})"
        entries.append({"date": s.settlement_date, "description": label, "cents": -s.amount_cents})

    entries.sort(key=lambda entry: entry["date"], reverse=True)
    return entries


def suggest_settlements(balances: dict[int, int]) -> list[tuple[int, int, int]]:
    """Minimal set of (from_member_id, to_member_id, cents) transfers that would
    zero everyone out, via a greedy largest-debtor-pays-largest-creditor match."""
    debtors = [[member_id, -amount] for member_id, amount in balances.items() if amount < 0]
    creditors = [[member_id, amount] for member_id, amount in balances.items() if amount > 0]
    debtors.sort(key=lambda x: -x[1])
    creditors.sort(key=lambda x: -x[1])

    suggestions: list[tuple[int, int, int]] = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, owed = debtors[i]
        creditor_id, due = creditors[j]
        pay = min(owed, due)
        if pay > 0:
            suggestions.append((debtor_id, creditor_id, pay))
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return suggestions
