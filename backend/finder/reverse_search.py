
import base64
from urllib.parse import urlparse


def detect_platform(url):
    """Guess platform from a result URL; not proof of ownership."""
    host = (urlparse(url).hostname or "").lower()
    host = host.removeprefix("www.")

    if host in {"instagram.com"} or host.endswith(".instagram.com"):
        return "Instagram"

    if host in {"facebook.com", "fb.watch"} or host.endswith(".facebook.com"):
        return "Facebook"

    if host in {"youtube.com", "youtu.be"} or host.endswith(".youtube.com"):
        return "YouTube"

    if host in {"tiktok.com"} or host.endswith(".tiktok.com"):
        return "TikTok"

    if host in {"x.com", "twitter.com"} or host.endswith(".x.com"):
        return "X"

    return host or "Unknown"


def _normalise_url(url):
    return (url or "").strip().rstrip("/")


def reverse_search_frames(frames, max_results_per_frame=10):
    """
    Search sampled video frames using Google Cloud Vision Web Detection.

    Requires Application Default Credentials (ADC).
    Set GOOGLE_APPLICATION_CREDENTIALS to your service-account JSON path.

    Output is a list of candidate pages. A page match is not automatically
    an exact video match.
    """
    try:
        from google.cloud import vision
    except ImportError as exc:
        raise RuntimeError(
            "Google Cloud Vision SDK is missing. Run: "
            "pip install google-cloud-vision"
        ) from exc

    client = vision.ImageAnnotatorClient()
    candidates = {}

    for frame in frames:
        image_bytes = base64.b64decode(frame["image_base64"])
        image = vision.Image(content=image_bytes)

        response = client.web_detection(image=image)

        if response.error and response.error.message:
            raise RuntimeError(
                f"Google Vision API error: {response.error.message}"
            )

        web_detection = response.web_detection
        timestamp = frame.get("timestamp_seconds", 0)

        # Pages that contain matching images are the most useful candidate URLs.
        for page in list(web_detection.pages_with_matching_images)[:max_results_per_frame]:
            url = _normalise_url(page.url)
            if not url:
                continue

            candidate = candidates.setdefault(url, {
                "url": url,
                "title": getattr(page, "page_title", "") or "",
                "platform": detect_platform(url),
                "evidence_frames": [],
                "matching_image_urls": [],
                "evidence_type": "web_page_with_matching_image",
            })

            if timestamp not in candidate["evidence_frames"]:
                candidate["evidence_frames"].append(timestamp)

            for matching_image in getattr(page, "full_matching_images", []):
                image_url = getattr(matching_image, "url", "")
                if image_url and image_url not in candidate["matching_image_urls"]:
                    candidate["matching_image_urls"].append(image_url)

            for matching_image in getattr(page, "partial_matching_images", []):
                image_url = getattr(matching_image, "url", "")
                if image_url and image_url not in candidate["matching_image_urls"]:
                    candidate["matching_image_urls"].append(image_url)

        # Image URLs are evidence, but are not necessarily playable video URLs.
        for item in list(web_detection.full_matching_images)[:max_results_per_frame]:
            image_url = _normalise_url(item.url)
            if not image_url:
                continue

            candidates.setdefault(image_url, {
                "url": image_url,
                "title": "Matching image URL (not a verified video page)",
                "platform": detect_platform(image_url),
                "evidence_frames": [timestamp],
                "matching_image_urls": [image_url],
                "evidence_type": "full_matching_image",
            })

    results = []

    for candidate in candidates.values():
        frame_count = len(candidate["evidence_frames"])

        # Evidence score is a ranking heuristic, NOT a probability of identity.
        # Do not label this an exact match.
        score = min(85, 35 + frame_count * 12)
        candidate["confidence_score"] = score
        candidate["confidence_label"] = (
            "Higher visual evidence"
            if frame_count >= 2
            else "Limited visual evidence"
        )
        candidate["match_status"] = "Possible match" if (
            candidate["evidence_type"] == "web_page_with_matching_image"
        ) else "Unverified"

        candidate["confidence_note"] = (
            "Evidence score based on how many sampled frames produced this URL; "
            "it is not a calibrated probability and does not verify the full video."
        )

        results.append(candidate)

    results.sort(
        key=lambda item: (
            item["evidence_type"] == "web_page_with_matching_image",
            len(item["evidence_frames"]),
        ),
        reverse=True,
    )

    return results
