def test_login_success_admin(client, auth):
    """Test administrator login with valid credentials."""
    response = auth.login("admin@test.com", "Admin@1234")
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"Dashboard" in response.data


def test_login_success_member(client, auth):
    """Test student member login with valid credentials."""
    response = auth.login("member1@test.com", "Member@1234")
    assert response.status_code == 200
    assert b"Welcome back, Member One!" in response.data
    assert b"My Current Loans" in response.data


def test_login_invalid_password(client, auth):
    """Test login with wrong password."""
    response = auth.login("admin@test.com", "WrongPassword")
    assert response.status_code == 401
    assert b"Invalid email or password" in response.data


def test_login_nonexistent_user(client, auth):
    """Test login with an unregistered email."""
    response = auth.login("nobody@nowhere.com", "Secret@123")
    assert response.status_code == 401
    assert b"Invalid email or password" in response.data


def test_logout(client, auth):
    """Test user logout."""
    auth.login("admin@test.com", "Admin@1234")
    response = auth.logout()
    assert response.status_code == 200
    assert b"You have been signed out" in response.data


def test_member_registration(client):
    """Test student member registration."""
    response = client.post(
        "/auth/register",
        data={
            "name": "New Student",
            "email": "new.student@university.edu",
            "password": "Password123!",
            "phone": "555-9999",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Registration successful" in response.data


def test_registration_duplicate_email(client):
    """Test rejection of duplicate member email."""
    response = client.post(
        "/auth/register",
        data={
            "name": "Impostor",
            "email": "member1@test.com",  # Already exists in conftest
            "password": "Password123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_unauthorized_admin_access(client):
    """Test that accessing admin dashboard without login redirects to login."""
    response = client.get("/admin/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert b"Please sign in" in response.data


def test_member_forbidden_admin_access(client, auth):
    """Test that a member cannot access administrative routes."""
    auth.login("member1@test.com", "Member@1234")
    response = client.get("/admin/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert b"Unauthorized" in response.data
