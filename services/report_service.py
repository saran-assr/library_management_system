import csv
import io
from datetime import date
from database import query_db
from config import Config
from services import fine_service


def get_dashboard_stats():
    """Aggregate high-level library operational metrics for the Admin Dashboard."""
    today_str = date.today().isoformat()

    titles_cnt = query_db("SELECT COUNT(*) AS c FROM books WHERE is_deleted = 0", one=True)["c"]
    copies_cnt = query_db("SELECT COUNT(*) AS c FROM book_copies WHERE is_deleted = 0", one=True)["c"]
    available_cnt = query_db("SELECT COUNT(*) AS c FROM book_copies WHERE status = 'available' AND is_deleted = 0", one=True)["c"]
    borrowed_cnt = query_db("SELECT COUNT(*) AS c FROM book_copies WHERE status = 'borrowed' AND is_deleted = 0", one=True)["c"]
    members_cnt = query_db("SELECT COUNT(*) AS c FROM users WHERE role = 'member'", one=True)["c"]

    overdue_cnt = query_db(
        "SELECT COUNT(*) AS c FROM loans WHERE (status = 'overdue' OR (status = 'active' AND due_date < ?))",
        (today_str,),
        one=True,
    )["c"]

    pending_res_cnt = query_db(
        "SELECT COUNT(*) AS c FROM reservations WHERE status IN ('waiting', 'available_for_pickup')",
        one=True,
    )["c"]

    unpaid_fines = query_db(
        "SELECT COALESCE(SUM(amount), 0.0) AS s FROM fines WHERE status = 'unpaid'",
        one=True,
    )["s"]

    # Recent transactions
    recent_loans = query_db(
        """
        SELECT l.*, u.name AS member_name, b.title AS book_title, bc.accession_id
        FROM loans l
        JOIN users u ON l.user_id = u.id
        JOIN book_copies bc ON l.copy_id = bc.id
        JOIN books b ON bc.book_id = b.id
        ORDER BY l.id DESC
        LIMIT 7
        """
    )

    return {
        "total_titles": titles_cnt,
        "total_copies": copies_cnt,
        "available_copies": available_cnt,
        "borrowed_copies": borrowed_cnt,
        "registered_members": members_cnt,
        "overdue_loans": overdue_cnt,
        "pending_reservations": pending_res_cnt,
        "unpaid_fines_total": unpaid_fines,
        "currency": Config.CURRENCY_SYMBOL,
        "recent_loans": recent_loans,
    }


def get_chart_data():
    """Compile aggregated data arrays for Chart.js rendering."""
    # 1. Category Distribution
    categories_data = query_db(
        """
        SELECT c.name, COUNT(DISTINCT b.id) AS book_count, COUNT(l.id) AS loan_count
        FROM categories c
        LEFT JOIN books b ON c.id = b.category_id AND b.is_deleted = 0
        LEFT JOIN book_copies bc ON b.id = bc.book_id AND bc.is_deleted = 0
        LEFT JOIN loans l ON bc.id = l.copy_id
        GROUP BY c.id
        ORDER BY book_count DESC
        LIMIT 6
        """
    )

    # 2. Monthly Borrowing Trends (Last 6 distinct months or grouped)
    monthly_data = query_db(
        """
        SELECT SUBSTR(issue_date, 1, 7) AS month_label, COUNT(*) AS count
        FROM loans
        GROUP BY month_label
        ORDER BY month_label ASC
        LIMIT 6
        """
    )

    # 3. Loan Status breakdown
    today_str = date.today().isoformat()
    status_counts = query_db(
        """
        SELECT
            COUNT(CASE WHEN status = 'returned' THEN 1 END) AS returned,
            COUNT(CASE WHEN status = 'active' AND due_date >= ? THEN 1 END) AS on_schedule,
            COUNT(CASE WHEN (status = 'overdue' OR (status = 'active' AND due_date < ?)) THEN 1 END) AS overdue
        FROM loans
        """,
        (today_str, today_str),
        one=True,
    )

    return {
        "categories": {
            "labels": [r["name"] for r in categories_data],
            "counts": [r["book_count"] for r in categories_data],
            "loans": [r["loan_count"] for r in categories_data],
        },
        "monthly": {
            "labels": [r["month_label"] for r in monthly_data] if monthly_data else ["Current Month"],
            "counts": [r["count"] for r in monthly_data] if monthly_data else [0],
        },
        "status_distribution": {
            "returned": status_counts["returned"] if status_counts else 0,
            "active": status_counts["on_schedule"] if status_counts else 0,
            "overdue": status_counts["overdue"] if status_counts else 0,
        },
    }


