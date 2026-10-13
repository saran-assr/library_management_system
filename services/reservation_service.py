from datetime import date, timedelta
from database import query_db, execute_db, transaction
from config import Config
from services import notification_service, audit_service


def create_reservation(book_id, user_id):
    """
    Place a reservation for a book when all copies are borrowed or unavailable.
    Maintains a strict FIFO queue.
    """
    # Verify book exists
    book = query_db("SELECT id, title FROM books WHERE id = ? AND is_deleted = 0", (book_id,), one=True)
    if not book:
        return None, "Book not found."

    # Verify if copies are available
    available_copy = query_db(
        "SELECT id FROM book_copies WHERE book_id = ? AND status = 'available' AND is_deleted = 0",
        (book_id,),
        one=True,
    )
    if available_copy:
        return None, "Copies of this book are currently available on the shelf. You can borrow one directly."

    # Prevent duplicate active reservations
    existing = query_db(
        """
        SELECT id, queue_position, status FROM reservations
        WHERE book_id = ? AND user_id = ? AND status IN ('waiting', 'available_for_pickup')
        """,
        (book_id, user_id),
        one=True,
    )
    if existing:
        return None, f"You already have an active reservation for this book (Status: {existing['status']})."

    # Calculate FIFO queue position
    pos_row = query_db(
        "SELECT COALESCE(MAX(queue_position), 0) + 1 AS next_pos FROM reservations WHERE book_id = ? AND status = 'waiting'",
        (book_id,),
        one=True,
    )
    next_pos = pos_row["next_pos"] if pos_row else 1

    res = execute_db(
        """
        INSERT INTO reservations (book_id, user_id, queue_position, status)
        VALUES (?, ?, ?, 'waiting')
        """,
        (book_id, user_id, next_pos),
    )
    res_id = res["lastrowid"]

    notification_service.send_notification(
        user_id=user_id,
        title="Reservation Confirmed",
        message=f"You have reserved '{book['title']}'. Your position in queue: #{next_pos}.",
        notif_type="success",
        link="/member/reservations",
    )

    return res_id, None


