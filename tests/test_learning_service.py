import tempfile
import unittest
from pathlib import Path

from learning import LearningService


class LearningServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "learning.db"
        self.service = LearningService(self.db_path)
        self.service.bootstrap_schema("learning/schema.sql")

    def tearDown(self):
        self.tmp.cleanup()

    def test_suggest_and_apply(self):
        cid = self.service.create_correction(
            pattern_signature="email missing at symbol",
            correction_payload={"replace": "@"},
            confidence_before=0.2,
            confidence_after=0.9,
            context_metadata={"field": "email"},
            rule_type="normalization",
        )
        suggestions = self.service.suggest_low_confidence_items(0.3)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["id"], cid)

        decision = self.service.apply_fix_to_similar_cases(
            correction_id=cid,
            target_pattern_signature="email missing symbol",
            similarity_threshold=0.4,
        )
        self.assertTrue(decision.accepted)

        history = self.service.list_rule_history()
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["reuse_success"])

    def test_rule_history_crud(self):
        cid = self.service.create_correction(
            pattern_signature="phone whitespace",
            correction_payload={"trim": True},
            confidence_before=0.4,
            confidence_after=0.88,
            context_metadata={},
            rule_type="cleanup",
        )
        hid = self.service.create_rule_history(
            {
                "correction_id": cid,
                "target_pattern_signature": "phone spacing issue",
                "similarity_threshold": 0.5,
                "computed_similarity": 0.6,
                "reuse_success": True,
                "outcome_reason": "accepted",
                "context_metadata": {"source": "ui"},
                "optional_notes": "manual",
            }
        )
        fetched = self.service.get_rule_history(hid)
        self.assertEqual(fetched["optional_notes"], "manual")

        updated = self.service.update_rule_history(hid, {"optional_notes": "edited"})
        self.assertTrue(updated)
        self.assertEqual(self.service.get_rule_history(hid)["optional_notes"], "edited")

        deleted = self.service.delete_rule_history(hid)
        self.assertTrue(deleted)
        self.assertIsNone(self.service.get_rule_history(hid))


if __name__ == "__main__":
    unittest.main()
