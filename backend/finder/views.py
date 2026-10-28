
import logging
import os
import tempfile
from pathlib import Path

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .video_analyzer import analyze_video
from .search_services import search_video_sources


logger = logging.getLogger(__name__)


@ensure_csrf_cookie
@api_view(["GET"])
def csrf_token(request):
    return Response({
        "csrfToken": get_token(request),
        "googleConfigured": bool(
            getattr(settings, "GOOGLE_CLIENT_ID", "")
            and getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        ),
    })


@api_view(["POST"])
@csrf_protect
def sign_up(request):
    email = str(request.data.get("email", "")).strip().lower()
    password = str(request.data.get("password", ""))
    if not email or not password:
        return Response({"error": "Email and password are required."}, status=400)
    if len(email) > 150:
        return Response({"error": "Email addresses must be 150 characters or fewer."}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return Response({"error": "Enter a valid email address."}, status=400)
    try:
        validate_password(password)
    except ValidationError as exc:
        return Response({"error": " ".join(exc.messages)}, status=400)
    if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
        return Response({"error": "An account with this email already exists. Please sign in."}, status=409)
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=email, email=email, password=password)
    except IntegrityError:
        return Response({"error": "An account with this email already exists. Please sign in."}, status=409)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(60 * 60 * 24 * 14)
    return Response({"email": user.email, "next": _safe_next(request, request.data.get("next"))}, status=201)


@api_view(["POST"])
@csrf_protect
def sign_in(request):
    email = str(request.data.get("email", "")).strip().lower()
    password = str(request.data.get("password", ""))
    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response({"error": "Email or password is incorrect."}, status=401)
    login(request, user)
    if not request.data.get("remember", True):
        request.session.set_expiry(0)
    else:
        request.session.set_expiry(60 * 60 * 24 * 14)
    return Response({
        "email": user.email or user.username,
        "next": _safe_next(request, request.data.get("next")),
    })


@api_view(["POST"])
@csrf_protect
def sign_out(request):
    logout(request)
    return Response({"status": "signed_out"})


@api_view(["GET"])
def current_user(request):
    if not request.user.is_authenticated:
        return Response({"error": "Not signed in."}, status=401)
    return Response({"email": request.user.email or request.user.username})


def _safe_next(request, candidate):
    from django.utils.http import url_has_allowed_host_and_scheme

    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return "/"


@api_view(["GET"])
def google_start(request):
    if not (getattr(settings, "GOOGLE_CLIENT_ID", "") and getattr(settings, "GOOGLE_CLIENT_SECRET", "")):
        return Response({"error": "Google sign-in is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env."}, status=503)
    next_url = _safe_next(request, request.query_params.get("next"))
    from urllib.parse import urlencode

    return Response({"url": "/accounts/google/login/?" + urlencode({"process": "login", "next": next_url})})

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
}

MAX_UPLOAD_MB = max(
    1,
    int(getattr(settings, "MAX_UPLOAD_MB", 100)),
)
MAX_UPLOAD_SIZE = MAX_UPLOAD_MB * 1024 * 1024


@api_view(["GET"])
def health_check(request):
    return Response({
        "status": "ok",
        "message": "AI Video Source Finder API is running.",
        "search_mode": "youtube_text_search",
        "google_vision": "disabled",
    })


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def search_video(request):
    uploaded_file = request.FILES.get("video")

    if uploaded_file is None:
        return Response({
            "error": "No video uploaded.",
            "detail": "Upload a file using the multipart field 'video'.",
        }, status=status.HTTP_400_BAD_REQUEST)

    filename = Path(uploaded_file.name).name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return Response({
            "error": "Unsupported video format.",
            "allowed_formats": sorted(ALLOWED_EXTENSIONS),
        }, status=status.HTTP_400_BAD_REQUEST)

    if uploaded_file.size <= 0:
        return Response({
            "error": "The uploaded file is empty.",
        }, status=status.HTTP_400_BAD_REQUEST)

    if uploaded_file.size > MAX_UPLOAD_SIZE:
        return Response({
            "error": "Video file is too large.",
            "maximum_size_mb": MAX_UPLOAD_MB,
        }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    temp_path = None

    try:
        # Save the uploaded file and close it before analysis.
        fd, temp_path = tempfile.mkstemp(
            suffix=extension,
            prefix="video_source_",
        )
        os.close(fd)

        bytes_written = 0

        with open(temp_path, "wb") as destination:
            for chunk in uploaded_file.chunks():
                bytes_written += len(chunk)

                if bytes_written > MAX_UPLOAD_SIZE:
                    raise ValueError(
                        f"Video exceeds the {MAX_UPLOAD_MB} MB limit."
                    )

                destination.write(chunk)

        logger.info(
            "Upload received: filename=%s size=%s bytes",
            filename,
            bytes_written,
        )

        # Analyze video frames and audio.
        logger.info("Starting video analysis.")

        analysis = analyze_video(
            temp_path,
            max_frames=8,
        )

        frames = analysis.get("frames") or []
        ocr_text = (analysis.get("search_text") or "").strip()
        transcript = (
            analysis.get("audio_transcript") or ""
        ).strip()

        logger.info(
            "ANALYSIS DIAGNOSTICS: duration=%s frames=%s "
            "ocr_chars=%s transcript_chars=%s",
            analysis.get("duration_seconds"),
            len(frames),
            len(ocr_text),
            len(transcript),
        )

        logger.info(
            "Audio status=%s language=%s error=%s",
            analysis.get("audio_status"),
            analysis.get("audio_language"),
            analysis.get("audio_error"),
        )

        if ocr_text:
            logger.info("OCR/search text preview: %r", ocr_text[:500])
        else:
            logger.warning("No OCR/search text was extracted.")

        if transcript:
            logger.info("Transcript preview: %r", transcript[:500])
        else:
            logger.warning("No audio transcript was extracted.")

        # Search YouTube using extracted text.
        logger.info("Starting YouTube text search.")

        result_payload = search_video_sources(analysis)

        candidates = result_payload.get("results") or []

        logger.info(
            "SEARCH DIAGNOSTICS: candidates=%s services=%s errors=%s",
            len(candidates),
            result_payload.get("services"),
            result_payload.get("service_errors"),
        )

        # Keep the response shape expected by the current frontend.
        return Response(
            result_payload,
            status=status.HTTP_200_OK,
        )

    except ValueError as exc:
        logger.warning("Video analysis validation error: %s", exc)

        return Response({
            "error": "Video analysis failed.",
            "detail": str(exc),
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception:
        logger.exception("Video source search failed.")

        return Response({
            "error": "Video source search failed.",
            "detail": (
                "Check the Django terminal for the full error traceback."
            ),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info("Temporary video file deleted.")
            except OSError:
                logger.warning(
                    "Could not delete temporary file: %s",
                    temp_path,
                )
