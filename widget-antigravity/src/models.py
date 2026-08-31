"""
Data models for Antigravity Quota Monitor (SAO Edition).
Accurately maps Google Antigravity official RetrieveUserQuotaSummary and GetUserStatus endpoints.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any


@dataclass
class QuotaBucket:
    """Represents a specific limit bucket (e.g. Weekly Limit or Five Hour Limit)."""
    bucket_id: str
    display_name: str
    window: str  # "weekly" or "5h"
    remaining_fraction: float  # 0.0 to 1.0
    reset_time: Optional[datetime] = None
    reset_time_str: str = ""
    description: str = ""

    @property
    def percentage(self) -> float:
        return max(0.0, min(100.0, self.remaining_fraction * 100.0))

    @property
    def percentage_int(self) -> int:
        return int(round(self.percentage))

    @property
    def status_color(self) -> str:
        """SAO HP Colors."""
        pct = self.percentage
        if pct >= 50.0:
            return "#00FF88"  # SAO Green (Normal)
        elif pct >= 20.0:
            return "#FFB703"  # SAO Amber (Caution)
        else:
            return "#FF3344"  # SAO Red (Critical)

    @property
    def status_level(self) -> str:
        pct = self.percentage
        if pct >= 50.0:
            return "normal"
        elif pct >= 20.0:
            return "warning"
        else:
            return "critical"

    def time_until_reset(self) -> Optional[str]:
        if not self.reset_time:
            return None
        now = datetime.now(timezone.utc)
        diff = self.reset_time - now
        total_seconds = int(diff.total_seconds())
        if total_seconds <= 0:
            return "Resetting"
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours >= 24:
            days = hours // 24
            rem_hours = hours % 24
            return f"{days}d {rem_hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


@dataclass
class QuotaGroup:
    """Represents a model family group (e.g. Gemini Models or Claude and GPT models)."""
    display_name: str
    description: str
    buckets: List[QuotaBucket] = field(default_factory=list)

    @property
    def weekly_bucket(self) -> Optional[QuotaBucket]:
        for b in self.buckets:
            if b.window == "weekly":
                return b
        return None

    @property
    def five_hour_bucket(self) -> Optional[QuotaBucket]:
        for b in self.buckets:
            if b.window == "5h":
                return b
        return None


@dataclass
class UserInfo:
    name: str = ""
    email: str = ""
    plan_name: str = "Pro"
    tier: str = ""


@dataclass
class QuotaSnapshot:
    """Full snapshot of official quota summary and user details."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    groups: List[QuotaGroup] = field(default_factory=list)
    user_info: UserInfo = field(default_factory=UserInfo)
    is_success: bool = True
    error_message: str = ""
    server_port: Optional[int] = None

    @property
    def formatted_time(self) -> str:
        return self.timestamp.astimezone().strftime("%H:%M:%S")

    # Backward compatibility helper for legacy code
    @property
    def buckets(self) -> List[QuotaBucket]:
        flat = []
        for g in self.groups:
            flat.extend(g.buckets)
        return flat
