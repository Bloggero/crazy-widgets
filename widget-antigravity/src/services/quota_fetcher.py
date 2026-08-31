"""
Quota Fetcher Service for Antigravity Quota Monitor (SAO Edition).
Directly queries official RetrieveUserQuotaSummary and GetUserStatus Connect-RPC endpoints.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import dateutil.parser
import requests

from src.models import QuotaSnapshot, QuotaGroup, QuotaBucket, UserInfo
from src.services.ls_discovery import LSDiscovery, LSInstance


class QuotaFetcher:
    """Fetches and parses live quota summary and user info from Google Antigravity."""

    def __init__(self, discovery: Optional[LSDiscovery] = None):
        self._discovery = discovery or LSDiscovery()
        self._last_successful_snapshot: Optional[QuotaSnapshot] = None

    @property
    def last_successful_snapshot(self) -> Optional[QuotaSnapshot]:
        return self._last_successful_snapshot

    def fetch(self, force_rediscover: bool = False) -> QuotaSnapshot:
        """
        Queries RetrieveUserQuotaSummary and GetUserStatus.
        """
        now = datetime.now(timezone.utc)
        
        try:
            # 1. Discover active language server
            instance = self._discovery.find_active_server(force_refresh=force_rediscover)
            if not instance:
                return QuotaSnapshot(
                    timestamp=now,
                    is_success=False,
                    error_message="Antigravity not detected\nOpen Antigravity IDE to establish link.",
                    groups=[]
                )

            headers = {
                "Content-Type": "application/json",
                "x-codeium-csrf-token": instance.csrf_token,
            }

            # 2. Query RetrieveUserQuotaSummary (Official Antigravity Models quota endpoint)
            summary_url = f"http://127.0.0.1:{instance.port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
            user_url = f"http://127.0.0.1:{instance.port}/exa.language_server_pb.LanguageServerService/GetUserStatus"

            summary_resp = requests.post(summary_url, headers=headers, json={}, timeout=3.0)
            if summary_resp.status_code != 200:
                return QuotaSnapshot(
                    timestamp=now,
                    is_success=False,
                    error_message=f"HTTP Error {summary_resp.status_code}\nUnable to retrieve quota summary.",
                    server_port=instance.port
                )

            summary_data = summary_resp.json()
            groups = self._parse_groups(summary_data)

            # Query User Info (best effort)
            user_info = UserInfo()
            try:
                user_resp = requests.post(user_url, headers=headers, json={}, timeout=2.0)
                if user_resp.status_code == 200:
                    u_data = user_resp.json().get("userStatus", {})
                    plan_info = u_data.get("planStatus", {}).get("planInfo", {})
                    user_info = UserInfo(
                        name=u_data.get("name", ""),
                        email=u_data.get("email", ""),
                        plan_name=plan_info.get("planName", "Pro"),
                        tier=plan_info.get("teamsTier", "")
                    )
            except Exception:
                pass

            snapshot = QuotaSnapshot(
                timestamp=now,
                groups=groups,
                user_info=user_info,
                is_success=True,
                error_message="",
                server_port=instance.port
            )
            self._last_successful_snapshot = snapshot
            return snapshot

        except requests.exceptions.Timeout:
            return QuotaSnapshot(
                timestamp=now,
                is_success=False,
                error_message="Connection timed out\nAntigravity server is busy.",
                server_port=instance.port if instance else None
            )
        except requests.exceptions.ConnectionError:
            try:
                self._discovery.find_active_server(force_refresh=True)
            except Exception:
                pass
            return QuotaSnapshot(
                timestamp=now,
                is_success=False,
                error_message="Connection lost\nAntigravity server disconnected.",
                server_port=instance.port if instance else None
            )
        except Exception as e:
            return QuotaSnapshot(
                timestamp=now,
                is_success=False,
                error_message=f"Unexpected error: {str(e)}",
                server_port=instance.port if 'instance' in dir() and instance else None
            )

    def _parse_groups(self, data: Dict[str, Any]) -> List[QuotaGroup]:
        """Parses groups array from RetrieveUserQuotaSummary."""
        raw_groups = data.get("response", {}).get("groups", [])
        groups: List[QuotaGroup] = []

        for g in raw_groups:
            display_name = g.get("displayName", "")
            description = g.get("description", "")
            raw_buckets = g.get("buckets", [])

            buckets: List[QuotaBucket] = []
            for b in raw_buckets:
                bucket_id = b.get("bucketId", "")
                b_name = b.get("displayName", "")
                window = b.get("window", "")
                rem = b.get("remainingFraction", 0.0)
                reset_str = b.get("resetTime", "")
                b_desc = b.get("description", "")

                reset_dt = None
                if reset_str:
                    try:
                        reset_dt = dateutil.parser.isoparse(reset_str)
                    except Exception:
                        pass

                bucket = QuotaBucket(
                    bucket_id=bucket_id,
                    display_name=b_name,
                    window=window,
                    remaining_fraction=float(rem),
                    reset_time=reset_dt,
                    reset_time_str=reset_str,
                    description=b_desc
                )
                buckets.append(bucket)

            # Sort buckets: Weekly first, 5-Hour second
            buckets.sort(key=lambda x: 0 if x.window == "weekly" else 1)

            group = QuotaGroup(
                display_name=display_name,
                description=description,
                buckets=buckets
            )
            groups.append(group)

        return groups
