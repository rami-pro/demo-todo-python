"""
Management command: python manage.py cleanup_completed [--days N] [--dry-run]

Good use case for scheduled jobs (e.g. via cron or Celery Beat).
Demonstrates --dry-run pattern so operators can preview the impact first.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.todos.models import Todo


class Command(BaseCommand):
    help = "Delete completed todos that have not been updated in the last N days"

    def add_arguments(self, parser) -> None:  # type: ignore[override]
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Age threshold in days (default: 30)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Print what would be deleted without actually deleting",
        )

    def handle(self, *args: object, **options: object) -> None:
        days = int(options["days"])
        cutoff = timezone.now() - timedelta(days=days)
        qs = Todo.objects.filter(completed=True, updated_at__lt=cutoff)
        count = qs.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: would delete {count} completed todo(s) "
                    f"older than {days} day(s)."
                )
            )
            return

        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} completed todo(s) older than {days} day(s)."
            )
        )
