import base64
import json
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from .models import Celebrant
from django.db.models import F

from rest_framework.throttling import ScopedRateThrottle
from .serializers import CelebrantSerializer
from .models import Presence, SiteCounter
from .serializers import (
    PresencePingSerializer,
    PresencePingResponseSerializer,
    OnlinePresenceSerializer,
    OnlineUserSerializer,
    SiteStatsSerializer,
)

from rest_framework import viewsets, generics, status, filters, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from .models import (
    Celebrity, Article, Post, Charity,
    LoveStory, LoveStoryLike, LoveStoryComment,
    Subscription,
)
from .serializers import (
    CelebritySerializer, ArticleSerializer, PostSerializer,
    CharitySerializer, LoveStorySerializer, LoveStoryCommentSerializer,
    RegisterSerializer, UserSerializer, SubscriptionSerializer,
)
from .permissions import IsAdminOrReadOnly, IsAdminOnly, IsOwnerOrAdmin
from .utils import generate_article_audio


# ──────────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['auth'])
class RegisterView(generics.CreateAPIView):
    queryset         = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=['auth'])
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class   = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


# ──────────────────────────────────────────────────────────────────────────────
# Celebrities
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['celebrities'],
        summary='List all celebrities',
        parameters=[OpenApiParameter('search', str, description='Search by name, profession or nationality')],
    ),
    retrieve=extend_schema(tags=['celebrities'], summary='Get a celebrity by ID'),
    create=extend_schema(tags=['celebrities'], summary='Add a celebrity (Admin only)'),
    update=extend_schema(tags=['celebrities'], summary='Update a celebrity (Admin only)'),
    partial_update=extend_schema(tags=['celebrities'], summary='Partially update a celebrity (Admin only)'),
    destroy=extend_schema(tags=['celebrities'], summary='Delete a celebrity (Admin only)'),
)
class CelebrityViewSet(viewsets.ModelViewSet):
    queryset           = Celebrity.objects.all()
    serializer_class   = CelebritySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['name', 'profession', 'nationality']
    ordering_fields    = ['name', 'age', 'created_at']

    @extend_schema(
        tags=['celebrities'],
        summary="Today's birthdays",
        description="Returns celebrities whose birthday falls on today's date.",
    )
    @action(detail=False, methods=['get'], url_path='birthdays-today')
    def birthdays_today(self, request):
        from datetime import date
        today = date.today()
        qs = self.get_queryset().filter(
            birth_date__month=today.month,
            birth_date__day=today.day,
        )
        return Response(self.get_serializer(qs, many=True).data)


# ──────────────────────────────────────────────────────────────────────────────
# Articles
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['articles'],
        summary='List published articles',
        parameters=[
            OpenApiParameter('category', str, enum=['birthday', 'sports', 'love_story', 'charity', 'general']),
            OpenApiParameter('search', str, description='Search title, content or tag'),
        ],
    ),
    retrieve=extend_schema(tags=['articles'], summary='Get an article'),
    create=extend_schema(tags=['articles'], summary='Create an article (Admin only)'),
    update=extend_schema(tags=['articles'], summary='Update an article (Admin only)'),
    partial_update=extend_schema(tags=['articles'], summary='Partially update an article (Admin only)'),
    destroy=extend_schema(tags=['articles'], summary='Delete an article (Admin only)'),
)
class ArticleViewSet(viewsets.ModelViewSet):
    queryset           = Article.objects.filter(is_published=True)
    serializer_class   = ArticleSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends    = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields      = ['title', 'content', 'tag']
    filterset_fields   = ['category', 'tag', 'is_editors_pick']
    ordering_fields    = ['created_at', 'likes', 'reads']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @extend_schema(tags=['articles'], summary='Like an article', request=None,
                   responses={200: {'type': 'object', 'properties': {'likes': {'type': 'integer'}}}})
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        article = self.get_object()
        article.likes += 1
        article.save(update_fields=['likes'])
        return Response({'likes': article.likes})

    @extend_schema(tags=['articles'], summary='Share an article', request=None,
                   responses={200: {'type': 'object', 'properties': {'shares': {'type': 'integer'}}}})
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def share(self, request, pk=None):
        article = self.get_object()
        article.shares += 1
        article.save(update_fields=['shares'])
        return Response({'shares': article.shares})

    @extend_schema(tags=['articles'], summary='Increment comment count', request=None,
                   responses={200: {'type': 'object', 'properties': {'comments': {'type': 'integer'}}}})
    @action(detail=True, methods=['post'], url_path='add-comment', permission_classes=[IsAuthenticated])
    def add_comment(self, request, pk=None):
        article = self.get_object()
        article.comments += 1
        article.save(update_fields=['comments'])
        return Response({'comments': article.comments})

    @extend_schema(
        tags=['articles'],
        summary='Generate audio for an article (TTS)',
        request=None,
        responses={
            200: {'type': 'object', 'properties': {
                'audio_url': {'type': 'string'},
                'detail':    {'type': 'string'},
            }},
            202: {'type': 'object', 'properties': {'detail': {'type': 'string'}}},
        },
    )
    @action(detail=True, methods=['post'], url_path='generate-audio', permission_classes=[AllowAny])
    def generate_audio(self, request, pk=None):
        article = self.get_object()
        success = generate_article_audio(article.id)
        if not success:
            return Response(
                {'detail': 'Audio generation failed. Please try again.'},
                status=status.HTTP_202_ACCEPTED,
            )
        article.refresh_from_db()
        audio_url = request.build_absolute_uri(article.audio.url) if article.audio else None
        return Response({'audio_url': audio_url, 'detail': 'Audio generated successfully.'})


