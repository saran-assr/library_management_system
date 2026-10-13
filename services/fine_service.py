from datetime import datetime, date
from database import query_db, execute_db
from config import Config


def parse_date(date_str):
    """Parse ISO date string (YYYY-MM-DD) into date object."""
    if isinstance(date_str, (date, datetime)):
        return date_str if isinstance(date_str, date) else date_str.date()
    return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()


def calculate_overdue_days(due_date_val, reference_date_val=None):
    """
    Calculate overdue days between due date and reference date (default today).
    Returns 0 if not overdue.
    """
    if not due_date_val:
        return 0
    d_due = parse_date(due_date_val)
    d_ref = parse_date(reference_date_val) if reference_date_val else date.today()
    delta = (d_ref - d_due).days
    return max(0, delta)


def calculate_fine_amount(overdue_days):
    """Calculate fine amount based on configurable daily rate and maximum cap."""
    if overdue_days <= 0:
        return 0.0
    raw_fine = overdue_days * Config.FINE_RATE_PER_DAY
    return round(min(raw_fine, Config.MAX_FINE_PER_LOAN), 2)


def assess_fine_for_loan(loan_id, user_id, due_date_val, return_date_val=None, conn=None):
    """
    Idempotently assess and record a fine for an overdue loan.
    Guarantees no duplicate fine rows are created for the same loan.
    """
    overdue_days = calculate_overdue_days(due_date_val, return_date_val)
    if overdue_days <= 0:
        return 0, 0.0, None

    fine_amount = calculate_fine_amount(overdue_days)

    # Check for existing fine on this loan
    existing = query_db(
        "SELECT id, amount, status FROM fines WHERE loan_id = ?",
        (loan_id,),
        one=True,
        conn=conn,
    )

    if existing:
        # If fine was already paid or waived, do not alter it
        if existing["status"] in ("paid", "waived"):
            return overdue_days, existing["amount"], existing["id"]

        # Update existing unpaid fine with accurate days and amount
        execute_db(
            """
            UPDATE fines
            SET amount = ?, calculated_days = ?
            WHERE id = ?
            """,
            (fine_amount, overdue_days, existing["id"]),
            conn=conn,
        )
        return overdue_days, fine_amount, existing["id"]

    # Insert new fine
    res = execute_db(
        """
        INSERT INTO fines (loan_id, user_id, amount, status, calculated_days)
        VALUES (?, ?, ?, 'unpaid', ?)
        """,
        (loan_id, user_id, fine_amount, overdue_days),
        conn=conn,
    )
    return overdue_days, fine_amount, res["lastrowid"]


def pay_fine(fine_id, admin_id=None, notes=None):
    """Record fine payment."""
    res = execute_db(
        """
        UPDATE fines
        SET status = 'paid', paid_at = CURRENT_TIMESTAMP, notes = ?
        WHERE id = ? AND status = 'unpaid'
        """,
        (notes, fine_id),
    )
    return res["rowcount"] > 0


def waive_fine(fine_id, admin_id=None, notes=None):
    """Waive fine by administrator."""
    res = execute_db(
        """
        UPDATE fines
        SET status = 'waived', notes = ?
        WHERE id = ? AND status = 'unpaid'
        """,
        (notes, fine_id),
    )
    return res["rowcount"] > 0


def get_unpaid_fines_total(user_id):
    """Calculate total unpaid fine amount for a specific user."""
    row = query_db(
        "SELECT COALESCE(SUM(amount), 0.0) AS total FROM fines WHERE user_id = ? AND status = 'unpaid'",
        (user_id,),
        one=True,
    )
    return float(row["total"]) if row else 0.0


def get_fines(status=None, user_id=None):
    """Retrieve fines with member details and loan information."""
    where_clauses = []
    args = []

    if status:
        where_clauses.append("f.status = ?")
        args.append(status)

    if user_id:
        where_clauses.append("f.user_id = ?")
        args.append(user_id)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    query = f"""
        SELECT f.*,
               u.name AS member_name,
               u.email AS member_email,
               b.title AS book_title,
               bc.accession_id,
               l.due_date,
               l.return_date
        FROM fines f
        JOIN users u ON f.user_id = u.id
        JOIN loans l ON f.loan_id = l.id
        JOIN book_copies bc ON l.copy_id = bc.id
        JOIN books b ON bc.book_id = b.id
        {where_sql}
        ORDER BY f.created_at DESC, f.id DESC
    """
    return query_db(query, args)