def fulfill_next_reservation_on_return(book_id, copy_id, conn=None):
    """
    When a copy is returned, check if there is an eligible waiting reservation.
    If yes, hold copy and notify next member. If none, mark copy as 'available'.
    Returns (fulfilled_user_id or None).
    """
    # Find top waiting reservation in FIFO order
    top_res = query_db(
        """
        SELECT r.id, r.user_id, r.book_id, b.title AS book_title
        FROM reservations r
        JOIN books b ON r.book_id = b.id
        WHERE r.book_id = ? AND r.status = 'waiting'
        ORDER BY r.queue_position ASC, r.reserved_at ASC
        LIMIT 1
        """,
        (book_id,),
        one=True,
        conn=conn,
    )

    if top_res:
        hold_date = (date.today() + timedelta(days=Config.RESERVATION_HOLD_DAYS)).isoformat()
        # Mark reservation as available_for_pickup and assign copy
        execute_db(
            """
            UPDATE reservations
            SET status = 'available_for_pickup',
                assigned_copy_id = ?,
                hold_until = ?,
                notified_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (copy_id, hold_date, top_res["id"]),
            conn=conn,
        )
        # Mark physical copy as reserved
        execute_db(
            "UPDATE book_copies SET status = 'reserved' WHERE id = ?",
            (copy_id,),
            conn=conn,
        )
        # Re-index remaining waiting queue positions
        _reindex_queue(book_id, conn=conn)

        # Notify waiting member
        notification_service.send_notification(
            user_id=top_res["user_id"],
            title="Reserved Book Ready for Pickup",
            message=f"A copy of '{top_res['book_title']}' is ready for you! Held until {hold_date}.",
            notif_type="success",
            link="/member/reservations",
            conn=conn,
        )
        return top_res["user_id"]
    else:
        # No reservations waiting, set copy available
        execute_db(
            "UPDATE book_copies SET status = 'available' WHERE id = ?",
            (copy_id,),
            conn=conn,
        )
        return None


def cancel_reservation(reservation_id, user_id=None):
    """
    Cancel an active reservation.
    If it was held for pickup, reassign the copy to next waiting member or make available.
    """
    with transaction() as conn:
        res = query_db(
            "SELECT * FROM reservations WHERE id = ?",
            (reservation_id,),
            one=True,
            conn=conn,
        )
        if not res:
            return False, "Reservation not found."

        if user_id and res["user_id"] != user_id:
            return False, "You can only cancel your own reservations."

        if res["status"] not in ("waiting", "available_for_pickup"):
            return False, f"Cannot cancel reservation with status '{res['status']}'."

        copy_to_reassign = res["assigned_copy_id"]
        book_id = res["book_id"]

        execute_db(
            "UPDATE reservations SET status = 'cancelled', assigned_copy_id = NULL WHERE id = ?",
            (reservation_id,),
            conn=conn,
        )

        _reindex_queue(book_id, conn=conn)

        if copy_to_reassign and res["status"] == "available_for_pickup":
            fulfill_next_reservation_on_return(book_id, copy_to_reassign, conn=conn)

    return True, None


def check_and_expire_reservations():
    """Check for expired pickup holds and reassign copies."""
    today_str = date.today().isoformat()
    expired_list = query_db(
        """
        SELECT r.id, r.book_id, r.user_id, r.assigned_copy_id, b.title AS book_title
        FROM reservations r
        JOIN books b ON r.book_id = b.id
        WHERE r.status = 'available_for_pickup' AND r.hold_until < ?
        """,
        (today_str,),
    )

    for r in expired_list:
        with transaction() as conn:
            execute_db(
                "UPDATE reservations SET status = 'expired', assigned_copy_id = NULL WHERE id = ?",
                (r["id"],),
                conn=conn,
            )
            notification_service.send_notification(
                user_id=r["user_id"],
                title="Reservation Hold Expired",
                message=f"The hold period for '{r['book_title']}' has expired.",
                notif_type="warning",
                conn=conn,
            )
            if r["assigned_copy_id"]:
                fulfill_next_reservation_on_return(r["book_id"], r["assigned_copy_id"], conn=conn)


def _reindex_queue(book_id, conn=None):
    """Ensure contiguous 1, 2, 3 queue positions for waiting reservations."""
    waiting = query_db(
        """
        SELECT id FROM reservations
        WHERE book_id = ? AND status = 'waiting'
        ORDER BY queue_position ASC, reserved_at ASC
        """,
        (book_id,),
        conn=conn,
    )
    for idx, row in enumerate(waiting, start=1):
        execute_db(
            "UPDATE reservations SET queue_position = ? WHERE id = ?",
            (idx, row["id"]),
            conn=conn,
        )


def get_user_reservations(user_id):
    """Retrieve reservations placed by a user."""
    query = """
        SELECT r.*,
               b.title AS book_title,
               b.author AS book_author,
               b.isbn AS book_isbn,
               bc.accession_id AS assigned_accession_id
        FROM reservations r
        JOIN books b ON r.book_id = b.id
        LEFT JOIN book_copies bc ON r.assigned_copy_id = bc.id
        WHERE r.user_id = ?
        ORDER BY CASE r.status
            WHEN 'available_for_pickup' THEN 1
            WHEN 'waiting' THEN 2
            ELSE 3 END,
            r.reserved_at DESC
    """
    return query_db(query, (user_id,))


def get_all_active_reservations():
    """Retrieve all waiting and pickup-ready reservations across the library."""
    query = """
        SELECT r.*,
               u.name AS member_name,
               u.email AS member_email,
               b.title AS book_title,
               bc.accession_id AS assigned_accession_id
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        JOIN books b ON r.book_id = b.id
        LEFT JOIN book_copies bc ON r.assigned_copy_id = bc.id
        WHERE r.status IN ('waiting', 'available_for_pickup')
        ORDER BY r.status DESC, r.book_id, r.queue_position ASC
    """
    return query_db(query)
