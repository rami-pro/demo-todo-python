from django.apps import AppConfig


class TodosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.todos"
    verbose_name = "Todos"

    def ready(self) -> None:
        import apps.todos.signals  # noqa: F401
