from rest_framework import serializers

from .models import Category, Tag, Todo


class TagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "created_at"]
        read_only_fields = ["id", "slug", "created_at"]

    def create(self, validated_data: dict) -> Tag:  # type: ignore[override]
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class CategorySerializer(serializers.ModelSerializer[Category]):
    todo_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "color", "todo_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_todo_count(self, obj: Category) -> int:
        return obj.todos.count()  # type: ignore[attr-defined]

    def create(self, validated_data: dict) -> Category:  # type: ignore[override]
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class TodoSerializer(serializers.ModelSerializer[Todo]):
    """
    Demonstrates advanced serializer patterns:

    - Nested read  : `tags` and `category_detail` are full object representations.
    - Write via IDs: `tag_ids` (PrimaryKeyRelatedField many=True) and `category`
                     accept UUIDs on write.  Querysets are scoped to request.user
                     in __init__ to prevent assigning other users' objects.
    - SerializerMethodField: `owner_username` is derived, not a DB column.
    - source=         : `category_detail` reads from the `category` FK;
                        `priority_display` reads from `get_priority_display()`.
    - write_only      : `tag_ids` and `category` never appear in responses.
    - read_only       : `tags`, `category_detail` are never accepted on writes.
    """

    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.none(),  # scoped dynamically in __init__
        write_only=True,
        source="tags",
        required=False,
    )
    owner_username = serializers.SerializerMethodField()
    category_detail = CategorySerializer(source="category", read_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),  # scoped dynamically in __init__
        required=False,
        allow_null=True,
        write_only=True,
    )
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )

    class Meta:
        model = Todo
        fields = [
            "id",
            "title",
            "description",
            "completed",
            "priority",
            "priority_display",
            "due_date",
            "created_at",
            "updated_at",
            "owner_username",
            "category",
            "category_detail",
            "tags",
            "tag_ids",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "owner_username"]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["tag_ids"].child_relation.queryset = (  # type: ignore[attr-defined]
                Tag.objects.filter(owner=request.user)
            )
            self.fields["category"].queryset = (  # type: ignore[union-attr]
                Category.objects.filter(owner=request.user)
            )

    def get_owner_username(self, obj: Todo) -> str:
        return obj.owner.username  # type: ignore[union-attr]

    def create(self, validated_data: dict) -> Todo:  # type: ignore[override]
        tags = validated_data.pop("tags", [])
        validated_data["owner"] = self.context["request"].user
        todo = Todo.objects.create(**validated_data)
        if tags:
            todo.tags.set(tags)
        return todo

    def update(self, instance: Todo, validated_data: dict) -> Todo:  # type: ignore[override]
        tags = validated_data.pop("tags", None)
        todo = super().update(instance, validated_data)
        if tags is not None:
            todo.tags.set(tags)
        return todo
