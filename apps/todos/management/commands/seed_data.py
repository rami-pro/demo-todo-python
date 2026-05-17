"""
Management command: python manage.py seed_data

Management commands live in <app>/management/commands/<name>.py.
They are discovered automatically by Django — no registration needed.

Key APIs:
  self.stdout.write()        → respects --no-color flag; preferred over print()
  self.style.SUCCESS/WARNING → coloured output
  add_arguments()            → adds typed CLI arguments (argparse under the hood)
  options["key"]             → access parsed argument values
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.todos.models import Category, Tag, Todo

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with sample data for development / manual testing"

    def add_arguments(self, parser) -> None:  # type: ignore[override]
        parser.add_argument(
            "--users",
            type=int,
            default=3,
            help="Number of test users to create (default: 3)",
        )
        parser.add_argument(
            "--todos-per-user",
            type=int,
            default=10,
            dest="todos_per_user",
            help="Todos per user (default: 10)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing data before seeding",
        )

    def handle(self, *args: object, **options: object) -> None:
        if options["clear"]:
            self.stdout.write(self.style.WARNING("Clearing existing data…"))
            Todo.objects.all().delete()
            Category.objects.all().delete()
            Tag.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        priorities = [Todo.Priority.LOW, Todo.Priority.MEDIUM, Todo.Priority.HIGH]
        created_users = 0

        for i in range(1, int(options["users"]) + 1):
            username = f"testuser{i}"
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"  User '{username}' already exists — skipping.")
                continue

            user = User.objects.create_user(  # type: ignore[union-attr]
                username=username,
                email=f"testuser{i}@example.com",
                password="testpass123",
                bio=f"I am test user number {i}",
            )
            created_users += 1

            cat_work = Category.objects.create(name="Work", owner=user, color="#EF4444")
            cat_personal = Category.objects.create(
                name="Personal", owner=user, color="#10B981"
            )
            tag_urgent = Tag.objects.create(name="urgent", owner=user)
            tag_review = Tag.objects.create(name="review", owner=user)

            todos_per_user = int(options["todos_per_user"])
            for j in range(1, todos_per_user + 1):
                todo = Todo.objects.create(
                    title=f"Task {j} for {username}",
                    description=f"Description of task {j}",
                    priority=priorities[j % 3],
                    completed=(j % 4 == 0),
                    owner=user,
                    category=cat_work if j % 2 == 0 else cat_personal,
                )
                if j % 3 == 0:
                    todo.tags.set([tag_urgent])
                elif j % 5 == 0:
                    todo.tags.set([tag_review])

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_users} user(s) with "
                f"{options['todos_per_user']} todo(s) each."
            )
        )
