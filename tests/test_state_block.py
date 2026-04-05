from __future__ import annotations

import unittest

from signal_forge.utils.state import build_state_block


class StateBlockTests(unittest.TestCase):
    def test_build_state_block_with_multiple_working_items_and_issues(self) -> None:
        result = build_state_block(
            {
                "task": "pipeline validation",
                "status": "PASS",
                "working": ["state format locked", "status normalized"],
                "issues": ["missing field fixed", "next action limited"],
                "next": "run pipeline validation",
            },
            None,
            None,
        )

        self.assertEqual(
            result,
            "\n".join(
                [
                    "## STATE",
                    "",
                    "Task",
                    "- pipeline validation",
                    "",
                    "Status",
                    "- PASS",
                    "",
                    "Working",
                    "- state format locked",
                    "- status normalized",
                    "",
                    "Issues",
                    "- missing field fixed",
                    "- next action limited",
                    "",
                    "Next",
                    "- run pipeline validation",
                ]
            ),
        )

    def test_build_state_block_renders_none_for_empty_issues(self) -> None:
        result = build_state_block(
            {
                "task": "edge case handling",
                "status": "PASS",
                "working": ["empty issues normalized"],
                "issues": [],
                "next": "run focused tests",
            },
            None,
            None,
        )

        self.assertIn("## STATE", result)
        self.assertIn("\nIssues\n- none\n", result)
        self.assertIn("\nStatus\n- PASS\n", result)

    def test_build_state_block_keeps_single_working_item_as_list(self) -> None:
        result = build_state_block(
            {
                "task": "single item check",
                "status": "FAIL",
                "working": ["single behavior verified"],
                "issues": ["format deviation"],
                "next": ["regenerate output", "ignore this extra action"],
            },
            None,
            None,
        )

        self.assertIn("\nWorking\n- single behavior verified\n", result)
        self.assertIn("\nNext\n- regenerate output", result)
        self.assertNotIn("- ignore this extra action", result)


if __name__ == "__main__":
    unittest.main()