# ──────────────────────────────────────────────────────────────────────────────
# Posts
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(tags=['posts'], summary='List feed posts'),
    retrieve=extend_schema(tags=['posts'], summary='Get a post'),
    create=extend_schema(tags=['posts'], summary='Create a post (logged-in users)'),
    update=extend_schema(tags=['posts'], summary='Update your post'),
    partial_update=extend_schema(tags=['posts'], summary='Partially update your post'),
    destroy=extend_schema(tags=['posts'], summary='Delete your post'),
)
class PostViewSet(viewsets.ModelViewSet):
    queryset           = Post.objects.filter(is_published=True)
    serializer_class   = PostSerializer
    permission_classes = [IsOwnerOrAdmin]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(tags=['posts'], summary='Like a post', request=None,
                   responses={200: {'type': 'object', 'properties': {'likes': {'type': 'integer'}}}})
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        post = self.get_object()
        post.likes += 1
        post.save(update_fields=['likes'])
        return Response({'likes': post.likes})


# ──────────────────────────────────────────────────────────────────────────────
# Charities
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(tags=['charities'], summary='List active charity campaigns'),
    retrieve=extend_schema(tags=['charities'], summary='Get a charity'),
    create=extend_schema(tags=['charities'], summary='Add a charity campaign (Admin only)'),
    update=extend_schema(tags=['charities'], summary='Update a charity (Admin only)'),
    partial_update=extend_schema(tags=['charities'], summary='Partially update a charity (Admin only)'),
    destroy=extend_schema(tags=['charities'], summary='Delete a charity (Admin only)'),
)
class CharityViewSet(viewsets.ModelViewSet):
    queryset           = Charity.objects.filter(is_active=True)
    serializer_class   = CharitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends    = [filters.SearchFilter, DjangoFilterBackend]
    search_fields      = ['title', 'tag', 'beneficiary', 'location']
    filterset_fields   = ['tag', 'urgent']
    ordering_fields    = ['created_at', 'goal', 'raised']


