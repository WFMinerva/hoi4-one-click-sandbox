#!/usr/bin/env python3
"""Regression tests for project-specific static validation rules."""

from __future__ import annotations

import unittest

from tools import validate_mod as validator


def parsed_repository() -> dict:
    return {
        path: validator.parse_script(validator.read_utf8(path))[0]
        for path in validator.collect_script_files()
    }


class ValidatorRegressionTests(unittest.TestCase):
    def run_structure_check(self, scripts: dict) -> list[str]:
        errors: list[str] = []
        validator.check_script_structure(scripts, errors)
        return errors

    def test_parser_ignores_comments_and_braces_in_strings(self) -> None:
        parsed, errors = validator.parse_script(
            'effect = { value = "{not_a_block}" # limit = { }\n real = yes }'
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(parsed.assignments), 1)
        effect = parsed.assignments[0].value
        self.assertIsInstance(effect, validator.Block)
        self.assertEqual(validator.direct_scalars(effect, "real"), ["yes"])

    def test_unclosed_string_is_rejected(self) -> None:
        _, errors = validator.parse_script('effect = { name = "unfinished }')
        self.assertTrue(any("字符串未闭合" in error for error in errors))

    def test_duplicate_limit_is_rejected(self) -> None:
        scripts = parsed_repository()
        target = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_construction_effects.txt"
        ]
        target.assignments.append(
            validator.Assignment(
                "TEST_duplicate_limit",
                validator.Block(
                    [
                        validator.Assignment("limit", validator.Block(), 9001),
                        validator.Assignment("limit", validator.Block(), 9002),
                    ]
                ),
                9000,
            )
        )
        self.assertTrue(
            any("同一作用域存在多个 limit" in error for error in self.run_structure_check(scripts))
        )

    def test_unpaired_prc_condition_is_rejected(self) -> None:
        scripts = parsed_repository()
        target = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_effects.txt"
        ]
        target.assignments.append(
            validator.Assignment(
                "TEST_unpaired_prc",
                validator.Block(
                    [validator.Assignment("original_tag", "PRC", 9001)]
                ),
                9000,
            )
        )
        self.assertTrue(
            any("PRC 判断未同时包含" in error for error in self.run_structure_check(scripts))
        )

    def test_uncontrolled_owned_state_is_rejected(self) -> None:
        scripts = parsed_repository()
        target = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_construction_effects.txt"
        ]
        target.assignments.append(
            validator.Assignment(
                "TEST_uncontrolled_state",
                validator.Block(
                    [
                        validator.Assignment(
                            "every_owned_state", validator.Block(), 9001
                        )
                    ]
                ),
                9000,
            )
        )
        self.assertTrue(
            any("缺少 is_controlled_by = ROOT" in error for error in self.run_structure_check(scripts))
        )

    def test_decision_without_ai_guard_is_rejected(self) -> None:
        scripts = parsed_repository()
        decision_root = scripts[
            validator.ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
        ]
        category = decision_root.assignments[0].value
        self.assertIsInstance(category, validator.Block)
        decision = category.assignments[0].value
        self.assertIsInstance(decision, validator.Block)
        decision.assignments = [
            assignment
            for assignment in decision.assignments
            if assignment.key != "ai_will_do"
        ]
        self.assertTrue(
            any("缺少 ai_will_do" in error for error in self.run_structure_check(scripts))
        )


if __name__ == "__main__":
    unittest.main()
