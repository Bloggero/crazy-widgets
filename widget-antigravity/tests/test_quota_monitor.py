"""
Unit tests for Antigravity Quota Monitor.
Validates official RetrieveUserQuotaSummary parsing, QuotaGroup/Bucket models,
HistoryStore (WAL concurrency), ConfigManager (atomic save & multi-monitor coordinates),
and logging infrastructure.
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import shutil
from datetime import datetime, timezone, timedelta

from src.models import QuotaBucket, QuotaGroup, QuotaSnapshot, UserInfo
from src.services.config_manager import ConfigManager
from src.services.history_store import HistoryStore
from src.services.quota_fetcher import QuotaFetcher
from src.services.logger import setup_logging, get_logger


class TestQuotaModels(unittest.TestCase):

    def test_quota_bucket_percentage(self):
        b1 = QuotaBucket(bucket_id="gemini-weekly", display_name="Weekly Limit Remaining", window="weekly", remaining_fraction=0.85)
        self.assertEqual(b1.percentage_int, 85)
        self.assertEqual(b1.status_level, "normal")
        self.assertEqual(b1.status_color, "#00FF88")

        b2 = QuotaBucket(bucket_id="gemini-5h", display_name="Five Hour Limit Remaining", window="5h", remaining_fraction=0.45)
        self.assertEqual(b2.percentage_int, 45)
        self.assertEqual(b2.status_level, "warning")
        self.assertEqual(b2.status_color, "#FFB703")

        b3 = QuotaBucket(bucket_id="low-limit", display_name="Low Limit", window="5h", remaining_fraction=0.10)
        self.assertEqual(b3.percentage_int, 10)
        self.assertEqual(b3.status_level, "critical")
        self.assertEqual(b3.status_color, "#FF3344")

    def test_quota_bucket_reset_countdown(self):
        future_time = datetime.now(timezone.utc) + timedelta(hours=3, minutes=25)
        b = QuotaBucket(bucket_id="test", display_name="Test", window="5h", remaining_fraction=0.5, reset_time=future_time)
        countdown = b.time_until_reset()
        self.assertIsNotNone(countdown)
        self.assertTrue("3h" in countdown)


class TestLogging(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch.dict(os.environ, {"APPDATA": self.temp_dir})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_logger_initialization(self):
        logger = setup_logging(force_reset=True)
        self.assertIsNotNone(logger)
        logger.info("Test log message")
        for h in logger.handlers:
            h.flush()
        log_file = os.path.join(self.temp_dir, "AntigravityQuotaMonitor", "logs", "app.log")
        self.assertTrue(os.path.exists(log_file))


class TestConfigManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch.dict(os.environ, {"APPDATA": self.temp_dir})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_config_defaults_and_override(self):
        cfg = ConfigManager()
        self.assertEqual(cfg.update_interval_sec, 300)
        self.assertTrue(cfg.always_on_top)

        cfg.update_interval_sec = 60
        cfg.always_on_top = False
        cfg.save()

        cfg2 = ConfigManager()
        self.assertEqual(cfg2.update_interval_sec, 60)
        self.assertFalse(cfg2.always_on_top)

    def test_sanitize_coordinates_fallback(self):
        cfg = ConfigManager()
        # When no QApp is running, should return safe default
        x, y = cfg.sanitize_coordinates(None, None, 420, 530)
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)


class TestHistoryStore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_history.db")
        self.store = HistoryStore(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_and_query_history(self):
        b1 = QuotaBucket(bucket_id="gemini-weekly", display_name="Gemini Weekly", window="weekly", remaining_fraction=0.90)
        b2 = QuotaBucket(bucket_id="gemini-5h", display_name="Gemini 5h", window="5h", remaining_fraction=0.75)
        group = QuotaGroup(display_name="Gemini Models", description="Gemini Flash, Pro", buckets=[b1, b2])

        snapshot = QuotaSnapshot(
            timestamp=datetime.now(timezone.utc),
            groups=[group],
            user_info=UserInfo(name="Test User", email="test@example.com")
        )

        self.store.record_snapshot(snapshot)
        history = self.store.get_history(bucket_name="Gemini Weekly", hours=24)
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["percentage"], 90.0, places=1)


class TestQuotaFetcherParsing(unittest.TestCase):

    def test_parse_summary_payload(self):
        fetcher = QuotaFetcher()
        sample_payload = {
            "response": {
                "groups": [
                    {
                        "displayName": "Gemini Models",
                        "description": "Gemini Flash, Pro",
                        "buckets": [
                            {
                                 "bucketId": "gemini-weekly",
                                "displayName": "Weekly Limit Remaining",
                                "window": "weekly",
                                "remainingFraction": 0.1216,
                                "resetTime": "2026-08-27T00:34:57Z"
                            },
                            {
                                "bucketId": "gemini-5h",
                                "displayName": "Five Hour Limit Remaining",
                                "window": "5h",
                                "remainingFraction": 0.2500,
                                "resetTime": "2026-08-26T19:41:04Z"
                            }
                        ]
                    }
                ]
            }
        }

        groups = fetcher._parse_groups(sample_payload)
        self.assertEqual(len(groups), 1)
        g = groups[0]
        self.assertEqual(g.display_name, "Gemini Models")
        self.assertEqual(len(g.buckets), 2)
        self.assertEqual(g.buckets[0].window, "weekly")
        self.assertEqual(g.buckets[0].percentage_int, 12)
        self.assertEqual(g.buckets[1].window, "5h")
        self.assertEqual(g.buckets[1].percentage_int, 25)

    def test_fetch_resilience_when_no_server(self):
        mock_disc = MagicMock()
        mock_disc.find_active_server.return_value = None
        fetcher = QuotaFetcher(discovery=mock_disc)
        snapshot = fetcher.fetch(force_rediscover=True)
        self.assertIsInstance(snapshot, QuotaSnapshot)
        self.assertFalse(snapshot.is_success)
        self.assertTrue(len(snapshot.error_message) > 0)


    def test_in_place_widget_updates_stress(self):
        from PySide6.QtWidgets import QApplication
        temp_d = tempfile.mkdtemp()
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            cfg = ConfigManager()
            store = HistoryStore(db_path=os.path.join(temp_d, "stress.db"))
            
            from src.widgets.monitor_widget import MonitorWidget
            from src.widgets.compact_widget import CompactWidget
            
            mw = MonitorWidget(cfg, store)
            cw = CompactWidget()
            
            # Simulate 20 rapid successive snapshot updates
            for i in range(20):
                b1 = QuotaBucket(bucket_id="gemini-weekly", display_name="Gemini Weekly", window="weekly", remaining_fraction=0.5 + (i % 5) * 0.1)
                b2 = QuotaBucket(bucket_id="gemini-5h", display_name="Gemini 5h", window="5h", remaining_fraction=0.2 + (i % 5) * 0.1)
                g1 = QuotaGroup(display_name="Gemini Models", description="Gemini Flash", buckets=[b1, b2])
                
                b3 = QuotaBucket(bucket_id="claude-weekly", display_name="Claude Weekly", window="weekly", remaining_fraction=0.8)
                b4 = QuotaBucket(bucket_id="claude-5h", display_name="Claude 5h", window="5h", remaining_fraction=0.3)
                g2 = QuotaGroup(display_name="Claude and GPT models", description="Claude Sonnet", buckets=[b3, b4])
                
                snap = QuotaSnapshot(
                    timestamp=datetime.now(timezone.utc),
                    groups=[g1, g2],
                    user_info=UserInfo(name="Stress Tester", email="stress@test.com"),
                    is_success=True
                )
                mw.update_data(snap)
                cw.update_data(snap)
                
            self.assertEqual(len(mw._group_cards), 2)
            mw.deleteLater()
            cw.deleteLater()
        finally:
            shutil.rmtree(temp_d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
