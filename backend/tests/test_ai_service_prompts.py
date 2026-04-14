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
        self.assertLess(prompt.index("Prioritize billing and refund issues."), prompt.index("This mailbox belongs to the finance team."))

    def test_reply_prompt_enforces_chinese_output_and_keeps_account_context(self):
        prompt = ai_service.build_reply_system_prompt(
            role="采购负责人",
            focus="供应商沟通",
            tone="专业、友好",
            language="zh-CN",
            reply_system_prompt="优先保持礼貌但明确的商务语气。",
            account_prompt_context="这是采购部门邮箱，主要处理报价与合同。",
        )

        self.assertIn("只输出中文邮件正文", prompt)
        self.assertIn("优先保持礼貌但明确的商务语气。", prompt)
        self.assertIn("这是采购部门邮箱，主要处理报价与合同。", prompt)


if __name__ == "__main__":
    unittest.main()
