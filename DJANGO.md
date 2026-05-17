# DJANGO.md — Guide de l'écosystème Django

Guide de référence pour les développeurs venant de FastAPI qui apprennent Django et DRF.  
Chaque concept est ancré dans le code de ce projet.

---

## 1. Django MTV vs FastAPI — Table de correspondance

| Concept | FastAPI | Django / DRF | Notes |
|---------|---------|--------------|-------|
| Configuration app | `app = FastAPI()` | `settings.py` + `manage.py` | Django est configuré via des modules Python, pas une instance |
| Définition de route | `@app.get("/items")` | `router.register(r"items", ItemViewSet)` | DRF Router génère automatiquement toutes les URLs CRUD |
| Handler de requête | `async def get_items()` | `class ItemViewSet(ModelViewSet)` | Le ViewSet regroupe toutes les actions CRUD dans une classe |
| Validation des données | Pydantic `BaseModel` | DRF `Serializer` / `ModelSerializer` | Les Serializers gèrent aussi la sérialisation et les écritures DB |
| ORM | SQLAlchemy (typique) | Django ORM (intégré) | ORM synchrone par défaut, support async depuis Django 4.1 |
| Migrations | Alembic | `makemigrations` + `migrate` | Django génère les migrations automatiquement depuis les models |
| Auth | `python-jose` + custom | `djangorestframework-simplejwt` | JWT géré par une librairie maintenue |
| Injection de dépendances | `Depends()` | Pas d'équivalent direct | Django utilise des patterns orientés classe (`get_queryset()`, middleware) |
| Schema / Docs | OpenAPI intégré | `drf-spectacular` + Swagger UI | Pas natif, mais `drf-spectacular` s'intègre parfaitement |
| Tâches de fond | asyncio / Celery | Celery (install séparé) | Django n'a pas de file de tâches async intégrée |
| Interface Admin | Aucune | Django Admin (intégré) | Un des super-pouvoirs de Django — UI d'admin auto-générée |
| Gestion env vars | `pydantic-settings` | `django-environ` + settings split | Les settings Django sont des modules Python, pas des modèles Pydantic |
| Fichiers statiques | Non géré | `STATICFILES` + `collectstatic` | Django gère la collection des fichiers statiques pour la production |

---

## 2. Concepts clés — Où les trouver dans ce projet

### 2.1 Custom User Model (AbstractUser)

**Règle fondamentale :** toujours déclarer un modèle utilisateur custom avant la première migration. Changer après coup est douloureux.

**Où :** [apps/users/models.py](apps/users/models.py)

```python
# AbstractUser vous donne : username, email, password, first_name, last_name,
# is_active, is_staff, is_superuser, last_login, date_joined, groups,
# user_permissions, et toutes les méthodes auth (set_password, check_password…)
class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    # …

# Dans config/settings/base.py :
AUTH_USER_MODEL = "users.User"  # DOIT être défini avant la première migration
```

**Variante :** `AbstractBaseUser` si vous voulez tout contrôler (y compris `USERNAME_FIELD`). `AbstractUser` est plus simple et couvre 95% des cas.

---

### 2.2 Django ORM — Cheat Sheet

**Où :** [apps/todos/models.py](apps/todos/models.py), tous les `get_queryset()`

#### Queries de base

```python
# SELECT * FROM todos_todo
Todo.objects.all()

# WHERE completed = True
Todo.objects.filter(completed=True)

# WHERE priority IN ('high', 'medium')
Todo.objects.filter(priority__in=["high", "medium"])

# WHERE title LIKE '%grocery%' (insensible à la casse)
Todo.objects.filter(title__icontains="grocery")

# WHERE completed != True
Todo.objects.exclude(completed=True)

# Lève DoesNotExist si introuvable, MultipleObjectsReturned si plusieurs
Todo.objects.get(id=pk)

# Chainage de filtres (AND implicite)
Todo.objects.filter(owner=user, completed=False).order_by("-created_at")

# Compter sans charger les objets
Todo.objects.filter(owner=user).count()

# Mise à jour en bulk — un seul UPDATE SQL, pas de .save() en boucle
Todo.objects.filter(owner=user, id__in=ids).update(completed=True)

# Suppression en bulk
Todo.objects.filter(completed=True, updated_at__lt=cutoff).delete()
```

