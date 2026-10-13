from services import loan_service, book_service, fine_service
from database import execute_db


def test_issue_and_return_book(app):
    """Test standard checkout and checkin cycle."""
    with app.app_context():
        # Issue ACC-CC-01 to Member 1 (id=2)
        loan_id, err = loan_service.issue_book(
            accession_id="ACC-CC-01",
            user_id=2,
            issued_by_id=1,
            duration_days=14,
        )
        assert err is None
        assert loan_id is not None

        # Verify copy status updated to 'borrowed'
        copy = book_service.get_copy_by_accession_id("ACC-CC-01")
        assert copy["status"] == "borrowed"

        # Verify active loans list
        active = loan_service.get_active_loans(user_id=2)
        assert len(active) == 1
        assert active[0]["accession_id"] == "ACC-CC-01"

        # Return book
        res, ret_err = loan_service.return_book("ACC-CC-01", returned_by_id=1)
        assert ret_err is None
        assert res["overdue_days"] == 0
        assert res["fine_amount"] == 0.0

        # Verify copy status restored to 'available'
        copy_after = book_service.get_copy_by_accession_id("ACC-CC-01")
        assert copy_after["status"] == "available"


def test_issue_already_borrowed_copy(app):
    """Test that issuing a currently borrowed copy is rejected."""
    with app.app_context():
        # Member 1 borrows ACC-CC-01
        loan_service.issue_book("ACC-CC-01", user_id=2, issued_by_id=1)

        # Member 2 attempts to borrow same copy
        _, err = loan_service.issue_book("ACC-CC-01", user_id=3, issued_by_id=1)
        assert err is not None
        assert "already checked out" in err.lower()


def test_max_loans_limit(app):
    """Test that a member cannot exceed their maximum borrowing quota."""
    with app.app_context():
        # Member 1 limit is 3. Conftest has 3 copies: ACC-CC-01, ACC-CC-02, ACC-1984-01
        l1, _ = loan_service.issue_book("ACC-CC-01", user_id=2, issued_by_id=1)
        l2, _ = loan_service.issue_book("ACC-CC-02", user_id=2, issued_by_id=1)
        l3, _ = loan_service.issue_book("ACC-1984-01", user_id=2, issued_by_id=1)
        assert l1 and l2 and l3

        # Add a 4th copy to try borrowing
        c4, _ = book_service.add_copy(book_id=1, accession_id="ACC-EXTRA-01")

        # 4th borrow attempt should be rejected
        _, err = loan_service.issue_book("ACC-EXTRA-01", user_id=2, issued_by_id=1)
        assert err is not None
        assert "maximum borrowing limit" in err.lower()


def test_block_issue_on_unpaid_fines_limit(app):
    """Test that borrowing is blocked when member exceeds the unpaid fine threshold."""
    with app.app_context():
        # Create an artificial overdue fine of $25 (limit is $20)
        # First create a dummy loan to satisfy FK
        loan_id, _ = loan_service.issue_book("ACC-CC-01", user_id=2, issued_by_id=1)
        execute_db(
            "INSERT INTO fines (loan_id, user_id, amount, status, calculated_days) VALUES (?, ?, 25.00, 'unpaid', 25)",
            (loan_id, 2),
        )

        # Attempt to borrow another book
        _, err = loan_service.issue_book("ACC-CC-02", user_id=2, issued_by_id=1)
        assert err is not None
        assert "unpaid fines" in err.lower()


def test_prevent_book_delete_with_active_loan(app):
    """Test that a book title cannot be deleted if any of its copies are currently borrowed."""
    with app.app_context():
        loan_service.issue_book("ACC-CC-01", user_id=2, issued_by_id=1)
        ok, err = book_service.delete_book(book_id=1)
        assert ok is False
        assert "currently borrowed" in err.lower()
