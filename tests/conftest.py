import os
import tempfile
import pytest
from app import create_app
from config import TestingConfig
from database import init_db, create_connection
from services.auth_service import hash_password


class TestConfig(TestingConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key-12345"


@pytest.fixture
def app_and_db():
    """Create a temporary test database and configured Flask test application."""
    # Create temp database file
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    # Initialize schema
    init_db(db_path)

    # Seed baseline fixture data
    conn = create_connection(db_path)
    try:
        # Categories
        conn.execute("INSERT INTO categories (id, name, icon) VALUES (1, 'Computer Science', 'bi-code-slash')")
        conn.execute("INSERT INTO categories (id, name, icon) VALUES (2, 'Literature', 'bi-book')")

        # Users
        admin_hash = hash_password("Admin@1234")
        member_hash = hash_password("Member@1234")
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash, role, status, max_loans) VALUES (1, 'Test Admin', 'admin@test.com', ?, 'admin', 'active', 10)",
            (admin_hash,)
        )
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash, role, status, max_loans) VALUES (2, 'Member One', 'member1@test.com', ?, 'member', 'active', 3)",
            (member_hash,)
        )
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash, role, status, max_loans) VALUES (3, 'Member Two', 'member2@test.com', ?, 'member', 'active', 3)",
            (member_hash,)
        )

        # Books
        conn.execute(
            """
            INSERT INTO books (id, isbn, title, author, category_id, publication_year, is_deleted)
            VALUES (1, '978-0132350884', 'Clean Code', 'Robert C. Martin', 1, 2008, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO books (id, isbn, title, author, category_id, publication_year, is_deleted)
            VALUES (2, '978-0451524935', '1984', 'George Orwell', 2, 1949, 0)
            """
        )

        # Book Copies
        conn.execute(
            "INSERT INTO book_copies (id, book_id, accession_id, status, location_rack, is_deleted) VALUES (1, 1, 'ACC-CC-01', 'available', 'Rack A', 0)"
        )
        conn.execute(
            "INSERT INTO book_copies (id, book_id, accession_id, status, location_rack, is_deleted) VALUES (2, 1, 'ACC-CC-02', 'available', 'Rack A', 0)"
        )
        conn.execute(
            "INSERT INTO book_copies (id, book_id, accession_id, status, location_rack, is_deleted) VALUES (3, 2, 'ACC-1984-01', 'available', 'Rack B', 0)"
        )

        conn.commit()
    finally:
        conn.close()

    # Configure App
    test_config = TestConfig()
    test_config.DATABASE_PATH = db_path
    app = create_app(test_config)

    yield app, db_path

    # Teardown
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def app(app_and_db):
    app_instance, _ = app_and_db
    return app_instance


@pytest.fixture
def client(app):
    return app.test_client()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, email="admin@test.com", password="Admin@1234"):
        return self._client.post(
            "/auth/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def logout(self):
        return self._client.get("/auth/logout", follow_redirects=True)


@pytest.fixture
def auth(client):
    return AuthActions(client)
