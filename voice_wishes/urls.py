from django.urls import path

from . import views

app_name = "voice_wishes"

urlpatterns = [
    path("wishes/", views.VoiceWishCreateView.as_view(), name="create"),
    path("wishes/<uuid:wish_id>/", views.VoiceWishStatusView.as_view(), name="status"),
    path("callbacks/voice/", views.VoiceCallbackView.as_view(), name="voice-callback"),
    path("callbacks/voice/status/", views.VoiceCallStatusView.as_view(), name="voice-status"),
]
