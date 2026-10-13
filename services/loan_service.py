from datetime import date, timedelta
from database import query_db, execute_db, transaction
from config import Config
from services import fine_service, reservation_service, notification_service, audit_service


def issue_book(accession_id, user_id, issued_by_id, duration_days=None, notes=None):
    """
    Issue a physical book copy to a member with complete eligibility and reservation checks.
    Atomic transaction ensures concurrency safety.
    Returns (loan_id, None) on success or (None, error_message).
    """
    accession_id = (accession_id or "").strip().upper()
    duration = duration_days or Config.LOAN_DURATION_DAYS

    with transaction() as conn:
        # 1. Validate Member
        member = query_db(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
            one=True,
            conn=conn,
        )
        if not member:
            return None, "Member not found."
        if member["status"] != "active":
            return None, f"Member account is {member['status']}. Cannot issue books."

        # Check member loan limit
        active_loans_count = query_db(
            "SELECT COUNT(*) AS cnt FROM loans WHERE user_id = ? AND status IN ('active', 'overdue')",
            (user_id,),
            one=True,
            conn=conn,
        )["cnt"]
        max_allowed = member["max_loans"] or Config.MAX_LOANS_PER_MEMBER
        if active_loans_count >= max_allowed:
            return None, f"Member has reached the maximum borrowing limit ({max_allowed} books)."

        # Check unpaid fines limit
        unpaid_fines = fine_service.get_unpaid_fines_total(user_id)
        if unpaid_fines > Config.MAX_UNPAID_FINE_LIMIT:
            return None, (
                f"Member has {Config.CURRENCY_SYMBOL}{unpaid_fines:.2f} in unpaid fines, "
                f"exceeding the limit of {Config.CURRENCY_SYMBOL}{Config.MAX_UNPAID_FINE_LIMIT:.2f}. "
                "Fines must be cleared before borrowing."
            )

        # 2. Validate Physical Copy
        copy = query_db(
            """
            SELECT bc.*, b.title AS book_title, b.id AS book_id
            FROM book_copies bc
            JOIN books b ON bc.book_id = b.id
            WHERE bc.accession_id = ? AND bc.is_deleted = 0
            """,
            (accession_id,),
            one=True,
            conn=conn,
        )
        if not copy:
            return None, f"Physical copy with Accession ID '{accession_id}' not found."

        if copy["status"] == "borrowed":
            return None, f"Copy '{accession_id}' is already checked out to another member."
        if copy["status"] in ("maintenance", "lost"):
            return None, f"Copy '{accession_id}' cannot be issued (Status: {copy['status']})."

        # Check if copy is reserved
        if copy["status"] == "reserved":
            reserved_res = query_db(
                """
                SELECT r.*, u.name AS reserved_for_name
                FROM reservations r
                JOIN users u ON r.user_id = u.id
                WHERE r.assigned_copy_id = ? AND r.status = 'available_for_pickup'
                """,
                (copy["id"],),
                one=True,
                conn=conn,
            )
            if reserved_res:
                if reserved_res["user_id"] != user_id:
                    return None, (
                        f"This copy is currently on hold for member '{reserved_res['reserved_for_name']}' "
                        f"until {reserved_res['hold_until']}."
                    )
                # It is reserved for THIS member! Fulfill the reservation
                execute_db(
                    "UPDATE reservations SET status = 'fulfilled' WHERE id = ?",
                    (reserved_res["id"],),
                    conn=conn,
                )

        # 3. Create Loan Record
        issue_date = date.today().isoformat()
        due_date = (date.today() + timedelta(days=duration)).isoformat()

        loan_res = execute_db(
            """
            INSERT INTO loans (copy_id, user_id, issued_by, issue_date, due_date, status, notes)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (copy["id"], user_id, issued_by_id, issue_date, due_date, notes),
            conn=conn,
        )
        loan_id = loan_res["lastrowid"]

        # Update Copy Status to 'borrowed'
        execute_db(
            "UPDATE book_copies SET status = 'borrowed' WHERE id = ?",
            (copy["id"],),
            conn=conn,
        )

        # Audit Log
        audit_service.log_action(
            user_id=issued_by_id,
            action="ISSUE_BOOK",
            entity_type="loan",
            entity_id=loan_id,
            details=f"Issued '{copy['book_title']}' ({accession_id}) to {member['name']} (Due: {due_date})",
            conn=conn,
        )

        # In-app notification for member
        notification_service.send_notification(
            user_id=user_id,
            title="Book Issued",
            message=f"You borrowed '{copy['book_title']}' ({accession_id}). Due date: {due_date}.",
            notif_type="info",
            link="/member/loans",
            conn=conn,
        )

        return loan_id, None


def return_book(accession_id, returned_by_id, notes=None):
    """
    Accept return of a borrowed book copy.
    Calculates overdue fines, updates loan history, and fulfills reservation queue if pending.
    Returns (result_dict, None) or (None, error_message).
    """
    accession_id = (accession_id or "").strip().upper()

    with transaction() as conn:
        copy = query_db(
            """
            SELECT bc.*, b.title AS book_title, b.id AS book_id
            FROM book_copies bc
            JOIN books b ON bc.book_id = b.id
            WHERE bc.accession_id = ? AND bc.is_deleted = 0
            """,
            (accession_id,),
            one=True,
            conn=conn,
        )
        if not copy:
            return None, f"Copy with Accession ID '{accession_id}' not found."

        # Find active loan
        loan = query_db(
            """
            SELECT l.*, u.name AS member_name, u.email AS member_email
            FROM loans l
            JOIN users u ON l.user_id = u.id
            WHERE l.copy_id = ? AND l.status IN ('active', 'overdue')
            ORDER BY l.id DESC
            LIMIT 1
            """,
            (copy["id"],),
            one=True,
            conn=conn,
        )
        if not loan:
            return None, f"No active loan record found for copy '{accession_id}'."

        today_str = date.today().isoformat()

        # Overdue check and fine assessment
        overdue_days, fine_amount, fine_id = fine_service.assess_fine_for_loan(
            loan_id=loan["id"],
            user_id=loan["user_id"],
            due_date_val=loan["due_date"],
            return_date_val=today_str,
            conn=conn,
        )

        # Mark loan as returned
        return_notes = f"{loan['notes'] or ''} {notes or ''}".strip() or None
        execute_db(
            """
            UPDATE loans
            SET return_date = ?, status = 'returned', notes = ?
            WHERE id = ?
            """,
            (today_str, return_notes, loan["id"]),
            conn=conn,
        )

        # Check and fulfill next reservation FIFO
        reserved_user_id = reservation_service.fulfill_next_reservation_on_return(
            book_id=copy["book_id"],
            copy_id=copy["id"],
            conn=conn,
        )

        # Audit log
        details = f"Returned '{copy['book_title']}' ({accession_id}) by {loan['member_name']}."
        if overdue_days > 0:
            details += f" Overdue by {overdue_days} days. Fine: {Config.CURRENCY_SYMBOL}{fine_amount:.2f}."
        if reserved_user_id:
            details += " Copy placed on hold for next reservation."

        audit_service.log_action(
            user_id=returned_by_id,
            action="RETURN_BOOK",
            entity_type="loan",
            entity_id=loan["id"],
            details=details,
            conn=conn,
        )

        # Notification for member who returned
        if overdue_days > 0:
            notification_service.send_notification(
                user_id=loan["user_id"],
                title="Book Returned (Overdue)",
                message=(
                    f"'{copy['book_title']}' returned {overdue_days} days late. "
                    f"Fine assessed: {Config.CURRENCY_SYMBOL}{fine_amount:.2f}."
                ),
                notif_type="warning",
                link="/member/loans",
                conn=conn,
            )
        else:
            notification_service.send_notification(
                user_id=loan["user_id"],
                title="Book Returned Successfully",
                message=f"'{copy['book_title']}' was returned on time. Thank you!",
                notif_type="success",
                link="/member/loans",
                conn=conn,
            )

        result = {
            "loan_id": loan["id"],
            "book_title": copy["book_title"],
            "accession_id": accession_id,
            "member_name": loan["member_name"],
            "overdue_days": overdue_days,
            "fine_amount": fine_amount,
            "reserved_for_next": bool(reserved_user_id),
        }
        return result, None


def get_active_loans(user_id=None):
    """
    Retrieve active/overdue loans with live computed overdue days and accrued fines.
    Works accurately without relying solely on background schedulers.
    """
    where_sql = "WHERE l.status IN ('active', 'overdue')"
    args = []
    if user_id:
        where_sql += " AND l.user_id = ?"
        args.append(user_id)

    query = f"""
        SELECT l.*,
               u.name AS member_name,
               u.email AS member_email,
               b.id AS book_id,
               b.title AS book_title,
               b.author AS book_author,
               b.isbn AS book_isbn,
               bc.accession_id,
               bc.location_rack,
               f.id AS fine_id,
               f.amount AS fine_amount,
               f.status AS fine_status
        FROM loans l
        JOIN users u ON l.user_id = u.id
        JOIN book_copies bc ON l.copy_id = bc.id
        JOIN books b ON bc.book_id = b.id
        LEFT JOIN fines f ON l.id = f.loan_id
        {where_sql}
        ORDER BY l.due_date ASC
    """
    raw_loans = query_db(query, args)

    loans = []
    today = date.today()
    for row in raw_loans:
        item = dict(row)
        due = fine_service.parse_date(item["due_date"])
        overdue_days = max(0, (today - due).days)
        item["is_overdue"] = overdue_days > 0
        item["overdue_days"] = overdue_days
        item["calculated_fine"] = fine_service.calculate_fine_amount(overdue_days) if overdue_days > 0 else 0.0
        loans.append(item)

    return loans


def get_loan_history(user_id=None, limit=100):
    """Retrieve historical loans (returned and current)."""
    where_sql = ""
    args = []
    if user_id:
        where_sql = "WHERE l.user_id = ?"
        args.append(user_id)

    query = f"""
        SELECT l.*,
               u.name AS member_name,
               u.email AS member_email,
               b.id AS book_id,
               b.title AS book_title,
               b.author AS book_author,
               bc.accession_id,
               f.amount AS fine_amount,
               f.status AS fine_status
        FROM loans l
        JOIN users u ON l.user_id = u.id
        JOIN book_copies bc ON l.copy_id = bc.id
        JOIN books b ON bc.book_id = b.id
        LEFT JOIN fines f ON l.id = f.loan_id
        {where_sql}
        ORDER BY l.id DESC
        LIMIT ?
    """
    return query_db(query, args + [limit])


def sync_overdue_statuses():
    """Update loan status to 'overdue' for any unreturned loan past its due date."""
    today_str = date.today().isoformat()
    execute_db(
        """
        UPDATE loans
        SET status = 'overdue'
        WHERE status = 'active' AND due_date < ?
        """,
        (today_str,),
    )
