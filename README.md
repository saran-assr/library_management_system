# SmartShelf — Intelligent Library Management System

[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue.svg)](https://python.org)
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask%203.1-black.svg)](https://flask.palletsprojects.com)
[![Database: SQLite](https://img.shields.io/badge/Database-SQLite3-003B57.svg)](https://sqlite.org)
[![Frontend: Bootstrap 5](https://img.shields.io/badge/UI-Bootstrap%205.3-7952B3.svg)](https://getbootstrap.com)
[![Tests: Pytest](https://img.shields.io/badge/Tests-30%20Passed-brightgreen.svg)](https://pytest.org)

SmartShelf is a modern, full-stack digital library management system built with Python (Flask), SQLite, Bootstrap 5, and Chart.js. Designed to solve the acute limitations of traditional library management registers, it provides real-time physical copy tracking, automated checkouts and checkins, FIFO reservation queues, dynamic overdue fine calculations, QR-code identification, explainable book recommendations, and institutional CSV reporting.

---

## 1. Traditional System Limitations vs. SmartShelf Solutions

| Traditional Library System Challenge | SmartShelf Intelligent Solution |
| :--- | :--- |
| **Manual paper registers & paper issue slips** | Automated digital checkout/checkin workstation with instant copy status tracking. |
| **Slow, inflexible book discovery** | Responsive catalog search by Title, Author, ISBN, Category, Availability, and Year. |
| **Duplicate accession and catalog records** | Strict database normalization, unique constraints, and foreign-key integrity enforcement. |
| **Simultaneous checkout conflicts** | Concurrency-safe atomic database transactions preventing double-issue of physical copies. |
| **Unfair reservation bottlenecks** | Automated First-In, First-Out (FIFO) reservation queue with automatic copy hold on return. |
| **Uncalculated and manual overdue fines** | Dynamic fine calculations ($1.00/day up to a $50 cap) evaluated without reliance on background daemons. |
| **Lack of copy-level granularity** | Independent tracking of book titles vs. physical copies with unique accession IDs and location racks. |
| **Zero visibility for librarians** | Interactive operational dashboards with Chart.js analytics and one-click institutional CSV exports. |

---

## 2. Technology Stack

- **Backend**: Python 3.14 with Flask 3.1.
- **Architecture**: Modular Service Layer (`services/`) separating business rules from route controllers.
- **Database**: SQLite3 with WAL mode, foreign keys (`PRAGMA foreign_keys = ON`), transactions, and parameterization.
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, and Bootstrap Icons.
- **Data Visualization**: Chart.js for circulation trends, category distribution, and status breakdowns.
- **Book Identification**: QR-code generation via Python `qrcode` (vector SVG) with camera/scanner support.
- **Security**: Werkzeug password hashing (scrypt/pbkdf2), session rotation, server-side role authorization, and CSRF protection.
- **Testing**: Pytest with automated isolated temporary SQLite fixtures.

---

## 3. Project Structure

```
library_management_system/
├── app.py                      # Application factory, routes, blueprints, error handlers
├── config.py                   # Centralized environments & business policy rules
├── database.py                 # SQLite connection manager, foreign-key enforcement, query helpers
├── schema.sql                  # Relational DDL (9 tables, constraints, indexes)
├── seed.py                     # Idempotent demo data seeder (accounts, books, loans, fines)
├── requirements.txt            # Python dependencies (Flask, pytest, qrcode, python-dotenv)
├── .env.example                # Environment template with secret keys and configurable policies
├── README.md                   # Complete architectural and setup documentation
├── instance/
│   └── library.db              # SQLite persistent database (created upon seed/run)
├── services/
│   ├── auth_service.py         # Login, registration, password hashing, session, role decorators
│   ├── book_service.py         # Book title and copy management, search, filters, pagination
│   ├── loan_service.py         # Issue, return, renewal, copy availability checks, loan policies
│   ├── reservation_service.py  # FIFO queue management, copy availability notification, auto-expiry
│   ├── fine_service.py         # Daily overdue calculation, caps, payment recording
│   ├── qr_service.py           # QR code generation for accession IDs (SVG/vector)
│   ├── recommendation_service.py # Explainable category & author-based recommendations
│   ├── report_service.py       # Metrics, Chart.js data aggregation, and CSV exports
│   ├── notification_service.py # In-app notification center dispatch and retrieval
│   └── audit_service.py        # Centralized audit logging for admin actions
├── templates/
│   ├── base.html               # Master layout with responsive sidebar, navbar, toasts, modals
│   ├── auth/                   # Login & registration templates
│   ├── admin/                  # Dashboard, book management, copies, issue/return, fines, reports
│   ├── member/                 # Member portal, active loans, reservations, notifications
│   ├── books/                  # Public/member searchable catalogue and detail views
│   └── profile/                # Profile editing and password updates
├── static/
│   ├── css/style.css           # Modern theme styling, dark navy palette, badges, responsive layout
│   └── js/
│       ├── main.js             # Real-time search, modals, toast triggers, scanner bridge
│       └── charts.js           # Chart.js initialization for librarian dashboard & reports
└── tests/
    ├── conftest.py             # Temporary SQLite fixtures and test clients
    ├── test_auth.py            # Authentication, authorization, session tests
    ├── test_books.py           # CRUD on books, unique ISBN, copy accession IDs
    ├── test_loans.py           # Issue, return, duplicate prevention, copy status tracking
    ├── test_reservations.py    # FIFO queue ordering, eligibility, cancellation
    ├── test_fines.py           # Overdue calculation, fine limits, payment handling
    └── test_qr_reports.py      # QR code generation, CSV export validation, recommendations
```

---

## 4. User Roles & Capabilities

### A. Librarian / Administrator
- **Dashboard**: Real-time stats (titles, copies, available, borrowed, overdue, fines, reservations).
- **Issue & Return Workstation**: Quick accession ID lookup, member verification, instant return processing.
- **Book & Copy Management**: Add/edit titles, track physical copies, assign location racks, print QR badges.
- **Member Management**: Monitor student quotas, review unpaid fines, suspend/activate borrowing privileges.
- **Reservation Fulfilment**: View FIFO queues, manage holds, review automated assignments.
- **Overdue Tracking & Fines**: Collect fine payments, issue official waivers, track financial balances.
- **Reports & CSV Export**: One-click exports for Inventory, Active Loans, Overdue Loans, Fines, and Members.
- **Security Audit Logs**: Track all administrative actions with timestamps and IP addresses.

### B. Student / Member
- **Book Catalogue**: Responsive search by title, author, or ISBN; filter by category and availability.
- **Copy Details**: View rack shelf location, physical condition, and real-time availability.
- **Reserve Books**: Place FIFO holds when all physical copies are checked out.
- **Loan Tracking**: View active loans with countdown to due dates and overdue fee warnings.
- **In-App Notification Centre**: Instant alerts for due dates, overdue fines, and reservation availability.
- **Account Settings**: Manage contact details and update account password.

---

## 5. Installation and Setup (Windows)

### Prerequisites
- Windows 10 or 11
- Python 3.10+ (tested on Python 3.14)
- Git (optional)

### Step 1: Open PowerShell in the Project Directory
```powershell
cd C:\Users\acer\Desktop\library_management_system
```

### Step 2: Create and Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Configure Environment (Optional)
Copy the default environment template:
```powershell
Copy-Item .env.example .env
```

### Step 5: Initialize and Seed Demo Database
Run the idempotent seed script. It populates categories, books, copies, loans, reservations, fines, and demo accounts:
```powershell
python seed.py
```
*(Note: `seed.py` can be safely executed repeatedly without creating duplicate records).*

---

## 6. Running and Deploying the Application

### Option A: 1-Click Windows Launcher (Easiest)
Simply double-click [`run.bat`](file:///c:/Users/acer/Desktop/library_management_system/run.bat) in the project folder. It checks the virtual environment, initializes the database if needed, and starts the production WSGI server automatically.

### Option B: Production Server with Waitress (Recommended)
Waitress is a production-grade multi-threaded WSGI server that runs natively on Windows:
```powershell
python wsgi.py
```

### Option C: Development Server
```powershell
python app.py
```

### Option D: Docker Container Deployment
Build and run the container:
```bash
docker build -t smartshelf .
docker run -p 5000:5000 smartshelf
```

### Option E: Vercel Cloud Deployment (Serverless)
SmartShelf includes built-in Vercel serverless configurations ([`vercel.json`](file:///c:/Users/acer/Desktop/library_management_system/vercel.json), [`api/index.py`](file:///c:/Users/acer/Desktop/library_management_system/api/index.py), and [`.vercelignore`](file:///c:/Users/acer/Desktop/library_management_system/.vercelignore)).

1. Push your project to a GitHub repository.
2. Sign in to [Vercel](https://vercel.com) and click **"Add New..." > "Project"**.
3. Import your GitHub repository.
4. Set Framework Preset to **"Other"** (Vercel automatically detects `vercel.json` and `api/index.py`).
5. Click **"Deploy"**.
Vercel will build the serverless functions and provide an instant live public URL (e.g. `https://smartshelf.vercel.app`).

Once running, navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)** (or your Vercel public URL)

---

## 7. Demo Login Credentials

For local demonstration and interview walkthroughs, the login screen includes **Quick Demo Login** buttons for 1-click authentication:

| Role | Email | Password | Scenario / Highlights |
| :--- | :--- | :--- | :--- |
| **Librarian / Admin** | `admin@smartshelf.local` | `Admin@1234` | Full access to circulation desk, reports, copies, audit logs. |
| **Student Member** | `john.doe@student.edu` | `Member@1234` | Active loan (*Clean Code*), borrowing history, recommendations. |
| **Student Member (Overdue)** | `jane.smith@student.edu` | `Member@1234` | Overdue loan (*1984*), accrued fine notice, warning badges. |
| **Student Member (Waitlist)** | `alex.turner@student.edu` | `Member@1234` | Position #1 in reservation queue, active loan (*Pragmatic Programmer*). |

---

## 8. Automated Testing

The project includes an automated test suite covering authentication, permissions, copy-level inventory, issue/return transactions, reservation FIFO ordering, fine calculation edge cases, QR generation, and CSV exports.

Execute the test suite using pytest:
```powershell
python -m pytest -v tests/
```

### Test Results Summary:
- **Total Tests**: 30
- **Passed**: 30 (100%)
- **Failed**: 0
- **Warnings**: 0
- **Database Safety**: Tests run against a temporary isolated database created via `tempfile` and do not alter `instance/library.db`.

---

## 9. Key Business Rules & Integrity Guarantees

1. **Copy Concurrency Protection**: Atomic database transactions guarantee that a physical copy cannot be checked out simultaneously by multiple members.
2. **Quota Enforcement**: Members are capped at `MAX_LOANS_PER_MEMBER` (default: 3 books).
3. **Fine Threshold Block**: Members with unpaid fines exceeding `MAX_UNPAID_FINE_LIMIT` (default: $20.00) are prevented from checking out additional materials.
4. **Idempotent Fines**: Fine calculations are assessed only once per loan, preventing duplicate fee records upon recalculation. Returned books are never charged for dates after their return date.
5. **Strict FIFO Reservations**: Returned copies automatically fulfill the next waiting member's hold, locking the copy for that specific member during the holding window (default: 3 days).
6. **Dynamic Overdue Calculations**: Overdue status is computed dynamically on query, ensuring accurate statuses even without a background scheduler.

---

## 10. Limitations & Future Enhancements

- **Email Dispatch**: Currently, overdue and reservation notifications are delivered via the in-app Notification Centre. SMTP email dispatch (SendGrid / Flask-Mail) can be plugged directly into `services/notification_service.py`.
- **Online Payment Gateway**: Fine payments are recorded by the librarian. Integration with Stripe or PayPal can be added for direct online student fine payments.
- **RFID Support**: Accession IDs and QR codes can be linked to RFID tag readers for contactless self-checkout kiosks.
