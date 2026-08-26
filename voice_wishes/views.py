import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VoiceWish
from .serializers import VoiceWishCreateSerializer, VoiceWishStatusSerializer
from .services.voice_call_service import build_play_and_hangup_response
from .tasks import polish_text

logger = logging.getLogger(__name__)

# Maps Africa's Talking call-status values to our internal status values.
AT_STATUS_MAP = {
    "Success": VoiceWish.Status.DELIVERED,
    "Failed": VoiceWish.Status.FAILED,
    "NoAnswer": VoiceWish.Status.NO_ANSWER,
    "Busy": VoiceWish.Status.NO_ANSWER,
}


class VoiceWishCreateView(APIView):
    """POST a new wish; kicks off the async polish -> tts -> mix -> call pipeline."""

    def post(self, request):
        serializer = VoiceWishCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wish = serializer.save(status=VoiceWish.Status.PENDING)
        polish_text.delay(str(wish.id))
        return Response(VoiceWishCreateSerializer(wish).data, status=status.HTTP_201_CREATED)


class VoiceWishStatusView(APIView):
    """GET the current pipeline status of a wish, for polling from the frontend."""

    def get(self, request, wish_id):
        try:
            wish = VoiceWish.objects.get(id=wish_id)
        except VoiceWish.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(VoiceWishStatusSerializer(wish).data)


class VoiceCallbackView(APIView):
    """
    Africa's Talking hits this when the call connects. Responds with XML that
    only ever contains a passive <Play> action, never anything that listens
    to the recipient.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        session_id = request.data.get("sessionId")
        try:
            wish = VoiceWish.objects.get(call_session_id=session_id)
        except VoiceWish.DoesNotExist:
            logger.warning("VoiceCallbackView: no wish for session %s", session_id)
            return HttpResponse(
                '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
                content_type="application/xml",
            )

        xml_response = build_play_and_hangup_response(wish.final_audio_url)
        return HttpResponse(xml_response, content_type="application/xml")


class VoiceCallStatusView(APIView):
    """Africa's Talking hits this after the call ends with the final outcome."""

    permission_classes = [AllowAny]

    def post(self, request):
        session_id = request.data.get("sessionId")
        durationStatus = request.data.get("durationStatus") or request.data.get("status")
        new_status = AT_STATUS_MAP.get(durationStatus, VoiceWish.Status.FAILED)

        updated = VoiceWish.objects.filter(call_session_id=session_id).update(status=new_status)
        if not updated:
            logger.warning("VoiceCallStatusView: no wish for session %s", session_id)
        return Response(status=status.HTTP_200_OK)
