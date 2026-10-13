from services import qr_service, recommendation_service, report_service


def test_qr_code_generation():
    """Test QR code generation produces valid SVG vector content and data URI."""
    accession_id = "ACC-BK-999"
    svg = qr_service.generate_qr_svg(accession_id)
    assert "<svg" in svg
    assert "</svg>" in svg

    data_uri = qr_service.generate_qr_data_uri(accession_id)
    assert data_uri.startswith("data:image/svg+xml;base64,")


def test_recommendations_fallback(app):
    """Test recommendations fallback for a new member with no loan history."""
    with app.app_context():
        # Member 2 has no loan history in conftest
        recs = recommendation_service.get_recommendations_for_user(user_id=2, limit=4)
        assert len(recs) > 0
        assert all("book" in r and "reason" in r and "badge" in r for r in recs)


def test_csv_reports_export(client, auth):
    """Test that all CSV export endpoints respond with valid CSV headers and content."""
    auth.login("admin@test.com", "Admin@1234")

    endpoints = [
        ("inventory", "ISBN,Title"),
        ("active_loans", "Loan ID,Accession ID"),
        ("overdue_loans", "Loan ID,Accession ID"),
        ("fines", "Fine ID,Member Name"),
        ("members", "Member ID,Name"),
    ]

    for report_type, expected_header in endpoints:
        resp = client.get(f"/admin/reports/export?type={report_type}")
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        assert expected_header.encode("utf-8") in resp.data
