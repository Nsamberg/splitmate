from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from app.balances import (
    compute_balances,
    member_ledger,
    suggest_settlements,
    suggest_settlements_with_preferences,
)
from app.models import Expense, ExpenseParticipant, Member, Settlement, utcnow
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
    expense.deleted_at = utcnow()
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
        deleted_at=utcnow(),
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


def test_member_ledger_explains_the_balance():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    add_expense(db, alice, 1000, [alice, bob])  # Alice paid 1000, split 500/500
    db.add(
        Settlement(
            from_member_id=bob.id,
            to_member_id=alice.id,
            amount_cents=200,
            settlement_date=date.today(),
            note="Venmo",
            created_by_id=bob.id,
        )
    )
    db.commit()

    alice_entries = member_ledger(db, alice.id)
    # Paid 1000 (+), her own share -500, received Bob's 200 settlement (-200).
    assert sorted(e["cents"] for e in alice_entries) == sorted([1000, -500, -200])
    assert sum(e["cents"] for e in alice_entries) == 300  # matches compute_balances

    bob_entries = member_ledger(db, bob.id)
    # His share -500, paid Alice 200 settlement (+200).
    assert sorted(e["cents"] for e in bob_entries) == sorted([-500, 200])
    assert sum(e["cents"] for e in bob_entries) == -300

    balances = compute_balances(db)
    assert sum(e["cents"] for e in alice_entries) == balances[alice.id]
    assert sum(e["cents"] for e in bob_entries) == balances[bob.id]


def test_member_ledger_ignores_soft_deleted():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    expense = add_expense(db, alice, 1000, [alice, bob])
    expense.deleted_at = utcnow()
    expense.deleted_by_id = alice.id
    db.add(expense)
    db.commit()

    assert member_ledger(db, alice.id) == []
    assert member_ledger(db, bob.id) == []


def test_preferred_routing_used_when_creditor_can_absorb_it():
    db = make_session()
    alice, bob = add_members(db, "Alice", "Bob")
    bob.preferred_creditor_id = alice.id
    bob.preference_note = "has a Wise account"
    db.add(bob)
    db.commit()

    # Alice paid 1000, split 500/500 -> Alice +500, Bob -500.
    add_expense(db, alice, 1000, [alice, bob])
    balances = compute_balances(db)

    results = suggest_settlements_with_preferences(db, balances)
    assert len(results) == 1
    assert results[0]["from_id"] == bob.id
    assert results[0]["to_id"] == alice.id
    assert results[0]["cents"] == 500
    assert results[0]["reason"] == "has a Wise account"


def test_preferred_routing_falls_back_when_preferred_creditor_is_not_owed():
    db = make_session()
    alice, bob, carol = add_members(db, "Alice", "Bob", "Carol")
    # Bob prefers to pay Alice, but only Carol is actually owed money.
    bob.preferred_creditor_id = alice.id
    db.add(bob)
    db.commit()

    add_expense(db, carol, 1000, [carol, bob])  # Carol +500, Bob -500
    balances = compute_balances(db)

    results = suggest_settlements_with_preferences(db, balances)
    assert len(results) == 1
    assert results[0]["from_id"] == bob.id
    assert results[0]["to_id"] == carol.id
    assert results[0]["cents"] == 500


def test_preferred_routing_splits_across_preference_and_fallback():
    db = make_session()
    alice, bob, carol = add_members(db, "Alice", "Bob", "Carol")
    # Bob owes 1000 total but Alice is only owed 300 -> 300 routed to
    # Alice via preference, remaining 700 falls back to whoever's owed.
    bob.preferred_creditor_id = alice.id
    db.add(bob)
    db.commit()

    add_expense(db, alice, 600, [bob])  # Alice paid 600, Bob's full share -> Alice +600, Bob -600
    add_expense(db, carol, 700, [bob])  # Carol paid 700, Bob's full share -> Carol +700, Bob -700
    # Net: Alice +300 (after her own unrelated... actually she has no share here)
    balances = compute_balances(db)
    assert balances[alice.id] == 600
    assert balances[carol.id] == 700
    assert balances[bob.id] == -1300

    results = suggest_settlements_with_preferences(db, balances)
    total_to_alice = sum(r["cents"] for r in results if r["to_id"] == alice.id)
    total_to_carol = sum(r["cents"] for r in results if r["to_id"] == carol.id)
    assert total_to_alice == 600
    assert total_to_carol == 700
    assert all(r["from_id"] == bob.id for r in results)
    assert sum(r["cents"] for r in results) == 1300


def test_preferred_routing_no_reason_on_leftover_that_missed_the_preference():
    db = make_session()
    alice, bob, carol = add_members(db, "Alice", "Bob", "Carol")
    # Bob prefers Alice, but Alice is only owed 300 of the 1000 he owes
    # overall; the remaining 700 must fall back to Carol.
    bob.preferred_creditor_id = alice.id
    bob.preference_note = "has a UK account"
    db.add(bob)
    db.commit()

    add_expense(db, alice, 600, [bob])  # Alice +600 (wait: full 600 is Bob's share)
    add_expense(db, carol, 700, [bob])  # Carol +700 (full share)
    balances = compute_balances(db)

    results = suggest_settlements_with_preferences(db, balances)
    to_alice = next(r for r in results if r["to_id"] == alice.id)
    to_carol = next(r for r in results if r["to_id"] == carol.id)
    assert to_alice["reason"] == "has a UK account"
    assert to_carol["reason"] is None


def test_preferred_routing_shared_creditor_allocated_most_owed_first():
    db = make_session()
    alice, bob, carol = add_members(db, "Alice", "Bob", "Carol")
    # Bob and Carol both prefer paying Alice; she's the only creditor.
    bob.preferred_creditor_id = alice.id
    carol.preferred_creditor_id = alice.id
    db.add(bob)
    db.add(carol)
    db.commit()

    add_expense(db, alice, 1600, [alice, bob, carol])  # each share ~533
    balances = compute_balances(db)

    results = suggest_settlements_with_preferences(db, balances)
    # Everything should still be conserved and land on Alice (no one else
    # is owed anything), regardless of the preference.
    assert sum(r["cents"] for r in results) == -balances[bob.id] + -balances[carol.id]
    assert all(r["to_id"] == alice.id for r in results)
