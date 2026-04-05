"""notifications/urls.py"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'notifications'
router   = DefaultRouter()
router.register('preferences', views.ResourceNotifPreferenceViewSet, basename='notif-preference')
router.register('', views.NotificationViewSet, basename='notification')
urlpatterns = [path('', include(router.urls))]