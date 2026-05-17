# ROUTES.md — Anatomie des requêtes, couche par couche

Guide pédagogique pour développeurs FastAPI migrant vers Django/DRF.  
Chaque route est tracée de l'octet TCP entrant jusqu'au JSON renvoyé.  
Les comparaisons FastAPI sont isolées dans des blocs séparés pour ne pas brouiller la lecture Django.

**5 routes choisies pour couvrir des features distinctes :**

| Route | Feature Django principale |
|-------|--------------------------|
| `POST /api/v1/users/` | Middleware, `get_permissions()`, `get_serializer_class()`, cross-field validation, Signal `post_save` |
| `POST /api/v1/auth/token/` | SimpleJWT, authentication backend, `check_password()`, JWT encoding |
| `GET /api/v1/todos/?...` | JWTAuthentication, `get_queryset()`, N+1 prevention, FilterSet, SearchFilter, Pagination |
| `POST /api/v1/todos/` | Serializer `__init__` queryset scoping, dual read/write fields, ManyToMany `.set()` |
| `PATCH /api/v1/users/{id}/` | `has_permission` vs `has_object_permission`, `get_object()`, `partial=True` |

---

## Route 1 — POST /api/v1/users/ : Inscription

**Requête :** `POST /api/v1/users/` avec `{"username": "alice", "email": "alice@example.com", "password": "secret123", "password_confirm": "secret123"}`

**Features couvertes :** Middleware (onion pattern), `get_permissions()` par action, `get_serializer_class()` par action, cross-field `validate()`, `set_password()`, Signal `post_save`, création automatique de `UserProfile` via `OneToOneField`

### Arbre de flux

```
POST /api/v1/users/ ──────────────────────────────────────────────────────
│
├── [1] Middleware Stack (descente, top → bottom)
│   ├── SecurityMiddleware          — force HTTPS, headers X-Content-Type, HSTS
│   ├── SessionMiddleware           — parse cookie de session (inutile pour JWT, toujours présent)
│   ├── CommonMiddleware            — normalise les trailing slashes, gère Content-Type
│   ├── CsrfViewMiddleware          — vérifie le token CSRF (DRF l'exclut pour APIView via SessionAuthentication)
│   ├── AuthenticationMiddleware    — attache AnonymousUser à request.user (Django core, pas DRF)
│   ├── MessageMiddleware           — messages flash (inutile ici, mais dans la stack)
│   ├── XFrameOptionsMiddleware     — header X-Frame-Options: DENY (clickjacking)
│   └── RequestLoggingMiddleware    — chronomètre : start = time.monotonic()
│
├── [2] URL Resolver (config/urls.py)
│   ├── Itère urlpatterns dans l'ordre, cherche le premier match pour "/api/v1/users/"
│   ├── path("api/v1/", include("apps.users.urls"))  ← match "/api/v1/"
│   └── apps/users/urls.py : router.register(r"users", UserViewSet, basename="user")
│       └── DefaultRouter génère : POST /users/ → UserViewSet, action="create"
│
├── [3] DRF dispatch — avant d'entrer dans la vue
│   ├── DRF enveloppe HttpRequest dans son propre Request object
│   ├── JWTAuthentication.authenticate() — header Authorization absent → AnonymousUser
│   ├── UserViewSet.get_permissions()
│   │   └── self.action == "create" → return [AllowAny()]
│   └── AllowAny.has_permission() → True (toujours)
│
├── [4] UserViewSet.create() — hérité de ModelViewSet
│   ├── get_serializer_class()
│   │   └── self.action == "create" → return UserRegistrationSerializer
│   ├── serializer = UserRegistrationSerializer(data=request.data, context={"request": ...})
│   └── serializer.is_valid(raise_exception=True) ──────────────────────────
│       │
│       ├── Validation champ par champ (ordre Django : chaque field.run_validators())
│       │   ├── username   CharField(max_length=150) — longueur, caractères autorisés
│       │   ├── email      EmailField(unique=True)   — format RFC + SELECT EXISTS en DB
│       │   ├── password   CharField(write_only=True, min_length=8) — longueur minimum
│       │   └── password_confirm CharField(write_only=True)
│       │
│       └── validate(attrs) — validation cross-field (toujours après les champs individuels)
│           ├── attrs["password"] != attrs.pop("password_confirm") ?
│           ├── OUI → raise ValidationError({"password_confirm": "Passwords do not match."})
│           │         → DRF retourne 400 {"password_confirm": ["Passwords do not match."]}
│           └── NON → retourne attrs (password_confirm poppé — NE sera PAS passé à create())
│
├── [5] serializer.save() → create(validated_data)
│   ├── password = validated_data.pop("password")
│   ├── user = User(**validated_data)      — instancie l'objet Python, PAS encore en DB
│   ├── user.set_password(password)        — hachage PBKDF2-SHA256 + salt aléatoire
│   └── user.save()
│       └── SQL : INSERT INTO users_user (id, username, email, password, ...) VALUES (...)
│
├── [6] Signal post_save — déclenché automatiquement par Django après le save()
│   ├── Django émet : post_save(sender=User, instance=user, created=True, ...)
│   ├── create_user_profile() [apps/users/signals.py]
│   │   ├── created=True → c'est un INSERT (pas un UPDATE)
│   │   └── UserProfile.objects.create(user=instance)
│   │       └── SQL : INSERT INTO users_userprofile (user_id, preferences, updated_at) VALUES (...)
│   └── save_user_profile() — garde-fou : instance.profile.save() si le profil existe déjà
│
├── [7] Middleware (remontée, bottom → top)
│   └── RequestLoggingMiddleware
│       └── duration_ms = (time.monotonic() - start) * 1000
│           log : "POST /api/v1/users/ → 201 (45.2 ms) [127.0.0.1]"
│
└── RESPONSE : 201 Created
    {"username": "alice", "email": "alice@example.com"}
    (password absent de la réponse — write_only=True sur le champ)
```

### Zoom couche 1 — Middleware, le pattern onion

