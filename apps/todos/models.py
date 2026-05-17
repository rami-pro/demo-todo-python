import uuid

from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.text import slugify

from apps.users.models import User


class Tag(models.Model):
    """
    User-scoped label. The slug is derived from the name and auto-populated
    in save(). unique_together prevents duplicate slugs per user.

    db_index on slug speeds up lookups by slug (used in filters).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, validators=[MinLengthValidator(1)])
    slug = models.SlugField(max_length=60, db_index=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["owner", "slug"]]
        verbose_name = "tag"
        verbose_name_plural = "tags"

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Category(models.Model):
    """
    User-scoped grouping for todos.

    ForeignKey with on_delete=CASCADE: deleting a User also deletes all their
    categories. unique_together prevents the same user from having two
    categories with the same name.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text="Hex colour code, e.g. #3B82F6",
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="categories")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["owner", "name"]]
        verbose_name = "category"
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return f"{self.name} ({self.owner.username})"


class Todo(models.Model):
    """
    Core entity. Demonstrates:
    - TextChoices: Pythonic way to define choice fields (Django 3.0+).
    - ManyToManyField: Django auto-creates the join table todos_todo_tags.
    - ForeignKey SET_NULL: deleting a Category doesn't cascade to todos.
    - db_index on completed and priority for fast filtering queries.
    - Meta.indexes: composite B-tree indexes for compound filter patterns.
    - auto_now_add vs auto_now: add → set once on INSERT; now → set on every UPDATE.
    """

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, validators=[MinLengthValidator(1)])
    description = models.TextField(blank=True, default="")
    completed = models.BooleanField(default=False, db_index=True)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="todos")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="todos",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="todos")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "todo"
        verbose_name_plural = "todos"
        indexes = [
            # Compound indexes speed up the most common query pattern:
            # "fetch all incomplete todos for user X" or "fetch high-priority todos for user X"
            models.Index(fields=["owner", "completed"]),
            models.Index(fields=["owner", "priority"]),
        ]

    def __str__(self) -> str:
        marker = "✓" if self.completed else "○"
        return f"[{marker}] {self.title}"
