from services import book_service


def test_create_and_get_book(app):
    """Test creating a book and retrieving it by ID and ISBN."""
    with app.app_context():
        book_id, err = book_service.create_book(
            isbn="978-0131103627",
            title="The C Programming Language",
            author="Brian Kernighan, Dennis Ritchie",
            category_id=1,
            publisher="Prentice Hall",
            publication_year=1988,
            description="The definitive book on C programming.",
        )
        assert err is None
        assert book_id is not None

        book = book_service.get_book_by_id(book_id)
        assert book["title"] == "The C Programming Language"
        assert book["author"] == "Brian Kernighan, Dennis Ritchie"

        by_isbn = book_service.get_book_by_isbn("978-0131103627")
        assert by_isbn["id"] == book_id


def test_duplicate_isbn_rejection(app):
    """Test that creating a book with duplicate ISBN fails."""
    with app.app_context():
        _, err = book_service.create_book(
            isbn="978-0132350884",  # Already exists in conftest (Clean Code)
            title="Duplicate Title",
            author="Someone Else",
            category_id=1,
        )
        assert err is not None
        assert "already exists" in err.lower()


def test_update_book(app):
    """Test updating existing book information."""
    with app.app_context():
        ok, err = book_service.update_book(
            book_id=1,
            isbn="978-0132350884",
            title="Clean Code (Updated Edition)",
            author="Robert C. Martin",
            category_id=1,
        )
        assert ok is True
        assert err is None

        book = book_service.get_book_by_id(1)
        assert book["title"] == "Clean Code (Updated Edition)"


def test_book_search_and_filter(app):
    """Test case-insensitive book searching and filtering."""
    with app.app_context():
        # Search by partial title (case insensitive)
        books, pag = book_service.get_books(search="clean")
        assert len(books) >= 1
        assert any(b["title"] == "Clean Code" for b in books)

        # Search by author
        books, _ = book_service.get_books(search="orwell")
        assert len(books) == 1
        assert books[0]["title"] == "1984"

        # Search by ISBN
        books, _ = book_service.get_books(search="0451524935")
        assert len(books) == 1
        assert books[0]["title"] == "1984"

        # Filter by Category
        books, _ = book_service.get_books(category_id=1)
        assert all(b["category_id"] == 1 for b in books)


def test_add_copy_and_duplicate_accession_id(app):
    """Test adding a physical copy and rejecting duplicate accession IDs."""
    with app.app_context():
        copy_id, err = book_service.add_copy(
            book_id=1,
            accession_id="ACC-CC-03",
            location_rack="Rack A-3",
            condition="New",
        )
        assert err is None
        assert copy_id is not None

        copy = book_service.get_copy_by_accession_id("ACC-CC-03")
        assert copy is not None
        assert copy["location_rack"] == "Rack A-3"

        # Duplicate Accession ID attempt
        _, err_dup = book_service.add_copy(
            book_id=2,
            accession_id="ACC-CC-03",
        )
        assert err_dup is not None
        assert "already assigned" in err_dup.lower()


def test_delete_copy(app):
    """Test deleting an available copy."""
    with app.app_context():
        copy_id, _ = book_service.add_copy(book_id=2, accession_id="ACC-TEMP-01")
        ok, err = book_service.delete_copy(copy_id)
        assert ok is True
        assert err is None

        # Verify not returned in active list
        copies = book_service.get_copies_for_book(2)
        assert not any(c["accession_id"] == "ACC-TEMP-01" for c in copies)
