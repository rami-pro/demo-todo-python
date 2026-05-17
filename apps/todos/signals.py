import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import Category, Todo

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Todo)
def log_todo_deletion(sender: type, instance: Todo, **kwargs: object) -> None:
    """
    pre_delete fires before the object is removed from the DB.
    Use cases: audit trail, triggering external side effects (e.g. Slack
    notification), or blocking deletion by raising an exception.
    """
    logger.info(
        "Todo '%s' (id=%s) deleted by owner %s",
        instance.title,
        instance.pk,
        instance.owner.username,
    )


@receiver(pre_delete, sender=Category)
def log_category_deletion(sender: type, instance: Category, **kwargs: object) -> None:
    """Log how many todos will be orphaned (category FK set to NULL) on deletion."""
    todo_count = instance.todos.count()
    logger.warning(
        "Category '%s' deleted — %d todo(s) will have category set to NULL",
        instance.name,
        todo_count,
    )
