from fastapi import status
from fastapi.testclient import TestClient
import pytest

def test_create_user(client: TestClient, test_user_data):
    response = client.post(
        "/api/v1/auth/register",
        json=test_user_data
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "id" in data
    assert data["email"] == test_user_data["email"]
    assert "hashed_password" not in data # Ensure password is not returned

def test_create_existing_user(client: TestClient, test_user, test_user_data):
    response = client.post(
        "/api/v1/auth/register",
        json=test_user_data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "User with this email already registered" in response.json()["detail"]

def test_login_for_access_token(client: TestClient, test_user, test_user_data):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user_data["email"], "password": test_user_data["password"]}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_for_access_token_wrong_password(client: TestClient, test_user, test_user_data):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user_data["email"], "password": "wrongpassword"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Incorrect email or password" in response.json()["detail"]

def test_login_for_access_token_user_not_found(client: TestClient, test_user_data):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent@example.com", "password": "anypassword"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Incorrect email or password" in response.json()["detail"]

def test_read_users_me_authenticated(authorized_client: TestClient):
    response = authorized_client.get("/api/v1/users/me/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "email" in data
    assert "id" in data

def test_read_users_me_unauthenticated(client: TestClient):
    response = client.get("/api/v1/users/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in response.json()["detail"]