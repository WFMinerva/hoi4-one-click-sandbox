#!/usr/bin/env python3
"""Regression tests for project-specific static validation rules."""

from __future__ import annotations

import unittest

from tools import build_release
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

    def test_repeatable_24_division_contract(self) -> None:
        scripts = parsed_repository()
        decision_root = scripts[
            validator.ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
        ]
        category = decision_root.assignments[0].value
        self.assertIsInstance(category, validator.Block)
        decision = next(
            assignment.value
            for assignment in category.assignments
            if assignment.key == "PRC_OCS_raise_24_infantry_divisions"
        )
        self.assertIsInstance(decision, validator.Block)
        self.assertEqual(validator.direct_scalars(decision, "days_re_enable"), ["1"])
        self.assertEqual(validator.direct_scalars(decision, "fire_only_once"), ["no"])

        military_text = validator.read_utf8(
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_military_effects.txt"
        )
        self.assertNotIn("PRC_OCS_24_infantry_divisions_raised", military_text)

    def test_evolution_dependency_and_variant_contract(self) -> None:
        scripts = parsed_repository()
        decision_root = scripts[
            validator.ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
        ]
        category = decision_root.assignments[0].value
        self.assertIsInstance(category, validator.Block)
        decision = next(
            assignment.value
            for assignment in category.assignments
            if assignment.key == "PRC_OCS_evolve_special_project_forces"
        )
        self.assertIsInstance(decision, validator.Block)
        available = validator.direct_blocks(decision, "available")[0]
        self.assertEqual(
            set(validator.direct_scalars(available, "is_special_project_completed")),
            {
                "sp:sp_land_flamethrower_tank",
                "sp:sp_land_military_engineering_vehicles",
                "sp:sp_air_helicopter",
                "sp:sp_air_intercontinental_bomber",
                "sp:sp_air_mothership_aircraft",
                "sp:sp_air_axial_jet_engine",
            },
        )
        self.assertEqual(
            set(validator.direct_scalars(available, "has_tech")),
            {
                "tech_trucks",
                "amphibious_mechanized_infantry_2",
                "sp_armored_advanced_flamethrower_tech",
                "sp_armored_engineer_tech",
                "sp_armored_maintenance_tech",
                "sp_armored_signal_tech",
                "sp_helicopter_transport_pods_tech",
                "jet_strategic_bomber1",
                "jet_tactical_bomber2",
            },
        )

        equipment_text = validator.read_utf8(
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_equipment_effects.txt"
        )
        evolved_equipment_text = equipment_text.split(
            "PRC_OCS_create_evolved_variants_effect = {", 1
        )[1]
        self.assertEqual(evolved_equipment_text.count('name = "装甲支援车"'), 4)
        self.assertEqual(
            evolved_equipment_text.count('name = "改进型履带登陆车"'), 1
        )
        for aircraft_name in (
            "喷气式战略轰炸机 I型",
            "喷气式战术轰炸机 II型",
            "空天母舰",
            "洲际轰炸机",
        ):
            self.assertEqual(
                evolved_equipment_text.count(f'name = "{aircraft_name}"'), 2
            )
        self.assertEqual(
            evolved_equipment_text.count(
                "design_team = mio:PRC_peoples_aviation_company_of_china_organization"
            ),
            4,
        )
        self.assertIn(
            "has_military_industrial_organization = "
            "PRC_peoples_aviation_company_of_china_organization",
            evolved_equipment_text,
        )
        self.assertNotIn("43式喷火预备", equipment_text)
        for parent_version in (1, 2, 3, 4):
            self.assertIn(f"parent_version = {parent_version}", equipment_text)

        template_root = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_template_effects.txt"
        ]
        template_text = validator.read_utf8(
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_template_effects.txt"
        )
        self.assertNotIn("delete_unit_template_and_units =", template_text)
        evolved_templates = next(
            assignment.value
            for assignment in template_root.assignments
            if assignment.key == "PRC_OCS_create_evolved_templates_effect"
        )
        self.assertIsInstance(evolved_templates, validator.Block)
        templates = validator.direct_blocks(evolved_templates, "division_template")
        headquarters = next(
            template
            for template in templates
            if validator.direct_scalars(template, "name") == ["司令部"]
        )
        self.assertEqual(validator.direct_scalars(headquarters, "template_counter"), ["0"])
        self.assertEqual(
            validator.direct_scalars(headquarters, "ingame_set_template_counter"),
            ["yes"],
        )
        self.assertEqual(
            validator.direct_scalars(headquarters, "localization_key"),
            ["ARMY_HQ_TEMPLATE_NAME"],
        )
        armor = next(
            template
            for template in templates
            if validator.direct_scalars(template, "name") == ["装甲师·进化型"]
        )
        self.assertEqual(validator.direct_scalars(armor, "template_counter"), [])
        self.assertEqual(
            validator.direct_scalars(armor, "ingame_set_template_counter"), []
        )
        armor_regiments = validator.direct_blocks(armor, "regiments")[0]
        self.assertEqual(
            [assignment.key for assignment in armor_regiments.assignments].count(
                "mechanized"
            ),
            12,
        )
        self.assertEqual(
            [assignment.key for assignment in armor_regiments.assignments].count(
                "medium_sp_artillery_brigade"
            ),
            6,
        )
        armor_regimental_support = validator.direct_blocks(
            armor, "regimental_support"
        )[0]
        support_keys = [
            assignment.key for assignment in armor_regimental_support.assignments
        ]
        self.assertEqual(support_keys.count("mot_fire_support"), 3)
        self.assertEqual(support_keys.count("medium_tank_destroyer_support"), 2)
        armored_marines = next(
            template
            for template in templates
            if validator.direct_scalars(template, "name")
            == ["海军陆战队装甲师·进化型"]
        )
        self.assertEqual(
            validator.direct_scalars(armored_marines, "template_counter"), []
        )
        self.assertEqual(
            validator.direct_scalars(
                armored_marines, "ingame_set_template_counter"
            ),
            [],
        )
        main_infantry_tank = next(
            template
            for template in templates
            if validator.direct_scalars(template, "name") == ["主力步坦师·进化型"]
        )
        self.assertEqual(
            validator.direct_scalars(main_infantry_tank, "template_counter"), ["104"]
        )
        self.assertEqual(
            validator.direct_scalars(
                main_infantry_tank, "ingame_set_template_counter"
            ),
            ["yes"],
        )

    def test_test_build_package_routing(self) -> None:
        self.assertTrue(build_release.is_test_version("2.2-test1"))
        self.assertFalse(build_release.is_test_version("2.2"))
        docs = build_release.package_docs("2.2-test1")
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(path.parent.name == "testing" for path in docs))


if __name__ == "__main__":
    unittest.main()
