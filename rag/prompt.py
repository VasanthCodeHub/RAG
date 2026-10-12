# Bump when ANSWER_PROMPT changes, so a logged answer can be tied to the wording that produced it.
PROMPT_VERSION = "answer-v1"

ANSWER_PROMPT = """Answer the following query using the provided context.
- Query: {query}
- Context: {context}
"""
