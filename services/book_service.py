import math
from database import query_db, execute_db


def get_categories():
    """Retrieve all categories ordered by name."""
    return query_db("SELECT * FROM categories ORDER BY name ASC")


def get_category_by_id(category_id):
    """Retrieve a single category by its ID."""
    return query_db("SELECT * FROM categories WHERE id = ?", (category_id,), one=True)


def create_category(name, description=None, icon="bi-bookmark"):
    """Create a new category."""
    name = (name or "").strip()
    if not name:
        return None, "Category name cannot be empty."
    existing = query_db("SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,), one=True)
    if existing:
        return None, f"Category '{name}' already exists."
    res = execute_db(
        "INSERT INTO categories (name, description, icon) VALUES (?, ?, ?)",
        (name, description, icon or "bi-bookmark"),
    )
    return res["lastrowid"], None


def get_books(
    search=None,
    category_id=None,
    availability=None,
    year=None,
    sort_by="title",
    page=1,
    per_page=12,
    include_deleted=False,
):
    """
    Search, filter, sort and paginate books.
    Returns (books_list, pagination_metadata_dict).
    """
    where_clauses = []
    args = []

    if not include_deleted:
        where_clauses.append("b.is_deleted = 0")

    if search:
        search_term = f"%{search.strip()}%"
        where_clauses.append("(b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ?)")
        args.extend([search_term, search_term, search_term])

    if category_id:
        where_clauses.append("b.category_id = ?")
        args.append(category_id)

    if year:
        where_clauses.append("b.publication_year = ?")
        args.append(year)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Sort SQL
    sort_map = {
        "title": "b.title ASC",
        "author": "b.author ASC",
        "newest": "b.id DESC",
        "popularity": "loan_count DESC, b.title ASC",
    }
    sort_sql = sort_map.get(sort_by, "b.title ASC")

    # Base query to compute copy statistics and loan count
    base_query = f"""
        SELECT b.*,
               c.name AS category_name,
               c.icon AS category_icon,
               COUNT(DISTINCT bc.id) AS total_copies,
               COUNT(DISTINCT CASE WHEN bc.status = 'available' AND bc.is_deleted = 0 THEN bc.id END) AS available_copies,
               COUNT(DISTINCT l.id) AS loan_count
        FROM books b
        JOIN categories c ON b.category_id = c.id
        LEFT JOIN book_copies bc ON b.id = bc.book_id AND bc.is_deleted = 0
        LEFT JOIN loans l ON bc.id = l.copy_id
        {where_sql}
        GROUP BY b.id
    """

    # Filter by availability in HAVING clause if requested
    having_clauses = []
    if availability == "available":
        having_clauses.append("available_copies > 0")
    elif availability == "unavailable":
        having_clauses.append("available_copies = 0")

    having_sql = ("HAVING " + " AND ".join(having_clauses)) if having_clauses else ""

    full_sql = f"{base_query} {having_sql}"

    # Get total count for pagination
    count_sql = f"SELECT COUNT(*) AS total FROM ({full_sql}) sub"
    total_row = query_db(count_sql, args, one=True)
    total_records = total_row["total"] if total_row else 0

    total_pages = max(1, math.ceil(total_records / per_page))
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    paged_sql = f"{full_sql} ORDER BY {sort_sql} LIMIT ? OFFSET ?"
    records = query_db(paged_sql, args + [per_page, offset])

    pagination = {
        "page": page,
        "per_page": per_page,
        "total_records": total_records,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_num": page - 1,
        "next_num": page + 1,
    }

    return records, pagination


def get_book_by_id(book_id):
    """Retrieve complete book details including category and copy counts."""
    query = """
        SELECT b.*,
               c.name AS category_name,
               c.icon AS category_icon,
               COUNT(DISTINCT bc.id) AS total_copies,
               COUNT(DISTINCT CASE WHEN bc.status = 'available' AND bc.is_deleted = 0 THEN bc.id END) AS available_copies
        FROM books b
        JOIN categories c ON b.category_id = c.id
        LEFT JOIN book_copies bc ON b.id = bc.book_id AND bc.is_deleted = 0
        WHERE b.id = ?
        GROUP BY b.id
    """
    return query_db(query, (book_id,), one=True)


def get_book_by_isbn(isbn):
    """Retrieve book by ISBN."""
    query = "SELECT * FROM books WHERE isbn = ? AND is_deleted = 0"
    return query_db(query, (isbn.strip(),), one=True)


def create_book(isbn, title, author, category_id, publisher=None, publication_year=None, description=None, cover_image_url=None):
    """Validate and insert a new book title record."""
    isbn = (isbn or "").strip()
    title = (title or "").strip()
    author = (author or "").strip()

    if not isbn or len(isbn) < 5:
        return None, "ISBN must be at least 5 characters."
    if not title:
        return None, "Book title is required."
    if not author:
        return None, "Author name is required."
    if not category_id:
        return None, "Category is required."

    existing = query_db("SELECT id, is_deleted FROM books WHERE isbn = ?", (isbn,), one=True)
    if existing:
        if existing["is_deleted"] == 1:
            # Restore previously deleted book
            execute_db(
                """
                UPDATE books SET title = ?, author = ?, category_id = ?, publisher = ?,
                                 publication_year = ?, description = ?, cover_image_url = ?, is_deleted = 0
                WHERE id = ?
                """,
                (title, author, category_id, publisher, publication_year, description, cover_image_url, existing["id"]),
            )
            return existing["id"], None
        return None, f"A book with ISBN '{isbn}' already exists."

    res = execute_db(
        """
        INSERT INTO books (isbn, title, author, category_id, publisher, publication_year, description, cover_image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (isbn, title, author, category_id, publisher, publication_year, description, cover_image_url),
    )
    return res["lastrowid"], None


def update_book(book_id, isbn, title, author, category_id, publisher=None, publication_year=None, description=None, cover_image_url=None):
    """Update existing book title."""
    isbn = (isbn or "").strip()
    title = (title or "").strip()
    author = (author or "").strip()

    if not isbn or not title or not author:
        return False, "ISBN, Title, and Author are required."

    existing = query_db("SELECT id FROM books WHERE isbn = ? AND id != ?", (isbn, book_id), one=True)
    if existing:
        return False, f"Another book with ISBN '{isbn}' already exists."

    execute_db(
        """
        UPDATE books
        SET isbn = ?, title = ?, author = ?, category_id = ?, publisher = ?,
            publication_year = ?, description = ?, cover_image_url = ?
        WHERE id = ?
        """,
        (isbn, title, author, category_id, publisher, publication_year, description, cover_image_url, book_id),
    )
    return True, None


def delete_book(book_id):
    """
    Delete a book title.
    Integrity check: blocks deletion if any physical copy is currently borrowed.
    Uses soft deletion to preserve historical loan and reservation records.
    """
    active_loans = query_db(
        """
        SELECT l.id, bc.accession_id
        FROM loans l
        JOIN book_copies bc ON l.copy_id = bc.id
        WHERE bc.book_id = ? AND l.status IN ('active', 'overdue')
        """,
        (book_id,),
    )
    if active_loans:
        copies = ", ".join(r["accession_id"] for r in active_loans)
        return False, f"Cannot delete book: Copies ({copies}) are currently borrowed."

    # Soft delete book and copies
    execute_db("UPDATE books SET is_deleted = 1 WHERE id = ?", (book_id,))
    execute_db("UPDATE book_copies SET is_deleted = 1 WHERE book_id = ?", (book_id,))
    return True, None


# --- Physical Book Copies ---

def get_copies_for_book(book_id, include_deleted=False):
    """Retrieve physical copies for a given book title."""
    query = """
        SELECT bc.*,
               l.id AS active_loan_id,
               l.due_date AS active_due_date,
               u.name AS borrower_name,
               u.email AS borrower_email
        FROM book_copies bc
        LEFT JOIN loans l ON bc.id = l.copy_id AND l.status IN ('active', 'overdue')
        LEFT JOIN users u ON l.user_id = u.id
        WHERE bc.book_id = ?
    """
    if not include_deleted:
        query += " AND bc.is_deleted = 0"
    query += " ORDER BY bc.accession_id ASC"
    return query_db(query, (book_id,))


def get_copy_by_accession_id(accession_id):
    """Retrieve physical copy by unique accession ID with title and author info."""
    query = """
        SELECT bc.*, b.id AS book_id, b.title, b.author, b.isbn, c.name AS category_name
        FROM book_copies bc
        JOIN books b ON bc.book_id = b.id
        JOIN categories c ON b.category_id = c.id
        WHERE bc.accession_id = ? AND bc.is_deleted = 0
    """
    return query_db(query, (accession_id.strip(),), one=True)


def add_copy(book_id, accession_id, location_rack=None, condition="Good"):
    """Add a new physical copy for a book."""
    accession_id = (accession_id or "").strip().upper()
    if not accession_id:
        return None, "Accession ID is required."

    existing = query_db("SELECT id, is_deleted FROM book_copies WHERE accession_id = ?", (accession_id,), one=True)
    if existing:
        if existing["is_deleted"] == 1:
            execute_db(
                "UPDATE book_copies SET book_id = ?, location_rack = ?, condition = ?, status = 'available', is_deleted = 0 WHERE id = ?",
                (book_id, location_rack, condition, existing["id"]),
            )
            return existing["id"], None
        return None, f"Accession ID '{accession_id}' is already assigned to a book copy."

    res = execute_db(
        """
        INSERT INTO book_copies (book_id, accession_id, location_rack, condition, status)
        VALUES (?, ?, ?, ?, 'available')
        """,
        (book_id, accession_id, location_rack, condition),
    )
    return res["lastrowid"], None


def update_copy(copy_id, location_rack, condition, status=None):
    """Update physical copy metadata and optional status."""
    if status:
        execute_db(
            "UPDATE book_copies SET location_rack = ?, condition = ?, status = ? WHERE id = ?",
            (location_rack, condition, status, copy_id),
        )
    else:
        execute_db(
            "UPDATE book_copies SET location_rack = ?, condition = ? WHERE id = ?",
            (location_rack, condition, copy_id),
        )
    return True, None


def delete_copy(copy_id):
    """Delete a physical copy if not currently borrowed."""
    active_loan = query_db(
        "SELECT id FROM loans WHERE copy_id = ? AND status IN ('active', 'overdue')",
        (copy_id,),
        one=True,
    )
    if active_loan:
        return False, "Cannot delete copy: It is currently checked out by a member."

    execute_db("UPDATE book_copies SET is_deleted = 1 WHERE id = ?", (copy_id,))
    return True, None
