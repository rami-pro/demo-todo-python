import pytest
from rest_framework import status
from rest_framework.test import APIClient

from .factories import UserFactory


@pytest.mark.django_db
class TestUserRegistration:
    def setup_method(self) -> None:
        self.client = APIClient()

    def test_register_creates_user(self) -> None:
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass123",
            "password_confirm": "securepass123",
        }
        response = self.client.post("/api/v1/users/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["username"] == "newuser"
        # password must never be returned
        assert "password" not in response.data

    def test_register_mismatched_passwords_returns_400(self) -> None:
        payload = {
            "username": "newuser2",
            "email": "newuser2@example.com",
            "password": "securepass123",
            "password_confirm": "differentpass",
        }
        response = self.client.post("/api/v1/users/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserMe:
    def setup_method(self) -> None:
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_get_me_returns_own_data(self) -> None:
        response = self.client.get("/api/v1/users/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == self.user.username
        assert response.data["email"] == self.user.email

    def test_patch_me_updates_bio(self) -> None:
        response = self.client.patch(
            "/api/v1/users/me/", {"bio": "Updated bio"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["bio"] == "Updated bio"

    def test_unauthenticated_me_returns_401(self) -> None:
        client = APIClient()
        response = client.get("/api/v1/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_profile_nested_in_response(self) -> None:
        response = self.client.get("/api/v1/users/me/")
        assert response.status_code == status.HTTP_200_OK
        assert "profile" in response.data
        assert "preferences" in response.data["profile"]
