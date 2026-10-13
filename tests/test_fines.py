from datetime import date, timedelta
from services import fine_service, loan_service
from database import query_db, execute_db


def test_fine_amount_calculations():
    """Test fine rate calculation and maximum cap limit."""
    # 0 days late -> $0
    assert fine_service.calculate_fine_amount(0) == 0.0

    # 5 days late at $1.00/day -> $5.00
    assert fine_service.calculate_fine_amount(5) == 5.0

    # 100 days late -> capped at max fine ($50.00)
    assert fine_service.calculate_fine_amount(100) == 50.0


def test_overdue_days_calculation():
    """Test due date calculation logic."""
    today = date.today()
    due_past = (today - timedelta(days=7)).isoformat()
    due_future = (today + timedelta(days=7)).isoformat()

    assert fine_service.calculate_overdue_days(due_past) == 7
    assert fine_service.calculate_overdue_days(due_future) == 0

    # Reference return date earlier than today
    returned_earlier = (today - timedelta(days=3)).isoformat()
    # Loan was due 7 days ago, returned 3 days ago -> overdue days = 4
    assert fine_service.calculate_overdue_days(due_past, returned_earlier) == 4


def test_fine_assessment_idempotency(app):
    """Test that repeated assessments on an overdue loan do NOT create duplicate fines."""
    with app.app_context():
        # Issue book with due date in the past
        past_issue = (date.today() - timedelta(days=20)).isoformat()
        past_due = (date.today() - timedelta(days=6)).isoformat()

        res = execute_db(
            """
            INSERT INTO loans (copy_id, user_id, issued_by, issue_date, due_date, status)
            VALUES (1, 2, 1, ?, ?, 'overdue')
            """,
            (past_issue, past_due),
        )
        loan_id = res["lastrowid"]

        # First assessment
        days1, amt1, fine_id1 = fine_service.assess_fine_for_loan(loan_id, 2, past_due)
        assert days1 == 6
        assert amt1 == 6.0
        assert fine_id1 is not None

        # Second assessment (idempotent call)
        days2, amt2, fine_id2 = fine_service.assess_fine_for_loan(loan_id, 2, past_due)
        assert fine_id1 == fine_id2
        assert amt2 == 6.0

        # Verify only 1 row exists in fines table for this loan
        rows = query_db("SELECT * FROM fines WHERE loan_id = ?", (loan_id,))
        assert len(rows) == 1


def test_pay_and_waive_fines(app):
    """Test recording fine payment and administrative waiver."""
    with app.app_context():
        # Insert a dummy loan and fine
        res = execute_db(
            "INSERT INTO loans (copy_id, user_id, issued_by, issue_date, due_date, status) VALUES (1, 2, 1, '2026-01-01', '2026-01-15', 'returned')"
        )
        loan_id = res["lastrowid"]
        f_res = execute_db(
            "INSERT INTO fines (loan_id, user_id, amount, status, calculated_days) VALUES (?, 2, 10.00, 'unpaid', 10)",
            (loan_id,)
        )
        fine_id = f_res["lastrowid"]

        # Pay fine
        ok = fine_service.pay_fine(fine_id, admin_id=1, notes="Paid via cash receipt #890")
        assert ok is True

        fine = query_db("SELECT status, paid_at, notes FROM fines WHERE id = ?", (fine_id,), one=True)
        assert fine["status"] == "paid"
        assert fine["paid_at"] is not None

        # Test waiver on second fine
        res2 = execute_db(
            "INSERT INTO loans (copy_id, user_id, issued_by, issue_date, due_date, status) VALUES (2, 2, 1, '2026-01-01', '2026-01-15', 'returned')"
        )
        loan_id2 = res2["lastrowid"]
        f_res2 = execute_db(
            "INSERT INTO fines (loan_id, user_id, amount, status, calculated_days) VALUES (?, 2, 8.00, 'unpaid', 8)",
            (loan_id2,)
        )
        fine_id2 = f_res2["lastrowid"]

        ok_waive = fine_service.waive_fine(fine_id2, admin_id=1, notes="Waived by head librarian")
        assert ok_waive is True

        fine2 = query_db("SELECT status, notes FROM fines WHERE id = ?", (fine_id2,), one=True)
        assert fine2["status"] == "waived"
