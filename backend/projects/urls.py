"""projects/urls.py"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'projects'
router   = DefaultRouter()
router.register('', views.ProjectViewSet, basename='project')

approval_router = DefaultRouter()
approval_router.register('', views.ProjectApprovalViewSet, basename='approval')

urlpatterns = [
    path('', include(router.urls)),
    path('approvals/', include(approval_router.urls)),
]