#### Relations — éviter le N+1

```python
# select_related : charge les FK en JOIN (relations "vers une seule entité")
Todo.objects.select_related("owner", "category")

# prefetch_related : charge les M2M / reverse FK en requête séparée optimisée
Todo.objects.prefetch_related("tags")

# Combiné — le pattern qu'on utilise dans TodoViewSet.get_queryset()
Todo.objects.filter(owner=user) \
            .select_related("owner", "category") \
            .prefetch_related("tags")
```

#### Lookups utiles

```python
# Dates
Todo.objects.filter(due_date__gte=today)          # >=
Todo.objects.filter(created_at__date=today)        # tronquer à la date
Todo.objects.filter(created_at__year=2026)

# String
Todo.objects.filter(title__startswith="Buy")
Todo.objects.filter(title__regex=r"^[A-Z]")

# Null
Todo.objects.filter(due_date__isnull=True)
Todo.objects.filter(category__isnull=False)

# Relations (double underscore = traversée de FK)
Todo.objects.filter(owner__username="alice")
Todo.objects.filter(tags__name="urgent")
```

#### Types de champs importants

| Champ | Usage | Notes |
|-------|-------|-------|
| `UUIDField` | Clés primaires | `default=uuid.uuid4, editable=False` |
| `CharField` | Texte court | `max_length` obligatoire |
| `TextField` | Texte long | Pas de `max_length` |
| `BooleanField` | Vrai/faux | `default=False` recommandé |
| `DateField` | Date seule | `auto_now_add`, `null=True, blank=True` |
| `DateTimeField` | Date + heure | `auto_now_add` (insert) vs `auto_now` (chaque save) |
| `JSONField` | Données JSON | Natif depuis Django 3.1 sur tous les backends |
| `SlugField` | URLs lisibles | `db_index=True` par défaut |
| `ForeignKey` | Relation N:1 | `on_delete` obligatoire |
| `OneToOneField` | Relation 1:1 | FK avec `unique=True` |
| `ManyToManyField` | Relation N:M | Django crée la table de jointure automatiquement |

---

### 2.3 Django Admin

**Où :** [apps/users/admin.py](apps/users/admin.py), [apps/todos/admin.py](apps/todos/admin.py)

L'Admin Django est l'une des killer features : une interface CRUD complète générée automatiquement depuis vos modèles.

```python
@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    # Colonnes de la liste
    list_display = ["title", "owner", "priority", "completed", "created_at"]

    # Filtres dans la barre latérale
    list_filter = ["completed", "priority", "created_at"]

    # Champs utilisés par la barre de recherche (génère des LIKE)
    search_fields = ["title", "description", "owner__username"]

    # Édition inline depuis la liste (sans ouvrir la page de détail)
    list_editable = ["completed", "priority"]

    # Navigation chronologique en haut de la liste
    date_hierarchy = "created_at"

    # Champs affichés mais non modifiables
    readonly_fields = ["id", "created_at", "updated_at"]

    # Modèles liés intégrés dans la page de détail
    inlines = [TagInline]

    # Actions bulk sélectionnables via checkbox
    @admin.action(description="Mark as completed")
    def mark_completed(self, request, queryset):
        queryset.update(completed=True)
    actions = [mark_completed]
```

**Inline :** afficher des modèles liés dans la page d'un autre modèle

```python
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False

# StackedInline = chaque champ sur sa propre ligne
# TabularInline = disposition en tableau compact
```

---

### 2.4 Django Signals

**Où :** [apps/users/signals.py](apps/users/signals.py), [apps/todos/signals.py](apps/todos/signals.py)  
**Enregistrement :** [apps/users/apps.py](apps/users/apps.py) via `AppConfig.ready()`

Les signals permettent de réagir à des événements du cycle de vie des modèles sans coupler le code.

