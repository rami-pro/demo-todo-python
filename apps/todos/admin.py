from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Category, Tag, Todo


class TagInline(admin.TabularInline):
    """
    TabularInline renders the M2M through-table as a compact row table.
    extra=0 means no blank rows shown by default.
    """

    model = Todo.tags.through
    extra = 0
    verbose_name = "Tag"
    verbose_name_plural = "Tags"


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """
    Showcases key Django Admin customisation options:

    list_display   → columns on the changelist
    list_filter    → sidebar filter checkboxes
    search_fields  → search bar (generates LIKE queries)
    list_editable  → inline editing directly from the changelist
    date_hierarchy → drilldown breadcrumb by date at the top of the list
    readonly_fields → shown in detail but not editable
    inlines        → related models embedded in the detail page
    actions        → custom bulk actions selectable via checkbox
    """

    list_display = [
        "title",
        "owner",
        "priority",
        "completed",
        "due_date",
        "category",
        "created_at",
    ]
    list_filter = ["completed", "priority", "category", "created_at"]
    search_fields = ["title", "description", "owner__username"]
    readonly_fields = ["id", "created_at", "updated_at"]
    list_editable = ["completed", "priority"]
    date_hierarchy = "created_at"
    inlines = [TagInline]

    @admin.action(description="Mark selected todos as completed")
    def mark_completed(self, request: HttpRequest, queryset: QuerySet) -> None:  # type: ignore[type-arg]
        queryset.update(completed=True)

    actions = [mark_completed]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "color", "owner", "created_at"]
    list_filter = ["owner"]
    search_fields = ["name", "owner__username"]
    readonly_fields = ["id", "created_at"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "slug", "owner", "created_at"]
    search_fields = ["name", "owner__username"]
    readonly_fields = ["id", "slug", "created_at"]
    # prepopulated_fields auto-fills slug from name in the browser
    prepopulated_fields = {"slug": ("name",)}
