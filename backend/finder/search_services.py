
import logging
import re
import requests

from django.conf import settings

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def detect_platform(url):
    """Identify the platform from a candidate URL."""
    url = (url or "").lower()

    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    if "instagram.com" in url:
        return "Instagram"
    if "facebook.com" in url or "fb.watch" in url:
        return "Facebook"
    if "tiktok.com" in url:
        return "TikTok"
    if "x.com" in url or "twitter.com" in url:
        return "X"

    return "Web"


def _clean_text(value):
    """Remove excess whitespace and return safe text."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _build_search_queries(analysis, max_queries=5):
    """
    Build YouTube search queries from OCR text and audio transcript.
    This is text search, not reverse-video matching.
    """
    queries = []

    # Text recognized from video frames.
    ocr_text = _clean_text(analysis.get("search_text", ""))
    if ocr_text:
        queries.append(ocr_text[:180])

    # Words spoken in the video.
    transcript = _clean_text(analysis.get("audio_transcript", ""))
    if transcript:
        # Use a shorter phrase so the query is not too long.
        words = transcript.split()
        phrase = " ".join(words[:14])
        if phrase:
            queries.append(phrase[:180])

    # Remove duplicate queries while preserving order.
    unique_queries = []
    seen = set()

    for query in queries:
        query = _clean_text(query)
        key = query.casefold()

        if len(query) >= 3 and key not in seen:
            seen.add(key)
            unique_queries.append(query)

    return unique_queries[:max_queries]


def _youtube_search(query, api_key, max_results=5):
    """Search public YouTube results using the YouTube Data API."""
    response = requests.get(
        YOUTUBE_SEARCH_URL,
        params={
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": max_results,
            "key": api_key,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    candidates = []

    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})

        if not video_id:
            continue

        candidates.append({
            "title": snippet.get("title", "Untitled YouTube video"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "platform": "YouTube",
            "channel": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "description": snippet.get("description", ""),
            "match_status": "Unverified",
            "confidence_score": None,
            "evidence_type": "text_search",
            "matched_query": query,
        })

    return candidates


def _merge_candidates(candidates):
    """Remove duplicate URLs from search results."""
    merged = []
    seen_urls = set()

    for item in candidates:
        url = (item.get("url") or "").strip()
        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        merged.append(item)

    return merged


def search_video_sources(analysis):
    """
    Billing-free search mode:
    - Does not call Google Cloud Vision.
    - Searches YouTube using OCR text and speech transcript.
    - Returns clear messages when no search query or API key is available.
    """
    service_errors = []
    queries = _build_search_queries(analysis)
    api_key = getattr(settings, "YOUTUBE_API_KEY", "").strip()

    results = []
    services = {
        "video_analysis": "completed",
        "google_vision": "disabled_no_billing",
        "youtube_search": "not_started",
    }

    if not api_key:
        services["youtube_search"] = "missing_api_key"
        service_errors.append(
            "YouTube search skipped: YOUTUBE_API_KEY is not configured."
        )
    elif not queries:
        services["youtube_search"] = "no_search_text"
        service_errors.append(
            "YouTube search skipped: no useful OCR text or speech transcript "
            "was extracted from this video."
        )
    else:
        services["youtube_search"] = "running"

        for query in queries:
            try:
                results.extend(
                    _youtube_search(query, api_key, max_results=5)
                )
            except requests.HTTPError as exc:
                status_code = (
                    exc.response.status_code if exc.response is not None
                    else "unknown"
                )
                logger.warning(
                    "YouTube API HTTP error for query %r: %s",
                    query,
                    status_code,
                )
                service_errors.append(
                    f"YouTube API request failed (HTTP {status_code}). "
                    "Check your API key, API enablement, quota, and restrictions."
                )
            except requests.RequestException:
                logger.exception("YouTube API network error.")
                service_errors.append(
                    "Could not connect to the YouTube API. Check your internet "
                    "connection and try again."
                )
            except (ValueError, KeyError):
                logger.exception("Unexpected YouTube API response.")
                service_errors.append(
                    "YouTube returned a response that could not be processed."
                )

        results = _merge_candidates(results)
        services["youtube_search"] = (
            "completed_with_results" if results else "completed_no_results"
        )

    if results:
        summary = (
            f"Analysis completed. Found {len(results)} YouTube candidate(s). "
            "These are text-search candidates, not verified source matches."
        )
    elif not api_key:
        summary = (
            "Video analysis completed, but YouTube search did not run because "
            "the API key is missing. Google Vision is disabled."
        )
    elif not queries:
        summary = (
            "Video analysis completed, but no usable text was found for "
            "YouTube search. Google Vision is disabled."
        )
    else:
        summary = (
            "Video analysis completed, but no YouTube candidates were found "
            "for the extracted text. Google Vision is disabled."
        )

    return {
        "video": {
            "sha256": analysis.get("video_sha256"),
            "duration_seconds": analysis.get("duration_seconds"),
            "frames_sampled": analysis.get("frame_count_sampled", 0),
        },
        "audio": {
            "transcript": analysis.get("audio_transcript", ""),
            "language": analysis.get("audio_language"),
            "status": analysis.get("audio_status"),
            "error": analysis.get("audio_error"),
        },
        "summary": summary,
        "services": services,
        "service_errors": service_errors,
        "results": results,
        "accuracy_notice": (
            "Google Vision visual search is disabled. YouTube results are "
            "based on extracted text only. No exact source match is claimed. "
            "Instagram, Facebook, TikTok and X are not searched by this code."
        ),
    }
