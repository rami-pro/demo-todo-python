import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.tests.factories import UserFactory

from .factories import CategoryFactory, TagFactory, TodoFactory


@pytest.mark.django_db
class TestTodoViewSet:
    """
    All tests use force_authenticate — this bypasses JWT and lets us focus on
    business logic rather than auth mechanics. The DRF APIClient mirrors
    Django's test Client but speaks JSON by default.
    """

    def setup_method(self) -> None:
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    # ------------------------------------------------------------------ CRUD

    def test_list_returns_only_own_todos(self) -> None:
        TodoFactory.create_batch(3, owner=self.user)
        TodoFactory.create_batch(2, owner=UserFactory())  # other user

        response = self.client.get("/api/v1/todos/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["count"] == 3

    def test_create_todo(self) -> None:
        category = CategoryFactory(owner=self.user)
        payload = {
            "title": "Buy groceries",
            "description": "Milk, eggs, bread",
            "priority": "high",
            "category": str(category.id),
        }
        response = self.client.post("/api/v1/todos/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Buy groceries"
        assert response.data["priority"] == "high"
        assert response.data["priority_display"] == "High"

    def test_retrieve_own_todo(self) -> None:
        todo = TodoFactory(owner=self.user, title="My task")
        response = self.client.get(f"/api/v1/todos/{todo.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "My task"

    def test_update_todo(self) -> None:
        todo = TodoFactory(owner=self.user, completed=False)
        response = self.client.patch(
            f"/api/v1/todos/{todo.id}/", {"completed": True}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["completed"] is True

    def test_delete_todo(self) -> None:
        todo = TodoFactory(owner=self.user)
        response = self.client.delete(f"/api/v1/todos/{todo.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    # ------------------------------------------------------------------ Auth

    def test_unauthenticated_request_returns_401(self) -> None:
        response = APIClient().get("/api/v1/todos/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cannot_access_other_users_todo(self) -> None:
        other_todo = TodoFactory(owner=UserFactory())
        response = self.client.get(f"/api/v1/todos/{other_todo.id}/")
        # 404 because get_queryset already filters by owner
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ------------------------------------------------------------------ Filtering

    def test_filter_by_completed(self) -> None:
        TodoFactory.create_batch(2, owner=self.user, completed=True)
        TodoFactory.create_batch(3, owner=self.user, completed=False)

        response = self.client.get("/api/v1/todos/?completed=true")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["count"] == 2

    def test_filter_by_priority(self) -> None:
        TodoFactory.create_batch(2, owner=self.user, priority="high")
        TodoFactory.create_batch(1, owner=self.user, priority="low")

        response = self.client.get("/api/v1/todos/?priority=high")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["count"] == 2

    def test_search_by_title(self) -> None:
        TodoFactory(owner=self.user, title="Buy milk")
        TodoFactory(owner=self.user, title="Fix bug")

        response = self.client.get("/api/v1/todos/?search=milk")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["count"] == 1
        assert response.data["results"][0]["title"] == "Buy milk"

    # ------------------------------------------------------------------ Custom actions

    def test_stats_endpoint(self) -> None:
        TodoFactory.create_batch(2, owner=self.user, priority="high", completed=True)
        TodoFactory.create_batch(3, owner=self.user, priority="low", completed=False)

        response = self.client.get("/api/v1/todos/stats/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total"] == 5
        assert response.data["completed"] == 2
        assert response.data["pending"] == 3

    def test_bulk_complete(self) -> None:
        todos = TodoFactory.create_batch(3, owner=self.user, completed=False)
        ids = [str(t.id) for t in todos[:2]]

        response = self.client.post(
            "/api/v1/todos/bulk-complete/", {"ids": ids}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 2

    # ------------------------------------------------------------------ Tags

    def test_create_todo_with_tags(self) -> None:
        tag = TagFactory(owner=self.user)
        payload = {"title": "Tagged task", "tag_ids": [str(tag.id)]}

        response = self.client.post("/api/v1/todos/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["tags"]) == 1
        assert response.data["tags"][0]["name"] == tag.name


@pytest.mark.django_db
class TestCategoryViewSet:
    def setup_method(self) -> None:
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_create_category(self) -> None:
        payload = {"name": "Work", "color": "#EF4444"}
        response = self.client.post("/api/v1/categories/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Work"

    def test_list_returns_only_own_categories(self) -> None:
        CategoryFactory.create_batch(2, owner=self.user)
        CategoryFactory(owner=UserFactory())

        response = self.client.get("/api/v1/categories/")

        assert response.status_code == status.HTTP_200_OK
        # DefaultRouter + no custom pagination → plain list
        assert len(response.data["results"]) == 2
