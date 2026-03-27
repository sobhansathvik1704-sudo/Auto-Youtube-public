import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class PexelsImageProvider:
    BASE_URL = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search_and_download(
        self,
        query: str,
        output_path: Path,
    ) -> Path | None:
        """Search Pexels for an image matching *query* and download it.

        Returns the local *output_path* on success, or ``None`` if the API
        call fails or returns no results.
        """
        headers = {"Authorization": self.api_key}
        params = {"query": query, "per_page": 5, "orientation": "landscape"}
        try:
            resp = httpx.get(self.BASE_URL, headers=headers, params=params, timeout=10)
        except httpx.RequestError as exc:
            logger.warning("Pexels API request failed for query %r: %s", query, exc)
            return None

        if resp.status_code == 429:
            logger.warning("Pexels API rate limit reached (429) for query %r", query)
            return None

        if resp.status_code != 200:
            logger.warning(
                "Pexels API returned %s for query %r", resp.status_code, query
            )
            return None

        photos = resp.json().get("photos", [])
        if not photos:
            logger.info("Pexels returned no photos for query %r", query)
            return None

        photo_url = photos[0]["src"].get("large2x") or photos[0]["src"].get("large")
        if not photo_url:
            logger.warning("Pexels photo has no usable URL for query %r", query)
            return None

        try:
            img_resp = httpx.get(photo_url, timeout=30, follow_redirects=True)
            img_resp.raise_for_status()
        except httpx.RequestError as exc:
            logger.warning("Failed to download Pexels image for query %r: %s", query, exc)
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Pexels image download returned %s for query %r: %s",
                exc.response.status_code,
                query,
                exc,
            )
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img_resp.content)
        logger.info("Downloaded Pexels image for query %r → %s", query, output_path)
        return output_path
