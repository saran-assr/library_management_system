import os
import sys
from datetime import date, timedelta
from database import create_connection, init_db, query_db, execute_db
from services.auth_service import hash_password
from config import Config


def seed_database(db_path=None):
    """
    Idempotent database seeder. Populates realistic initial demo data
    including users, categories, books, physical copies, loans, reservations,
    and notifications. Running multiple times will NOT create duplicate records.
    """
    print(f"Initializing database at: {db_path or Config.DATABASE_PATH}")
    init_db(db_path)
    conn = create_connection(db_path)

    try:
        # 1. Seed Categories
        categories = [
            ("Computer Science & Engineering", "Software architecture, algorithms, and web technologies.", "bi-code-slash"),
            ("Data Science & AI", "Machine learning, statistical modeling, and data engineering.", "bi-cpu"),
            ("Literature & Classic Fiction", "Masterpieces of world and classic literature.", "bi-book"),
            ("Business & Management", "Entrepreneurship, strategy, economics, and leadership.", "bi-briefcase"),
            ("Science & Mathematics", "Physics, mathematics, and foundational sciences.", "bi-calculator"),
            ("History & Philosophy", "World history, critical thinking, and philosophical inquiries.", "bi-compass"),
        ]

        cat_map = {}
        for name, desc, icon in categories:
            existing = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
            if existing:
                cat_map[name] = existing["id"]
            else:
                cur = conn.execute("INSERT INTO categories (name, description, icon) VALUES (?, ?, ?)", (name, desc, icon))
                cat_map[name] = cur.lastrowid
        conn.commit()

        # 2. Seed Users
        # Passwords hashed with werkzeug
        users = [
            ("Librarian Administrator", "admin@smartshelf.local", "Admin@1234", "admin", "active", "555-0100", 10),
            ("John Doe", "john.doe@student.edu", "Member@1234", "member", "active", "555-0101", 3),
            ("Jane Smith", "jane.smith@student.edu", "Member@1234", "member", "active", "555-0102", 3),
            ("Alex Turner", "alex.turner@student.edu", "Member@1234", "member", "active", "555-0103", 3),
        ]

        user_map = {}
        for name, email, pw, role, status, phone, max_loans in users:
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                user_map[email] = existing["id"]
            else:
                pw_hash = hash_password(pw)
                cur = conn.execute(
                    """
                    INSERT INTO users (name, email, password_hash, role, status, phone, max_loans)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, email, pw_hash, role, status, phone, max_loans),
                )
                user_map[email] = cur.lastrowid
        conn.commit()

        # 3. Seed Books
        books = [
            (
                "978-0132350884", "Clean Code: A Handbook of Agile Software Craftsmanship",
                "Robert C. Martin", "Computer Science & Engineering", "Prentice Hall", 2008,
                "Even bad code can function. But if code isn't clean, it can bring a development organization to its knees.",
                "https://images.unsplash.com/photo-1532012164546-f432f2e3777a?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0201616224", "The Pragmatic Programmer: Your Journey to Mastery",
                "David Thomas, Andrew Hunt", "Computer Science & Engineering", "Addison-Wesley", 1999,
                "One of the most significant books on software development, covering process, code architecture, and mindset.",
                "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0596517748", "JavaScript: The Good Parts",
                "Douglas Crockford", "Computer Science & Engineering", "O'Reilly Media", 2008,
                "An authoritative guide peeling away the clumsy features to reveal JavaScript's elegant functional core.",
                "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-1449369415", "Introducing Python: Modern Computing in Simple Packages",
                "Bill Lubanovic", "Computer Science & Engineering", "O'Reilly Media", 2014,
                "A thorough introduction to Python 3, from fundamentals to web services and data parsing.",
                "https://images.unsplash.com/photo-1516979187457-637abb4f9353?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0262033848", "Introduction to Algorithms (CLRS)",
                "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
                "Computer Science & Engineering", "MIT Press", 2009,
                "The comprehensive textbook covering fundamental algorithmic techniques and analysis.",
                "https://images.unsplash.com/photo-1509228468518-180dd4864904?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-1491957660", "Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow",
                "Aurélien Géron", "Data Science & AI", "O'Reilly Media", 2019,
                "A practical guide to building intelligent systems using concrete examples and end-to-end projects.",
                "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0131429383", "Artificial Intelligence: A Modern Approach",
                "Stuart Russell, Peter Norvig", "Data Science & AI", "Pearson", 2020,
                "The global reference textbook in the field of Artificial Intelligence.",
                "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0451524935", "1984",
                "George Orwell", "Literature & Classic Fiction", "Signet Classic", 1949,
                "The haunting vision of a totalitarian regime where Big Brother is always watching.",
                "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0141439518", "Pride and Prejudice",
                "Jane Austen", "Literature & Classic Fiction", "Penguin Classics", 1813,
                "A witty romantic comedy exploring social status, misunderstandings, and marriage in 19th-century England.",
                "https://images.unsplash.com/photo-1476275466078-4007374efbbe?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0061120084", "To Kill a Mockingbird",
                "Harper Lee", "Literature & Classic Fiction", "Harper Perennial", 1960,
                "The unforgettable Pulitzer Prize-winning masterpiece set in the American South.",
                "https://images.unsplash.com/photo-1519682337058-a94d519337bc?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0062316097", "Sapiens: A Brief History of Humankind",
                "Yuval Noah Harari", "History & Philosophy", "Harper", 2015,
                "An audacious narrative tracing the evolution of humans from archaic forages to rulers of the planet.",
                "https://images.unsplash.com/photo-1461360370896-922624d12aa1?auto=format&fit=crop&w=400&q=80"
            ),
            (
                "978-0062457714", "The Subtle Art of Not Giving a F*ck",
                "Mark Manson", "Business & Management", "HarperOne", 2016,
                "A counterintuitive approach to living a good life by prioritizing what truly matters.",
                "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?auto=format&fit=crop&w=400&q=80"
            ),
        ]

        book_map = {}
        for isbn, title, author, cat_name, pub, year, desc, img in books:
            cat_id = cat_map[cat_name]
            existing = conn.execute("SELECT id FROM books WHERE isbn = ?", (isbn,)).fetchone()
            if existing:
                book_map[isbn] = existing["id"]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO books (isbn, title, author, category_id, publisher, publication_year, description, cover_image_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (isbn, title, author, cat_id, pub, year, desc, img),
                )
                book_map[isbn] = cur.lastrowid
        conn.commit()

        # 4. Seed Physical Copies with Unique Accession IDs
        copies = [
            ("978-0132350884", "ACC-CS101-01", "Rack A-1", "Good", "available"),
            ("978-0132350884", "ACC-CS101-02", "Rack A-1", "Good", "borrowed"),
            ("978-0201616224", "ACC-CS102-01", "Rack A-2", "New", "available"),
            ("978-0201616224", "ACC-CS102-02", "Rack A-2", "Good", "borrowed"),
            ("978-0596517748", "ACC-CS103-01", "Rack A-3", "Good", "available"),
            ("978-1449369415", "ACC-CS104-01", "Rack A-4", "New", "available"),
            ("978-0262033848", "ACC-CS105-01", "Rack B-1", "Good", "available"),
            ("978-0262033848", "ACC-CS105-02", "Rack B-1", "Fair", "available"),
            ("978-1491957660", "ACC-DS201-01", "Rack C-1", "New", "available"),
            ("978-0131429383", "ACC-DS202-01", "Rack C-2", "Good", "available"),
            ("978-0451524935", "ACC-LIT301-01", "Rack D-1", "Fair", "borrowed"),
            ("978-0141439518", "ACC-LIT302-01", "Rack D-2", "Good", "available"),
            ("978-0061120084", "ACC-LIT303-01", "Rack D-3", "Good", "available"),
            ("978-0062316097", "ACC-HIS401-01", "Rack E-1", "New", "available"),
            ("978-0062457714", "ACC-BUS501-01", "Rack F-1", "Good", "available"),
        ]

        copy_map = {}
        for isbn, acc_id, rack, cond, status in copies:
            b_id = book_map[isbn]
            existing = conn.execute("SELECT id FROM book_copies WHERE accession_id = ?", (acc_id,)).fetchone()
            if existing:
                copy_map[acc_id] = existing["id"]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO book_copies (book_id, accession_id, location_rack, condition, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (b_id, acc_id, rack, cond, status),
                )
                copy_map[acc_id] = cur.lastrowid
        conn.commit()

        # 5. Seed Historical and Active Loans
        today = date.today()
        loans_data = [
            # Active normal loan: John Doe borrowed Clean Code copy 2, due in 7 days
            ("ACC-CS101-02", "john.doe@student.edu", (today - timedelta(days=7)).isoformat(), (today + timedelta(days=7)).isoformat(), None, "active"),
            # Overdue loan: Jane Smith borrowed 1984 copy 1, due 5 days ago!
            ("ACC-LIT301-01", "jane.smith@student.edu", (today - timedelta(days=19)).isoformat(), (today - timedelta(days=5)).isoformat(), None, "overdue"),
            # Active loan: Alex Turner borrowed Pragmatic Programmer copy 2, due in 3 days
            ("ACC-CS102-02", "alex.turner@student.edu", (today - timedelta(days=11)).isoformat(), (today + timedelta(days=3)).isoformat(), None, "active"),
            # Historical returned loan: John Doe previously borrowed and returned Python book
            ("ACC-CS104-01", "john.doe@student.edu", (today - timedelta(days=30)).isoformat(), (today - timedelta(days=16)).isoformat(), (today - timedelta(days=18)).isoformat(), "returned"),
        ]

        admin_id = user_map["admin@smartshelf.local"]
        for acc_id, member_email, issue_d, due_d, ret_d, st in loans_data:
            c_id = copy_map[acc_id]
            m_id = user_map[member_email]
            existing = conn.execute(
                "SELECT id FROM loans WHERE copy_id = ? AND user_id = ? AND issue_date = ?",
                (c_id, m_id, issue_d),
            ).fetchone()
            if not existing:
                cur = conn.execute(
                    """
                    INSERT INTO loans (copy_id, user_id, issued_by, issue_date, due_date, return_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (c_id, m_id, admin_id, issue_d, due_d, ret_d, st),
                )
                loan_id = cur.lastrowid

                # If overdue loan, add fine record
                if st == "overdue":
                    fine_cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO fines (loan_id, user_id, amount, status, calculated_days)
                        VALUES (?, ?, 5.00, 'unpaid', 5)
                        """,
                        (loan_id, m_id),
                    )
        conn.commit()

        # 6. Seed Reservations
        # Alex Turner reserves Clean Code (which is in high demand)
        clean_code_id = book_map["978-0132350884"]
        alex_id = user_map["alex.turner@student.edu"]
        existing_res = conn.execute(
            "SELECT id FROM reservations WHERE book_id = ? AND user_id = ?",
            (clean_code_id, alex_id),
        ).fetchone()
        if not existing_res:
            conn.execute(
                """
                INSERT INTO reservations (book_id, user_id, queue_position, status)
                VALUES (?, ?, 1, 'waiting')
                """,
                (clean_code_id, alex_id),
            )
            conn.commit()

        # 7. Seed Notifications
        notifications = [
            (user_map["jane.smith@student.edu"], "Loan Overdue Notice", "Your loan for '1984' is 5 days overdue. Please return it to avoid accumulating further fines.", "warning", "/member/loans"),
            (user_map["alex.turner@student.edu"], "Reservation Confirmed", "You are #1 in queue for 'Clean Code'. You will be notified as soon as a copy is returned.", "info", "/member/reservations"),
            (user_map["john.doe@student.edu"], "Welcome to SmartShelf", "Welcome to the library! You can borrow up to 3 books simultaneously.", "success", "/books"),
        ]
        for u_id, title, msg, n_type, link in notifications:
            existing_n = conn.execute(
                "SELECT id FROM notifications WHERE user_id = ? AND title = ?",
                (u_id, title),
            ).fetchone()
            if not existing_n:
                conn.execute(
                    "INSERT INTO notifications (user_id, title, message, type, link) VALUES (?, ?, ?, ?, ?)",
                    (u_id, title, msg, n_type, link),
                )
        conn.commit()

        # 8. Seed Initial Audit Logs
        conn.execute(
            """
            INSERT OR IGNORE INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
            VALUES (?, 'SYSTEM_INIT', 'database', '1', 'Initial database schema and demo seed populated successfully.', '127.0.0.1')
            """,
            (admin_id,),
        )
        conn.commit()

        print("Database seeded successfully with demo catalog, accounts, loans, and reservations.")

    finally:
        conn.close()


if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else None
    seed_database(db_file)
