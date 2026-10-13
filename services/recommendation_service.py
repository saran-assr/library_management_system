from database import query_db


def get_recommendations_for_user(user_id=None, limit=6):
    """
    Produce explainable book recommendations for a member based on borrowing history.
    Provides popular & recent arrivals as fallbacks for new users.
    """
    recommendations = []
    seen_book_ids = set()

    if user_id:
        # 1. Books already borrowed by user
        borrowed_rows = query_db(
            """
            SELECT DISTINCT bc.book_id
            FROM loans l
            JOIN book_copies bc ON l.copy_id = bc.id
            WHERE l.user_id = ?
            """,
            (user_id,),
        )
        for r in borrowed_rows:
            seen_book_ids.add(r["book_id"])

        # 2. Favorite Categories
        top_cats = query_db(
            """
            SELECT b.category_id, c.name AS category_name, COUNT(*) AS count
            FROM loans l
            JOIN book_copies bc ON l.copy_id = bc.id
            JOIN books b ON bc.book_id = b.id
            JOIN categories c ON b.category_id = c.id
            WHERE l.user_id = ?
            GROUP BY b.category_id
            ORDER BY count DESC
            LIMIT 2
            """,
            (user_id,),
        )

        for cat in top_cats:
            cat_books = query_db(
                """
                SELECT b.*, c.name AS category_name, c.icon AS category_icon,
                       COUNT(DISTINCT l2.id) AS popularity
                FROM books b
                JOIN categories c ON b.category_id = c.id
                LEFT JOIN book_copies bc ON b.id = bc.book_id AND bc.is_deleted = 0
                LEFT JOIN loans l2 ON bc.id = l2.copy_id
                WHERE b.category_id = ? AND b.is_deleted = 0
                GROUP BY b.id
                ORDER BY popularity DESC, b.id DESC
                LIMIT 3
                """,
                (cat["category_id"],),
            )
            for b in cat_books:
                if b["id"] not in seen_book_ids and len(recommendations) < limit:
                    seen_book_ids.add(b["id"])
                    recommendations.append({
                        "book": dict(b),
                        "reason": f"Because you enjoy reading {cat['category_name']}",
                        "badge": "Category Match",
                    })

        # 3. Favorite Authors
        top_authors = query_db(
            """
            SELECT b.author, COUNT(*) AS count
            FROM loans l
            JOIN book_copies bc ON l.copy_id = bc.id
            JOIN books b ON bc.book_id = b.id
            WHERE l.user_id = ?
            GROUP BY b.author
            ORDER BY count DESC
            LIMIT 2
            """,
            (user_id,),
        )

        for author_row in top_authors:
            author_books = query_db(
                """
                SELECT b.*, c.name AS category_name, c.icon AS category_icon
                FROM books b
                JOIN categories c ON b.category_id = c.id
                WHERE b.author = ? AND b.is_deleted = 0
                GROUP BY b.id
                ORDER BY b.id DESC
                LIMIT 2
                """,
                (author_row["author"],),
            )
            for b in author_books:
                if b["id"] not in seen_book_ids and len(recommendations) < limit:
                    seen_book_ids.add(b["id"])
                    recommendations.append({
                        "book": dict(b),
                        "reason": f"More works by {author_row['author']}",
                        "badge": "Author Match",
                    })

    # 4. Fallback: Most Popular Books across the Library
    if len(recommendations) < limit:
        popular_books = query_db(
            """
            SELECT b.*, c.name AS category_name, c.icon AS category_icon,
                   COUNT(DISTINCT l.id) AS loan_count
            FROM books b
            JOIN categories c ON b.category_id = c.id
            LEFT JOIN book_copies bc ON b.id = bc.book_id AND bc.is_deleted = 0
            LEFT JOIN loans l ON bc.id = l.copy_id
            WHERE b.is_deleted = 0
            GROUP BY b.id
            ORDER BY loan_count DESC, b.id DESC
            LIMIT 6
            """
        )
        for b in popular_books:
            if b["id"] not in seen_book_ids and len(recommendations) < limit:
                seen_book_ids.add(b["id"])
                recommendations.append({
                    "book": dict(b),
                    "reason": "Top trending title among SmartShelf readers",
                    "badge": "Popular",
                })

    # 5. Fallback: Newest Arrivals
    if len(recommendations) < limit:
        recent_books = query_db(
            """
            SELECT b.*, c.name AS category_name, c.icon AS category_icon
            FROM books b
            JOIN categories c ON b.category_id = c.id
            WHERE b.is_deleted = 0
            ORDER BY b.id DESC
            LIMIT 6
            """
        )
        for b in recent_books:
            if b["id"] not in seen_book_ids and len(recommendations) < limit:
                seen_book_ids.add(b["id"])
                recommendations.append({
                    "book": dict(b),
                    "reason": "Recently added to the library collection",
                    "badge": "New Arrival",
                })

    return recommendations


def get_similar_books(book_id, limit=4):
    """Find similar books by category and author for a specific book detail page."""
    current = query_db("SELECT id, category_id, author FROM books WHERE id = ?", (book_id,), one=True)
    if not current:
        return []

    query = """
        SELECT b.*, c.name AS category_name, c.icon AS category_icon,
               CASE
                   WHEN b.author = ? THEN 'Same Author'
                   ELSE 'Same Category'
               END AS relation_reason
        FROM books b
        JOIN categories c ON b.category_id = c.id
        WHERE b.id != ? AND b.is_deleted = 0 AND (b.category_id = ? OR b.author = ?)
        LIMIT ?
    """
    return query_db(query, (current["author"], book_id, current["category_id"], current["author"], limit))
