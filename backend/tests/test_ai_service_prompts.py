import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import ai_service


class AIServicePromptTests(unittest.TestCase):
    def test_analysis_prompt_appends_global_and_account_context_in_selected_language(self):
        prompt = ai_service.build_analysis_system_prompt(
            role="Founder",
            focus="customer support",
            tone="warm and direct",
            language="en-US",
            analysis_system_prompt="Prioritize billing and refund issues.",
            account_prompt_context="This mailbox belongs to the finance team.",
        )

        self.assertIn("You are an email assistant.", prompt)
        self.assertIn("Prioritize billing and refund issues.", prompt)
        self.assertIn("This mailbox belongs to the finance team.", prompt)
        self.assertIn("Use English only for the analysis output.", prompt)
        self.assertLess(
            prompt.index("Prioritize billing and refund issues."),
            prompt.index("This mailbox belongs to the finance team."),
        )

    def test_reply_prompt_keeps_context_and_language_constraint(self):
        prompt = ai_service.build_reply_system_prompt(
            role="Founder",
            focus="customer support",
            tone="warm and direct",
            language="en-US",
            reply_system_prompt="Keep the answer concise and polite.",
            account_prompt_context="This mailbox belongs to the finance team.",
        )

        self.assertIn("Output only the email body in English.", prompt)
        self.assertIn("Keep the answer concise and polite.", prompt)
        self.assertIn("This mailbox belongs to the finance team.", prompt)
        self.assertLess(
            prompt.index("This mailbox belongs to the finance team."),
            prompt.index("Expand the user's draft into a complete, professional reply email."),
        )


if __name__ == "__main__":
    unittest.main()
