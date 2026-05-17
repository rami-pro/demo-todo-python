import django_filters

from .models import Todo


class TodoFilter(django_filters.FilterSet):
    """
    Declarative FilterSet — each field maps a query parameter to an ORM lookup.

    Usage examples:
        GET /api/v1/todos/?completed=true
        GET /api/v1/todos/?priority=high
        GET /api/v1/todos/?due_date_after=2026-01-01&due_date_before=2026-12-31
        GET /api/v1/todos/?category=<uuid>
        GET /api/v1/todos/?tag=<uuid>

    Filters are applied on top of get_queryset() — the user scope is already
    enforced before FilterSet runs.
    """

    title = django_filters.CharFilter(lookup_expr="icontains")
    completed = django_filters.BooleanFilter()
    priority = django_filters.ChoiceFilter(choices=Todo.Priority.choices)
    due_date_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_before = django_filters.DateFilter(
        field_name="due_date", lookup_expr="lte"
    )
    category = django_filters.UUIDFilter(field_name="category__id")
    tag = django_filters.UUIDFilter(field_name="tags__id")
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )

    class Meta:
        model = Todo
        fields = [
            "title",
            "completed",
            "priority",
            "due_date_after",
            "due_date_before",
            "category",
            "tag",
        ]
