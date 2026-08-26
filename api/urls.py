from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from drf_spectacular.utils import extend_schema
from . import views

# Tag the JWT views
TokenObtainPairView = extend_schema(tags=['auth'], summary='Login — get access & refresh tokens')(TokenObtainPairView)
TokenRefreshView    = extend_schema(tags=['auth'], summary='Refresh access token')(TokenRefreshView)

router = DefaultRouter()
router.register('celebrities',  views.CelebrityViewSet,  basename='celebrity')
router.register('articles',     views.ArticleViewSet,    basename='article')
router.register('posts',        views.PostViewSet,       basename='post')
router.register('charities',    views.CharityViewSet,    basename='charity')
router.register('love-stories', views.LoveStoryViewSet,  basename='lovestory')
router.register('birthdays',    views.CelebrantViewSet,  basename='celebrant')   # ← new

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path('auth/register/', views.RegisterView.as_view(),   name='register'),
    path('auth/login/',    TokenObtainPairView.as_view(),  name='token_obtain'),
    path('auth/refresh/',  TokenRefreshView.as_view(),     name='token_refresh'),
    path('auth/me/',       views.MeView.as_view(),         name='me'),
    path('subscribe/<int:author_id>/', views.SubscribeView.as_view(),      name='subscribe'),
    path('my-subscriptions/',          views.MySubscriptionsView.as_view(), name='my-subscriptions'),

    # ── Wish OG preview (must be BEFORE router.urls) ──────────────────────
    path('wish/<str:token>/', views.wish_og_view, name='wish_og'),

    # ── Presence / site stats ───────────────────────────────────────────────
    path('presence/ping/',   views.PresencePingView.as_view(),   name='presence_ping'),
    path('presence/online/', views.OnlinePresenceView.as_view(), name='presence_online'),
    path('stats/',           views.SiteStatsView.as_view(),      name='site_stats'),

    # ── Swagger / OpenAPI ─────────────────────────────────────────────────
    path('schema/',        SpectacularAPIView.as_view(),   name='schema'),
    path('docs/',          SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/',         SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),

    # ── Resources ─────────────────────────────────────────────────────────
    path('', include(router.urls)),
]