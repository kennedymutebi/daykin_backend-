from datetime import timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Presence, SiteCounter, Article, LoveStory


class PresencePingTests(APITestCase):
    def setUp(self):
        self.url = reverse('presence_ping')

    def test_ping_creates_presence_and_increments_visits_once(self):
        response = self.client.post(self.url, {'device_id': 'device-1'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('online_now', response.data)
        self.assertEqual(Presence.objects.filter(device_id='device-1').count(), 1)

        counter = SiteCounter.objects.get(key='total_visits')
        self.assertEqual(counter.value, 1)

    def test_repeat_ping_same_device_does_not_increment_visits(self):
        self.client.post(self.url, {'device_id': 'device-2'}, format='json')
        self.client.post(self.url, {'device_id': 'device-2'}, format='json')
        self.client.post(self.url, {'device_id': 'device-2'}, format='json')

        counter = SiteCounter.objects.get(key='total_visits')
        self.assertEqual(counter.value, 1)
        self.assertEqual(Presence.objects.filter(device_id='device-2').count(), 1)

    def test_ping_missing_device_id_returns_400(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authenticated_ping_attaches_user(self):
        user = User.objects.create_user(username='alice', password='pass12345')
        self.client.force_authenticate(user=user)

        self.client.post(self.url, {'device_id': 'device-3'}, format='json')

        presence = Presence.objects.get(device_id='device-3')
        self.assertEqual(presence.user, user)

    def test_ping_updates_existing_device_user(self):
        # First ping as guest
        self.client.post(self.url, {'device_id': 'device-4'}, format='json')
        self.assertIsNone(Presence.objects.get(device_id='device-4').user)

        # Then authenticate and ping again with same device_id
        user = User.objects.create_user(username='bob', password='pass12345')
        self.client.force_authenticate(user=user)
        self.client.post(self.url, {'device_id': 'device-4'}, format='json')

        presence = Presence.objects.get(device_id='device-4')
        self.assertEqual(presence.user, user)
        # Still only one Presence row for this device
        self.assertEqual(Presence.objects.filter(device_id='device-4').count(), 1)


class OnlinePresenceTests(APITestCase):
    def setUp(self):
        self.url = reverse('presence_online')

    def _make_presence(self, device_id, user=None, minutes_ago=0):
        p = Presence.objects.create(device_id=device_id, user=user)
        if minutes_ago:
            Presence.objects.filter(pk=p.pk).update(
                last_seen=timezone.now() - timedelta(minutes=minutes_ago)
            )
        return p

    def test_count_includes_guests_and_users_within_window(self):
        self._make_presence('g1')
        self._make_presence('g2')
        user = User.objects.create_user(username='carol', password='pass12345')
        self._make_presence('u1', user=user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['users']), 1)

    def test_stale_presence_excluded_from_count(self):
        self._make_presence('recent')
        self._make_presence('stale', minutes_ago=10)  # outside 5-min window

        response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 1)

    def test_only_authenticated_users_appear_in_users_list(self):
        self._make_presence('guest-only')

        response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['users'], [])

    def test_users_list_capped_at_ten(self):
        for i in range(12):
            user = User.objects.create_user(username=f'user{i}', password='pass12345')
            self._make_presence(f'device-{i}', user=user)

        response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 12)
        self.assertLessEqual(len(response.data['users']), 10)

    def test_user_serializer_shape_matches_frontend_contract(self):
        user = User.objects.create_user(
            username='dana', password='pass12345', first_name='Dana', last_name='Smith'
        )
        self._make_presence('device-dana', user=user)

        response = self.client.get(self.url)
        online_user = response.data['users'][0]
        self.assertEqual(set(online_user.keys()), {'id', 'name', 'initials'})
        self.assertEqual(online_user['name'], 'Dana Smith')
        self.assertEqual(online_user['initials'], 'DA')


class SiteStatsTests(APITestCase):
    def setUp(self):
        self.url = reverse('site_stats')

    def test_stats_shape_and_values(self):
        User.objects.create_user(username='member1', password='pass12345')
        User.objects.create_user(username='member2', password='pass12345')

        Article.objects.create(title='Published one', is_published=True)
        Article.objects.create(title='Draft one', is_published=False)
        LoveStory.objects.create(title='Love story', is_published=True)

        SiteCounter.objects.create(key='total_visits', value=42)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['members'], 2)
        self.assertEqual(response.data['stories_published'], 2)  # 1 article + 1 love story
        self.assertEqual(response.data['total_visits'], 42)
        self.assertIn('online_now', response.data)

    def test_stats_with_no_data_defaults_sanely(self):
        response = self.client.get(self.url)
        self.assertEqual(response.data['members'], 0)
        self.assertEqual(response.data['stories_published'], 0)
        self.assertEqual(response.data['total_visits'], 0)
        self.assertEqual(response.data['online_now'], 0)


class ArticleOgViewTests(APITestCase):
    """
    Covers the new /api/article/<source>/<pk>/ view used to give shared
    article/love-story links a real title/image/description preview
    before redirecting into the React app.
    """

    def test_published_article_returns_og_html_and_correct_redirect(self):
        article = Article.objects.create(
            title='A published article', excerpt='Short excerpt', content='Body text',
            is_published=True,
        )
        url = reverse('article_og', args=['article', article.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('A published article', body)
        self.assertIn(f'/article/article/{article.id}/', body)  # redirect target present

    def test_published_love_story_returns_og_html(self):
        story = LoveStory.objects.create(
            title='A love story', excerpt='Sweet excerpt', content='Body text',
            is_published=True,
        )
        url = reverse('article_og', args=['love_story', story.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('A love story', body)
        self.assertIn(f'/article/love_story/{story.id}/', body)

    def test_unpublished_article_returns_404(self):
        article = Article.objects.create(title='Draft', content='x', is_published=False)
        url = reverse('article_og', args=['article', article.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_unknown_source_returns_404(self):
        article = Article.objects.create(title='Published', content='x', is_published=True)
        url = reverse('article_og', args=['not_a_real_source', article.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_id_returns_404(self):
        url = reverse('article_og', args=['article', 999999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_no_image_falls_back_to_default_og_image(self):
        article = Article.objects.create(title='No image here', content='x', is_published=True)
        url = reverse('article_og', args=['article', article.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('og-birthday.png', response.content.decode())