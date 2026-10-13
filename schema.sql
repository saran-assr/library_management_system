-- SmartShelf SQLite Schema Definition
-- Foreign keys must be enabled on every connection: PRAGMA foreign_keys = ON;

PRAGMA foreign_keys = ON;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'member')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'suspended')),
    phone TEXT,
    max_loans INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Categories Table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL COLLATE NOCASE,
    description TEXT,
    icon TEXT DEFAULT 'bi-bookmark'
);

-- 3. Books Table (Titles)
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL COLLATE NOCASE,
    author TEXT NOT NULL COLLATE NOCASE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    publisher TEXT,
    publication_year INTEGER,
    description TEXT,
    cover_image_url TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Physical Book Copies Table
CREATE TABLE IF NOT EXISTS book_copies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    accession_id TEXT UNIQUE NOT NULL COLLATE NOCASE,
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'borrowed', 'reserved', 'maintenance', 'lost')),
    location_rack TEXT,
    condition TEXT NOT NULL DEFAULT 'Good',
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Loans Table
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id INTEGER NOT NULL REFERENCES book_copies(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    issued_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    issue_date TEXT NOT NULL,       -- ISO YYYY-MM-DD
    due_date TEXT NOT NULL,         -- ISO YYYY-MM-DD
    return_date TEXT,               -- ISO YYYY-MM-DD (NULL if unreturned)
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'returned', 'overdue')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Reservations Table
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    queue_position INTEGER NOT NULL,
    reserved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'waiting' CHECK(status IN ('waiting', 'available_for_pickup', 'fulfilled', 'cancelled', 'expired')),
    hold_until TEXT,                -- ISO YYYY-MM-DD
    assigned_copy_id INTEGER REFERENCES book_copies(id) ON DELETE SET NULL,
    notified_at TIMESTAMP
);

-- 7. Fines Table
CREATE TABLE IF NOT EXISTS fines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER UNIQUE NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount REAL NOT NULL CHECK(amount >= 0),
    status TEXT NOT NULL DEFAULT 'unpaid' CHECK(status IN ('unpaid', 'paid', 'waived')),
    calculated_days INTEGER NOT NULL DEFAULT 0,
    paid_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Notifications Table
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'info' CHECK(type IN ('info', 'warning', 'success', 'danger')),
    is_read INTEGER NOT NULL DEFAULT 0,
    link TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
CREATE INDEX IF NOT EXISTS idx_books_category ON books(category_id);

CREATE INDEX IF NOT EXISTS idx_copies_accession ON book_copies(accession_id);
CREATE INDEX IF NOT EXISTS idx_copies_book_status ON book_copies(book_id, status);

CREATE INDEX IF NOT EXISTS idx_loans_active ON loans(user_id, status);
CREATE INDEX IF NOT EXISTS idx_loans_copy ON loans(copy_id, status);
CREATE INDEX IF NOT EXISTS idx_loans_due_date ON loans(due_date);

CREATE INDEX IF NOT EXISTS idx_reservations_queue ON reservations(book_id, status, queue_position);
CREATE INDEX IF NOT EXISTS idx_fines_user_status ON fines(user_id, status);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
