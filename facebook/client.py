"""
Facebook Graph API + Marketing API client wrapper.
Handles auth, retries, rate-limit back-off, and clean error surfacing.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class FacebookAPIError(Exception):
    def __init__(self, message: str, code: int = 0, subcode: int = 0):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class FacebookClient:
    """
    Thin wrapper around the Facebook Graph API.

    Required env vars:
        FB_PAGE_ACCESS_TOKEN  — permanent page access token
        FB_PAGE_ID            — numeric page ID
        FB_AD_ACCOUNT_ID      — ad account ID: act_XXXXXXXXX
        FB_APP_ID             — app ID (for ad creative)
        FB_APP_SECRET         — app secret
    """

    def __init__(
        self,
        page_access_token: Optional[str] = None,
        page_id: Optional[str] = None,
        ad_account_id: Optional[str] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        self.token = page_access_token or os.environ["FB_PAGE_ACCESS_TOKEN"]
        self.page_id = page_id or os.environ["FB_PAGE_ID"]
        self.ad_account_id = ad_account_id or os.environ.get("FB_AD_ACCOUNT_ID", "")
        self.app_id = app_id or os.environ.get("FB_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("FB_APP_SECRET", "")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    @classmethod
    def from_config(cls, cfg) -> "FacebookClient":
        """Create a FacebookClient from a Config dataclass instance."""
        return cls(
            page_access_token=cfg.FB_PAGE_ACCESS_TOKEN,
            page_id=cfg.FB_PAGE_ID,
            ad_account_id=cfg.FB_AD_ACCOUNT_ID,
            app_id=cfg.FB_APP_ID,
            app_secret=cfg.FB_APP_SECRET,
        )

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{GRAPH_BASE}/{path.lstrip('/')}"

    def _params(self, extra: Optional[Dict] = None) -> Dict:
        p = {"access_token": self.token}
        if extra:
            p.update(extra)
        return p

    def _handle_response(self, resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except (ValueError, requests.JSONDecodeError):
            resp.raise_for_status()
            raise FacebookAPIError(f"Non-JSON response (status {resp.status_code}): {resp.text[:200]}")

        if "error" in data:
            err = data["error"]
            raise FacebookAPIError(
                err.get("message", "Unknown Facebook API error"),
                code=err.get("code", 0),
                subcode=err.get("error_subcode", 0),
            )
        resp.raise_for_status()
        return data

    RETRYABLE_FB_CODES = {1, 2, 4, 17}

    def _get(self, path: str, params: Optional[Dict] = None, retries: int = 3) -> Dict[str, Any]:
        url = self._url(path)
        p = self._params(params)
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=p, timeout=30)
                return self._handle_response(resp)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < retries - 1:
                    wait = 2 ** attempt * 5
                    logger.warning("Network error (attempt %d/%d) — retrying in %ds: %s",
                                   attempt + 1, retries, wait, e)
                    time.sleep(wait)
                    continue
                raise FacebookAPIError(f"Network error after {retries} attempts: {e}")
            except FacebookAPIError as e:
                if e.code in self.RETRYABLE_FB_CODES and attempt < retries - 1:
                    wait = 2 ** attempt * 30
                    logger.warning("Retryable FB error %d — sleeping %ds", e.code, wait)
                    time.sleep(wait)
                    continue
                raise
        raise FacebookAPIError("Max retries exceeded")

    def _post(self, path: str, data: Optional[Dict] = None, retries: int = 3) -> Dict[str, Any]:
        url = self._url(path)
        payload = self._params(data)
        for attempt in range(retries):
            try:
                resp = self.session.post(url, data=payload, timeout=30)
                return self._handle_response(resp)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < retries - 1:
                    wait = 2 ** attempt * 5
                    logger.warning("Network error (attempt %d/%d) — retrying in %ds: %s",
                                   attempt + 1, retries, wait, e)
                    time.sleep(wait)
                    continue
                raise FacebookAPIError(f"Network error after {retries} attempts: {e}")
            except FacebookAPIError as e:
                if e.code in self.RETRYABLE_FB_CODES and attempt < retries - 1:
                    wait = 2 ** attempt * 30
                    logger.warning("Retryable FB error %d — sleeping %ds", e.code, wait)
                    time.sleep(wait)
                    continue
                raise
        raise FacebookAPIError("Max retries exceeded")

    # ── Page posts ─────────────────────────────────────────────────────────────

    def post_to_page(
        self,
        message: str,
        link: Optional[str] = None,
        scheduled_publish_time: Optional[int] = None,
    ) -> str:
        """
        Publish an organic post to the page.
        Returns the new post ID.
        """
        payload: Dict[str, Any] = {"message": message}
        if link:
            payload["link"] = link
        if scheduled_publish_time:
            payload["published"] = False
            payload["scheduled_publish_time"] = scheduled_publish_time

        result = self._post(f"{self.page_id}/feed", data=payload)
        post_id = result.get("id", "")
        logger.info("Published page post: %s", post_id)
        return post_id

    def post_photo_to_page(
        self,
        image_url: str,
        caption: str,
        scheduled_publish_time: Optional[int] = None,
    ) -> str:
        """Upload a photo post (by URL) to the page."""
        payload: Dict[str, Any] = {"url": image_url, "caption": caption}
        if scheduled_publish_time:
            payload["published"] = False
            payload["scheduled_publish_time"] = scheduled_publish_time

        result = self._post(f"{self.page_id}/photos", data=payload)
        return result.get("id", "")

    def get_page_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        data = self._get(f"{self.page_id}/feed", params={"limit": limit, "fields": "id,message,created_time,likes.summary(true)"})
        return data.get("data", [])

    def get_post_insights(self, post_id: str) -> Dict[str, Any]:
        metrics = "post_impressions,post_engaged_users,post_clicks,post_reactions_by_type_total"
        return self._get(f"{post_id}/insights", params={"metric": metrics})

    # ── Ad Campaigns (Marketing API) ──────────────────────────────────────────

    def create_campaign(
        self,
        name: str,
        objective: str = "OUTCOME_TRAFFIC",
        status: str = "PAUSED",
        daily_budget: int = 5000,  # in agorot (ILS * 100)
    ) -> str:
        """Create a Facebook Ad campaign. Returns campaign ID."""
        if not self.ad_account_id:
            raise FacebookAPIError("FB_AD_ACCOUNT_ID not configured")

        payload = {
            "name": name,
            "objective": objective,
            "status": status,
            "special_ad_categories": "[]",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "daily_budget": daily_budget,
        }
        result = self._post(f"{self.ad_account_id}/campaigns", data=payload)
        campaign_id = result.get("id", "")
        logger.info("Created campaign: %s (%s)", name, campaign_id)
        return campaign_id

    def create_ad_set(
        self,
        campaign_id: str,
        name: str,
        daily_budget: int = 5000,
        targeting: Optional[Dict] = None,
        optimization_goal: str = "LINK_CLICKS",
        status: str = "PAUSED",
    ) -> str:
        """Create an ad set inside a campaign. Returns ad set ID."""
        if targeting is None:
            targeting = _default_israel_targeting()

        payload = {
            "campaign_id": campaign_id,
            "name": name,
            "daily_budget": daily_budget,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": optimization_goal,
            "targeting": json.dumps(targeting),
            "status": status,
        }
        result = self._post(f"{self.ad_account_id}/adsets", data=payload)
        ad_set_id = result.get("id", "")
        logger.info("Created ad set: %s (%s)", name, ad_set_id)
        return ad_set_id

    def create_ad_creative(self, name: str, message: str, link: str, headline: str, description: str, image_url: Optional[str] = None) -> str:
        """Create an ad creative. Returns creative ID."""
        object_story_spec = {
            "page_id": self.page_id,
            "link_data": {
                "message": message,
                "link": link,
                "name": headline,
                "description": description,
                "call_to_action": {"type": "LEARN_MORE"},
            },
        }
        if image_url:
            object_story_spec["link_data"]["picture"] = image_url

        payload = {
            "name": name,
            "object_story_spec": json.dumps(object_story_spec),
        }
        result = self._post(f"{self.ad_account_id}/adcreatives", data=payload)
        creative_id = result.get("id", "")
        logger.info("Created ad creative: %s (%s)", name, creative_id)
        return creative_id

    def create_ad(self, ad_set_id: str, creative_id: str, name: str, status: str = "PAUSED") -> str:
        """Create an ad inside an ad set. Returns ad ID."""
        payload = {
            "adset_id": ad_set_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "name": name,
            "status": status,
        }
        result = self._post(f"{self.ad_account_id}/ads", data=payload)
        ad_id = result.get("id", "")
        logger.info("Created ad: %s (%s)", name, ad_id)
        return ad_id

    def get_ad_insights(self, ad_id: str, date_preset: str = "last_7d") -> Dict[str, Any]:
        return self._get(
            f"{ad_id}/insights",
            params={
                "fields": "impressions,clicks,spend,ctr,cpm,reach,actions",
                "date_preset": date_preset,
            },
        )

    def list_campaigns(self) -> List[Dict[str, Any]]:
        data = self._get(
            f"{self.ad_account_id}/campaigns",
            params={"fields": "id,name,status,objective,daily_budget"},
        )
        return data.get("data", [])


def _default_israel_targeting() -> Dict[str, Any]:
    """Default targeting: Israeli men aged 30-55, interested in health/wellness."""
    return {
        "geo_locations": {"countries": ["IL"]},
        "age_min": 30,
        "age_max": 55,
        "genders": [1],  # men only
        "flexible_spec": [
            {
                "interests": [
                    {"id": "6003107902433", "name": "Health"},
                    {"id": "6003012347806", "name": "Dietary supplement"},
                    {"id": "6003020834693", "name": "Fitness"},
                    {"id": "6003139266461", "name": "Natural foods"},
                ]
            }
        ],
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed", "story"],
        "instagram_positions": ["stream", "story"],
    }
