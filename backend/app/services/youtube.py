"""YouTube Data API v3 upload service.

Authentication uses OAuth 2.0.  On the first run the user must complete the
browser-based consent flow; the resulting credentials are cached in
``YOUTUBE_TOKEN_FILE`` so that subsequent runs are fully automatic.

Required environment variables (see .env.example):
    YOUTUBE_CLIENT_SECRETS_FILE – path to the client_secrets.json downloaded
        from Google Cloud Console (OAuth 2.0 Client ID, type "Desktop app").
    YOUTUBE_TOKEN_FILE – path where the OAuth token is persisted.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Maximum chunk size for resumable uploads (256 KiB multiples; 8 MiB default)
_CHUNK_SIZE = 8 * 1024 * 1024


class YouTubeUploader:
    """Wraps the YouTube Data API v3 for video uploads."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._youtube = None  # lazy-initialised

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_credentials(self):
        """Return valid OAuth2 credentials, running the consent flow if needed."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = Path(self.settings.youtube_token_file)
        creds = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), [YOUTUBE_UPLOAD_SCOPE])

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                secrets_path = Path(self.settings.youtube_client_secrets_file)
                if not secrets_path.exists():
                    raise FileNotFoundError(
                        f"YouTube client secrets file not found: {secrets_path}. "
                        "Download it from Google Cloud Console and set "
                        "YOUTUBE_CLIENT_SECRETS_FILE in your .env."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(secrets_path), [YOUTUBE_UPLOAD_SCOPE]
                )
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json())

        return creds

    def _build_client(self):
        """Return an authenticated YouTube API client."""
        if self._youtube is None:
            import httplib2
            from googleapiclient.discovery import build
            from google_auth_httplib2 import AuthorizedHttp

            creds = self._get_credentials()
            authorised_http = AuthorizedHttp(creds, http=httplib2.Http())
            self._youtube = build(
                YOUTUBE_API_SERVICE_NAME,
                YOUTUBE_API_VERSION,
                http=authorised_http,
                cache_discovery=False,
            )
        return self._youtube

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        category_id: str = "28",  # 28 = Science & Technology
        privacy_status: str = "private",
    ) -> str:
        """Upload *video_path* to YouTube and return the YouTube video ID.

        The video is uploaded as *private* by default so the user can review
        it before making it public.

        Args:
            video_path: Absolute path to the rendered MP4 file.
            title: Video title (max 100 chars).
            description: Video description.
            tags: List of keyword tags.
            category_id: YouTube category ID string (default "28" = Science & Technology).
            privacy_status: One of "private", "unlisted", "public".

        Returns:
            The YouTube video ID (e.g. ``"dQw4w9WgXcQ"``).
        """
        from googleapiclient.http import MediaFileUpload

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        youtube = self._build_client()

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            chunksize=_CHUNK_SIZE,
            resumable=True,
        )

        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        logger.info("Starting YouTube upload for: %s", video_path.name)
        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.resumable_progress / status.total_size * 100)
                logger.info("Upload progress: %d%%", progress)

        video_id = response["id"]
        logger.info("Upload complete. YouTube video ID: %s", video_id)
        return video_id

    @staticmethod
    def read_metadata(metadata_path: Path) -> dict:
        """Parse the youtube.json metadata file produced by the pipeline."""
        with metadata_path.open() as fh:
            return json.load(fh)

    def upload_thumbnail(self, video_id: str, thumbnail_path: Path) -> None:
        """Upload a custom thumbnail for *video_id*.

        Requires the YouTube channel to be verified.  If the channel is not
        verified the API returns a 403 error which is caught and logged as a
        warning so the calling code can continue gracefully.

        Args:
            video_id: The YouTube video ID returned by :meth:`upload`.
            thumbnail_path: Absolute path to the JPEG thumbnail file.
        """
        from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

        if not thumbnail_path.exists():
            logger.warning("Thumbnail file not found: %s", thumbnail_path)
            return

        youtube = self._build_client()
        media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
            logger.info("Thumbnail uploaded for YouTube video %s", video_id)
        except Exception as exc:
            # Re-raise so the caller can decide how to handle it.
            # Callers should catch this and log a warning rather than failing.
            raise RuntimeError(
                f"YouTube thumbnail upload failed for video {video_id}: {exc}"
            ) from exc
