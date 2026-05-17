import factory
from factory.django import DjangoModelFactory

from apps.users.models import User


class UserFactory(DjangoModelFactory):
    """
    factory_boy builds model instances with realistic data:
    - Sequence: generates a unique value per call (user0, user1, …)
    - LazyAttribute: computed from other fields after they are resolved
    - Faker: generates realistic random data via the Faker library
    """

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    bio = factory.Faker("text", max_nb_chars=200)
    is_active = True

    @classmethod
    def _create(cls, model_class: type, *args: object, **kwargs: object) -> User:
        password: str = str(kwargs.pop("password", "testpass123"))
        user: User = model_class(*args, **kwargs)
        user.set_password(password)
        user.save()
        return user
