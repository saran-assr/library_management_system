from services import reservation_service, loan_service, book_service
from database import query_db


def test_cannot_reserve_available_book(app):
    """Test that a member cannot place a reservation when copies are on the shelf."""
    with app.app_context():
        # Clean Code (book_id=1) has available copies in conftest
        res_id, err = reservation_service.create_reservation(book_id=1, user_id=2)
        assert res_id is None
        assert "currently available" in err.lower()


def test_fifo_reservation_and_fulfillment_on_return(app):
    """
    Test end-to-end FIFO queue:
    1. Borrow all copies of book 2 (1984 only has ACC-1984-01).
    2. Member 1 reserves 1984 -> Queue position 1.
    3. Member 2 reserves 1984 -> Queue position 2.
    4. Reject duplicate reservation by Member 1.
    5. Return 1984 -> copy automatically placed on hold for Member 1!
    """
    with app.app_context():
        # Borrow the only copy of 1984
        loan_service.issue_book("ACC-1984-01", user_id=1, issued_by_id=1)

        # Member 1 (id=2) reserves
        r1, err1 = reservation_service.create_reservation(book_id=2, user_id=2)
        assert err1 is None
        assert r1 is not None

        # Member 2 (id=3) reserves
        r2, err2 = reservation_service.create_reservation(book_id=2, user_id=3)
        assert err2 is None
        assert r2 is not None

        # Verify FIFO queue positions
        res1 = query_db("SELECT queue_position, status FROM reservations WHERE id = ?", (r1,), one=True)
        res2 = query_db("SELECT queue_position, status FROM reservations WHERE id = ?", (r2,), one=True)
        assert res1["queue_position"] == 1
        assert res2["queue_position"] == 2

        # Verify duplicate prevention
        _, err_dup = reservation_service.create_reservation(book_id=2, user_id=2)
        assert "already have an active reservation" in err_dup.lower()

        # Admin returns the copy
        ret_res, ret_err = loan_service.return_book("ACC-1984-01", returned_by_id=1)
        assert ret_err is None
        assert ret_res["reserved_for_next"] is True

        # Verify copy is reserved and assigned to Member 1
        copy = book_service.get_copy_by_accession_id("ACC-1984-01")
        assert copy["status"] == "reserved"

        res1_after = query_db("SELECT * FROM reservations WHERE id = ?", (r1,), one=True)
        assert res1_after["status"] == "available_for_pickup"
        assert res1_after["assigned_copy_id"] == copy["id"]
        assert res1_after["hold_until"] is not None


def test_cancel_reservation(app):
    """Test cancelling an active reservation."""
    with app.app_context():
        # Check out 1984 copy
        loan_service.issue_book("ACC-1984-01", user_id=1, issued_by_id=1)
        r_id, _ = reservation_service.create_reservation(book_id=2, user_id=2)

        ok, err = reservation_service.cancel_reservation(r_id, user_id=2)
        assert ok is True
        assert err is None

        res = query_db("SELECT status FROM reservations WHERE id = ?", (r_id,), one=True)
        assert res["status"] == "cancelled"
