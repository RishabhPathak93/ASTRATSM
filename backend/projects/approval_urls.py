from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectApprovalViewSet

router = DefaultRouter()
router.register('', ProjectApprovalViewSet, basename='approval')
urlpatterns = [path('', include(router.urls))]