Le middleware Django est une liste ordonnée dans `MIDDLEWARE` ([config/settings/base.py:46](config/settings/base.py)). Chaque classe enveloppe la suivante — c'est le **pattern decorator/onion** : la requête traverse la liste de haut en bas, la réponse remonte de bas en haut.

```python
# middleware/request_logger.py
class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response  # référence à la couche suivante

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)  # ← toute la chaîne (vue comprise) s'exécute ici
        duration_ms = (time.monotonic() - start) * 1000
        logger.info("%s %s → %d (%.1f ms)", ...)
        return response
```

Point critique : `AuthenticationMiddleware` (Django core) attache `request.user = AnonymousUser` pour toutes les requêtes HTTP. DRF **réécrit** `request.user` via sa propre authentification (JWT). Ce sont deux mécanismes distincts — `AuthenticationMiddleware` sert à l'admin Django et aux templates, pas à l'API REST.

### Zoom couche 3 — get_permissions() par action

`self.action` est une string injectée par DRF correspondant à l'action en cours (`"create"`, `"list"`, `"retrieve"`, `"update"`, `"partial_update"`, `"destroy"`, ou le nom d'un `@action` custom).

```python
# apps/users/views.py
def get_permissions(self):
    if self.action == "create":
        return [permissions.AllowAny()]       # inscription : pas besoin d'être connecté
    if self.action in ("list", "destroy"):
        return [permissions.IsAdminUser()]    # lister/supprimer : admin seulement
    return [IsSelfOrAdmin()]                  # retrieve/update : soi-même ou admin
```

C'est le mécanisme Django pour avoir des permissions différentes par verb HTTP sur le même ViewSet sans dupliquer le code en plusieurs fonctions.

### Zoom couche 3 — get_serializer_class() par action

Même principe : un serializer dédié par cas d'usage.

```python
def get_serializer_class(self):
    if self.action == "create":
        return UserRegistrationSerializer  # expose password_confirm, pas de nested profile
    return UserSerializer                  # expose nested profile, SerializerMethodField, etc.
```

`UserRegistrationSerializer` est **single-responsibility** : il valide l'inscription uniquement. `UserSerializer` est le serializer de lecture/édition général. Les séparer évite d'avoir un serializer avec des conditions partout.

### Zoom couche 4 — validate() cross-field

```python
# apps/users/serializers.py
def validate(self, attrs: dict) -> dict:
    if attrs["password"] != attrs.pop("password_confirm"):
        raise serializers.ValidationError(
            {"password_confirm": "Passwords do not match."}
        )
    return attrs  # password_confirm poppé — ne sera jamais passé à create()
```

`validate()` sans suffixe = validation **globale** qui reçoit tous les champs validés. `validate_<field>()` = validation d'un seul champ spécifique. L'ordre d'exécution : d'abord chaque `validate_<field>()`, puis `validate()` global.

### Zoom couche 6 — Signal post_save

```python
# apps/users/signals.py
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:  # True uniquement sur INSERT, False sur UPDATE
        UserProfile.objects.create(user=instance)
```

Ce signal est enregistré dans `UsersConfig.ready()` ([apps/users/apps.py:9](apps/users/apps.py)). Django émet `post_save` **après** le `user.save()`, dans la même transaction. La séquence des signals enregistrés sur le même sender + même signal est l'ordre d'enregistrement.

> ---
> **vs FastAPI**
>
> | | FastAPI | Django/DRF |
> |---|---|---|
> | Routing | `@app.post("/users")` sur une fonction | `router.register("users", UserViewSet)` — Router génère toutes les URLs CRUD |
> | Permissions par verb | `Depends()` différent par fonction handler | `get_permissions()` override — un seul ViewSet, logique centralisée |
> | Validation cross-field | `@model_validator(mode="after")` sur un Pydantic model | `validate()` sur le Serializer |
> | Hachage password | Manuel avec `passlib` / `bcrypt` | `user.set_password()` — PBKDF2+SHA256 intégré dans Django |
> | Side-effects au save | Callback explicite dans le handler | Signal `post_save` — découplé, dans un fichier séparé, zéro couplage |
> | Middleware | `app.add_middleware(...)` (Starlette) | Liste `MIDDLEWARE` dans settings — même pattern onion |
> ---

---

## Route 2 — POST /api/v1/auth/token/ : Connexion JWT

**Requête :** `POST /api/v1/auth/token/` avec `{"username": "alice", "password": "secret123"}`

**Features couvertes :** `TokenObtainPairView` (APIView, pas ViewSet), authentication backend Django, `check_password()` PBKDF2, JWT encoding HS256, stateless auth

### Arbre de flux

```
POST /api/v1/auth/token/ ─────────────────────────────────────────────────
│
├── [1] Middleware Stack (descente) — identique à toute requête
│
├── [2] URL Resolver (config/urls.py)
│   └── path("api/v1/auth/token/", TokenObtainPairView.as_view())
│       └── Pas de Router — SimpleJWT expose des vues directement comme des APIView
│
├── [3] TokenObtainPairView — fournie par simplejwt, zéro code custom nécessaire
│   ├── Hérite de APIView (pas ModelViewSet — pas de CRUD implicite, juste un POST)
│   ├── permission_classes = [AllowAny]   (se connecter ne requiert pas d'être authentifié)
│   └── authentication_classes = []       (pas d'auth JWT pour obtenir un JWT)
│
├── [4] TokenObtainPairSerializer.validate()
│   ├── authenticate(request, username="alice", password="secret123")
│   │   ├── Django itère AUTHENTICATION_BACKENDS (settings : ModelBackend par défaut)
│   │   ├── ModelBackend.authenticate()
│   │   │   ├── User.objects.get(username="alice")
│   │   │   │   └── SELECT * FROM users_user WHERE username = 'alice'
│   │   │   ├── user.check_password("secret123")
│   │   │   │   └── PBKDF2-SHA256 : recalcule hash(raw_password + salt) == stored_hash ?
│   │   │   └── retourne user si match, None sinon
│   │   └── (Protection timing : même si le user n'existe pas, un hash factice est calculé)
│   │
│   ├── user is None → raise AuthenticationFailed → 401 Unauthorized
│   ├── user.is_active == False → raise AuthenticationFailed → 401 Unauthorized
│   │
│   └── Génération des tokens
│       ├── refresh = RefreshToken.for_user(user)
│       │   └── Payload : {"token_type": "refresh", "exp": <now+7j>, "iat": <now>, "jti": "<uuid>", "user_id": "<uuid>"}
│       │       Signature : HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)
│       └── access = refresh.access_token
│           └── Payload : {"token_type": "access", "exp": <now+60min>, "iat": <now>, "jti": "<uuid>", "user_id": "<uuid>"}
│
├── [5] Middleware (remontée) — log
│
└── RESPONSE : 200 OK
    {
      "access":  "eyJhbGci...",    ← valide 60 min (JWT_ACCESS_MINUTES dans .env)
      "refresh": "eyJhbGci..."     ← valide 7 jours (JWT_REFRESH_DAYS dans .env)
    }
```

