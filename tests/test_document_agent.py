import io
import unittest
import zipfile
from types import SimpleNamespace

from agent.document_agent import run_document_agent
from rag.data_helper import read_document_bytes


def _msg(content=None, calls=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
    )


def _call(i, question):
    return SimpleNamespace(
        id=f"c{i}", function=SimpleNamespace(name="search_document", arguments=f'{{"question": "{question}"}}')
    )


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools=None, max_retries=3):
        return self.script.pop(0)


def fake_search(question):
    return {"answer": f"answer to {question}", "quality_signal": {"label": "strong_match"}}


class DocumentAgentTests(unittest.TestCase):
    def test_decomposes_then_answers(self):
        llm = FakeLLM([_msg(calls=[_call(1, "a"), _call(2, "b")]), _msg(content="final")])
        result = run_document_agent("compare a and b", llm, fake_search)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["answer"], "final")
        self.assertEqual([t["question"] for t in result["tool_log"]], ["a", "b"])
        self.assertEqual(result["total_tokens"], 240)

    def test_iteration_budget_ends_cleanly_with_evidence(self):
        llm = FakeLLM([_msg(calls=[_call(i, f"q{i}")]) for i in range(5)])
        result = run_document_agent("loop forever", llm, fake_search, max_iterations=2)
        self.assertEqual(result["status"], "budget_exceeded")
        self.assertEqual(result["budget_exceeded"], "max_iterations")
        self.assertIn("answer to q0", result["answer"])

    def test_token_budget(self):
        llm = FakeLLM([_msg(calls=[_call(1, "a")]), _msg(content="never reached")])
        result = run_document_agent("q", llm, fake_search, max_tokens=100)
        self.assertEqual(result["budget_exceeded"], "max_tokens")

    def test_tool_error_is_reported_not_raised(self):
        llm = FakeLLM([_msg(calls=[_call(1, "a")]), _msg(content="could not find it")])
        result = run_document_agent("q", llm, lambda q: {"error": "backend down"})
        self.assertEqual(result["tool_log"][0]["error"], "backend down")
        self.assertEqual(result["status"], "ok")


class ReadDocumentTests(unittest.TestCase):
    def test_text_and_markdown(self):
        self.assertEqual(read_document_bytes(b"hello", "a.txt"), "hello")
        self.assertEqual(read_document_bytes(b"# T", "a.md"), "# T")

    def test_html_strips_tags_and_scripts(self):
        text = read_document_bytes(b"<html><script>x()</script><p>Hi there</p></html>", "a.html")
        self.assertIn("Hi there", text)
        self.assertNotIn("x()", text)

    def test_docx(self):
        xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            "<w:p><w:r><w:t>First para</w:t></w:r></w:p><w:p><w:r><w:t>Second</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", xml)
        self.assertEqual(read_document_bytes(buf.getvalue(), "a.docx"), "First para\nSecond")

    def test_unsupported_type(self):
        with self.assertRaises(ValueError):
            read_document_bytes(b"x", "a.exe")


if __name__ == "__main__":
    unittest.main()