def generate_csv(headers, rows):
    """Utility to build an in-memory CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    return output.getvalue()


def export_inventory_csv():
    """Export complete inventory including physical copies."""
    data = query_db(
        """
        SELECT b.isbn, b.title, b.author, c.name AS category,
               bc.accession_id, bc.status, bc.location_rack, bc.condition
        FROM book_copies bc
        JOIN books b ON bc.book_id = b.id
        JOIN categories c ON b.category_id = c.id
        WHERE bc.is_deleted = 0 AND b.is_deleted = 0
        ORDER BY b.title ASC, bc.accession_id ASC
        """
    )
    headers = ["ISBN", "Title", "Author", "Category", "Accession ID", "Status", "Location Rack", "Condition"]
    rows = [
        [r["isbn"], r["title"], r["author"], r["category"], r["accession_id"], r["status"], r["location_rack"] or "", r["condition"]]
        for r in data
    ]
    return generate_csv(headers, rows)


def export_loans_csv(filter_type="all"):
    """Export loans data with calculated overdue status and fines."""
    where_sql = ""
    today_str = date.today().isoformat()
    if filter_type == "active":
        where_sql = "WHERE l.status IN ('active', 'overdue')"
    elif filter_type == "overdue":
        where_sql = f"WHERE (l.status = 'overdue' OR (l.status = 'active' AND l.due_date < '{today_str}'))"

    query = f"""
        SELECT l.id, bc.accession_id, b.title, u.name AS member_name, u.email AS member_email,
               l.issue_date, l.due_date, l.return_date, l.status,
               f.amount AS fine_amount, f.status AS fine_status
        FROM loans l
        JOIN book_copies bc ON l.copy_id = bc.id
        JOIN books b ON bc.book_id = b.id
        JOIN users u ON l.user_id = u.id
        LEFT JOIN fines f ON l.id = f.loan_id
        {where_sql}
        ORDER BY l.id DESC
    """
    data = query_db(query)
    headers = ["Loan ID", "Accession ID", "Book Title", "Member Name", "Member Email", "Issue Date", "Due Date", "Return Date", "Status", "Fine Amount", "Fine Status"]
    rows = [
        [
            r["id"], r["accession_id"], r["title"], r["member_name"], r["member_email"],
            r["issue_date"], r["due_date"], r["return_date"] or "N/A", r["status"],
            f"{r['fine_amount']:.2f}" if r["fine_amount"] is not None else "0.00",
            r["fine_status"] or "N/A",
        ]
        for r in data
    ]
    return generate_csv(headers, rows)


def export_fines_csv():
    """Export fines summary."""
    data = query_db(
        """
        SELECT f.id, u.name AS member_name, u.email AS member_email,
               b.title AS book_title, bc.accession_id, f.amount, f.status,
               f.calculated_days, f.created_at, f.paid_at
        FROM fines f
        JOIN users u ON f.user_id = u.id
        JOIN loans l ON f.loan_id = l.id
        JOIN book_copies bc ON l.copy_id = bc.id
        JOIN books b ON bc.book_id = b.id
        ORDER BY f.id DESC
        """
    )
    headers = ["Fine ID", "Member Name", "Email", "Book Title", "Accession ID", "Amount ($)", "Status", "Overdue Days", "Assessed Date", "Paid Date"]
    rows = [
        [
            r["id"], r["member_name"], r["member_email"], r["book_title"], r["accession_id"],
            f"{r['amount']:.2f}", r["status"], r["calculated_days"], r["created_at"], r["paid_at"] or "N/A"
        ]
        for r in data
    ]
    return generate_csv(headers, rows)


def export_members_csv():
    """Export member registration and borrowing activity."""
    data = query_db(
        """
        SELECT u.id, u.name, u.email, u.phone, u.status, u.created_at,
               COUNT(DISTINCT l.id) AS total_loans,
               COUNT(DISTINCT CASE WHEN l.status IN ('active', 'overdue') THEN l.id END) AS current_active_loans,
               COALESCE(SUM(CASE WHEN f.status = 'unpaid' THEN f.amount ELSE 0 END), 0.0) AS unpaid_fines
        FROM users u
        LEFT JOIN loans l ON u.id = l.user_id
        LEFT JOIN fines f ON u.id = f.user_id
        WHERE u.role = 'member'
        GROUP BY u.id
        ORDER BY u.name ASC
        """
    )
    headers = ["Member ID", "Name", "Email", "Phone", "Status", "Joined Date", "Total Borrowed", "Current Loans", "Unpaid Fines ($)"]
    rows = [
        [
            r["id"], r["name"], r["email"], r["phone"] or "N/A", r["status"], r["created_at"],
            r["total_loans"], r["current_active_loans"], f"{r['unpaid_fines']:.2f}"
        ]
        for r in data
    ]
    return generate_csv(headers, rows)
