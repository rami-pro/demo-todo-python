import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import User, UserProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(
    sender: type, instance: User, created: bool, **kwargs: object
) -> None:
    """
    Automatically create a UserProfile whenever a new User is saved for the
    first time. `created` is True only on INSERT, False on subsequent saves.
    """
    if created:
        UserProfile.objects.create(user=instance)
        logger.info("UserProfile created for user: %s", instance.username)


@receiver(post_save, sender=User)
def save_user_profile(sender: type, instance: User, **kwargs: object) -> None:
    """Keep the profile row in sync whenever the User is saved (edge-case guard)."""
    if hasattr(instance, "profile"):
        instance.profile.save()


@receiver(pre_delete, sender=User)
def log_user_deletion(sender: type, instance: User, **kwargs: object) -> None:
    """
    pre_delete fires before the DELETE SQL. Use case: audit logging, or
    triggering side-effects that must run before cascade deletion.
    """
    logger.warning("User is being deleted: %s (id=%s)", instance.username, instance.pk)
