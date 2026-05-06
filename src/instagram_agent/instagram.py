"""Instagram Graph API client via the Facebook Graph API.

Supports the Instagram Content Publishing API for Business/Creator accounts:
  - Create media containers (single image, carousel, reel)
  - Check container processing status
  - Publish a ready container
  - Get post insights (impressions, reach, likes, comments, saves)
  - Get account info

References:
  https://developers.facebook.com/docs/instagram-platform/content-publishing
  https://developers.facebook.com/docs/instagram-platform/reference/v19.0
"""

import time
from typing import Optional

import requests

from instagram_agent.config import get, get_ig_access_token, get_ig_account_id

FB_GRAPH_URL = "https://graph.facebook.com/v19.0"


class InstagramClient:
    """Low-level Instagram Graph API wrapper."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        account_id: Optional[str] = None,
    ):
        self.access_token = access_token or get_ig_access_token()
        self.account_id = account_id or get_ig_account_id()

        if not self.access_token:
            raise SystemExit(
                "ERROR: IG_ACCESS_TOKEN not found.\n"
                "Run 'instagram-agent auth' to set up OAuth, or set IG_ACCESS_TOKEN in config.ini."
            )
        if not self.account_id:
            raise SystemExit(
                "ERROR: IG_ACCOUNT_ID not found.\n"
                "Run 'instagram-agent auth' to set up OAuth, or set IG_ACCOUNT_ID in config.ini."
            )

    # ── Account info ────────────────────────────────────────────────

    def get_account_info(self) -> dict:
        """Get the Instagram Business Account profile info."""
        resp = requests.get(
            f"{FB_GRAPH_URL}/{self.account_id}",
            params={
                "fields": "id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url,website",
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ── Media containers ────────────────────────────────────────────

    def create_image_container(
        self,
        image_url: str,
        caption: str = "",
    ) -> str:
        """Create a media container for a single image post.

        Args:
            image_url: Publicly accessible URL of the image.
            caption: Post caption (can include hashtags).

        Returns:
            Container ID (use check_container_status then publish).
        """
        params = {
            "image_url": image_url,
            "access_token": self.access_token,
        }
        if caption:
            params["caption"] = caption

        resp = requests.post(
            f"{FB_GRAPH_URL}/{self.account_id}/media",
            data=params,
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]
        print(f"  📦 Image container created: {container_id}")
        return container_id

    def create_carousel_container(
        self,
        image_urls: list[str],
        caption: str = "",
    ) -> str:
        """Create a media container for a carousel (multi-image) post.

        Args:
            image_urls: List of publicly accessible image URLs (2-10 images).
            caption: Post caption.

        Returns:
            Container ID.
        """
        if len(image_urls) < 2 or len(image_urls) > 10:
            raise ValueError("Carousel requires 2-10 images.")

        # Step 1: Create individual children containers
        children_ids = []
        for url in image_urls:
            child_resp = requests.post(
                f"{FB_GRAPH_URL}/{self.account_id}/media",
                data={
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": self.access_token,
                },
            )
            child_resp.raise_for_status()
            child_id = child_resp.json()["id"]
            children_ids.append(child_id)
            print(f"  📦 Carousel child created: {child_id}")

        # Step 2: Create the carousel container referencing the children
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "access_token": self.access_token,
        }
        if caption:
            params["caption"] = caption

        resp = requests.post(
            f"{FB_GRAPH_URL}/{self.account_id}/media",
            data=params,
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]
        print(f"  📦 Carousel container created: {container_id}")
        return container_id

    def create_reel_container(
        self,
        video_url: str,
        caption: str = "",
        share_to_feed: bool = True,
    ) -> str:
        """Create a media container for a Reel (video).

        Args:
            video_url: Publicly accessible URL of the video (MP4, 3-90 seconds).
            caption: Reel caption.
            share_to_feed: Whether the Reel appears in the main feed.

        Returns:
            Container ID.
        """
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "share_to_feed": "true" if share_to_feed else "false",
            "access_token": self.access_token,
        }
        if caption:
            params["caption"] = caption

        resp = requests.post(
            f"{FB_GRAPH_URL}/{self.account_id}/media",
            data=params,
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]
        print(f"  📦 Reel container created: {container_id}")
        return container_id

    # ── Container status ────────────────────────────────────────────

    def check_container_status(self, container_id: str) -> dict:
        """Check the processing status of a media container.

        Returns:
            dict with 'status_code' and 'status' fields.
            status_code values:
              - IN_PROGRESS: still processing
              - FINISHED: ready to publish
              - ERROR: processing failed (see status message)
        """
        resp = requests.get(
            f"{FB_GRAPH_URL}/{container_id}",
            params={
                "fields": "status_code,status",
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def wait_for_container(
        self,
        container_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> str:
        """Poll until a container is ready, then return its status.

        Args:
            container_id: The container to wait for.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between status checks.

        Returns:
            "FINISHED" when ready.

        Raises:
            SystemExit on error or timeout.
        """
        print(f"  ⏳ Waiting for container {container_id} to finish processing...")
        start = time.time()

        while time.time() - start < timeout:
            status = self.check_container_status(container_id)
            code = status.get("status_code", "UNKNOWN")

            if code == "FINISHED":
                print(f"  ✅ Container {container_id} is ready!")
                return "FINISHED"
            elif code == "ERROR":
                raise SystemExit(
                    f"Container processing failed: {status.get('status', 'Unknown error')}"
                )
            elif code == "IN_PROGRESS":
                elapsed = int(time.time() - start)
                print(f"  ⏳ Still processing... ({elapsed}s elapsed)")
                time.sleep(poll_interval)
            else:
                print(f"  ⚠️  Unexpected status: {code}")
                time.sleep(poll_interval)

        raise SystemExit(f"Container {container_id} timed out after {timeout}s.")

    # ── Publish ─────────────────────────────────────────────────────

    def publish_media(self, container_id: str) -> dict:
        """Publish a ready media container to Instagram.

        Args:
            container_id: ID of a container with status FINISHED.

        Returns:
            dict with the published media ID.
        """
        resp = requests.post(
            f"{FB_GRAPH_URL}/{self.account_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        result = resp.json()
        media_id = result.get("id", "")
        print(f"  🎉 Published! Media ID: {media_id}")
        return result

    # ── Insights ────────────────────────────────────────────────────

    def get_media_insights(self, media_id: str) -> dict:
        """Get insights for a published media object.

        Available metrics depend on media type:
          - Image/Carousel: impressions, reach, likes, comments, saves, shares
          - Reel: plays, likes, comments, saves, shares, reach

        Returns:
            dict with metric name → value pairs.
        """
        # Determine media type first
        media_resp = requests.get(
            f"{FB_GRAPH_URL}/{media_id}",
            params={
                "fields": "media_type",
                "access_token": self.access_token,
            },
        )
        media_resp.raise_for_status()
        media_type = media_resp.json().get("media_type", "IMAGE")

        # Choose metrics based on type
        if media_type == "REELS":
            metrics = "clips_replays_count,likes,comments,saves,shares,reach,views"
        elif media_type == "CAROUSEL":
            metrics = "impressions,reach,likes,comments,saves,shares"
        else:
            metrics = "impressions,reach,likes,comments,saves,shares"

        resp = requests.get(
            f"{FB_GRAPH_URL}/{media_id}/insights",
            params={
                "metric": metrics,
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        # Flatten into {metric_name: value}
        insights = {}
        for item in data.get("data", []):
            insights[item["name"]] = item["values"][0]["value"] if item.get("values") else 0

        return insights

    def get_account_insights(self, period: str = "day") -> dict:
        """Get account-level insights.

        Args:
            period: 'day' or 'week' or 'days_28'

        Returns:
            dict with metric name → value pairs.
        """
        resp = requests.get(
            f"{FB_GRAPH_URL}/{self.account_id}/insights",
            params={
                "metric": "impressions,reach,profile_views,follower_count",
                "period": period,
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        insights = {}
        for item in data.get("data", []):
            insights[item["name"]] = item["values"][-1]["value"] if item.get("values") else 0

        return insights
