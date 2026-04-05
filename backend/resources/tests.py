from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from clients.models import Client
from projects.models import Project
from resources.models import ResourceProfile, TimeEntry


class TimeEntryPermissionTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            email='manager@example.com',
            password='Testpass123!',
            name='Manager User',
            role=User.Role.MANAGER,
        )
        self.resource = User.objects.create_user(
            email='resource@example.com',
            password='Testpass123!',
            name='Resource User',
            role=User.Role.RESOURCE,
        )
        self.other_resource = User.objects.create_user(
            email='other-resource@example.com',
            password='Testpass123!',
            name='Other Resource',
            role=User.Role.RESOURCE,
        )
        self.resource_profile = self.resource.resource_profile
        self.resource_profile.resource_id = 'R-1'
        self.resource_profile.save(update_fields=['resource_id'])
        self.other_profile = self.other_resource.resource_profile
        self.other_profile.resource_id = 'R-2'
        self.other_profile.save(update_fields=['resource_id'])
        self.client_record = Client.objects.create(name='Visible Client', email='client@example.com')
        self.project = Project.objects.create(name='Assigned Project', manager=self.manager, client=self.client_record)
        self.project.resources.add(self.resource)

    def test_resource_can_only_log_time_for_self(self):
        self.api.force_authenticate(user=self.resource)

        response = self.api.post('/api/v1/resources/time-entries/', {
            'resource': self.other_profile.id,
            'project': self.project.id,
            'date': '2026-04-05',
            'hours': '2.00',
            'description': 'Attempted escalation',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TimeEntry.objects.count(), 0)

    def test_resource_cannot_log_time_for_unassigned_project(self):
        unassigned_project = Project.objects.create(name='Unassigned Project', manager=self.manager)

        self.api.force_authenticate(user=self.resource)
        response = self.api.post('/api/v1/resources/time-entries/', {
            'resource': self.resource_profile.id,
            'project': unassigned_project.id,
            'date': '2026-04-05',
            'hours': '2.00',
            'description': 'Unassigned work',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TimeEntry.objects.count(), 0)

    def test_resource_can_log_time_without_sending_resource_field(self):
        self.api.force_authenticate(user=self.resource)

        response = self.api.post('/api/v1/resources/time-entries/', {
            'project': self.project.id,
            'date': '2026-04-05',
            'hours': '2.00',
            'description': 'Worked on assigned phase',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TimeEntry.objects.count(), 1)
        self.assertEqual(TimeEntry.objects.get().resource, self.resource_profile)
