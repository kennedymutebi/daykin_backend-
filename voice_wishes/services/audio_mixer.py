"""
Mixes a voice track with a background music bed via ffmpeg/ffprobe, and
uploads the result to public storage so the telephony provider can fetch it.
"""
import json
import logging
import os
import subprocess
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

MUSIC_VOLUME = 0.18  # background music stays well under the voice
FADE_SECONDS = 0.6


class AudioMixerError(Exception):
    pass


def get_duration(file_path: str) -> float:
    """Return the duration of an audio file in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", file_path,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, text=True)
        data = json.loads(out.stdout)
        return float(data["format"]["duration"])
    except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AudioMixerError(f"Could not read duration for {file_path}: {exc}") from exc


def mix(voice_path: str, music_track: str) -> str:
    """
    Overlay `voice_path` on top of the given music track (ducked in volume,
    trimmed to the voice length + a short tail, with fade out). Returns the
    local path of the mixed file.
    """
    music_path = os.path.join(settings.VOICE_WISH_MUSIC_DIR, music_track)
    if not os.path.exists(music_path):
        raise AudioMixerError(f"Music track not found: {music_track}")

    voice_duration = get_duration(voice_path)
    total_duration = voice_duration + FADE_SECONDS

    out_dir = settings.VOICE_WISH_AUDIO_TMP_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"mixed_{uuid.uuid4().hex}.mp3")

    filter_complex = (
        f"[1:a]volume={MUSIC_VOLUME},atrim=0:{total_duration},"
        f"afade=t=out:st={total_duration - FADE_SECONDS}:d={FADE_SECONDS}[music];"
        f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[out]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", voice_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        out_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - ffmpeg failure path
        raise AudioMixerError(f"ffmpeg mix failed: {exc.stderr}") from exc

    if not os.path.exists(out_path):
        raise AudioMixerError("ffmpeg did not produce an output file")
    return out_path


def upload_public(file_path: str) -> str:
    """Upload the final mixed file to public storage and return its URL."""
    return _upload(file_path)  # pragma: no cover - thin storage wrapper


def _upload(file_path: str) -> str:  # pragma: no cover
    from django.core.files.storage import default_storage

    filename = f"voice_wishes/{os.path.basename(file_path)}"
    with open(file_path, "rb") as f:
        saved_name = default_storage.save(filename, f)
    return default_storage.url(saved_name)
