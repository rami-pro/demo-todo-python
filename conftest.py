"""
Root conftest.py — shared pytest fixtures available to all test modules.

pytest-django uses DJANGO_SETTINGS_MODULE from pyproject.toml
[tool.pytest.ini_options] to configure Django before tests run.
"""

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def user(db):  # type: ignore[no-untyped-def]
    """A freshly-created test user (triggers UserProfile signal)."""
    from apps.users.tests.factories import UserFactory

    return UserFactory()


@pytest.fixture
def authenticated_client(api_client: APIClient, user):  # type: ignore[no-untyped-def]
    """APIClient pre-authenticated as `user`. Returns (client, user) tuple."""
    api_client.force_authenticate(user=user)
    return api_client, user
