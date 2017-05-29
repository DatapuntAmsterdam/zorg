"""
Test the flow of the app. Steps taken:

- Create a user
- Create a token
- Add 2 orgs
- Check guid
- Create 2 locations
- Check guid
- Create 2 activities
- Check guid
- Do crazy stuff
"""

import json
from datetime import datetime
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from datasets.normalized.tests import factories
from datasets.normalized.views import BatchUpdateView
from datasets.normalized.batch import process_updates
from datasets.normalized import models

from unittest.mock import patch
from django.http import JsonResponse
from django.test import testcases


class OrganisatieTests(APITestCase):
    url = reverse('organisatie-list')

    @classmethod
    def setUpTestData(cls):
        cls.user = factories.create_user()
        cls.token = factories.create_token(cls.user.auth_user)

    def _get_client(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        return client

    def test_create_organisaties(self):
        client = self._get_client(self.token)

        org = factories.create_organisate()
        response = client.post(self.url, org)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {'guid': 'test', 'id': '1', 'naam': 'Org',
                                         'beschrijving': 'Dit is een lang verhaal', 'afdeling': '',
                                         'contact': {'tel': '123'}, 'locatie_id': None})

    def test_organisatie_constraints(self):
        """
        Test that a same name org is not created
        """
        client = self._get_client(self.token)

        org = factories.create_organisate()
        response = client.post(self.url, org)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {'guid': 'test', 'locatie_id': None, 'id': '1', 'naam': 'Org',
                                         'beschrijving': 'Dit is een lang verhaal', 'afdeling': '',
                                         'contact': {'tel': '123'}})

        # name
        org = factories.create_organisate(naam='Org', id=2)
        response = client.post(self.url, org)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # guid == user
        org = factories.create_organisate(naam='Andere Org', id=3, guid='ander')
        response = client.post(self.url, org)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_organisatie_information(self):
        client = self._get_client(self.token)

        org = factories.create_organisate()
        response = client.post(self.url, org)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {'guid': 'test', 'id': '1', 'naam': 'Org',
                                         'beschrijving': 'Dit is een lang verhaal', 'afdeling': '',
                                         'contact': {'tel': '123'}, 'locatie_id': None})

        response = client.put(f"{self.url}{response.data['guid']}/", {'id': '1', 'naam': ' Nieuwe naam'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'guid': 'test', 'id': '1', 'naam': 'Nieuwe naam',
                                         'beschrijving': 'Dit is een lang verhaal', 'afdeling': '',
                                         'contact': {'tel': '123'}, 'locatie_id': None})