```python
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    # `created` = True uniquement lors d'un INSERT (pas d'un UPDATE)
    if created:
        UserProfile.objects.create(user=instance)

@receiver(pre_delete, sender=Todo)
def log_todo_deletion(sender, instance, **kwargs):
    # pre_delete : avant le DELETE SQL
    # post_delete : après le DELETE SQL (instance.pk est encore disponible)
    logger.info("Deleting todo: %s", instance.title)
```

**Règle critique — enregistrer les signals dans `AppConfig.ready()`**

```python
# apps/users/apps.py
class UsersConfig(AppConfig):
    name = "apps.users"

    def ready(self):
        import apps.users.signals  # noqa: F401
        # ↑ Ne pas importer au niveau module (double enregistrement en tests)
        # ↑ Ne pas importer dans models.py (import circulaire)
```

**Signals disponibles :** `pre_save`, `post_save`, `pre_delete`, `post_delete`, `m2m_changed`, `pre_migrate`, `post_migrate`

---

### 2.5 Management Commands

**Où :** [apps/todos/management/commands/](apps/todos/management/commands/)

```bash
# Découverte automatique — aucun enregistrement nécessaire
python manage.py seed_data --users 3 --todos-per-user 10
python manage.py cleanup_completed --days 30 --dry-run

# Commandes Django intégrées utiles
python manage.py shell          # shell Python avec Django configuré
python manage.py dbshell        # shell SQL direct
python manage.py showmigrations # état des migrations
python manage.py sqlmigrate todos 0001  # voir le SQL généré
python manage.py check          # valider la configuration
```

**Structure d'une commande :**

```python
# apps/myapp/management/commands/my_command.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Description de la commande"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        # Préférer self.stdout.write() à print()
        self.stdout.write(self.style.SUCCESS("Done!"))
        self.stdout.write(self.style.WARNING("Warning!"))
        self.stdout.write(self.style.ERROR("Error!"))
```

**Fichiers `__init__.py` obligatoires :**  
`management/__init__.py` ET `management/commands/__init__.py`

---

### 2.6 Middleware

**Où :** [middleware/request_logger.py](middleware/request_logger.py)  
**Configuration :** `MIDDLEWARE` dans `config/settings/base.py`

```python
class RequestLoggingMiddleware:
    def __init__(self, get_response):
        # Appelé une fois au démarrage de Django
        self.get_response = get_response

    def __call__(self, request):
        # Code ici → s'exécute AVANT la vue
        start = time.monotonic()

        response = self.get_response(request)  # ← appel à la prochaine couche

        # Code ici → s'exécute APRÈS la vue (réponse disponible)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info("%s %s → %d (%.1f ms)", request.method, request.path,
                    response.status_code, duration_ms)
        return response
```

**Ordre du middleware :** les requêtes descendent (top → bottom), les réponses remontent (bottom → top).

---

## 3. Django REST Framework en profondeur

### 3.1 Serializers vs Pydantic

| | Pydantic (FastAPI) | DRF Serializer |
|-|-------------------|----------------|
| Définition | `class Item(BaseModel)` | `class ItemSerializer(ModelSerializer)` |
| Validation | Automatique (type hints) | `.is_valid()` → `.errors` |
| Sérialisation | `item.model_dump()` | `serializer.data` |
| Création | `Item(**data)` | `serializer.save()` |
| Champs générés | Depuis annotations | Depuis `Meta.model` + `fields` |
| Champs custom | `@validator` / `@computed_field` | `SerializerMethodField` |
| Imbrication | Nested models | Nested serializers |

```python
class TodoSerializer(serializers.ModelSerializer):
    # Champ calculé (lecture seule) — méthode get_<nom>
    owner_username = serializers.SerializerMethodField()
    def get_owner_username(self, obj):
        return obj.owner.username

    # Lecture imbriquée / écriture par ID
    category_detail = CategorySerializer(source="category", read_only=True)
    category = serializers.PrimaryKeyRelatedField(write_only=True, …)

    # Affichage lisible d'un TextChoices
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)

    class Meta:
        model = Todo
        fields = ["id", "title", "priority", "priority_display", …]
        read_only_fields = ["id", "created_at"]
```

