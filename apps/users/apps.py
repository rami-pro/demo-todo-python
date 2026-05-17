from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Users"

    def ready(self) -> None:
        """
        Import signals here so they are registered exactly once when Django
        starts. Importing at module level causes double-registration in tests;
        importing inside models.py causes circular imports.
        """
        import apps.users.signals  # noqa: F401
