import factory
from factory.django import DjangoModelFactory

from apps.users.tests.factories import UserFactory

from ..models import Category, Tag, Todo


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    color = "#3B82F6"
    owner = factory.SubFactory(UserFactory)


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"tag{n}")
    owner = factory.SubFactory(UserFactory)


class TodoFactory(DjangoModelFactory):
    class Meta:
        model = Todo

    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph")
    completed = False
    priority = Todo.Priority.MEDIUM
    owner = factory.SubFactory(UserFactory)
    category = factory.SubFactory(
        CategoryFactory,
        owner=factory.SelfAttribute("..owner"),
    )