### Zoom couche 3 — APIView vs ViewSet

`TokenObtainPairView` hérite d'`APIView`. La hiérarchie complète :

```
APIView
  └── GenericAPIView      (+ queryset, serializer_class, get_object()...)
        └── ModelViewSet  (+ list, create, retrieve, update, destroy)
```

`APIView` = une vue qui handle une seule ressource, pas de CRUD implicite. On surcharge `get()`, `post()`, `patch()`, etc. directement. C'est l'équivalent d'un handler FastAPI classique — simple et direct.

`ModelViewSet` = les 6 actions CRUD générées automatiquement depuis le modèle + Router.

### Zoom couche 4 — Authentication backend Django

`authenticate()` est une fonction Django core (pas DRF). Elle itère sur `AUTHENTICATION_BACKENDS` :

```python
# Configurable dans settings.py
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
# On peut en ajouter d'autres : LDAP, OAuth, token custom, etc.
```

`ModelBackend` fait deux choses :
1. Cherche le user par `username` en DB
2. Appelle `user.check_password(raw_password)` qui recalcule le hash PBKDF2 et compare bit-à-bit

Le hash stocké en DB a ce format : `pbkdf2_sha256$<iterations>$<salt>$<hash>`. Tout est dans la colonne `password` de la table `users_user`.

