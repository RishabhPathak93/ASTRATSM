"""timelines/urls.py"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'timelines'

# Specific prefixes FIRST
router = DefaultRouter()
router.register('milestones', views.MilestoneViewSet, basename='milestone')

# Empty prefix LAST — so it doesn't swallow other paths
timeline_router = DefaultRouter()
timeline_router.register('', views.TimelineViewSet, basename='timeline')

approval_router = DefaultRouter()
approval_router.register('', views.TimelineApprovalViewSet, basename='timeline-approval')

urlpatterns = [
    path('milestones/', include(router.urls)),
    path('approvals/', include(approval_router.urls)),
    path('', include(timeline_router.urls)),  # ← empty prefix LAST
]