from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from clients.models import Client
from projects.models import Project


class ClientVisibilityTests(TestCase):
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
        self.visible_client = Client.objects.create(name='Visible Client', email='visible@example.com')
        self.hidden_client = Client.objects.create(name='Hidden Client', email='hidden@example.com')
        visible_project = Project.objects.create(name='Visible Project', manager=self.manager, client=self.visible_client)
        visible_project.resources.add(self.resource)
        Project.objects.create(name='Hidden Project', manager=self.manager, client=self.hidden_client)

    def test_resource_only_sees_clients_for_assigned_projects(self):
        self.api.force_authenticate(user=self.resource)

        response = self.api.get('/api/v1/clients/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        results = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
        names = {entry['name'] for entry in results}

        self.assertEqual(names, {'Visible Client'})
