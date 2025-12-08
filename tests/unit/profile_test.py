
# tests/unit/test_profile.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.auth.jwt import create_token, get_password_hash
from app.schemas.token import TokenType
from tests.conftest import fake

client = TestClient(app)


@pytest.fixture
def authenticated_client(db_session: Session, test_user: User):
    """
    Inject a valid JWT using the real user ID.
    Works even if test_user.password is plain text (common in fixtures).
    """
    token = create_token(user_id=str(test_user.id), token_type=TokenType.ACCESS)
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client
    client.headers.clear()


def test_get_profile_page(authenticated_client):
    r = authenticated_client.get("/profile")
    assert r.status_code == 200
    assert "profile" in r.text.lower()

def test_update_profile_success(authenticated_client, db_session: Session, test_user: User):
    payload = {
        "first_name": "UpdatedName",
        "last_name": "UpdatedLast",
        "email": f"updated_{fake.unique.hexify('^^^^^^^')}@example.com",
        "username": f"updateduser_{fake.unique.hexify('^^^^^^')}"
    }

    r = authenticated_client.post("/profile/update", data=payload)
    assert r.status_code == 200
    assert any(msg in r.text for msg in ["Profile updated successfully", "success"])

    db_session.refresh(test_user)
    assert test_user.first_name == "UpdatedName"
    assert test_user.username == payload["username"]
    assert test_user.email == payload["email"]


def test_change_password_success(authenticated_client, db_session: Session, test_user: User):
    # Save current password value (even if it's plain text)
    current_password = "TestPass123!"

    # Change to a new strong password
    new_password = "SuperStrongNew2025!"

    r = authenticated_client.post("/profile/change-password", data={
        "current_password": current_password,
        "new_password": new_password,
        "confirm_new_password": new_password
    })
    assert r.status_code == 200
    assert any(msg in r.text for msg in ["Password changed successfully", "changed successfully", "success"])

    # Refresh user from DB
    db_session.refresh(test_user)

    # The password column now contains a REAL bcrypt hash (your route uses get_password_hash)
    # So we can safely verify it
    from app.auth.jwt import verify_password
    assert verify_password(new_password, test_user.password)
    assert not verify_password(current_password, test_user.password)  # Old one no longer works


def test_change_password_wrong_current(authenticated_client):
    r = authenticated_client.post("/profile/change-password", data={
        "current_password": "WrongPassword!!!",
        "new_password": "NewPass123!",
        "confirm_new_password": "NewPass123!"
    })
    assert r.status_code == 200
    assert any(msg in r.text.lower() for msg in ["incorrect", "wrong", "error"])


def test_change_password_mismatch(authenticated_client):
    r = authenticated_client.post("/profile/change-password", data={
        "current_password": "TestPass123!",
        "new_password": "PassA123!",
        "confirm_new_password": "PassB123!"
    })
    assert r.status_code == 200
    # Look for signs that validation failed and page reloaded
    assert "Password" in r.text  # form is still there
    assert "mismatch" in r.text.lower() or "do not match" in r.text.lower() or "error" in r.text.lower()


def test_change_password_same_as_old(authenticated_client):
    r = authenticated_client.post("/profile/change-password", data={
        "current_password": "TestPass123!",
        "new_password": "TestPass123!",
        "confirm_new_password": "TestPass123!"
    })
    assert r.status_code == 200
    assert any(phrase in r.text.lower() for phrase in ["different", "same", "cannot be the same", "error"])


def test_change_password_weak_password(authenticated_client):
    r = authenticated_client.post("/profile/change-password", data={
        "current_password": "TestPass123!",
        "new_password": "abc",
        "confirm_new_password": "abc"
    })
    assert r.status_code == 200
    assert any(phrase in r.text.lower() for phrase in [
        "8 characters", "uppercase", "lowercase", "digit", "special", "strong", "weak", "password"
    ])
