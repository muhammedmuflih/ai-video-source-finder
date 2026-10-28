
import hashlib
import logging
import os
import re
from functools import lru_cache

import cv2
from PIL import Image
import io
import base64

logger = logging.getLogger(__name__)


def _normalise_text(text):
    """Normalize OCR and transcript text."""
    if not text:
        return ""

    text = re.sub(r"\s+", " ", str(text))
    return text.strip()


def _difference_hash(image, hash_size=8):
    """Create a simple perceptual difference hash."""
    resized = cv2.resize(
        image,
        (hash_size + 1, hash_size),
        interpolation=cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    diff = gray[:, 1:] > gray[:, :-1]

    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bit)

    return f"{value:016x}"


def _extract_ocr_text(image):
    """
    Extract visible text if pytesseract and the Tesseract
    OCR application are installed.
    """
    try:
        import pytesseract

        # Optional Windows path override.
        # Set TESSERACT_CMD in the environment if necessary.
        tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip()
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)

        text = pytesseract.image_to_string(
            pil_image,
            lang="eng",
        )
        return _normalise_text(text)

    except ImportError:
        logger.warning(
            "pytesseract is not installed; OCR is disabled."
        )
        return ""

    except Exception:
        logger.exception(
            "OCR failed. Check that the Tesseract application is installed."
        )
        return ""


def _calculate_file_sha256(video_path):
    """Calculate the uploaded file's SHA-256 hash."""
    sha256 = hashlib.sha256()

    with open(video_path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


@lru_cache(maxsize=1)
def _get_whisper_model():
    """Load the Whisper model once per Django worker."""
    from faster_whisper import WhisperModel

    model_name = os.getenv("WHISPER_MODEL", "base").strip() or "base"

    return WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
    )


def transcribe_audio(video_path):
    """
    Transcribe speech from the video's audio track.
    Returns a structured status even when transcription fails.
    """
    result = {
        "transcript": "",
        "segments": [],
        "language": None,
        "status": "not_started",
        "error": None,
    }

    try:
        model = _get_whisper_model()

        segments, info = model.transcribe(
            video_path,
            beam_size=5,
            vad_filter=True,
        )

        transcript_parts = []
        segment_items = []

        # Transcription is generated as segments are iterated.
        for segment in segments:
            text = _normalise_text(segment.text)

            if text:
                transcript_parts.append(text)

            segment_items.append({
                "start": round(float(segment.start), 2),
                "end": round(float(segment.end), 2),
                "text": text,
            })

        transcript = _normalise_text(" ".join(transcript_parts))

        result.update({
            "transcript": transcript,
            "segments": segment_items,
            "language": getattr(info, "language", None),
            "status": "completed" if transcript else "no_speech_detected",
            "error": None,
        })

        if not transcript:
            logger.warning(
                "Whisper completed but did not return any speech text."
            )

    except Exception as exc:
        logger.exception("Audio transcription failed.")

        result.update({
            "transcript": "",
            "segments": [],
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        })

    return result


def analyze_video(video_path, max_frames=8):
    """
    Extract representative frames, optional OCR text,
    audio transcript, video duration and file hash.
    """
    if not os.path.isfile(video_path):
        raise ValueError("The temporary video file does not exist.")

    if os.path.getsize(video_path) == 0:
        raise ValueError("The uploaded video file is empty.")

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        cap.release()
        raise ValueError(
            "OpenCV could not open this video. Try a standard MP4 "
            "file encoded with H.264 video."
        )

    frames = []
    frame_hashes = []
    ocr_texts = []

    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)

        if frame_count <= 0:
            raise ValueError(
                "No readable video frames were detected."
            )

        duration_seconds = (
            frame_count / fps if fps > 0 else None
        )

        sample_count = min(max(1, int(max_frames)), frame_count)

        if sample_count == 1:
            frame_positions = [0]
        else:
            frame_positions = [
                round(i * (frame_count - 1) / (sample_count - 1))
                for i in range(sample_count)
            ]

        for position in frame_positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            success, frame = cap.read()

            if not success or frame is None:
                logger.warning(
                    "Could not read video frame at index %s.",
                    position,
                )
                continue

            height, width = frame.shape[:2]
            max_dimension = 1000

            if max(height, width) > max_dimension:
                scale = max_dimension / max(height, width)
                new_width = max(1, int(width * scale))
                new_height = max(1, int(height * scale))

                frame = cv2.resize(
                    frame,
                    (new_width, new_height),
                    interpolation=cv2.INTER_AREA,
                )

            frame_hashes.append(_difference_hash(frame))

            # OCR is optional; visual search is disabled in this version.
            text = _extract_ocr_text(frame)
            if text:
                ocr_texts.append(text)

            success, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 85],
            )

            if success:
                frames.append({
                    "image_base64": base64.b64encode(
                        encoded.tobytes()
                    ).decode("ascii"),
                    "timestamp_seconds": (
                        round(position / fps, 2) if fps > 0 else None
                    ),
                })

    finally:
        cap.release()

    if not frames:
        raise ValueError(
            "The video opened, but no usable frames could be extracted."
        )

    # Keep unique OCR snippets in the order encountered.
    unique_ocr = []
    seen_ocr = set()

    for text in ocr_texts:
        key = text.casefold()
        if key not in seen_ocr:
            seen_ocr.add(key)
            unique_ocr.append(text)

    search_text = _normalise_text(" ".join(unique_ocr))

    logger.info(
        "Video frames extracted: %s; OCR characters: %s",
        len(frames),
        len(search_text),
    )

    # Run audio transcription separately so audio failure
    # does not discard successfully extracted video frames.
    audio = transcribe_audio(video_path)

    return {
        "video_sha256": _calculate_file_sha256(video_path),
        "duration_seconds": (
            round(duration_seconds, 2)
            if duration_seconds is not None
            else None
        ),
        "frame_count_sampled": len(frames),
        "frames": frames,
        "frame_hashes": frame_hashes,
        "search_text": search_text,
        "audio_transcript": audio["transcript"],
        "audio_segments": audio["segments"],
        "audio_language": audio["language"],
        "audio_status": audio["status"],
        "audio_error": audio["error"],
    }
