# DAT.md — Document d'Architecture Technique

**Projet :** Todo App — Django REST Framework Edition  
**Version :** 1.0.0  
**Date :** 2026-05-12  
**Auteur :** Rami GB  
**Statut :** Actif

---

## 1. Vue d'ensemble

Application de gestion de tâches (todos) construite avec Django 5 et Django REST Framework. Objectif principal : servir de référence pédagogique pour les développeurs venant de FastAPI qui apprennent l'écosystème Django. L'API est complète (authentification JWT, CRUD, filtrage, pagination, documentation OpenAPI) et prête pour une mise en production.

**Ce que le projet couvre :**
- Authentification JWT (register → login → bearer token → refresh)
- CRUD complet pour les todos, catégories et tags
- Filtrage, recherche, tri et pagination côté serveur
- Isolation des données par utilisateur (chaque utilisateur ne voit que ses propres données)
- Interface d'administration Django prête à l'emploi
- Documentation OpenAPI 3 avec Swagger UI et ReDoc

---

## 2. Stack technique

| Couche | Technologie | Version | Raison du choix |
|--------|------------|---------|-----------------|
| Langage | Python | 3.12 | Dernière stable ; annotations de types modernes |
| Framework | Django | 5.1 | LTS-ready, améliorations async, admin intégré |
| Couche API | Django REST Framework | 3.15 | Standard industriel pour les APIs Django |
| Auth | djangorestframework-simplejwt | 5.3 | JWT minimal à configurer, bien maintenu |
| Filtrage | django-filter | 24.3 | FilterSet déclaratif, intégration native DRF |
| Docs API | drf-spectacular | 0.27 | OpenAPI 3, Swagger UI, ReDoc, génère depuis les ViewSets |
| Env vars | django-environ | 0.11 | Django-natif, supporte DATABASE_URL, cast vers types Python |
| Base de données | PostgreSQL (dev : SQLite) | 16 | Production-grade ; SQLite pour dev sans config |
| Driver DB | psycopg2-binary | 2.9 | Driver Django PostgreSQL standard |
| Tests | pytest-django + factory-boy | 4.9 / 3.3 | Tests basés sur fixtures avec factories réalistes |
| Conteneur | Docker + docker-compose | latest | Environnements cohérents |
| Qualité code | black + isort + ruff + mypy | voir pyproject.toml | Formatage, lint et typage stricts |

---

## 3. Architecture (diagramme ASCII)

```
┌──────────────────────────────────────────────────────────────┐
│                         Client                               │
│              (Browser / Postman / Frontend)                  │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼─────────────────────────────────────┐
│               Middleware Stack (settings.py)                 │
│  SecurityMiddleware → SessionMiddleware → CommonMiddleware   │
│  AuthenticationMiddleware → RequestLoggingMiddleware (custom)│
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                    config/urls.py                            │
│  /api/v1/auth/token/     → JWT (SimpleJWT)                   │
│  /api/v1/users/          → UserViewSet                       │
│  /api/v1/todos/          → TodoViewSet                       │
│  /api/v1/categories/     → CategoryViewSet                   │
│  /api/v1/tags/           → TagViewSet                        │
│  /api/docs/              → Swagger UI                        │
│  /api/redoc/             → ReDoc                             │
│  /admin/                 → Django Admin                      │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│               ViewSets (Django REST Framework)               │
│  Permissions → Throttling → Filtering → Pagination           │
│           ↓                                                  │
│      Serializers (validation + sérialisation)                │
│           ↓                                                  │
│      Django ORM (select_related / prefetch_related)          │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                    Base de données                           │
│  SQLite (dev) ou PostgreSQL (production)                     │
│                                                              │
│  users_user          → Custom AbstractUser                   │
│  users_userprofile   → OneToOne, préférences JSON            │
│  todos_category      → Catégories par utilisateur            │
│  todos_tag           → Tags avec slugs auto-générés          │
│  todos_todo          → Entité principale (FK + M2M)          │
│  todos_todo_tags     → Table de jointure M2M (auto)          │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Modèle de données (ERD)

```
┌─────────────────────┐      ┌──────────────────────┐
│        User         │      │     UserProfile       │
│─────────────────────│      │──────────────────────│
│ id (UUID, PK)       │─────▶│ id (auto)             │
│ username (unique)   │ 1:1  │ user (OneToOne FK)    │
│ email (unique)      │      │ preferences (JSON)    │
│ bio                 │      │ updated_at            │
│ avatar_url          │      └──────────────────────┘
│ is_active / is_staff│
│ created_at          │
└──────────┬──────────┘
           │ 1    propriétaire de
           │
     ┌─────┴──────────────────┐
     │                        │
     ▼ N                      ▼ N
