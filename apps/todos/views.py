from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .filters import TodoFilter
from .models import Category, Tag, Todo
from .pagination import StandardResultsSetPagination
from .permissions import IsOwner
from .serializers import CategorySerializer, TagSerializer, TodoSerializer


@extend_schema_view(
    list=extend_schema(summary="List all todos for the current user"),
    create=extend_schema(summary="Create a new todo"),
    retrieve=extend_schema(summary="Retrieve a single todo"),
    update=extend_schema(summary="Replace a todo (full update)"),
    partial_update=extend_schema(summary="Update a todo (partial)"),
    destroy=extend_schema(summary="Delete a todo"),
)
class TodoViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for todos, always scoped to the current user.

    Key patterns:
    - get_queryset(): filters by owner; uses select_related + prefetch_related
      to avoid N+1 queries when serialising FK and M2M relations.
    - filterset_class: declarative query-param filtering via TodoFilter.
    - search_fields: ?search=term does a case-insensitive substring search.
    - ordering_fields: ?ordering=-priority sorts results server-side.
    - @action: adds non-CRUD endpoints (stats, bulk-complete) without extra URLs.
    """

    serializer_class = TodoSerializer
    permission_classes = [IsOwner]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = TodoFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "priority", "due_date", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):  # type: ignore[override]
        return (
            Todo.objects.filter(owner=self.request.user)
            .select_related("owner", "category")
            .prefetch_related("tags")
        )

    @extend_schema(summary="Get completion statistics for the current user")
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request: Request) -> Response:
        """GET /api/v1/todos/stats/"""
        qs = self.get_queryset()
        return Response(
            {
                "total": qs.count(),
                "completed": qs.filter(completed=True).count(),
                "pending": qs.filter(completed=False).count(),
                "by_priority": {
                    p: qs.filter(priority=p).count()
                    for p in [
                        Todo.Priority.LOW,
                        Todo.Priority.MEDIUM,
                        Todo.Priority.HIGH,
                    ]
                },
            }
        )

    @extend_schema(
        summary="Bulk mark todos as completed",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string", "format": "uuid"},
                    }
                },
            }
        },
    )
    @action(detail=False, methods=["post"], url_path="bulk-complete")
    def bulk_complete(self, request: Request) -> Response:
        """
        POST /api/v1/todos/bulk-complete/
        Body: {"ids": ["uuid1", "uuid2", …]}

        queryset.update() runs a single UPDATE SQL — much more efficient than
        calling .save() on each instance in a loop.
        """
        ids = request.data.get("ids", [])
        updated = Todo.objects.filter(owner=request.user, id__in=ids).update(
            completed=True
        )
        return Response({"updated": updated})


@extend_schema_view(
    list=extend_schema(summary="List categories for the current user"),
    create=extend_schema(summary="Create a category"),
    retrieve=extend_schema(summary="Retrieve a category"),
    update=extend_schema(summary="Update a category"),
    partial_update=extend_schema(summary="Partially update a category"),
    destroy=extend_schema(summary="Delete a category"),
)
class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsOwner]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):  # type: ignore[override]
        return Category.objects.filter(owner=self.request.user).prefetch_related(
            "todos"
        )


@extend_schema_view(
    list=extend_schema(summary="List tags for the current user"),
    create=extend_schema(summary="Create a tag"),
    retrieve=extend_schema(summary="Retrieve a tag"),
    update=extend_schema(summary="Update a tag"),
    partial_update=extend_schema(summary="Partially update a tag"),
    destroy=extend_schema(summary="Delete a tag"),
)
class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [IsOwner]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):  # type: ignore[override]
        return Tag.objects.filter(owner=self.request.user)