### 3.2 ViewSets et Routers

Un **ViewSet** regroupe toutes les actions CRUD. Un **Router** génère automatiquement les URLs correspondantes.

```python
# ViewSet = list + create + retrieve + update + partial_update + destroy
class TodoViewSet(viewsets.ModelViewSet):
    serializer_class = TodoSerializer

    def get_queryset(self):
        # TOUJOURS filtrer par owner — isolation des données
        return Todo.objects.filter(owner=self.request.user)

# Router → génère automatiquement :
#   GET  /todos/           → list
#   POST /todos/           → create
#   GET  /todos/{id}/      → retrieve
#   PUT  /todos/{id}/      → update
#   PATCH /todos/{id}/     → partial_update
#   DELETE /todos/{id}/    → destroy
router = DefaultRouter()
router.register(r"todos", TodoViewSet, basename="todo")
urlpatterns = router.urls
```

**Actions custom avec `@action` :**

```python
@action(detail=False, methods=["get"], url_path="stats")
def stats(self, request):
    # detail=False → /todos/stats/
    # detail=True  → /todos/{id}/stats/
    return Response({…})
```

### 3.3 Permissions

```python
# Permission globale (toutes les actions)
permission_classes = [IsAuthenticated]

# Par action — override get_permissions()
def get_permissions(self):
    if self.action == "create":
        return [AllowAny()]
    return [IsAdminUser()]

# Permission au niveau objet (detail views)
class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user

# Permissions intégrées : AllowAny, IsAuthenticated, IsAdminUser,
# IsAuthenticatedOrReadOnly, DjangoModelPermissions
```

### 3.4 Filtrage, Recherche, Tri

```python
class TodoViewSet(viewsets.ModelViewSet):
    filter_backends = [
        DjangoFilterBackend,    # ?completed=true&priority=high
        filters.SearchFilter,   # ?search=term (LIKE sur search_fields)
        filters.OrderingFilter, # ?ordering=-created_at
    ]
    filterset_class = TodoFilter  # FilterSet déclaratif
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "priority", "due_date"]
```

**FilterSet :**

```python
class TodoFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")
    due_date_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")

    class Meta:
        model = Todo
        fields = ["completed", "priority"]
```

### 3.5 Throttling (limitation de débit)

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
    },
}

# Désactivé en développement (development.py) :
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
```

### 3.6 Pagination

```python
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"  # ?page_size=50
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "pagination": {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
            },
            "results": data,
        })
```

---

## 4. Tests avec pytest-django

### Structure

```
apps/
  todos/
    tests/
      __init__.py
      factories.py    ← factory_boy
      test_views.py   ← tests des endpoints
```

### Fixtures et factories

```python
# factory_boy génère des données réalistes avec un minimum de code
class TodoFactory(DjangoModelFactory):
    class Meta:
        model = Todo

    title = factory.Faker("sentence", nb_words=4)
    owner = factory.SubFactory(UserFactory)
    # SubFactory avec référence au parent : même owner que le todo
    category = factory.SubFactory(CategoryFactory,
                                  owner=factory.SelfAttribute("..owner"))