┌─────────────────┐    ┌──────────────────┐
│    Category     │    │      Tag         │
│─────────────────│    │──────────────────│
│ id (UUID, PK)   │    │ id (UUID, PK)    │
│ name            │    │ name             │
│ color (#hex)    │    │ slug (indexé)    │
│ owner (FK)      │    │ owner (FK)       │
│ created_at      │    │ created_at       │
└────────┬────────┘    └────────┬─────────┘
         │ 1:N                  │ M:N
         │                      │
         ▼                      │
┌─────────────────────────────┐ │
│            Todo             │◀┘
│─────────────────────────────│
│ id (UUID, PK)               │
│ title                       │
│ description                 │
│ completed (db_index)        │
│ priority (low/medium/high)  │
│ due_date (nullable)         │
│ created_at / updated_at     │
│ owner (FK → User, CASCADE)  │
│ category (FK, SET_NULL)     │
│ tags (ManyToMany → Tag)     │
└─────────────────────────────┘

  todos_todo_tags (table de jointure auto-générée)
  ┌──────────────────────────────┐
  │ todo_id (FK → Todo)          │
  │ tag_id  (FK → Tag)           │
  └──────────────────────────────┘
```

---

## 5. Surface API

### Authentification

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| POST | `/api/v1/auth/token/` | Obtenir access + refresh JWT | Non |
| POST | `/api/v1/auth/token/refresh/` | Rafraîchir l'access token | Non |
| POST | `/api/v1/auth/token/verify/` | Vérifier la validité d'un token | Non |

### Utilisateurs

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| POST | `/api/v1/users/` | Inscription | Non |
| GET | `/api/v1/users/` | Lister tous les utilisateurs | Admin |
| GET | `/api/v1/users/{id}/` | Obtenir un utilisateur | Soi-même / Admin |
| PUT/PATCH | `/api/v1/users/{id}/` | Mettre à jour | Soi-même / Admin |
| DELETE | `/api/v1/users/{id}/` | Supprimer | Admin |
| GET | `/api/v1/users/me/` | Profil de l'utilisateur courant | Oui |
| PATCH | `/api/v1/users/me/` | Mettre à jour son profil | Oui |

### Todos

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| GET | `/api/v1/todos/` | Lister ses todos (paginé, filtrable) | Oui |
| POST | `/api/v1/todos/` | Créer un todo | Oui |
| GET | `/api/v1/todos/{id}/` | Obtenir un todo | Propriétaire |
| PUT/PATCH | `/api/v1/todos/{id}/` | Mettre à jour | Propriétaire |
| DELETE | `/api/v1/todos/{id}/` | Supprimer | Propriétaire |
| GET | `/api/v1/todos/stats/` | Statistiques de complétion | Oui |
| POST | `/api/v1/todos/bulk-complete/` | Marquer plusieurs todos comme complétés | Oui |

### Catégories & Tags

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| GET/POST | `/api/v1/categories/` | Lister/créer | Oui |
| GET/PUT/PATCH/DELETE | `/api/v1/categories/{id}/` | CRUD | Propriétaire |
| GET/POST | `/api/v1/tags/` | Lister/créer | Oui |
| GET/PUT/PATCH/DELETE | `/api/v1/tags/{id}/` | CRUD | Propriétaire |

### Paramètres de requête (Todos)

| Paramètre | Exemple | Description |
|-----------|---------|-------------|
| `?completed=true` | `?completed=false` | Filtrer par statut |
| `?priority=high` | `?priority=medium` | Filtrer par priorité |
| `?due_date_after=` | `?due_date_after=2026-01-01` | Plage de dates |
| `?due_date_before=` | `?due_date_before=2026-12-31` | Plage de dates |
| `?search=groceries` | `?search=work` | Recherche dans titre et description |
| `?ordering=-priority` | `?ordering=due_date` | Tri (préfixe `-` = descendant) |
| `?page=2` | `?page=3` | Pagination |
| `?page_size=50` | `?page_size=10` | Taille de page (max 100) |

---

## 6. Flux d'authentification

```
1. Inscription :
   POST /api/v1/users/
   Body: {username, email, password, password_confirm}
   → 201 Created : {id, username, email, …}

2. Connexion (obtenir les tokens) :
   POST /api/v1/auth/token/
   Body: {username, password}
   → 200 OK : {access: "eyJ…", refresh: "eyJ…"}

3. Requêtes authentifiées :
   GET /api/v1/todos/
   Header: Authorization: Bearer eyJ…
   → 200 OK : liste paginée des todos

4. Rafraîchissement :
   POST /api/v1/auth/token/refresh/
   Body: {refresh: "eyJ…"}
   → 200 OK : {access: "eyJ…"} (nouveau token d'accès)

Durées de vie (configurables via .env) :
  Access  : 60 minutes  (JWT_ACCESS_MINUTES)
  Refresh : 7 jours     (JWT_REFRESH_DAYS)
```

---

## 7. Gestion des settings / variables d'environnement

### Hiérarchie des settings

```
config/settings/
├── base.py         ← Tout ce qui est indépendant de l'environnement
├── development.py  ← Importe base + désactive throttling, SQLite par défaut
└── production.py   ← Importe base + force HTTPS, PostgreSQL obligatoire
```

### Sélection du module de settings

```bash
# Développement (défaut — configuré dans manage.py)
python manage.py runserver

# Production
DJANGO_SETTINGS_MODULE=config.settings.production gunicorn config.wsgi

# Tests (configuré dans pyproject.toml [tool.pytest.ini_options])
pytest
```

### Variables d'environnement

Copier `.env.example` → `.env` et remplir les valeurs. `django-environ` lit `.env` automatiquement.

| Variable | Défaut | Description |
|----------|--------|-------------|
| `SECRET_KEY` | — | Clé secrète Django (obligatoire, pas de défaut en prod) |
| `DEBUG` | `False` | Mode debug |
| `ALLOWED_HOSTS` | `[]` | Hosts autorisés (liste séparée par virgules) |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | URL de connexion à la base |
| `JWT_ACCESS_MINUTES` | `60` | Durée de vie du token d'accès |
| `JWT_REFRESH_DAYS` | `7` | Durée de vie du token de rafraîchissement |

---

## 8. Lancer le projet

### Sans Docker (SQLite, le plus rapide)

```bash
# 1. Installer les dépendances
poetry install

# 2. Copier le fichier d'environnement
cp .env.example .env

# 3. Appliquer les migrations
python manage.py migrate

# 4. Créer un superutilisateur
python manage.py createsuperuser

# 5. Peupler avec des données de test (optionnel)
python manage.py seed_data --users 3 --todos-per-user 10

# 6. Lancer le serveur
python manage.py runserver

# 7. URLs :
#   API :     http://localhost:8000/api/v1/
#   Swagger : http://localhost:8000/api/docs/
#   Admin :   http://localhost:8000/admin/
```

### Avec Docker (PostgreSQL)

```bash
# 1. Copier le fichier d'environnement
cp .env.example .env

# 2. Démarrer les services
docker-compose up --build

# 3. Dans un autre terminal, migrer et peupler
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py seed_data
```

---

## 9. Étendre l'application

### Ajouter une nouvelle app

```bash
# 1. Créer l'app dans le bon répertoire
python manage.py startapp my_feature apps/my_feature

# 2. Ajouter à INSTALLED_APPS dans config/settings/base.py
LOCAL_APPS = [
    "apps.users",
    "apps.todos",
    "apps.my_feature",  # ← ajouter ici
]

# 3. Créer model, serializer, viewset, urls, admin
# 4. Inclure les URLs dans config/urls.py
# 5. Générer et appliquer les migrations
python manage.py makemigrations my_feature
python manage.py migrate
```

### Ajouter un endpoint custom à un ViewSet existant

```python
# Dans apps/todos/views.py
@action(detail=False, methods=["get"], url_path="overdue")
def overdue(self, request: Request) -> Response:
    """GET /api/v1/todos/overdue/ — todos en retard"""
    from django.utils import timezone
    qs = self.get_queryset().filter(
        due_date__lt=timezone.now().date(),
        completed=False,
    )
    serializer = self.get_serializer(qs, many=True)
    return Response(serializer.data)
```

### Ajouter un champ à un modèle existant

```bash
# 1. Modifier le modèle (apps/todos/models.py)
# 2. Générer la migration
python manage.py makemigrations todos
# 3. Appliquer
python manage.py migrate
# 4. Mettre à jour le serializer et l'admin si nécessaire
```

---

## 10. Qualité du code

```bash
# Formatage
black .
isort .

# Lint
ruff check .
ruff check . --fix   # correction automatique des problèmes sûrs

# Type checking
mypy .

# Séquence recommandée
black . && isort . && ruff check . && mypy .
```

Toute la configuration est dans `pyproject.toml` — sections `[tool.black]`, `[tool.isort]`, `[tool.ruff]`, `[tool.mypy]`.

---

## 11. Tests

```bash
# Lancer tous les tests
pytest

# Avec couverture de code
pytest --cov=apps --cov-report=html
# → ouvrir htmlcov/index.html dans le navigateur

# Fichier de test spécifique
pytest apps/todos/tests/test_views.py -v

# Test spécifique
pytest apps/todos/tests/test_views.py::TestTodoViewSet::test_create_todo -v
```

**Philosophie :**
- Chaque ViewSet a une classe de test correspondante
- `factory_boy` génère les données de test — pas de fixtures JSON à maintenir
- `force_authenticate()` contourne JWT pour les tests unitaires
- Chaque méthode de test est isolée — transactions rollbackées après chaque test
- `@pytest.mark.django_db` autorise les accès DB dans le test

---

## 12. Considérations production

| Aspect | Recommandation |
|--------|----------------|
| Base de données | PostgreSQL 16 + PgBouncer (connection pooling) |
| Fichiers statiques | `collectstatic` + nginx ou CDN |
| Secrets | Variables d'environnement, jamais committer `.env` |
| HTTPS | Terminer à nginx / load balancer ; activer HSTS |
| Gunicorn | 2–4 workers par cœur CPU |
| Migrations | `python manage.py migrate` avant chaque déploiement |
| Backups | pg_dump automatisé ou service managé |
| Monitoring | Sentry pour le suivi des erreurs (`pip install sentry-sdk`) |
| Rate limiting | Ajuster `DEFAULT_THROTTLE_RATES` dans production.py |
| Fichiers media | django-storages + S3 pour les uploads utilisateurs |
| Logs | Diriger vers stdout (Docker) ou un agrégateur (Datadog, Loki) |
