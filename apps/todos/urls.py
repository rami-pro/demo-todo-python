from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, TagViewSet, TodoViewSet

router = DefaultRouter()
router.register(r"todos", TodoViewSet, basename="todo")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"tags", TagViewSet, basename="tag")

urlpatterns = router.urls
