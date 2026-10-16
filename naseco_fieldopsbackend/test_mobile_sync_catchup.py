from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace

from naseco_fieldopsbackend import mobile_sync as sync


class TestMobileSyncCatchup(TestCase):
    def test_full_snapshot_uses_request_start_watermark_not_page_end(self):
        rows = [SimpleNamespace(name="010", document_type="Outgrower",
                                document_name="H001", requires_full_sync=1)]
        with patch.object(sync, "_latest_cursor", return_value="090"), \
             patch.object(sync, "_cursor_expired", return_value=False), \
             patch.object(sync.frappe, "session", SimpleNamespace(user="test@example.com")), \
             patch.object(sync.frappe, "get_all", return_value=rows), \
             patch.object(sync, "_api") as api:
            api.return_value._mobile_allowed_doctypes.return_value = {"Outgrower"}
            result = sync.get_mobile_changes("001")
        self.assertEqual(result["cursor"], "090")
        self.assertTrue(result["requires_full_sync"])
        self.assertFalse(result["has_more"])
        self.assertEqual(result["data"], {})

    def test_empty_ledger_does_not_repeat_bootstrap_after_snapshot(self):
        with patch.object(sync, "_latest_cursor", return_value="0"), \
             patch.object(sync, "_cursor_expired", return_value=False), \
             patch.object(sync.frappe, "session", SimpleNamespace(user="test@example.com")), \
             patch.object(sync.frappe, "get_all", return_value=[]), \
             patch.object(sync, "_api"):
            self.assertTrue(sync.get_mobile_changes(None)["requires_full_sync"])
            result = sync.get_mobile_changes("0")
        self.assertFalse(result["requires_full_sync"])
        self.assertEqual(result["cursor"], "0")
