"""accounts/urls.py"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'accounts'

router = DefaultRouter()
router.register('users',            views.UserViewSet,           basename='user')
router.register('role-permissions', views.RolePermissionViewSet, basename='role-permission')

urlpatterns = [
    path('login/',           views.LoginView.as_view(),          name='login'),
    path('logout/',          views.LogoutView.as_view(),         name='logout'),
    path('token/refresh/',   TokenRefreshView.as_view(),         name='token-refresh'),
    path('me/',              views.MeView.as_view(),             name='me'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('',                 include(router.urls)),
]