# ──────────────────────────────────────────────────────────────────────────────
# Love Stories
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['love-stories'],
        summary='List published love stories',
        parameters=[
            OpenApiParameter('search',   str, description='Search title, excerpt or author name'),
            OpenApiParameter('ordering', str, description='Order by: created_at, likes, -created_at, -likes'),
        ],
    ),
    retrieve=extend_schema(tags=['love-stories'], summary='Get a love story'),
    create=extend_schema(tags=['love-stories'], summary='Submit a love story (logged-in users)'),
    update=extend_schema(tags=['love-stories'], summary='Update your story'),
    partial_update=extend_schema(tags=['love-stories'], summary='Partially update your story'),
    destroy=extend_schema(tags=['love-stories'], summary='Delete your story'),
)
class LoveStoryViewSet(viewsets.ModelViewSet):
    serializer_class = LoveStorySerializer
    filter_backends  = [filters.SearchFilter, filters.OrderingFilter]
    search_fields    = ['title', 'excerpt', 'author__first_name', 'author__last_name', 'author__username']
    ordering_fields  = ['created_at', 'likes']

    def get_queryset(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return LoveStory.objects.all()
        return LoveStory.objects.filter(is_published=True)

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'comments_list'):
            return [AllowAny()]
        if self.action in ('like', 'share', 'add_comment'):
            return [IsAuthenticated()]
        return [IsOwnerOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, is_published=True)

    def perform_update(self, serializer):
        serializer.save(is_published=True)

    # ── Like — toggle (unique per user, no double-liking) ─────────────────────
    @extend_schema(
        tags=['love-stories'],
        summary='Toggle like on a love story',
        request=None,
        responses={200: {'type': 'object', 'properties': {
            'likes': {'type': 'integer'},
            'liked': {'type': 'boolean'},
        }}},
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        story = self.get_object()
        like_obj, created = LoveStoryLike.objects.get_or_create(
            story=story, user=request.user
        )
        if created:
            story.likes += 1
            story.save(update_fields=['likes'])
            return Response({'likes': story.likes, 'liked': True})
        else:
            like_obj.delete()
            story.likes = max(0, story.likes - 1)
            story.save(update_fields=['likes'])
            return Response({'likes': story.likes, 'liked': False})

    # ── Share ─────────────────────────────────────────────────────────────────
    @extend_schema(
        tags=['love-stories'],
        summary='Share a love story',
        request=None,
        responses={200: {'type': 'object', 'properties': {'shares': {'type': 'integer'}}}},
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def share(self, request, pk=None):
        story = self.get_object()
        story.shares += 1
        story.save(update_fields=['shares'])
        return Response({'shares': story.shares})

    # ── Add comment — persists text, returns full comment object ──────────────
    @extend_schema(
        tags=['love-stories'],
        summary='Post a comment on a love story',
        request={'application/json': {'type': 'object', 'properties': {'text': {'type': 'string'}}}},
        responses={201: {'type': 'object', 'properties': {
            'id':        {'type': 'integer'},
            'author':    {'type': 'string'},
            'initials':  {'type': 'string'},
            'text':      {'type': 'string'},
            'timestamp': {'type': 'string'},
            'comments':  {'type': 'integer'},
        }}},
    )
    @action(detail=True, methods=['post'], url_path='add-comment', permission_classes=[IsAuthenticated])
    def add_comment(self, request, pk=None):
        story = self.get_object()
        text  = (request.data.get('text') or '').strip()
        if not text:
            return Response(
                {'detail': 'Comment text is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = LoveStoryComment.objects.create(
            story=story,
            user=request.user,
            text=text,
        )
        story.comments += 1
        story.save(update_fields=['comments'])

        name = request.user.get_full_name() or request.user.username
        return Response({
            'id':        comment.id,
            'author':    name,
            'initials':  name[:2].upper(),
            'text':      comment.text,
            'timestamp': comment.created_at.isoformat(),
            'comments':  story.comments,
        }, status=status.HTTP_201_CREATED)

    # ── List comments — fetched when panel opens ───────────────────────────────
    @extend_schema(
        tags=['love-stories'],
        summary='List all comments for a love story',
        responses={200: {'type': 'array', 'items': {'type': 'object', 'properties': {
            'id':        {'type': 'integer'},
            'author':    {'type': 'string'},
            'initials':  {'type': 'string'},
            'text':      {'type': 'string'},
            'timestamp': {'type': 'string'},
        }}}},
    )
    @action(detail=True, methods=['get'], url_path='comments', permission_classes=[AllowAny])
    def comments_list(self, request, pk=None):
        story    = self.get_object()
        qs       = LoveStoryComment.objects.filter(story=story).select_related('user')
        data = []
        for c in qs:
            name = c.user.get_full_name() or c.user.username
            data.append({
                'id':        c.id,
                'author':    name,
                'initials':  name[:2].upper(),
                'text':      c.text,
                'timestamp': c.created_at.isoformat(),
            })
        return Response(data)


# ──────────────────────────────────────────────────────────────────────────────
# Subscriptions
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['subscriptions'])
class SubscribeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = SubscriptionSerializer

    @extend_schema(summary='Subscribe to an author',
                   responses={201: SubscriptionSerializer,
                              200: {'type': 'object', 'properties': {'detail': {'type': 'string'}}}})
    def post(self, request, author_id):
        try:
            author = User.objects.get(pk=author_id)
        except User.DoesNotExist:
            return Response({'detail': 'Author not found.'}, status=status.HTTP_404_NOT_FOUND)
        if author == request.user:
            return Response({'detail': 'You cannot subscribe to yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        sub, created = Subscription.objects.get_or_create(subscriber=request.user, author=author)
        if created:
            return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)
        return Response({'detail': 'Already subscribed.'}, status=status.HTTP_200_OK)

    @extend_schema(summary='Unsubscribe from an author', responses={204: None})
    def delete(self, request, author_id):
        deleted, _ = Subscription.objects.filter(subscriber=request.user, author_id=author_id).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'Not subscribed.'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(tags=['subscriptions'])
class MySubscriptionsView(generics.ListAPIView):
    serializer_class   = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(subscriber=self.request.user)


# ──────────────────────────────────────────────────────────────────────────────
# Wish OG preview
# ──────────────────────────────────────────────────────────────────────────────

@csrf_exempt
def wish_og_view(request, token):
    encoded   = request.GET.get('d', '')
    to_name   = 'Someone Special'
    from_name = 'A Friend'

    if encoded:
        try:
            decoded   = json.loads(base64.b64decode(encoded).decode('utf-8'))
            to_name   = decoded.get('to',   to_name).strip() or to_name
            from_name = decoded.get('from', from_name).strip() or from_name
        except Exception:
            pass

    react_wish_url = request.build_absolute_uri().replace('/api/wish/', '/wish/', 1)
    og_image_url   = request.build_absolute_uri('/static/og-birthday.png')
    og_title       = f"🎂 Happy Birthday, {to_name}!"
    og_description = (
        f"{from_name} wrote you a special birthday wish. "
        "Tap to open your private message 🎁"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{og_title}</title>
  <meta property="og:type"         content="website" />
  <meta property="og:site_name"    content="Daykin" />
  <meta property="og:url"          content="{react_wish_url}" />
  <meta property="og:title"        content="{og_title}" />
  <meta property="og:description"  content="{og_description}" />
  <meta property="og:image"        content="{og_image_url}" />
  <meta property="og:image:width"  content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card"        content="summary_large_image" />
  <meta name="twitter:title"       content="{og_title}" />
  <meta name="twitter:description" content="{og_description}" />
  <meta name="twitter:image"       content="{og_image_url}" />
  <meta name="apple-mobile-web-app-title" content="Daykin Birthday Wish" />
  <meta http-equiv="refresh" content="0;url={react_wish_url}" />
  <script>window.location.replace("{react_wish_url}");</script>
  <style>
    body {{
      margin: 0; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: #0f0c29; font-family: sans-serif;
      color: #FDE68A; font-size: 1.1rem;
    }}
  </style>
</head>
<body>
  <p>🎂 Opening your birthday wish…</p>
</body>
</html>"""

    return HttpResponse(html, content_type='text/html; charset=utf-8')


# ──────────────────────────────────────────────────────────────────────────────
# Article / Love Story OG preview — shareable link that shows a real
# title/image/description in WhatsApp, Facebook, Twitter, etc., then
# redirects into the React app at /article/<source>/<pk>. `source` is
# 'article' or 'love_story' since both share the same feed/composer but
# live in different DB tables with independently-numbered ids.
# ──────────────────────────────────────────────────────────────────────────────

@csrf_exempt
def article_og_view(request, source, pk):
    if source == 'article':
        obj = Article.objects.filter(pk=pk, is_published=True).first()
    elif source == 'love_story':
        obj = LoveStory.objects.filter(pk=pk, is_published=True).first()
    else:
        obj = None

    if obj is None:
        return HttpResponse("Article not found.", status=404)

    react_article_url = request.build_absolute_uri().replace('/api/article/', '/article/', 1)

    og_title       = obj.title
    og_description = (getattr(obj, 'excerpt', '') or obj.content[:150]).strip()
    if obj.image:
        og_image_url = request.build_absolute_uri(obj.image.url)
    else:
        og_image_url = request.build_absolute_uri('/static/og-birthday.png')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{og_title}</title>
  <meta property="og:type"         content="article" />
  <meta property="og:site_name"    content="Daykin" />
  <meta property="og:url"          content="{react_article_url}" />
  <meta property="og:title"        content="{og_title}" />
  <meta property="og:description"  content="{og_description}" />
  <meta property="og:image"        content="{og_image_url}" />
  <meta property="og:image:width"  content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card"        content="summary_large_image" />
  <meta name="twitter:title"       content="{og_title}" />
  <meta name="twitter:description" content="{og_description}" />
  <meta name="twitter:image"       content="{og_image_url}" />
  <meta http-equiv="refresh" content="0;url={react_article_url}" />
  <script>window.location.replace("{react_article_url}");</script>
  <style>
    body {{
      margin: 0; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: #0f0c29; font-family: sans-serif;
      color: #FDE68A; font-size: 1.1rem;
    }}
  </style>
</head>
<body>
  <p>📰 Opening the article…</p>
</body>
</html>"""

    return HttpResponse(html, content_type='text/html; charset=utf-8')


@extend_schema_view(
    list=extend_schema(
        tags=['birthdays'],
        summary='List celebrants on the roster',
        description=(
            "Public by default — returns every celebrant so anonymous and "
            "logged-in visitors can see the birthday feed. Pass ?mine=true "
            "while logged in to see only celebrants you personally added "
            "(used by the manage/roster screen)."
        ),
        parameters=[
            OpenApiParameter(
                'mine', bool, required=False,
                description='If true, restrict results to celebrants created by the current user.',
            ),
        ],
    ),
    create=extend_schema(tags=['birthdays'], summary='Add a celebrant to the roster'),
    retrieve=extend_schema(tags=['birthdays'], summary='Get a single celebrant'),
    update=extend_schema(tags=['birthdays'], summary='Update a celebrant (owner or admin only)'),
    partial_update=extend_schema(tags=['birthdays'], summary='Partially update a celebrant (owner or admin only)'),
    destroy=extend_schema(tags=['birthdays'], summary='Remove a celebrant from the roster (owner or admin only)'),
)
class CelebrantViewSet(viewsets.ModelViewSet):
    queryset = Celebrant.objects.all()
    serializer_class = CelebrantSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    # SAFE_METHODS (GET/HEAD/OPTIONS) are allowed for everyone, including
    # anonymous users — that's what makes the public feed work. Only
    # create/update/delete require auth + ownership (or staff).
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self):
        qs = Celebrant.objects.all()

        # Only scope down to "just what I created" when explicitly asked
        # for via ?mine=true — this is what the manage/roster screen uses.
        # Everyone else (anonymous visitors, logged-in users browsing the
        # public feed, or that same user without the param) sees the full
        # roster, which is what makes birthdays-today actually show up
        # for people who didn't personally add anyone.
        mine = self.request.query_params.get('mine', '').lower() == 'true'
        if mine:
            user = self.request.user
            if not user.is_authenticated:
                return Celebrant.objects.none()
            return qs.filter(created_by=user)

        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_serializer_context(self):
        return {'request': self.request}

ONLINE_WINDOW = timedelta(minutes=5)
ONLINE_USERS_CAP = 10


def _online_cutoff():
    return timezone.now() - ONLINE_WINDOW


def _online_now_count() -> int:
    return Presence.objects.filter(last_seen__gte=_online_cutoff()).count()


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/presence/ping/
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['presence'],
    summary='Send a presence heartbeat',
    description=(
        "Marks the calling device (and user, if authenticated) as active. "
        "Rate-limited per IP to stop device_id spam from inflating the "
        "visit counter. Only increments total_visits the first time a "
        "device_id is ever seen."
    ),
    request=PresencePingSerializer,
    responses={200: PresencePingResponseSerializer},
)
class PresencePingView(APIView):
    permission_classes = [AllowAny]
    throttle_classes    = [ScopedRateThrottle]
    throttle_scope       = 'presence_ping'

    def post(self, request):
        serializer = PresencePingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = serializer.validated_data['device_id']

        user = request.user if request.user.is_authenticated else None

        _, created = Presence.objects.update_or_create(
            device_id=device_id,
            defaults={'user': user},
        )

        if created:
            counter, _ = SiteCounter.objects.get_or_create(
                key='total_visits', defaults={'value': 0}
            )
            SiteCounter.objects.filter(pk=counter.pk).update(value=F('value') + 1)

        return Response({'online_now': _online_now_count()}, status=status.HTTP_200_OK)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/presence/online/
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['presence'],
    summary='Who is online right now',
    description='count includes guests; users lists only authenticated visitors, capped.',
    responses={200: OnlinePresenceSerializer},
)
class OnlinePresenceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Presence.objects.filter(last_seen__gte=_online_cutoff())
        count = qs.count()
        user_ids = (
            qs.filter(user__isnull=False)
              .order_by('-last_seen')
              .values_list('user_id', flat=True)[:ONLINE_USERS_CAP]
        )
        users = User.objects.filter(id__in=list(user_ids))
        data = {
            'count': count,
            'users': OnlineUserSerializer(users, many=True).data,
        }
        return Response(data, status=status.HTTP_200_OK)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/stats/
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['presence'],
    summary='Site-wide stats for the home hero',
    responses={200: SiteStatsSerializer},
)
class SiteStatsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        members = User.objects.count()
        stories_published = (
            Article.objects.filter(is_published=True).count()
            + LoveStory.objects.filter(is_published=True).count()
        )
        counter = SiteCounter.objects.filter(key='total_visits').first()
        total_visits = counter.value if counter else 0

        data = {
            'members': members,
            'stories_published': stories_published,
            'total_visits': total_visits,
            'online_now': _online_now_count(),
        }
        return Response(data, status=status.HTTP_200_OK)