### Zoom — Anatomie du JWT

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9   ← Header (base64)   {"alg": "HS256", "typ": "JWT"}
.
eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwI  ← Payload (base64)  {"token_type": "access", "exp": ..., "user_id": "uuid"}
.
xK8mN2pL...                              ← Signature          HMAC-SHA256(header.payload, SECRET_KEY)
```

Le token n'est **pas stocké en base** (stateless). Django le valide à chaque requête en recalculant la signature avec `SECRET_KEY`. Si quelqu'un modifie le payload, la signature ne correspond plus → 401.

> ---
> **vs FastAPI**
>
> | | FastAPI (typique) | Django/SimpleJWT |
> |---|---|---|
> | Login endpoint | Fonction décorée `@app.post("/token")` | `TokenObtainPairView.as_view()` — zéro code custom |
> | Vérification password | `pwd_context.verify(plain, hashed)` avec passlib | `user.check_password(plain)` — méthode sur le model User |
> | Auth backend | Service custom ou dépendance | `AUTHENTICATION_BACKENDS` — pluggable (LDAP, OAuth, custom) sans changer le code métier |
> | Refresh token | Endpoint custom ou bibliothèque | `TokenRefreshView` fourni par simplejwt |
> | Blacklist | Souvent Redis custom | `rest_framework_simplejwt.token_blacklist` (app Django à activer) |
> ---

---

## Route 3 — GET /api/v1/todos/?priority=high&search=work&ordering=-due_date : Liste filtrée

**Requête :** `GET /api/v1/todos/?priority=high&search=work&ordering=-due_date` avec `Authorization: Bearer eyJ...`

**Features couvertes :** `JWTAuthentication` (decode + user load), `IsOwner`, `get_queryset()` avec N+1 prevention (`select_related`/`prefetch_related`), `FilterSet` déclaratif, `SearchFilter`, `OrderingFilter`, Pagination custom, réponse enveloppée

### Arbre de flux

```
GET /api/v1/todos/?priority=high&search=work&ordering=-due_date ──────────
│
├── [1] Middleware (descente)
│   └── RequestLoggingMiddleware : start = time.monotonic()
│
├── [2] URL Resolver
│   └── include("apps.todos.urls") → DefaultRouter → GET /todos/ → TodoViewSet, action="list"
│
├── [3] DRF Authentication — JWTAuthentication
│   ├── Lit le header : Authorization: Bearer eyJ...
│   ├── Sépare "Bearer" + token_str (AUTH_HEADER_TYPES = ("Bearer",) dans SIMPLE_JWT)
│   ├── UntypedToken(token_str)
│   │   ├── Décode base64(header) + base64(payload)
│   │   ├── Recalcule HMAC-SHA256 → compare avec la signature → invalide → 401
│   │   ├── Vérifie exp : token expiré → raise TokenExpired → 401
│   │   └── Vérifie token_type == "access" (le refresh token est refusé ici)
│   ├── Extrait user_id du payload JWT
│   ├── User.objects.get(pk=user_id)
│   │   └── SELECT * FROM users_user WHERE id = '<alice-uuid>'
│   └── request.user = <User: alice>  /  request.auth = token validé
│
├── [4] Permissions — IsOwner
│   ├── has_permission(request, view)
│   │   └── request.user.is_authenticated → True ✓
│   └── has_object_permission NON appelé ici (action="list", pas de {pk})
│
├── [5] Throttling — UserRateThrottle
│   ├── Clé cache : "throttle_user_<user_id>"
│   ├── Vérifie l'historique : < 1000 requêtes sur les dernières 24h ?
│   └── (Désactivé en development.py : DEFAULT_THROTTLE_CLASSES = [])
│
├── [6] TodoViewSet.get_queryset() ← isolation des données + N+1 prevention
│   └── Todo.objects.filter(owner=request.user)
│               .select_related("owner", "category")
│               .prefetch_related("tags")
│   Pas de SQL exécuté ici — le queryset est LAZY (assemblage de l'AST SQL seulement)
│
├── [7] Filter backends — appliqués en séquence sur le queryset
│   │   (config/settings/base.py : DEFAULT_FILTER_BACKENDS)
│   │
│   ├── DjangoFilterBackend → TodoFilter.filter_queryset()
│   │   ├── Lit ?priority=high → ChoiceFilter → queryset.filter(priority="high")
│   │   ├── ?completed non fourni → ignoré
│   │   └── ?tag, ?category non fournis → ignorés
│   │
│   ├── SearchFilter → ?search=work
│   │   └── queryset.filter(Q(title__icontains="work") | Q(description__icontains="work"))
│   │       (search_fields = ["title", "description"] sur TodoViewSet)
│   │
│   └── OrderingFilter → ?ordering=-due_date
│       ├── "-" devant le champ = ORDER BY due_date DESC
│       ├── ordering_fields restreint les champs autorisés (sécurité)
│       └── queryset.order_by("-due_date")
│   Toujours pas de SQL — tout s'accumule dans l'AST du QuerySet
│
├── [8] Pagination — StandardResultsSetPagination
│   ├── paginate_queryset(queryset, request)
│   │   ├── queryset.count()    → SELECT COUNT(*) FROM todos_todo WHERE ... (1 requête)
│   │   └── queryset[0:20]      → SELECT ... LIMIT 20 OFFSET 0     (1 requête)
│   │       ← ici le SQL est enfin exécuté (premier accès réel aux données)
│   └── get_paginated_response(serializer.data) → enveloppe {pagination, results}
│
├── [9] Sérialisation — TodoSerializer(queryset_page, many=True)
│   Pour chaque Todo de la page (20 objets max) :
│   ├── id, title, description, completed, priority  — champs directs
│   ├── priority_display  ← source="get_priority_display" (méthode TextChoices)
│   │                       retourne "High" pour priority="high"
│   ├── owner_username    ← SerializerMethodField → obj.owner.username
│   │                       PAS de requête SQL : select_related a déjà chargé owner
│   ├── category_detail   ← CategorySerializer(source="category")
│   │                       PAS de requête SQL : select_related a déjà chargé category
│   └── tags              ← TagSerializer(many=True)
│                           PAS de requête SQL : prefetch_related a déjà chargé tous les tags
│   Total SQL pour 20 todos : 3 requêtes (count + select join + prefetch tags)
│
├── [10] Middleware (remontée)
│    └── RequestLoggingMiddleware : log "GET /api/v1/todos/ → 200 (23.1 ms) [127.0.0.1]"
│
└── RESPONSE : 200 OK
    {
      "pagination": {
        "count": 42,
        "page": 1,
        "page_size": 20,
        "total_pages": 3,
        "next": "http://localhost:8000/api/v1/todos/?page=2&priority=high&...",
        "previous": null
      },
      "results": [
        {"id": "...", "title": "Work meeting", "priority": "high", "priority_display": "High",
         "tags": [{"id": "...", "name": "urgent", "slug": "urgent"}],
         "category_detail": {"id": "...", "name": "Work", "color": "#3B82F6"},
         "owner_username": "alice",
         ...},
        ...
      ]
    }
```

### Zoom couche 3 — Comment DRF injecte request.user (lazy)

DRF enveloppe le `HttpRequest` Django dans son propre objet `Request`. `request.user` est une **property lazy** :

```python
# Simplifié de DRF source
@property
def user(self):
    if not hasattr(self, "_user"):
        self._authenticate()  # JWTAuthentication.authenticate(self) appelé ici
    return self._user
```

Le premier accès à `request.user` déclenche l'itération sur `authentication_classes`. `JWTAuthentication` est la première (et seule) classe configurée. Si elle retourne `(None, None)`, DRF continue la liste. Si aucune ne retourne de user, `AnonymousUser` est utilisé.

### Zoom couche 6 — select_related vs prefetch_related

Sans optimisation, pour une liste de 20 todos avec sérialisation des relations :
- 1 requête `SELECT * FROM todos_todo WHERE owner_id = ?`
- 20 × `SELECT * FROM users_user WHERE id = ?` (owner)
- 20 × `SELECT * FROM todos_category WHERE id = ?` (category)
- 20 × `SELECT * FROM todos_todo_tags t JOIN todos_tag tag ON ...` (tags)
= **61 requêtes SQL** pour 20 todos

Avec `select_related("owner", "category").prefetch_related("tags")` :
- 1 requête `SELECT todo.*, user.*, cat.* FROM todos_todo JOIN users_user JOIN todos_category WHERE owner_id = ?`
- 1 requête `SELECT tag.* ... WHERE todo_id IN (id1, id2, ..., id20)` (batch prefetch)
= **3 requêtes SQL** (count + les 2 ci-dessus)

Règle : `select_related` = FK et OneToOne → SQL JOIN. `prefetch_related` = M2M et reverse FK → requête séparée avec `IN (...)`.

### Zoom couche 7 — La chaîne de filter backends

```python
# DRF applique chaque backend en séquence — pipe fonctionnel
def filter_queryset(self, queryset):
    for backend in list(self.filter_backends):
        queryset = backend().filter_queryset(self.request, queryset, self)
    return queryset
```

Chaque backend reçoit le queryset de la couche précédente et retourne un queryset filtré. Les filtres s'accumulent via AND implicite. L'ORM Django enchaîne les `.filter()` sans exécuter de SQL intermédiaire grâce à la lazyness du QuerySet.

`TodoFilter` ([apps/todos/filters.py](apps/todos/filters.py)) — un `FilterSet` déclaratif :

```python
class TodoFilter(django_filters.FilterSet):
    priority      = django_filters.ChoiceFilter(choices=Todo.Priority.choices)
    due_date_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    tag            = django_filters.UUIDFilter(field_name="tags__id")  # traverse M2M via __
    # ...
```

`field_name="tags__id"` utilise le **double underscore** de Django pour traverser les relations — `queryset.filter(tags__id=<uuid>)` génère un JOIN automatique.

### Zoom couche 8 — Pourquoi count() avant le slice

```python
# Pagination — deux requêtes distinctes
queryset.count()    # SELECT COUNT(*) ... → pour construire total_pages, next, previous
queryset[0:20]      # SELECT ... LIMIT 20 OFFSET 0 → les données réelles
```

`queryset[0:20]` en Python → Django traduit en `LIMIT 20 OFFSET 0` SQL. C'est le **slicing** du QuerySet — il n'exécute pas la requête entière en mémoire pour la tronquer, il génère le SQL paginé directement.

> ---
> **vs FastAPI**
>
> | | FastAPI | Django/DRF |
> |---|---|---|
> | Authentication | `Depends(get_current_user)` dans la signature de la fonction | `JWTAuthentication` dans `DEFAULT_AUTHENTICATION_CLASSES` — transparent, zéro code |
> | Filtrage | Query params manuels ou `fastapi-filter` | `FilterSet` déclaratif + `SearchFilter` + `OrderingFilter` — zéro boilerplate |
> | N+1 prevention | `joinedload()`/`selectinload()` SQLAlchemy dans la query | `select_related()`/`prefetch_related()` dans `get_queryset()` |
> | Pagination | Manuel ou bibliothèque externe | `PageNumberPagination` — configurable globalement ou par ViewSet |
> | Réponse enveloppée | Schéma Pydantic custom en `response_model` | Override de `get_paginated_response()` dans la classe Pagination |
> | QuerySet lazy | SQLAlchemy lazy loading (différent) | QuerySet ne s'exécute qu'au premier accès aux données |
> ---

---

## Route 4 — POST /api/v1/todos/ : Création avec FK et Many-to-Many

**Requête :** `POST /api/v1/todos/` avec `{"title": "Réunion équipe", "priority": "high", "category": "<cat-uuid>", "tag_ids": ["<tag1-uuid>", "<tag2-uuid>"]}`

**Features couvertes :** `Serializer.__init__()` pour scoper les querysets (isolation sécurité), champs dual lecture/écriture (`read_only` vs `write_only`), `source=` pour remapper les noms, `PrimaryKeyRelatedField`, `ManyToMany.set()`, owner injecté côté serveur (jamais exposé côté client)

### Arbre de flux

```
POST /api/v1/todos/ (Authorization: Bearer alice-token) ──────────────────
│
├── [1-3] Middleware + URL Resolver + Auth — identique Route 3
│
├── [4] Permissions — IsOwner.has_permission()
│   └── request.user.is_authenticated → True ✓
│
├── [5] TodoViewSet.create() — hérité de ModelViewSet
│   └── serializer = self.get_serializer(data=request.data)
│       ↓ instancie TodoSerializer(data={...}, context={"request": request, "view": self, "format": None})
│
├── [6] TodoSerializer.__init__() ← couche critique pour l'isolation sécurité
│   ├── super().__init__(*args, **kwargs)  — champs déclarés dans la class body instanciés normalement
│   ├── request = self.context.get("request")
│   ├── Restriction dynamique du queryset de tag_ids :
│   │   self.fields["tag_ids"].child_relation.queryset = Tag.objects.filter(owner=request.user)
│   │   → alice ne peut soumettre que des tag UUID qui lui appartiennent
│   └── Restriction dynamique du queryset de category :
│       self.fields["category"].queryset = Category.objects.filter(owner=request.user)
│       → alice ne peut pas assigner la catégorie de bob
│   (Valeur par défaut : Tag.objects.none() — fail-safe sécurisé si context absent)
│
├── [7] serializer.is_valid(raise_exception=True)
│   │
│   ├── Champs WRITE-ONLY (acceptés en entrée, jamais dans la réponse) :
│   │   ├── category (PrimaryKeyRelatedField)
│   │   │   ├── Lit "<cat-uuid>" depuis le body
│   │   │   ├── SELECT * FROM todos_category WHERE id = '<cat-uuid>' AND owner_id = '<alice>'
│   │   │   └── Objet Category chargé → validated_data["category"] = <Category: Work>
│   │   └── tag_ids (PrimaryKeyRelatedField many=True, source="tags")
│   │       ├── Pour chaque UUID dans ["<tag1>", "<tag2>"] :
│   │       │   SELECT * FROM todos_tag WHERE id = ? AND owner_id = '<alice>'
│   │       └── validated_data["tags"] = [<Tag: urgent>, <Tag: team>]
│   │           (source="tags" → la clé dans validated_data est "tags", pas "tag_ids")
│   │
│   ├── Champs READ-ONLY (ignorés en entrée, même s'ils sont dans le body) :
│   │   ├── tags           (TagSerializer many=True)    — ignoré en écriture
│   │   ├── category_detail (CategorySerializer)         — ignoré en écriture
│   │   └── owner_username  (SerializerMethodField)      — ignoré en écriture
│   │
│   └── Autres champs : title (min_length=1), priority (choices), due_date (DateField, optionnel)
│
├── [8] serializer.save() → create(validated_data)
│   ├── tags = validated_data.pop("tags", [])
│   │   → retire les objets Tag de validated_data (Todo.objects.create ne sait pas gérer M2M)
│   ├── validated_data["owner"] = self.context["request"].user
│   │   → owner injecté ici — le client ne peut PAS l'imposer depuis le body
│   ├── todo = Todo.objects.create(**validated_data)
│   │   └── SQL : INSERT INTO todos_todo (id, title, priority, category_id, owner_id, ...) VALUES (...)
│   └── if tags: todo.tags.set(tags)
│       └── SQL 1 : DELETE FROM todos_todo_tags WHERE todo_id = '<new-todo-uuid>'  (reset)
│           SQL 2 : INSERT INTO todos_todo_tags (todo_id, tag_id) VALUES (?, ?), (?, ?)
│
├── [9] Sérialisation de la réponse — re-sérialise l'instance fraîchement créée
│   ├── tags           ← les objets Tag — déjà en mémoire (pas de requête SQL)
│   ├── category_detail ← CategorySerializer(source="category") — objet complet, pas l'UUID
│   └── owner_username ← obj.owner.username
│
└── RESPONSE : 201 Created
    {
      "id": "...",
      "title": "Réunion équipe",
      "priority": "high",
      "priority_display": "High",
      "category_detail": {"id": "...", "name": "Work", "color": "#3B82F6"},
      "tags": [{"id": "...", "name": "urgent", "slug": "urgent"}, ...],
      "owner_username": "alice"
      // category et tag_ids absents : write_only=True
    }
```

### Zoom couche 6 — Pourquoi scoper dans __init__ et pas ailleurs

```python
# apps/todos/serializers.py
tag_ids = serializers.PrimaryKeyRelatedField(
    many=True,
    queryset=Tag.objects.none(),  # ← none() par défaut — fail-safe sécurisé
    write_only=True,
    source="tags",                # ← remapping : "tag_ids" en API → "tags" en interne
    required=False,
)

def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    request = self.context.get("request")
    if request and request.user.is_authenticated:
        self.fields["tag_ids"].child_relation.queryset = Tag.objects.filter(owner=request.user)
        self.fields["category"].queryset = Category.objects.filter(owner=request.user)
```

La raison du `__init__` : les champs de classe sont partagés entre toutes les instances du serializer. Le queryset scopé par user doit être **par-instance**, pas par-classe. Si on le mettait au niveau `queryset=Tag.objects.filter(owner=???)` dans la déclaration de classe, il n'y aurait pas de contexte request disponible.

`Tag.objects.none()` retourne un QuerySet vide — si le contexte manque (ex: serializer utilisé en dehors d'une request), aucun tag ne sera accepté plutôt que tous. C'est un **secure default**.

### Zoom couche 7 — La dualité read/write sur le même champ logique

```python
# Même concept "category" → deux champs avec des rôles opposés

# Entrée (write_only) : client envoie un UUID
category = serializers.PrimaryKeyRelatedField(
    queryset=Category.objects.none(),
    required=False,
    allow_null=True,
    write_only=True,
)

# Sortie (read_only) : client reçoit un objet complet
category_detail = CategorySerializer(source="category", read_only=True)
```

`source="category"` sur `category_detail` dit à DRF : "ce champ s'appelle `category_detail` dans la représentation API, mais il lit l'attribut `category` sur l'instance Todo". C'est le mécanisme qui permet de séparer proprement les noms d'entrée et de sortie.

### Zoom couche 8 — ManyToMany : set() vs add() vs clear()

```python
todo.tags.set(tags)   # atomique : DELETE existants + INSERT nouveaux (pattern create/update)
todo.tags.add(tag)    # ajoute sans toucher les existants (pattern append)
todo.tags.remove(tag) # retire une relation spécifique
todo.tags.clear()     # retire toutes les relations

# Dans update() — garde l'état si tags non fourni dans le PATCH
def update(self, instance, validated_data):
    tags = validated_data.pop("tags", None)  # None si non fourni (≠ [] qui viderait les tags)
    todo = super().update(instance, validated_data)
    if tags is not None:         # PATCH sans tag_ids → tags inchangés
        todo.tags.set(tags)      # PATCH avec tag_ids: [] → tags vidés
    return todo
```

> ---
> **vs FastAPI**
>
> | | FastAPI / SQLAlchemy | Django/DRF |
> |---|---|---|
> | Relations M2M en écriture | `session.execute(insert(item_tag_table)...)` ou `item.tags = [tag1, tag2]` | `todo.tags.set([tag1, tag2])` — table de jointure gérée automatiquement |
> | Scope queryset par user | `Depends()` retournant un queryset ou levant 403 | `__init__` du Serializer avec `self.context["request"].user` |
> | Dual read/write fields | Deux schémas Pydantic distincts (Request / Response) | Un Serializer unique avec `read_only`/`write_only` par champ + `source=` |
> | Injection de l'owner | Paramètre dans l'endpoint ou `Depends()` | `self.context["request"].user` dans `create()` — jamais exposé au client |
> | Validation de relation | Requête manuelle + levée d'exception | Queryset scopé sur `PrimaryKeyRelatedField` — DRF valide et charge l'objet automatiquement |
> ---

---

## Route 5 — PATCH /api/v1/users/{id}/ : Mise à jour avec permission au niveau objet

**Requête :** `PATCH /api/v1/users/<bob-uuid>/` avec `{"bio": "Updated bio"}` par l'utilisateur alice (non-admin)

**Features couvertes :** `has_permission` vs `has_object_permission`, `get_object()`, stratégie 403 vs 404, `partial=True` sur le serializer, `set_password()` conditionnel dans `update()`

### Arbre de flux

```
PATCH /api/v1/users/<bob-uuid>/ (Authorization: Bearer alice-token) ──────
│
├── [1-2] Middleware + URL Resolver
│   └── DefaultRouter → PATCH /users/{pk}/ → UserViewSet, action="partial_update"
│
├── [3] DRF Authentication
│   └── request.user = alice (depuis le JWT)
│
├── [4] UserViewSet.get_permissions()
│   ├── self.action == "partial_update"
│   │   → ni "create", ni "list", ni "destroy"
│   └── return [IsSelfOrAdmin()]
│
├── [5] IsSelfOrAdmin.has_permission(request, view)
│   ├── Vérification NIVEAU REQUÊTE — avant de charger l'objet, avant de faire la moindre requête DB
│   └── request.user.is_authenticated → True ✓  (alice est authentifiée)
│       Si False → 401 Unauthorized (ou 403 selon is_authenticated vs user is None)
│
├── [6] UserViewSet.partial_update() appelle get_object()
│   ├── queryset = self.get_queryset()
│   │   └── User.objects.select_related("profile").all()
│   │       (pas filtré par owner — les admins doivent voir tous les users)
│   ├── filter_kwargs = {"pk": "<bob-uuid>"}
│   ├── obj = queryset.get(**filter_kwargs)
│   │   └── SELECT * FROM users_user WHERE id = '<bob-uuid>'
│   │   Si bob n'existe pas → Http404 immédiat  (pas de 403, même si le vrai problème est les droits)
│   └── self.check_object_permissions(request, obj=bob)
│       └── Appelle has_object_permission() sur chaque permission de la liste
│
├── [7] IsSelfOrAdmin.has_object_permission(request, view, obj=bob)
│   ├── Vérification NIVEAU OBJET — l'objet est en mémoire, une décision granulaire possible
│   ├── request.user.is_staff → False (alice n'est pas admin)
│   ├── obj == request.user → bob == alice → False
│   └── retourne False → DRF raise PermissionDenied → 403 Forbidden
│       {"detail": "You do not have permission to access this resource."}
│
│   ══════════ Scénario alternatif : alice modifie SON PROPRE profil ══════
│
├── [6'] get_object() avec pk=<alice-uuid>
│   └── obj = alice (trouvé en DB)
│
├── [7'] IsSelfOrAdmin.has_object_permission(request, view, obj=alice)
│   ├── request.user.is_staff → False
│   └── obj == request.user → alice == alice → True ✓
│
├── [8] UserViewSet.partial_update() → update(request, pk=..., partial=True)
│   └── serializer = self.get_serializer(alice, data={"bio": "Updated bio"}, partial=True)
│       ↓ UserSerializer(instance=alice, data={...}, partial=True)
│
├── [9] serializer.is_valid(raise_exception=True) avec partial=True
│   ├── partial=True → les champs non fournis NE sont PAS requis
│   │   (username et email seraient normalement obligatoires — ici ignorés car absents)
│   ├── Validation uniquement sur les champs FOURNIS : bio (TextField, blank=True) → OK
│   └── validated_data = {"bio": "Updated bio"}
│
├── [10] serializer.save() → update(instance=alice, validated_data={"bio": "Updated bio"})
│   ├── password = validated_data.pop("password", None)  → None (non fourni dans le PATCH)
│   ├── if password: instance.set_password(password)     → skipped
│   └── super().update(instance, validated_data)
│       ├── for attr, value in validated_data.items(): setattr(instance, attr, value)
│       └── instance.save()
│           └── SQL : UPDATE users_user SET bio = 'Updated bio', updated_at = NOW() WHERE id = '<alice>'
│           → Signal post_save déclenché (created=False cette fois)
│               → save_user_profile() : instance.profile.save()
│
└── RESPONSE : 200 OK
    {"id": "...", "username": "alice", "email": "alice@example.com", "bio": "Updated bio",
     "profile": {"preferences": {}, "updated_at": "..."}, "todo_count": 5}
```

### Zoom couche 5+7 — has_permission vs has_object_permission

C'est une des distinctions les plus importantes de DRF :

```
has_permission(request, view)
  → Appelé sur CHAQUE requête, AVANT de toucher à la DB
  → Question : "cet utilisateur peut-il accéder à cette vue ?"
  → Si False → 403 Forbidden (ou 401 si non authentifié)
  → Appelé pour list, create, retrieve, update, destroy

has_object_permission(request, view, obj)
  → Appelé UNIQUEMENT sur les vues "detail" (avec {pk} dans l'URL)
  → Appelé APRÈS get_object() — l'objet est déjà en mémoire
  → Question : "cet utilisateur peut-il accéder à CET objet spécifique ?"
  → Si False → 403 Forbidden
  → N'est jamais appelé si has_permission() a retourné False
```

**Important :** pour les vues `list` et `create`, seul `has_permission` est appelé. `has_object_permission` n'est invoqué que quand il y a un `{pk}` dans l'URL.

### Zoom couche 6 — La stratégie 404 vs 403

**Comportement de sécurité intentionnel :** si l'objet n'est pas dans le queryset, Django retourne **404** (pas 403). Dans `TodoViewSet`, `get_queryset()` filtre déjà par `owner=request.user`. Si alice essaie d'accéder au todo de bob :

```
1. get_queryset() → Todo.objects.filter(owner=alice)
2. queryset.get(pk=<bob-todo-uuid>) → DoesNotExist → Http404
```

Alice obtient 404, pas 403. Elle ne sait pas si cet UUID existe ou appartient à quelqu'un d'autre. C'est du **security by obscurity intentionnel** — éviter l'énumération d'IDs.

Dans `UserViewSet`, le queryset n'est pas filtré par owner (les admins doivent voir tous les users). L'objet est donc trouvé, puis `has_object_permission()` retourne False → 403.

Le **defense in depth** Django :
- Couche 1 : `get_queryset()` filtre (isolation des données) → 404 pour les non-propriétaires
- Couche 2 : `has_object_permission()` vérifie (défense secondaire) → 403 si le queryset n'est pas filtré

### Zoom couche 9 — partial=True

```python
# PUT complet (update) — tous les champs obligatoires requis
serializer = UserSerializer(alice, data={"bio": "x"})
serializer.is_valid()
# ERREUR : "username" et "email" sont required mais absents → 400

# PATCH partiel (partial_update) — seuls les champs fournis sont validés
serializer = UserSerializer(alice, data={"bio": "x"}, partial=True)
serializer.is_valid()
# OK — seul "bio" est validé, les autres champs gardent leur valeur actuelle
```

DRF passe `partial=True` automatiquement dans `partial_update()`. Le Router fait correspondre `PATCH → partial_update` et `PUT → update`. La sémantique HTTP est respectée : PUT remplace, PATCH modifie partiellement.

> ---
> **vs FastAPI**
>
> | | FastAPI | Django/DRF |
> |---|---|---|
> | Permission par objet | `Depends()` qui charge l'objet + vérifie l'ownership manuellement | `has_object_permission()` — separation of concerns claire |
> | 403 vs 404 | Choix explicite dans le handler | Découle naturellement de si `get_queryset()` filtre ou non |
> | PATCH vs PUT | Même endpoint, champs `Optional` + `model.model_copy(update=data)` | Deux méthodes séparées (`update`/`partial_update`) — `partial=True` automatique |
> | Chargement de l'objet | `Depends(get_object_or_404)` injecté en paramètre | `get_object()` dans le ViewSet — DRF l'appelle automatiquement |
> | Signal au UPDATE | Aucun mécanisme natif | `post_save(created=False)` — même signal, le flag `created` distingue INSERT vs UPDATE |
> ---

---

## Annexe — Couches transversales

### Le cycle de vie complet d'une requête DRF

```
HTTP Request
    │
    ▼
Django Middleware Stack (descente, top → bottom)
    │
    ▼
Django URL Resolver → ViewSet.as_view() callable
    │
    ▼
DRF enveloppe HttpRequest dans Request
    │
    ├── initial()
    │   ├── perform_content_negotiation()   → header Accept → choisit le renderer (JSON, etc.)
    │   ├── perform_authentication()        → request.user (évaluation lazy)
    │   ├── check_permissions()             → has_permission() sur chaque permission class
    │   └── check_throttles()              → vérifie les rate limits
    │
    ├── dispatch() → méthode HTTP → action ViewSet
    │   ├── get()    → list()         ou  retrieve()
    │   ├── post()   → create()       ou  @action(methods=["post"])
    │   ├── patch()  → partial_update()
    │   ├── put()    → update()
    │   └── delete() → destroy()
    │       └── si detail : get_object() → check_object_permissions() → has_object_permission()
    │
    └── finalize_response()
        └── renderer choisi → sérialise en JSON → Content-Type: application/json
    │
    ▼
Django Middleware Stack (remontée, bottom → top)
    │
    ▼
HTTP Response
```

### QuerySet — les 3 moments d'évaluation SQL

Un QuerySet Django est **lazy** — la requête SQL n'est exécutée que quand Python a besoin des données.

```python
qs = Todo.objects.filter(owner=user)           # pas de SQL — construit l'AST
qs = qs.filter(priority="high")               # pas de SQL — s'accumule
qs = qs.select_related("category")            # pas de SQL — s'accumule
qs = qs.order_by("-created_at")               # pas de SQL — s'accumule

# SQL exécuté quand Python accède aux données :
list(qs)          # itération → SELECT ... (charge tout en mémoire)
qs[0:20]          # slicing   → SELECT ... LIMIT 20 OFFSET 0
qs.count()        # COUNT     → SELECT COUNT(*) ... (requête séparée optimisée)
bool(qs)          # EXISTS    → SELECT 1 ... LIMIT 1
for item in qs:   # itération → SELECT ...
    ...
```

C'est ce qui permet à DRF de chaîner `get_queryset()` + `filter_backends` + `paginate_queryset()` sans exécuter plusieurs requêtes SQL intermédiaires — le SQL final est assemblé et exécuté une seule fois au moment du slice de pagination.

### DefaultRouter — table de correspondance complète

```
router.register(r"todos", TodoViewSet, basename="todo")

┌────────────────────────────┬────────┬──────────────────────────┬─────────────────────┐
│ URL Pattern                │ Méthode│ Action ViewSet           │ URL Name            │
├────────────────────────────┼────────┼──────────────────────────┼─────────────────────┤
│ /todos/                    │ GET    │ list()                   │ todo-list           │
│ /todos/                    │ POST   │ create()                 │ todo-list           │
│ /todos/{pk}/               │ GET    │ retrieve()               │ todo-detail         │
│ /todos/{pk}/               │ PUT    │ update()                 │ todo-detail         │
│ /todos/{pk}/               │ PATCH  │ partial_update()         │ todo-detail         │
│ /todos/{pk}/               │ DELETE │ destroy()                │ todo-detail         │
│ /todos/stats/              │ GET    │ stats()    [@action]     │ todo-stats          │
│ /todos/bulk-complete/      │ POST   │ bulk_complete() [@action]│ todo-bulk-complete  │
└────────────────────────────┴────────┴──────────────────────────┴─────────────────────┘

detail=False → URL sans {pk} : /todos/stats/
detail=True  → URL avec {pk} : /todos/{pk}/activate/
```

### Signals — les moments du cycle de vie d'un modèle

```python
# Ordre d'émission autour d'un .save()
pre_save(sender, instance, created, ...)    # avant INSERT ou UPDATE
    → instance.save() → SQL
post_save(sender, instance, created, ...)   # après INSERT ou UPDATE (même transaction)

# Ordre autour d'un .delete()
pre_delete(sender, instance, ...)           # avant le DELETE (instance.pk encore disponible)
    → SQL CASCADE (supprime les FK dépendantes)
    → SQL DELETE
post_delete(sender, instance, ...)          # après le DELETE (instance.pk = None)

# Autour des relations ManyToMany
m2m_changed(sender, instance, action, ...)
# action : "pre_add", "post_add", "pre_remove", "post_remove", "pre_clear", "post_clear"
```

**Règle critique :** toujours enregistrer les signals dans `AppConfig.ready()`, jamais au niveau module (double enregistrement en tests) ni dans `models.py` (import circulaire).

### Les 3 niveaux d'isolation des données

```
Niveau 1 — get_queryset()  (TodoViewSet)
    Todo.objects.filter(owner=request.user)
    → Un utilisateur ne reçoit que ses propres todos
    → Tentative d'accès à un todo d'un autre user → 404 (pas 403)
    → Couche ORM : SQL filtre dès la requête

Niveau 2 — has_object_permission()  (IsOwner)
    obj.owner == request.user
    → Double vérification si get_queryset() est contourné (admin, tests)
    → Couche permission : Python, après chargement de l'objet

Niveau 3 — Serializer __init__ queryset scoping  (TodoSerializer)
    Tag.objects.filter(owner=request.user)
    Category.objects.filter(owner=request.user)
    → Un utilisateur ne peut pas assigner les tags ou catégories d'un autre
    → Couche sérialisation : validation de la cohérence des relations
```
