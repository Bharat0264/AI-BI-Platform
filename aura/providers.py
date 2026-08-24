"""Optional LLM providers. Providers only narrate supplied evidence."""
from __future__ import annotations
import os

class GeminiEvidenceProvider:
    def explain(self, question, evidence):
        key=os.getenv("GEMINI_API_KEY")
        # Network narration is opt-in; deterministic evidence remains the default.
        if not key or os.getenv("AURA_ENABLE_LLM", "false").lower() != "true": return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            prompt=("Explain only the verified evidence below. Do not add numbers, causes, or facts. "
                    f"Question: {question}\nEvidence: {evidence}")
            return genai.GenerativeModel("models/gemini-2.5-flash").generate_content(prompt).text
        except Exception: return None
