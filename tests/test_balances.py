from datetime import date, datetime

from sqlmodel import Session, SQLModel, create_engine

from app.balances import compute_balances, suggest_settlements
from app.models import Expense, ExpenseParticipant, Member, Settlement
from app.money import split_equally


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def add_members(db: Session, *names: str) -> list[Member]:
    members = [Member(name=n) for n in names]
    for m in members:
        db.add(m)
    db.commit()
    for m in members:
        db.refresh(m)
    return members


def add_expense(db: Session, paid_by: Member, amount_cents: int, participants: list[Member]) -> Expense:
    expense = Expense(
        description="test expense",
        amount_cents=amount_cents,
        paid_by_id=paid_by.id,
        expense_date=date.today(),
        created_by_id=paid_by.id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)

    shares = split_equally(amount_cents, len(participants))
    for participant, share in zip(participants, shares):
        db.add(ExpenseParticipant(expense_id=expense.id, member_id=participant.id, share_cents=share))
    db.commit()
    return expense


def test_compute_balances_simple_split():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    add_expense(db, alice, 1000, [alice, bob])

    balances = compute_balances(db)
    assert balances[alice.id] == 500
    assert balances[bob.id] == -500


def test_compute_balances_subset_split():
    db = make_session()
    alice, bob, carol = add_members(db, "Alice", "Bob", "Carol")
    # Alice pays 900 for lunch, split only between herself and Bob (not Carol).
    add_expense(db, alice, 900, [alice, bob])

    balances = compute_balances(db)
    assert balances[alice.id] == 450
    assert balances[bob.id] == -450
    assert balances[carol.id] == 0


def test_compute_balances_ignores_soft_deleted_expense():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    expense = add_expense(db, alice, 1000, [alice, bob])
    expense.deleted_at = datetime.utcnow()
    expense.deleted_by_id = alice.id
    db.add(expense)
    db.commit()

    balances = compute_balances(db)
    assert balances[alice.id] == 0
    assert balances[bob.id] == 0


def test_settlement_adjusts_balance():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    # With no prior expenses, Bob just handing Alice $5 means the group now
    # owes Bob $5 back, and Alice owes the group $5.
    db.add(
        Settlement(
            from_member_id=bob.id,
            to_member_id=alice.id,
            amount_cents=500,
            settlement_date=date.today(),
            created_by_id=bob.id,
        )
    )
    db.commit()

    balances = compute_balances(db)
    assert balances[bob.id] == 500
    assert balances[alice.id] == -500


def test_settlement_and_expense_together_can_zero_out():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    add_expense(db, alice, 1000, [alice, bob])  # Bob owes Alice 500
    db.add(
        Settlement(
            from_member_id=bob.id,
            to_member_id=alice.id,
            amount_cents=500,
            settlement_date=date.today(),
            created_by_id=bob.id,
        )
    )
    db.commit()

    balances = compute_balances(db)
    assert balances[alice.id] == 0
    assert balances[bob.id] == 0


def test_ignores_soft_deleted_settlement():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    settlement = Settlement(
        from_member_id=bob.id,
        to_member_id=alice.id,
        amount_cents=500,
        settlement_date=date.today(),
        created_by_id=bob.id,
        deleted_at=datetime.utcnow(),
        deleted_by_id=bob.id,
    )
    db.add(settlement)
    db.commit()

    balances = compute_balances(db)
    assert balances[alice.id] == 0
    assert balances[bob.id] == 0


def test_suggest_settlements_minimal_transfers():
    balances = {1: 500, 2: -300, 3: -200}
    suggestions = suggest_settlements(balances)
    assert sorted(suggestions) == sorted([(2, 1, 300), (3, 1, 200)])


def test_suggest_settlements_empty_when_balanced():
    balances = {1: 0, 2: 0}
    assert suggest_settlements(balances) == []
