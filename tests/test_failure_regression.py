"""Failure -> test: production failures that must never come back.

Each class pins one failure that was really logged in logs/failures.jsonl
(query_id in the docstring) against the real handbook fixture, with no model
or network needed. Story and numbers: docs/SUPPORT_DRILL.md.

Failure 831f3491 -- "When do I need a medical certificate for sick leave?"
  The answer was correct ("more than three consecutive days"), but the
  cross-encoder scored the best chunk -0.85, so detect_issues() flagged it
  `low_relevance`. 33 of the 35 handbook failures in the log were false alarms
  like this one. Each one filled the failure queue AND was kept out of the
  semantic cache, so the same question paid for the LLM every time.
"""

import unittest
from pathlib import Path

from observability.tracing import answer_is_grounded, detect_issues

HANDBOOK = Path(__file__).resolve().parent.parent / "eval" / "fixtures" / "northwind_handbook.txt"
SICK_SECTION = next(p for p in HANDBOOK.read_text(encoding="utf-8").split("\n\n") if p.startswith("3. Sick leave"))


class FalseAlarmRegression(unittest.TestCase):
    """Real failure 831f3491 and its siblings: low score, correct answer."""

    def issues_for(self, answer, score=-0.8501, context=SICK_SECTION):
        issues, _ = detect_issues([context], [context], [score], answer)
        return [i["type"] for i in issues]

    def test_correct_answer_with_low_rerank_score_is_not_a_failure(self):
        answer = "A medical certificate is required when your sick-leave absence exceeds **three consecutive days**."
        self.assertEqual(self.issues_for(answer), [])

    def test_correct_refusal_with_low_rerank_score_is_not_a_failure(self):
        # real answer to "Who is the CEO of Northwind Logistics?" (80ec4acd)
        answer = "I’m sorry, but the provided handbook does not include information about the CEO of Northwind Logistics."
        self.assertEqual(self.issues_for(answer, score=-1.4316), [])


class RealFailuresStillCaught(unittest.TestCase):
    """The fix must not hide real problems."""

    def test_unsupported_answer_with_low_score_is_still_flagged(self):
        answer = "Employees need a certificate after 90 days, signed by the regional CEO in Paris."
        issues, _ = detect_issues([SICK_SECTION], [SICK_SECTION], [-0.85], answer)
        self.assertEqual([i["type"] for i in issues], ["low_relevance"])

    def test_empty_answer_and_empty_retrieval_still_flagged(self):
        types = [i["type"] for i in detect_issues([], [], [], "")[0]]
        self.assertEqual(types, ["empty_retrieval", "empty_context", "empty_answer"])

    def test_grounding_folds_spelled_out_numbers(self):
        self.assertTrue(answer_is_grounded("more than three consecutive days", [SICK_SECTION]))
        self.assertFalse(answer_is_grounded("more than nine consecutive weeks", [SICK_SECTION]))


if __name__ == "__main__":
    unittest.main()
