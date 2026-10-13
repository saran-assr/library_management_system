import os
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, Response, abort
)
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config, config_by_name
from database import close_db, init_db, query_db, execute_db
from services import (
    auth_service, book_service, loan_service,
    reservation_service, fine_service, notification_service,
    recommendation_service, report_service, qr_service, audit_service
)


def create_app(config_class=None):
    """Application factory for SmartShelf."""
    app = Flask(__name__)

    # Determine configuration
    if config_class is None:
        env_name = os.getenv("FLASK_ENV", "development").lower()
        config_class = config_by_name.get(env_name, Config)

    app.config.from_object(config_class)

    # Register database teardown
    app.teardown_appcontext(close_db)

    # ----------------------------------------------------
    # Request Hooks & Security
    # ----------------------------------------------------
    @app.before_request
    def before_request_hook():
        # CSRF Protection on modifying HTTP methods (skip in testing if disabled)
        if not app.config.get("TESTING", False):
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                # Exclude static or explicit webhooks if any
                auth_service.validate_csrf_token()

    # ----------------------------------------------------
    # Context Processors & Global Template Variables
    # ----------------------------------------------------
    @app.context_processor
    def inject_globals():
        user_id = session.get("user_id")
        unread_count = 0
        if user_id:
            unread_count = notification_service.get_unread_count(user_id)

        return {
            "csrf_token": auth_service.generate_csrf_token,
            "unread_notifs_count": unread_count,
            "currency_symbol": app.config.get("CURRENCY_SYMBOL", "$"),
            "now_year": datetime.now().year,
        }

    # ----------------------------------------------------
    # Root / Landing Route
    # ----------------------------------------------------
    @app.route("/")
    def index():
        role = session.get("user_role")
        if role == "admin":
            return redirect(url_for("admin.dashboard"))
        elif role == "member":
            return redirect(url_for("member.dashboard"))
        return redirect(url_for("books.catalogue"))

    # ----------------------------------------------------
    # Auth Routes
    # ----------------------------------------------------
    from flask import Blueprint
    auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("user_id"):
            return redirect(url_for("index"))

        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")

            user, error = auth_service.authenticate(email, password)
            if error:
                flash(error, "danger")
                return render_template("auth/login.html"), 401

            auth_service.login_user(user)
            flash(f"Welcome back, {user['name']}!", "success")

            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)

            if user["role"] == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("member.dashboard"))

        return render_template("auth/login.html")

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if session.get("user_id"):
            return redirect(url_for("index"))

        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")
            phone = request.form.get("phone")

            user_id, err = auth_service.register_member(name, email, password, phone)
            if err:
                flash(err, "danger")
                return render_template("auth/register.html"), 400

            flash("Registration successful! You can now sign in to your student account.", "success")
            return redirect(url_for("auth.login"))

        return render_template("auth/register.html")

    @auth_bp.route("/logout")
    def logout():
        auth_service.logout_user()
        flash("You have been signed out successfully.", "info")
        return redirect(url_for("auth.login"))

    app.register_blueprint(auth_bp)

    # ----------------------------------------------------
    # Books Blueprint
    # ----------------------------------------------------
    books_bp = Blueprint("books", __name__, url_prefix="/books")

    @books_bp.route("/")
    def catalogue():
        search = request.args.get("search")
        category_id = request.args.get("category_id")
        availability = request.args.get("availability")
        sort_by = request.args.get("sort_by", "title")
        page = request.args.get("page", 1, type=int)

        books_list, pagination = book_service.get_books(
            search=search,
            category_id=category_id,
            availability=availability,
            sort_by=sort_by,
            page=page,
            per_page=12,
        )
        categories = book_service.get_categories()

        return render_template(
            "books/catalogue.html",
            books=books_list,
            pagination=pagination,
            categories=categories,
            search_query=search,
            selected_category=category_id,
            selected_availability=availability,
            sort_by=sort_by,
        )

    @books_bp.route("/<int:book_id>")
    def book_detail(book_id):
        book = book_service.get_book_by_id(book_id)
        if not book:
            flash("Book not found.", "danger")
            return redirect(url_for("books.catalogue"))

        copies = book_service.get_copies_for_book(book_id)
        similar = recommendation_service.get_similar_books(book_id)

        return render_template(
            "books/detail.html",
            book=book,
            copies=copies,
            similar_books=similar,
        )

    @books_bp.route("/qr/<accession_id>")
    def view_qr(accession_id):
        copy = book_service.get_copy_by_accession_id(accession_id)
        if not copy:
            abort(404, description="Accession ID not found")

        svg_content = qr_service.generate_qr_svg(copy["accession_id"])
        return Response(svg_content, mimetype="image/svg+xml")

    app.register_blueprint(books_bp)

    # ----------------------------------------------------
    # Admin Blueprint
    # ----------------------------------------------------
    admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

    @admin_bp.before_request
    def require_admin_role():
        if not session.get("user_id"):
            flash("Please sign in as an administrator.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if session.get("user_role") != "admin":
            flash("Unauthorized. Administrator access required.", "danger")
            return redirect(url_for("member.dashboard"))

    @admin_bp.route("/dashboard")
    def dashboard():
        loan_service.sync_overdue_statuses()
        reservation_service.check_and_expire_reservations()

        stats = report_service.get_dashboard_stats()
        chart_data = report_service.get_chart_data()

        return render_template("admin/dashboard.html", stats=stats, chart_data=chart_data)

    @admin_bp.route("/books")
    def books():
        search = request.args.get("search")
        category_id = request.args.get("category_id")
        sort_by = request.args.get("sort_by", "title")
        page = request.args.get("page", 1, type=int)

        books_list, pagination = book_service.get_books(
            search=search,
            category_id=category_id,
            sort_by=sort_by,
            page=page,
            per_page=15,
        )
        categories = book_service.get_categories()

        return render_template(
            "admin/books.html",
            books=books_list,
            pagination=pagination,
            categories=categories,
            search_query=search,
            selected_category=category_id,
            sort_by=sort_by,
        )

    @admin_bp.route("/books/new", methods=["POST"])
    def create_book():
        isbn = request.form.get("isbn")
        title = request.form.get("title")
        author = request.form.get("author")
        category_id = request.form.get("category_id")
        publisher = request.form.get("publisher")
        publication_year = request.form.get("publication_year") or None
        description = request.form.get("description")
        cover_image_url = request.form.get("cover_image_url")

        book_id, err = book_service.create_book(
            isbn=isbn, title=title, author=author, category_id=category_id,
            publisher=publisher, publication_year=publication_year,
            description=description, cover_image_url=cover_image_url
        )
        if err:
            flash(err, "danger")
        else:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="CREATE_BOOK",
                entity_type="book",
                entity_id=book_id,
                details=f"Added book '{title}' (ISBN: {isbn})"
            )
            flash(f"Book '{title}' added successfully! You can now add physical copies.", "success")

        return redirect(url_for("admin.books"))

    @admin_bp.route("/books/<int:book_id>/edit", methods=["POST"])
    def edit_book(book_id):
        isbn = request.form.get("isbn")
        title = request.form.get("title")
        author = request.form.get("author")
        category_id = request.form.get("category_id")
        publisher = request.form.get("publisher")
        publication_year = request.form.get("publication_year") or None
        description = request.form.get("description")
        cover_image_url = request.form.get("cover_image_url")

        ok, err = book_service.update_book(
            book_id=book_id, isbn=isbn, title=title, author=author,
            category_id=category_id, publisher=publisher,
            publication_year=publication_year, description=description,
            cover_image_url=cover_image_url
        )
        if err:
            flash(err, "danger")
        else:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="UPDATE_BOOK",
                entity_type="book",
                entity_id=book_id,
                details=f"Updated details for book '{title}'"
            )
            flash(f"Book '{title}' updated successfully.", "success")

        return redirect(url_for("admin.books"))

    @admin_bp.route("/books/<int:book_id>/delete", methods=["POST"])
    def delete_book(book_id):
        ok, err = book_service.delete_book(book_id)
        if err:
            flash(err, "danger")
        else:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="DELETE_BOOK",
                entity_type="book",
                entity_id=book_id,
                details=f"Deleted book title ID {book_id}"
            )
            flash("Book deleted successfully.", "success")

        return redirect(url_for("admin.books"))

    @admin_bp.route("/books/<int:book_id>/copies")
    def book_copies(book_id):
        book = book_service.get_book_by_id(book_id)
        if not book:
            flash("Book not found.", "danger")
            return redirect(url_for("admin.books"))

        copies = book_service.get_copies_for_book(book_id)
        return render_template("admin/book_copies.html", book=book, copies=copies)

    @admin_bp.route("/books/<int:book_id>/copies/new", methods=["POST"])
    def add_copy(book_id):
        accession_id = request.form.get("accession_id")
        location_rack = request.form.get("location_rack")
        condition = request.form.get("condition", "Good")

        copy_id, err = book_service.add_copy(book_id, accession_id, location_rack, condition)
        if err:
            flash(err, "danger")
        else:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="ADD_COPY",
                entity_type="book_copy",
                entity_id=copy_id,
                details=f"Added physical copy {accession_id} for book ID {book_id}"
            )
            flash(f"Physical copy '{accession_id}' added successfully.", "success")

        return redirect(url_for("admin.book_copies", book_id=book_id))

    @admin_bp.route("/copies/<int:copy_id>/delete", methods=["POST"])
    def delete_copy(copy_id):
        copy = query_db("SELECT * FROM book_copies WHERE id = ?", (copy_id,), one=True)
        if not copy:
            flash("Copy not found.", "danger")
            return redirect(url_for("admin.books"))

        book_id = copy["book_id"]
        ok, err = book_service.delete_copy(copy_id)
        if err:
            flash(err, "danger")
        else:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="DELETE_COPY",
                entity_type="book_copy",
                entity_id=copy_id,
                details=f"Removed physical copy {copy['accession_id']}"
            )
            flash(f"Physical copy '{copy['accession_id']}' removed.", "success")

        return redirect(url_for("admin.book_copies", book_id=book_id))

    @admin_bp.route("/members")
    def members():
        members_data = query_db(
            """
            SELECT u.*,
                   COUNT(DISTINCT CASE WHEN l.status IN ('active', 'overdue') THEN l.id END) AS active_loans,
                   COALESCE(SUM(CASE WHEN f.status = 'unpaid' THEN f.amount ELSE 0 END), 0.0) AS unpaid_fines
            FROM users u
            LEFT JOIN loans l ON u.id = l.user_id
            LEFT JOIN fines f ON u.id = f.user_id
            WHERE u.role = 'member'
            GROUP BY u.id
            ORDER BY u.name ASC
            """
        )
        return render_template("admin/members.html", members=members_data)

    @admin_bp.route("/members/<int:user_id>/toggle-status", methods=["POST"])
    def toggle_member_status(user_id):
        user = auth_service.get_user_by_id(user_id)
        if not user or user["role"] != "member":
            flash("Member not found.", "danger")
            return redirect(url_for("admin.members"))

        new_status = "suspended" if user["status"] == "active" else "active"
        execute_db("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))

        audit_service.log_action(
            user_id=session.get("user_id"),
            action="UPDATE_MEMBER_STATUS",
            entity_type="user",
            entity_id=user_id,
            details=f"Changed account status for {user['name']} to '{new_status}'"
        )
        flash(f"Status for {user['name']} updated to {new_status.title()}.", "success")
        return redirect(url_for("admin.members"))

    @admin_bp.route("/issue-return")
    def issue_return():
        return render_template("admin/issue_return.html")

    @admin_bp.route("/issue", methods=["POST"])
    def issue_book():
        accession_id = request.form.get("accession_id")
        member_query = request.form.get("member_query", "").strip()
        duration_days = request.form.get("duration_days", 14, type=int)
        notes = request.form.get("notes")

        # Resolve member query (either numeric ID or email)
        member = None
        if member_query.isdigit():
            member = auth_service.get_user_by_id(int(member_query))
        if not member:
            member = auth_service.get_user_by_email(member_query)

        if not member:
            flash(f"Member '{member_query}' could not be identified.", "danger")
            return redirect(url_for("admin.issue_return"))

        loan_id, err = loan_service.issue_book(
            accession_id=accession_id,
            user_id=member["id"],
            issued_by_id=session.get("user_id"),
            duration_days=duration_days,
            notes=notes,
        )
        if err:
            flash(err, "danger")
        else:
            flash(f"Book successfully issued to {member['name']}! Due in {duration_days} days.", "success")

        return redirect(url_for("admin.issue_return"))

    @admin_bp.route("/return", methods=["POST"])
    def return_book():
        accession_id = request.form.get("accession_id")
        notes = request.form.get("notes")

        result, err = loan_service.return_book(
            accession_id=accession_id,
            returned_by_id=session.get("user_id"),
            notes=notes,
        )
        if err:
            flash(err, "danger")
        else:
            msg = f"'{result['book_title']}' ({result['accession_id']}) returned successfully by {result['member_name']}."
            if result["overdue_days"] > 0:
                msg += f" Note: Loan was {result['overdue_days']} days late. Fine of ${result['fine_amount']:.2f} assessed."
            if result["reserved_for_next"]:
                msg += " Book copy has been placed ON HOLD for next member in reservation queue!"
            flash(msg, "warning" if result["overdue_days"] > 0 else "success")

        return redirect(url_for("admin.issue_return"))

    @admin_bp.route("/reservations")
    def reservations():
        reservation_service.check_and_expire_reservations()
        res_list = reservation_service.get_all_active_reservations()
        return render_template("admin/reservations.html", reservations=res_list)

    @admin_bp.route("/reservations/<int:res_id>/cancel", methods=["POST"])
    def cancel_reservation(res_id):
        ok, err = reservation_service.cancel_reservation(res_id)
        if err:
            flash(err, "danger")
        else:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="CANCEL_RESERVATION",
                entity_type="reservation",
                entity_id=res_id,
                details=f"Admin cancelled reservation ID {res_id}"
            )
            flash("Reservation cancelled successfully.", "success")
        return redirect(url_for("admin.reservations"))

    @admin_bp.route("/fines")
    def fines():
        status = request.args.get("status")
        fines_list = fine_service.get_fines(status=status)
        return render_template("admin/fines.html", fines=fines_list, selected_status=status)

    @admin_bp.route("/fines/<int:fine_id>/pay", methods=["POST"])
    def pay_fine(fine_id):
        notes = request.form.get("notes")
        ok = fine_service.pay_fine(fine_id, admin_id=session.get("user_id"), notes=notes)
        if ok:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="PAY_FINE",
                entity_type="fine",
                entity_id=fine_id,
                details=f"Admin recorded payment for fine ID {fine_id}"
            )
            flash("Fine payment recorded successfully.", "success")
        else:
            flash("Unable to process payment for this fine record.", "danger")
        return redirect(url_for("admin.fines"))

    @admin_bp.route("/fines/<int:fine_id>/waive", methods=["POST"])
    def waive_fine(fine_id):
        notes = request.form.get("notes")
        ok = fine_service.waive_fine(fine_id, admin_id=session.get("user_id"), notes=notes)
        if ok:
            audit_service.log_action(
                user_id=session.get("user_id"),
                action="WAIVE_FINE",
                entity_type="fine",
                entity_id=fine_id,
                details=f"Admin waived fine ID {fine_id}"
            )
            flash("Fine penalty waived successfully.", "success")
        else:
            flash("Unable to waive this fine record.", "danger")
        return redirect(url_for("admin.fines"))

    @admin_bp.route("/reports")
    def reports():
        chart_data = report_service.get_chart_data()
        return render_template("admin/reports.html", chart_data=chart_data)

    @admin_bp.route("/reports/export")
    def export_csv():
        report_type = request.args.get("type", "inventory")
        if report_type == "inventory":
            csv_data = report_service.export_inventory_csv()
            filename = f"inventory_report_{datetime.now().strftime('%Y%m%d')}.csv"
        elif report_type == "active_loans":
            csv_data = report_service.export_loans_csv(filter_type="active")
            filename = f"active_loans_{datetime.now().strftime('%Y%m%d')}.csv"
        elif report_type == "overdue_loans":
            csv_data = report_service.export_loans_csv(filter_type="overdue")
            filename = f"overdue_loans_{datetime.now().strftime('%Y%m%d')}.csv"
        elif report_type == "fines":
            csv_data = report_service.export_fines_csv()
            filename = f"fines_report_{datetime.now().strftime('%Y%m%d')}.csv"
        elif report_type == "members":
            csv_data = report_service.export_members_csv()
            filename = f"members_report_{datetime.now().strftime('%Y%m%d')}.csv"
        else:
            abort(400, description="Invalid export report type")

        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    @admin_bp.route("/audit-logs")
    def audit_logs():
        logs = audit_service.get_recent_logs(limit=100)
        return render_template("admin/audit_logs.html", logs=logs)

    app.register_blueprint(admin_bp)

    # ----------------------------------------------------
    # Member Blueprint
    # ----------------------------------------------------
    member_bp = Blueprint("member", __name__, url_prefix="/member")

    @member_bp.before_request
    def require_member_login():
        if not session.get("user_id"):
            flash("Please sign in to access your member dashboard.", "warning")
            return redirect(url_for("auth.login", next=request.url))

    @member_bp.route("/dashboard")
    def dashboard():
        user_id = session.get("user_id")
        active_loans = loan_service.get_active_loans(user_id=user_id)
        reservations = reservation_service.get_user_reservations(user_id=user_id)
        unpaid_fines = fine_service.get_unpaid_fines_total(user_id=user_id)
        recommendations = recommendation_service.get_recommendations_for_user(user_id=user_id, limit=6)

        overdue_cnt = sum(1 for l in active_loans if l["is_overdue"])

        return render_template(
            "member/dashboard.html",
            active_loans=active_loans,
            reservations=reservations,
            unpaid_fines=unpaid_fines,
            recommendations=recommendations,
            overdue_count=overdue_cnt,
        )

    @member_bp.route("/loans")
    def my_loans():
        user_id = session.get("user_id")
        active_loans = loan_service.get_active_loans(user_id=user_id)
        history = loan_service.get_loan_history(user_id=user_id, limit=50)

        return render_template(
            "member/my_loans.html",
            active_loans=active_loans,
            history=history,
        )

    @member_bp.route("/reserve/<int:book_id>", methods=["POST"])
    def reserve_book(book_id):
        user_id = session.get("user_id")
        res_id, err = reservation_service.create_reservation(book_id, user_id)
        if err:
            flash(err, "warning")
        else:
            flash("Book reserved successfully! You will be notified when a copy is ready.", "success")
        return redirect(url_for("member.my_reservations"))

    @member_bp.route("/reservations")
    def my_reservations():
        user_id = session.get("user_id")
        reservation_service.check_and_expire_reservations()
        reservations = reservation_service.get_user_reservations(user_id=user_id)
        return render_template("member/my_reservations.html", reservations=reservations)

    @member_bp.route("/reservations/<int:res_id>/cancel", methods=["POST"])
    def cancel_reservation(res_id):
        user_id = session.get("user_id")
        ok, err = reservation_service.cancel_reservation(res_id, user_id=user_id)
        if err:
            flash(err, "danger")
        else:
            flash("Reservation hold cancelled successfully.", "info")
        return redirect(url_for("member.my_reservations"))

    @member_bp.route("/notifications")
    def notifications():
        user_id = session.get("user_id")
        notifs = notification_service.get_user_notifications(user_id=user_id, limit=50)
        return render_template("member/notifications.html", notifications=notifs)

    @member_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
    def mark_read(notif_id):
        user_id = session.get("user_id")
        notification_service.mark_as_read(notif_id, user_id)
        return redirect(url_for("member.notifications"))

    @member_bp.route("/notifications/read-all", methods=["POST"])
    def mark_all_read():
        user_id = session.get("user_id")
        notification_service.mark_all_read(user_id)
        flash("All notifications marked as read.", "success")
        return redirect(url_for("member.notifications"))

    @member_bp.route("/profile")
    def profile():
        user = auth_service.get_user_by_id(session.get("user_id"))
        return render_template("profile/settings.html", user=user)

    @member_bp.route("/profile/update", methods=["POST"])
    def update_profile():
        user_id = session.get("user_id")
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name or len(name) < 2:
            flash("Name must be at least 2 characters.", "danger")
            return redirect(url_for("member.profile"))

        execute_db("UPDATE users SET name = ?, phone = ? WHERE id = ?", (name, phone or None, user_id))
        session["user_name"] = name
        flash("Profile information updated successfully.", "success")
        return redirect(url_for("member.profile"))

    @member_bp.route("/profile/change-password", methods=["POST"])
    def change_password():
        user_id = session.get("user_id")
        current_pw = request.form.get("current_password")
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")

        user = auth_service.get_user_by_id(user_id)
        if not check_password_hash(user["password_hash"], current_pw):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("member.profile"))

        if len(new_pw) < 6:
            flash("New password must be at least 6 characters.", "danger")
            return redirect(url_for("member.profile"))

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("member.profile"))

        new_hash = generate_password_hash(new_pw)
        execute_db("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
        flash("Password changed successfully.", "success")
        return redirect(url_for("member.profile"))

    app.register_blueprint(member_bp)

    # ----------------------------------------------------
    # API Endpoints
    # ----------------------------------------------------
    api_bp = Blueprint("api", __name__, url_prefix="/api")

    @api_bp.route("/copy-lookup/<accession_id>")
    def copy_lookup(accession_id):
        copy = book_service.get_copy_by_accession_id(accession_id)
        if not copy:
            return jsonify({"success": False, "message": f"Copy '{accession_id}' not found."}), 404

        copy_dict = dict(copy)
        # Check active loan if borrowed
        active_loan = query_db(
            """
            SELECT l.id, l.due_date, u.name, u.email
            FROM loans l
            JOIN users u ON l.user_id = u.id
            WHERE l.copy_id = ? AND l.status IN ('active', 'overdue')
            LIMIT 1
            """,
            (copy["id"],),
            one=True,
        )
        if active_loan:
            copy_dict["active_borrower"] = {
                "name": active_loan["name"],
                "email": active_loan["email"],
                "due_date": active_loan["due_date"],
            }

        return jsonify({"success": True, "copy": copy_dict})

    @api_bp.route("/member-lookup/<query>")
    def member_lookup(query):
        query = query.strip()
        user = None
        if query.isdigit():
            user = auth_service.get_user_by_id(int(query))
        if not user:
            user = auth_service.get_user_by_email(query)

        if not user or user["role"] != "member":
            return jsonify({"success": False, "message": "Member not found."}), 404

        active_count = query_db(
            "SELECT COUNT(*) AS c FROM loans WHERE user_id = ? AND status IN ('active', 'overdue')",
            (user["id"],),
            one=True,
        )["c"]
        unpaid_fines = fine_service.get_unpaid_fines_total(user["id"])

        return jsonify({
            "success": True,
            "member": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "status": user["status"],
                "max_loans": user["max_loans"],
                "active_loans": active_count,
                "unpaid_fines": unpaid_fines,
            }
        })

    app.register_blueprint(api_bp)

    # ----------------------------------------------------
    # Error Handlers
    # ----------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        return render_template(
            "base.html",
            content=f'<div class="alert alert-danger card-custom m-4"><h4>Bad Request</h4><p>{e.description if hasattr(e, "description") else "Invalid request data or CSRF failure."}</p><a href="/" class="btn btn-sm btn-outline-primary">Return Home</a></div>'
        ), 400

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template(
            "base.html",
            content='<div class="card card-custom p-5 text-center m-4"><i class="bi bi-compass fs-1 text-secondary mb-2"></i><h4>Page Not Found</h4><p class="text-muted">The resource you requested does not exist or has been moved.</p><a href="/" class="btn btn-primary btn-sm d-inline-block mx-auto">Back to Home</a></div>'
        ), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template(
            "base.html",
            content='<div class="card card-custom p-5 text-center m-4"><i class="bi bi-exclamation-triangle fs-1 text-danger mb-2"></i><h4>Internal Server Error</h4><p class="text-muted">An unexpected error occurred. Please try again later or contact library support.</p><a href="/" class="btn btn-primary btn-sm d-inline-block mx-auto">Back to Home</a></div>'
        ), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
