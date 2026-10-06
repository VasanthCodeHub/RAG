import asyncio
import unittest
from unittest.mock import patch

from a2a.protocol import agent_card, message_text, task_response
from a2a.manager import _metrics, _run_manager


class A2AProtocolTests(unittest.TestCase):
    def test_agent_card_advertises_json_rpc_endpoint(self):
        card = agent_card("document-answer", "http://localhost:9000")

        self.assertEqual(card["protocolVersion"], "0.3.0")
        self.assertEqual(card["url"], "http://localhost:9000/a2a/document-answer")
        self.assertEqual(card["skills"][0]["id"], "document-answer")

    def test_message_text_reads_text_parts(self):
        text = message_text(
            {
                "role": "user",
                "parts": [{"kind": "text", "text": "question"}],
            }
        )

        self.assertEqual(text, "question")

    def test_task_response_contains_a_completed_text_artifact(self):
        task = task_response({"answer": "Found it."}, "context-1")

        self.assertEqual(task["contextId"], "context-1")
        self.assertEqual(task["status"]["state"], "completed")
        self.assertEqual(task["artifacts"][0]["parts"][0]["kind"], "text")

    def test_metrics_prefer_quality_before_cost(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 20, "estimated_cost_usd": 0.01}
        specialist = {"quality_signal": {"label": "strong_match"}, "usage": usage}
        solo = {"quality_signal": {"label": "weak_match"}, "usage": {**usage, "estimated_cost_usd": 0.001}}
        team = {"document_answer": specialist, "evidence_review": specialist}

        metrics = _metrics(team, solo, 200, 100)

        self.assertEqual(metrics["winner"], "A2A team")
        self.assertEqual(metrics["team"]["total_tokens"], 240)

    def test_metrics_use_cost_when_quality_ties(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 20, "estimated_cost_usd": 0.001}
        specialist = {"quality_signal": {"label": "weak_match"}, "usage": usage}
        solo = {"quality_signal": {"label": "weak_match"}, "usage": {**usage, "estimated_cost_usd": 0.01}}
        team = {"document_answer": specialist, "evidence_review": specialist}

        metrics = _metrics(team, solo, 200, 100)

        self.assertEqual(metrics["winner"], "A2A team")
        self.assertEqual(metrics["verdict_reason"], "Quality tied; lower estimated model cost wins.")

    def test_manager_delegates_and_returns_team_and_single_results(self):
        async def fake_agent(agent_name, pdf_hash, question, context_id):
            return {
                "answer": agent_name,
                "contexts": [],
                "quality_signal": {"label": "strong_match"},
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "estimated_cost_usd": 0.0001,
                },
            }

        async def fake_mcp(pdf_hash, question):
            return {
                "answer": "single",
                "contexts": [],
                "quality_signal": {"label": "weak_match"},
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "estimated_cost_usd": 0.0001,
                },
            }

        with (
            patch("a2a.manager._send_to_agent", side_effect=fake_agent),
            patch("a2a.manager._ask_mcp", side_effect=fake_mcp),
        ):
            result = asyncio.run(_run_manager("pdf-hash", "question"))

        self.assertEqual(len(result["team"]["delegations"]), 2)
        self.assertIn("document-answer", result["team"]["answer"])
        self.assertEqual(result["single"]["answer"], "single")
        self.assertEqual(result["metrics"]["winner"], "A2A team")


if __name__ == "__main__":
    unittest.main()