class LocatieTests(APITestCase):
    url = reverse('locatie-list')
    org_url = reverse('organisatie-list')

    @classmethod
    def setUpTestData(cls):
        cls.user = factories.create_user()
        cls.token = factories.create_token(cls.user.auth_user)
        cls.org = factories.create_organisate()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + cls.token.key)
        response = client.post(cls.org_url, cls.org)
        cls.org['guid'] = response.data['guid']

    def _get_client(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        return client

    def test_create_locations(self):
        client = self._get_client(self.token)

        loc = factories.create_locatie(huisletter='A')
        response = client.post(self.url, loc)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {'guid': 'test-1', 'id': '1', 'naam': 'Loc', 'openbare_ruimte_naam': 'Straat',
                                         'postcode': '1111AA', 'huisnummer': '1', 'huisletter': 'A',
                                         'huisnummer_toevoeging': '',
                                         'bag_link': '', 'geometrie': None}
                         )

        loc = factories.create_locatie(naam='Ergens Anders', id=2, postcode='1012JS', openbare_ruimte_naam='Dam')
        response = client.post(self.url, loc)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['guid'], 'test-2')
        self.assertEqual(response.data['id'], '2')
        self.assertEqual(response.data['naam'], 'Ergens Anders')
        self.assertEqual(response.data['openbare_ruimte_naam'], 'Dam')
        self.assertEqual(response.data['postcode'], '1012JS')
        self.assertEqual(response.data['huisnummer'], '1')
        self.assertEqual(response.data['huisletter'], '')
        self.assertEqual(response.data['huisnummer_toevoeging'], '')
        self.assertEqual(response.data['bag_link'],
                         f'{settings.DATAPUNT_API_URL}bag/nummeraanduiding/0363200003761447/')
        self.assertEqual(response.data['geometrie'], 'SRID=28992;POINT (121394 487383)')

    def test_add_location_to_org(self):
        client = self._get_client(self.token)

        loc = factories.create_locatie()
        response = client.post(self.url, loc)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Adding the loc to the org
        response = client.put(f"{self.org_url}{self.org['guid']}/", {'id': '1', 'locatie_id': response.data['guid']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        update_resp = response.data
        response = client.get(f"{self.org_url}{self.org['guid']}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, update_resp)


class ActiviteitenTests(APITestCase):
    loc_url = reverse('locatie-list')
    org_url = reverse('organisatie-list')
    url = reverse('activiteit-list')

    @classmethod
    def setUpTestData(cls):
        cls.user = factories.create_user()
        cls.token = factories.create_token(cls.user.auth_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + cls.token.key)

        # Creating organisation
        cls.org = factories.create_organisate()
        response = client.post(cls.org_url, cls.org)
        cls.org['guid'] = response.data['guid']
        # Creating location
        cls.loc = factories.create_locatie()
        response = client.post(cls.loc_url, cls.org)
        cls.loc['guid'] = response.data['guid']

    def _get_client(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        return client

    def test_create_activiteiten(self):
        client = self._get_client(self.token)

        act = factories.create_activiteit()
        response = client.post(self.url, act)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {'guid': 'test-1', 'locatie_id': None, 'organisatie_id': None, 'id': '1',
                                         'naam': 'Activiteit', 'beschrijving': 'Dingen doen',
                                         'bron_link': 'http://amsterdam.nl',
                                         'contactpersoon': 'Ik', 'tags': [], 'start_time': None, 'end_time': None,
                                         'persoon': []})

        act = factories.create_activiteit(naam='Doe nog eens wat',
                                          id=2, bron_link='http://amsterdam.nl/actie',
                                          locatie_id=self.loc['guid'])
        response = client.post(self.url, act)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {'guid': 'test-2', 'locatie_id': 'test-1', 'organisatie_id': None, 'id': '2',
                                         'naam': 'Doe nog eens wat', 'beschrijving': 'Dingen doen',
                                         'bron_link': 'http://amsterdam.nl/actie',
                                         'contactpersoon': 'Ik', 'tags': [], 'start_time': None, 'end_time': None,
                                         'persoon': []})

    def test_add_location_to_activiteit(self):
        client = self._get_client(self.token)

        act = factories.create_activiteit()
        response = client.post(self.url, act)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Create and add the loc to the org

        response = client.put(f"{self.org_url}{self.org['guid']}/",
                              {'id': '1', 'locatie_id': response.data['guid']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        update_resp = response.data
        response = client.get(f"{self.org_url}{self.org['guid']}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, update_resp)


class BatchUpdateEndpointTests(APITestCase):
    url = reverse('batch-update')
    locatie_url = reverse('locatie-list')
    organisatie_url = reverse('organisatie-list')

    @classmethod
    def setUpTestData(cls):
        cls.user = factories.create_user()
        cls.token = factories.create_token(cls.user.auth_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + cls.token.key)

        # Creating organisation
        cls.org = factories.create_organisate(guid='test')
        response = client.post(cls.organisatie_url, cls.org)

        # Creating location
        cls.loc = factories.create_locatie()
        response = client.post(cls.locatie_url, cls.org)
        cls.loc['guid'] = response.data['guid']

    def _get_client(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        return client

    def test_batch_update_endpoint(self):
        client = self._get_client(self.token)
        payload = json.dumps([{"insert": {"locatie": None, "activiteit": None}}])

        with patch.object(BatchUpdateView,
                          'create',
                          return_value=JsonResponse({'jobid': 1}, status=202)) as mocked_create:
            response = client.post(self.url, payload)
            assert mocked_create.called
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            assert json.loads(response.content)['jobid'] == 1

    def test_batch_job_id_endpoint(self):
        client = self._get_client(self.token)
        job_url = reverse('batch-job', args=(1,))

        with patch.object(BatchUpdateView,
                          'get_job',
                          return_value=JsonResponse({'jobid': 1}, status=200)) as mocked_get_job:
            response = client.get(job_url)
            assert mocked_get_job.called
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            assert json.loads(response.content)['jobid'] == 1


class BatchUpdateProcessingTests(APITestCase):
    org_url = reverse('organisatie-list')

    @classmethod
    def setUpTestData(cls):
        cls.user = factories.create_user()
        cls.token = factories.create_token(cls.user.auth_user)
        cls.org = factories.create_organisate(guid='test')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + cls.token.key)
        response = client.post(cls.org_url, cls.org)
        cls.org['guid'] = response.data['guid']

    def test_process_insert_empty(self):
        dt_now = datetime.now().isoformat()
        payload = [{"insert": {"ts": dt_now,
                               "locatie": None,
                               "activiteit": None}}]
        guid = self.org['guid']
        organisatie = models.Organisatie.objects.get(pk=guid)
        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 0
        assert res['insert'] == 0

    def test_process_insert_locatie_activiteit(self):
        dt_now = datetime.now().isoformat()

        loc = factories.create_locatie()
        act = factories.create_activiteit()

        payload = [{"insert": {"ts": dt_now,
                               "locatie": loc,
                               "activiteit": act}}]

        guid = self.org['guid']
        organisatie = models.Organisatie.objects.get(pk=guid)

        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 0
        assert res['insert'] == 1

    def test_process_insert_locatie_no_activiteit(self):
        dt_now = datetime.now().isoformat()

        loc = factories.create_locatie()

        payload = [{"insert": {"ts": dt_now,
                               "locatie": loc,
                               "activiteit": None}}]

        guid = self.org['guid']
        organisatie = models.Organisatie.objects.get(pk=guid)

        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 0
        assert res['insert'] == 1

    def test_process_insert_no_locatie_activiteit(self):
        dt_now = datetime.now().isoformat()
        act = factories.create_activiteit()

        payload = [{"insert": {"ts": dt_now,
                               "locatie": None,
                               "activiteit": act}}]

        guid = self.org['guid']
        organisatie = models.Organisatie.objects.get(pk=guid)

        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 0
        assert res['insert'] == 1

    def test_process_update_empty(self):
        dt_now = datetime.now().isoformat()
        payload = [{"patch": {"ts": dt_now,
                               "locatie": None,
                               "activiteit": None}}]
        guid = self.org['guid']
        organisatie = models.Organisatie.objects.get(pk=guid)
        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 0
        assert res['insert'] == 0

    def test_process_update_locatie_activiteit(self):
        dt_now = datetime.now().isoformat()
        loc = factories.create_locatie()
        event = models.LocatieEventLog(event_type='C', guid=f"{self.org['guid']}-{loc['id']}", data=loc)
        event.save()

        loc['naam'] = 'Locatie is veranderd'
        payload = [{"patch": {"ts": dt_now,
                              "locatie": loc,
                              "activiteit": None}}]

        organisatie = models.Organisatie.objects.get(pk=self.org['guid'])


        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 1
        assert res['insert'] == 0

    def test_process_update_no_activiteit(self):
        dt_now = datetime.now().isoformat()
        loc = factories.create_locatie()
        event = models.LocatieEventLog(event_type='C', guid=f"{self.org['guid']}-{loc['id']}", data=loc)
        event.save()

        act = factories.create_activiteit(id=1, guid='test-1')
        actevent = models.ActiviteitEventLog(event_type='C', guid=f"{self.org['guid']}-{act['id']}", data=act)
        actevent.save()

        act['naam'] = 'Effe iets gewijzigd aan deze activiteit'
        loc['naam'] = 'Locatie is veranderd'

        payload = [{"patch": {"ts": dt_now,
                               "locatie": loc,
                               "activiteit": act}}]

        organisatie = models.Organisatie.objects.get(pk=self.org['guid'])

        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 1
        assert res['insert'] == 0

    def test_process_update_no_locatie_activiteit(self):
        dt_now = datetime.now().isoformat()

        act = factories.create_activiteit(id=1, guid='test-1')
        event = models.ActiviteitEventLog(event_type='C', guid=f"{self.org['guid']}-{act['id']}", data=act)
        event.save()

        act['naam'] = 'Effe iets gewijzigd aan deze activiteit'

        payload = [{"patch": {"ts": dt_now,
                               "locatie": None,
                               "activiteit": act}}]

        guid = self.org['guid']
        organisatie = models.Organisatie.objects.get(pk=guid)

        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 1
        assert res['insert'] == 0

    def test_batch_process_update_multiple_records(self):
        dt_now = datetime.now().isoformat()
        guid = self.org['guid']
        organisatie = models.Organisatie.objects.get(pk=guid)

        act_16 = factories.create_activiteit(id=1, guid='test-16')
        act_17 = factories.create_activiteit(id=1, guid='test-17')
        act_18 = factories.create_activiteit(id=1, guid='test-18')
        act_19 = factories.create_activiteit(id=1, guid='test-19')
        act_20 = factories.create_activiteit(id=1, guid='test-20')

        models.ActiviteitEventLog(event_type='C', guid=f"{self.org['guid']}-{act_16['id']}", data=act_16)
        models.ActiviteitEventLog(event_type='C', guid=f"{self.org['guid']}-{act_17['id']}", data=act_17)
        models.ActiviteitEventLog(event_type='C', guid=f"{self.org['guid']}-{act_18['id']}", data=act_18)
        models.ActiviteitEventLog(event_type='C', guid=f"{self.org['guid']}-{act_19['id']}", data=act_19)
        models.ActiviteitEventLog(event_type='C', guid=f"{self.org['guid']}-{act_20['id']}", data=act_20)

        act_16['naam'] = ['act_16 is gewijzigd']
        act_17['naam'] = ['act_17 is gewijzigd']
        act_18['naam'] = ['act_18 is gewijzigd']
        act_19['naam'] = ['act_19 is gewijzigd']
        act_20['naam'] = ['act_20 is gewijzigd']

        payload = [
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=1, guid='test-1')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=2, guid='test-2')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=3, guid='test-3')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=4, guid='test-4')}},
            {"patch":
                 {"ts": dt_now, "locatie": None, 'activiteit': act_16}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=5, guid='test-5')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=6, guid='test-6')}},
            {"patch":
                 {"ts": dt_now, "locatie": None, 'activiteit': act_17}},
            {"patch":
                 {"ts": dt_now, "locatie": None, 'activiteit': act_18}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=7, guid='test-7')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=8, guid='test-8')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=9, guid='test-9')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=10, guid='test-10')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=11, guid='test-11')}},
            {"patch":
                 {"ts": dt_now, "locatie": None, 'activiteit': act_19}},
            {"patch":
                 {"ts": dt_now, "locatie": None, 'activiteit': act_20}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=12, guid='test-12')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=13, guid='test-13')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=14, guid='test-14')}},
            {"insert":
                 {"ts": dt_now, "locatie": None, 'activiteit': factories.create_activiteit(id=15, guid='test-15')}},
        ]

        res = process_updates(organisatie, payload)
        assert res['delete'] == 0
        assert res['patch'] == 5
        assert res['insert'] == 15

        # print(models.Activiteit.objects.all())



