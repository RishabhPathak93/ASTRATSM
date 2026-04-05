"""chat/urls.py"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'chat'
router   = DefaultRouter()
router.register('rooms', views.ChatRoomViewSet, basename='chat-room')
urlpatterns = [path('', include(router.urls))]