```

### Écrire un test

```python
@pytest.mark.django_db  # autorise l'accès à la DB (transaction rollbackée après)
class TestTodoViewSet:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)  # pas besoin de JWT

    def test_create_todo(self):
        payload = {"title": "Buy milk", "priority": "high"}
        response = self.client.post("/api/v1/todos/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Buy milk"

    def test_cannot_access_other_users_todo(self):
        other_todo = TodoFactory(owner=UserFactory())
        response = self.client.get(f"/api/v1/todos/{other_todo.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
```

### Fixtures pytest utiles

```python
# conftest.py
@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def authenticated_client(api_client, db):
    user = UserFactory()
    api_client.force_authenticate(user=user)
    return api_client, user
```

---

## 5. Settings Django — Bonnes pratiques

```python
# Ne jamais mettre de secrets dans settings.py — utiliser .env
SECRET_KEY = env("SECRET_KEY")  # django-environ

# Séparer INSTALLED_APPS par catégorie
DJANGO_APPS = ["django.contrib.admin", …]
THIRD_PARTY_APPS = ["rest_framework", …]
LOCAL_APPS = ["apps.users", "apps.todos"]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# DATABASE_URL comprend tout en une chaîne :
# sqlite:///db.sqlite3
# postgresql://user:pass@localhost:5432/mydb
DATABASES = {"default": env.db("DATABASE_URL")}
```

---

## 6. Migrations — Workflow

```bash
# Générer les migrations depuis les changements de modèles
python manage.py makemigrations

# Voir le SQL qu'une migration va exécuter (sans l'appliquer)
python manage.py sqlmigrate todos 0001

# Appliquer toutes les migrations en attente
python manage.py migrate

# État des migrations
python manage.py showmigrations

# Revenir à une migration précédente (rollback)
python manage.py migrate todos 0002

# Squasher des migrations pour nettoyer l'historique
python manage.py squashmigrations todos 0001 0010
```

**Règles :**
1. Ne jamais modifier une migration déjà appliquée en production
2. Committer les migrations dans git avec le code qui les génère
3. Tester les migrations (forward + backward) avant de déployer

---

## 7. Où aller ensuite

| Technologie | Usage | Priorité pour apprendre |
|------------|-------|-------------------------|
| **Celery** | Tâches asynchrones / files de messages | Haute — quasi-obligatoire en prod |
| **django-celery-beat** | Tâches planifiées (cron) | Haute |
| **Django Channels** | WebSockets / temps réel | Moyenne |
| **django-allauth** | Auth sociale (Google, GitHub…) | Moyenne |
| **django-storages** | Fichiers media sur S3 / GCS | Moyenne |
| **Sentry** | Tracking d'erreurs en production | Haute |
| **django-ninja** | API Django avec type hints Pydantic (style FastAPI) | Moyenne — alternative à DRF |
| **Wagtail** | CMS Django | Si vous avez besoin d'un CMS |
| **django-import-export** | Import/export CSV/Excel dans l'admin | Faible mais pratique |
| **django-debug-toolbar** | Debugging des requêtes en dev | Très utile pour l'optimisation |
| **django-silk** | Profiling des requêtes | Utile pour l'optimisation |
| **drf-standardized-errors** | Réponses d'erreur standardisées | Bonne pratique d'API |

### Commandes de diagnostic utiles

```bash
# Inspecter les requêtes SQL générées (activer logging dans settings)
python manage.py shell
>>> from django.db import connection
>>> from apps.todos.models import Todo
>>> list(Todo.objects.filter(owner_id=1).select_related("category"))
>>> connection.queries  # liste toutes les requêtes exécutées

# Valider la configuration
python manage.py check
python manage.py check --deploy  # vérifications supplémentaires pour la prod

# Shell avancé avec auto-import
pip install django-extensions
python manage.py shell_plus
```

---

## 8. Anti-patterns courants (erreurs à éviter)

| Anti-pattern | Problème | Solution |
|-------------|---------|----------|
| Ne pas définir `AUTH_USER_MODEL` avant la 1ère migration | Impossible à changer après | Toujours définir `AUTH_USER_MODEL` dans `base.py` |
| Importer les signals au niveau du module | Double enregistrement en tests | Importer dans `AppConfig.ready()` |
| Filtrer les données dans le serializer | La logique d'isolation doit être dans `get_queryset()` | Toujours filtrer dans `get_queryset()` |
| N+1 queries | 1 requête par objet dans une liste | `select_related()` / `prefetch_related()` |
| `Model.objects.all()` sans filtre dans un ViewSet | Expose les données de tous les users | Toujours filtrer par `owner=request.user` |
| Boucle de `.save()` pour bulk update | N requêtes UPDATE | `QuerySet.update()` → 1 seul UPDATE |
| Secrets dans `settings.py` | Risque de sécurité si le code est public | Variables d'environnement via `django-environ` |
| Pas de pagination sur les listes | Retourne potentiellement des millions de lignes | Toujours paginer les endpoints de liste |
