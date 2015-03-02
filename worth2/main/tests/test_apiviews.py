from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from worth2.main.models import Participant, WatchedVideo
from worth2.main.tests.factories import (
    ParticipantFactory, WatchedVideoFactory, UserFactory, VideoBlockFactory
)
from worth2.main.tests.mixins import (
    LoggedInFacilitatorTestMixin, LoggedInParticipantTestMixin
)


class LoginCheckTest(LoggedInParticipantTestMixin, APITestCase):
    def test_post_no_user(self):
        response = self.client.post(reverse('api-login-check'), {
            'facilitator_username': 'fake user',
            'facilitator_password': 'test',
        })
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error'], 'User "fake user" not found')

    def test_post_correct_password(self):
        facilitator = UserFactory(username='facilitator')
        facilitator.set_password('password1')
        facilitator.save()
        response = self.client.post(reverse('api-login-check'), {
            'facilitator_username': 'facilitator',
            'facilitator_password': 'password1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['login_check'], True)

    def test_post_wrong_password(self):
        facilitator = UserFactory(username='facilitator')
        facilitator.set_password('password1')
        facilitator.save()
        response = self.client.post(reverse('api-login-check'), {
            'facilitator_username': 'facilitator',
            'facilitator_password': 'wrong_password',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['login_check'], False)


class ParticipantViewSetTest(
        LoggedInFacilitatorTestMixin, APITestCase):
    def test_create(self):
        response = self.client.post(
            '/api/participants/', {'study_id': '777'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['study_id'], '777')

        participant = Participant.objects.get(study_id='777')
        self.assertEqual(participant.study_id, '777')
        self.assertEqual(participant.created_by, self.u)

    def test_update_study_id(self):
        p = ParticipantFactory(study_id='777')
        response = self.client.put(
            '/api/participants/' + unicode(p.pk) + '/',
            {'study_id': '7878'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['study_id'], '7878')

        participant = Participant.objects.get(study_id='7878')
        self.assertEqual(participant.study_id, '7878')

    def test_update_study_id_invalid(self):
        p = ParticipantFactory(study_id='777')
        response = self.client.put(
            '/api/participants/' + unicode(p.pk) + '/',
            {'study_id': 'j87878'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['study_id'],
            ['That study ID isn\'t valid. (It needs to start with a 7)'])

        with self.assertRaises(Participant.DoesNotExist):
            Participant.objects.get(study_id='j87878')

    def test_update_cohort_id(self):
        p = ParticipantFactory(study_id='700', cohort_id='111')
        response = self.client.put(
            '/api/participants/' + unicode(p.pk) + '/', {
                'study_id': '700',
                'cohort_id': '787',
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cohort_id'], '787')

        participant = Participant.objects.get(study_id='700')
        self.assertEqual(participant.cohort_id, '787')

    def test_update_cohort_id_invalid(self):
        p = ParticipantFactory(study_id='700', cohort_id='111')
        response = self.client.put(
            '/api/participants/' + unicode(p.pk) + '/', {
                'study_id': '700',
                'cohort_id': 'j87878',
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['cohort_id'],
            ['That cohort ID isn\'t valid. (It needs to be 3 digits)'])

        with self.assertRaises(Participant.DoesNotExist):
            Participant.objects.get(cohort_id='j87878')

    def test_update_archive(self):
        p = ParticipantFactory(is_archived=False)
        response = self.client.put(
            '/api/participants/' + unicode(p.pk) + '/',
            {'study_id': p.study_id, 'is_archived': True}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        participant = Participant.objects.get(pk=p.pk)
        self.assertEqual(participant.is_archived, True)


class ParticipantViewSetUnAuthedTest(APITestCase):
    def test_create(self):
        response = self.client.post(
            '/api/participants/', {'study_id': '777'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        with self.assertRaises(Participant.DoesNotExist):
            Participant.objects.get(study_id='777')

    def test_update_study_id(self):
        p = ParticipantFactory(study_id='777')
        response = self.client.put(
            '/api/participants/' + unicode(p.pk) + '/',
            {'study_id': '7878'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        with self.assertRaises(Participant.DoesNotExist):
            Participant.objects.get(study_id='7878')


class WatchedVideoViewSetUnAuthedTest(APITestCase):
    def test_create(self):
        block = VideoBlockFactory()
        response = self.client.post('/api/watched_videos/',
                                    {'video_block': block})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        with self.assertRaises(WatchedVideo.DoesNotExist):
            WatchedVideo.objects.get(video_block=block)

    def test_list(self):
        r = self.client.get('/api/watched_videos/')
        self.assertEqual(r.status_code, 403)

    def test_retrieve(self):
        response = self.client.get('/api/watched_videos/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class WatchedVideoViewSetTest(
        LoggedInParticipantTestMixin, APITestCase):
    """This endpoint should be accessible to any authenticated user."""

    def test_create(self):
        block = VideoBlockFactory()
        r = self.client.post('/api/watched_videos/',
                             {'video_block': block.pk})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

        objs = WatchedVideo.objects.filter(video_block=block, user=self.u)
        self.assertEqual(objs.count(), 1)

    def test_list(self):
        v1 = VideoBlockFactory()
        v2 = VideoBlockFactory()
        v3 = VideoBlockFactory()

        WatchedVideoFactory(user=self.u, video_block=v1)
        WatchedVideoFactory(user=self.u, video_block=v2)
        WatchedVideoFactory(user=self.u, video_block=v3)

        r = self.client.get('/api/watched_videos/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 3)
