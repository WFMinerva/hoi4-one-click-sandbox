#!/usr/bin/env python3
"""Regression tests for project-specific static validation rules."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import build_release
from tools import hoi4_paths
from tools import publish_github_release
from tools import publish_workshop
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

    def test_multiline_localisation_entry_is_rejected(self) -> None:
        errors = validator.localisation_line_errors(
            'l_english:\n KEY:0 "first line\nsecond line"\n'
        )
        self.assertEqual(len(errors), 2)

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

    def test_decision_visibility_contract(self) -> None:
        scripts = parsed_repository()
        category_root = scripts[
            validator.ROOT
            / "common"
            / "decisions"
            / "categories"
            / "PRC_OCS_categories.txt"
        ]
        category_definition = category_root.assignments[0].value
        self.assertIsInstance(category_definition, validator.Block)
        category_allowed = validator.direct_blocks(
            category_definition, "allowed"
        )[0]
        category_visible = validator.direct_blocks(
            category_definition, "visible"
        )[0]
        self.assertEqual(
            validator.direct_scalars(category_allowed, "always"), ["yes"]
        )
        self.assertEqual(
            validator.direct_scalars(category_allowed, "is_ai"), []
        )
        self.assertEqual(
            validator.direct_scalars(category_visible, "is_ai"), ["no"]
        )
        decision_root = scripts[
            validator.ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
        ]
        category = decision_root.assignments[0].value
        self.assertIsInstance(category, validator.Block)
        decisions = {
            assignment.key: assignment.value
            for assignment in category.assignments
        }
        one_time_flags = {
            "PRC_OCS_initialize": "PRC_OCS_initialized",
            "PRC_OCS_reorganize_army": "PRC_OCS_army_reorganized",
            "PRC_OCS_evolve_special_project_forces":
                "PRC_OCS_special_project_forces_evolved",
            "PRC_OCS_complete_air_special_projects":
                "PRC_OCS_air_special_projects_completed",
            "PRC_OCS_complete_land_special_projects":
                "PRC_OCS_land_special_projects_completed",
            "PRC_OCS_complete_naval_special_projects":
                "PRC_OCS_naval_special_projects_completed",
            "PRC_OCS_complete_nuclear_special_projects":
                "PRC_OCS_nuclear_special_projects_completed",
            "PRC_OCS_complete_rocket_special_projects":
                "PRC_OCS_rocket_special_projects_completed",
            "PRC_OCS_create_intelligence_agency":
                "PRC_OCS_intel_agency_created",
            "PRC_OCS_unlock_all_agency_upgrades":
                "PRC_OCS_intel_upgrades_done",
             "PRC_OCS_choose_air_special_project_bonuses":
                 "PRC_OCS_air_special_project_choices_done",
             "PRC_OCS_choose_land_special_project_bonuses":
                 "PRC_OCS_land_special_project_choices_done",
             "PRC_OCS_choose_naval_special_project_bonuses":
                 "PRC_OCS_naval_special_project_choices_done",
             "PRC_OCS_choose_nuclear_special_project_bonuses":
                 "PRC_OCS_nuclear_special_project_choices_done",
         }
        special_project_decisions = {
            name: flag
            for name, flag in one_time_flags.items()
            if "_complete_" in name
        }
        for decision_name, decision in decisions.items():
            self.assertIsInstance(decision, validator.Block)
            visible = validator.direct_blocks(decision, "visible")[0]
            self.assertEqual(validator.direct_scalars(visible, "is_ai"), ["no"])
            self.assertEqual(validator.direct_scalars(visible, "has_dlc"), [])
            self.assertEqual(
                validator.direct_scalars(visible, "has_country_flag"), []
            )
            not_blocks = validator.direct_blocks(visible, "NOT")
            if decision_name in one_time_flags:
                self.assertEqual(len(not_blocks), 1)
                self.assertEqual(
                    validator.direct_scalars(
                        not_blocks[0], "has_country_flag"
                    ),
                    [one_time_flags[decision_name]],
                )
            else:
                self.assertEqual(not_blocks, [])
            if decision_name in one_time_flags:
                self.assertEqual(
                    validator.direct_scalars(decision, "fire_only_once"), ["no"]
                )
        special_project_text = validator.read_utf8(
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_special_project_effects.txt"
        )
        for decision_name, completion_flag in special_project_decisions.items():
            decision = decisions[decision_name]
            self.assertEqual(
                validator.direct_scalars(decision, "days_re_enable"), []
            )
            self.assertIn(
                f"set_country_flag = {completion_flag}", special_project_text
            )

        for decision_name in (
            "PRC_OCS_resupply",
            "PRC_OCS_reorganize_army",
            "PRC_OCS_raise_24_infantry_divisions",
            "PRC_OCS_evolve_special_project_forces",
        ):
            available = validator.direct_blocks(
                decisions[decision_name], "available"
            )[0]
            self.assertIn(
                "PRC_OCS_initialized",
                validator.direct_scalars(available, "has_country_flag"),
            )

        for decision_name in (
            "PRC_OCS_complete_air_special_projects",
            "PRC_OCS_complete_land_special_projects",
            "PRC_OCS_complete_naval_special_projects",
            "PRC_OCS_complete_nuclear_special_projects",
            "PRC_OCS_complete_rocket_special_projects",
        ):
            available = validator.direct_blocks(
                decisions[decision_name], "available"
            )[0]
            self.assertEqual(
                validator.direct_scalars(available, "has_dlc"),
                ["Gotterdammerung"],
            )

        construction_tooltips = {
            "PRC_OCS_queue_coastal_dockyards":
                "PRC_OCS_queue_coastal_dockyards_available_tt",
            "PRC_OCS_queue_civilian_industry":
                "PRC_OCS_queue_civilian_industry_available_tt",
        }
        for decision_name, tooltip_key in construction_tooltips.items():
            available = validator.direct_blocks(
                decisions[decision_name], "available"
            )[0]
            self.assertEqual(
                validator.direct_blocks(available, "any_owned_state"), []
            )
            tooltip = validator.direct_blocks(
                available, "custom_trigger_tooltip"
            )
            self.assertEqual(len(tooltip), 1)
            self.assertEqual(
                validator.direct_scalars(tooltip[0], "tooltip"),
                [tooltip_key],
            )
            self.assertEqual(
                len(validator.direct_blocks(tooltip[0], "any_owned_state")),
                1,
            )

    def test_basic_armor_template_contract(self) -> None:
        scripts = parsed_repository()
        template_root = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_template_effects.txt"
        ]
        for effect_name in (
            "PRC_OCS_create_templates_effect",
            "PRC_OCS_create_generic_templates_effect",
        ):
            effect = next(
                assignment.value
                for assignment in template_root.assignments
                if assignment.key == effect_name
            )
            self.assertIsInstance(effect, validator.Block)
            armor = next(
                template
                for template in validator.direct_blocks(effect, "division_template")
                if validator.direct_scalars(template, "name") == ["装甲师"]
            )
            regiments = validator.direct_blocks(armor, "regiments")[0]
            regiment_layout = {
                (
                    assignment.key,
                    validator.direct_scalars(assignment.value, "x")[0],
                    validator.direct_scalars(assignment.value, "y")[0],
                )
                for assignment in regiments.assignments
            }
            self.assertEqual(
                regiment_layout,
                {
                    *{
                        ("mechanized", str(x), str(y))
                        for x in range(3)
                        for y in range(4)
                    },
                    *{
                        ("medium_sp_artillery_brigade", str(x), str(y))
                        for x in range(3, 5)
                        for y in range(3)
                    },
                },
            )
            regimental_support = validator.direct_blocks(
                armor, "regimental_support"
            )[0]
            self.assertEqual(
                [assignment.key for assignment in regimental_support.assignments],
                [
                    "mot_fire_support",
                    "mot_fire_support",
                    "mot_fire_support",
                    "medium_tank_destroyer_support",
                    "medium_tank_destroyer_support",
                ],
            )
            support = validator.direct_blocks(armor, "support")[0]
            self.assertEqual(
                [assignment.key for assignment in support.assignments],
                [
                    "artillery",
                    "engineer",
                    "light_tank_recon",
                    "logistics_company",
                    "field_hospital",
                ],
            )

    def test_basic_main_infantry_tank_template_contract(self) -> None:
        scripts = parsed_repository()
        template_root = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_template_effects.txt"
        ]
        for effect_name, infantry_type in (
            ("PRC_OCS_create_templates_effect", "militia"),
            ("PRC_OCS_create_generic_templates_effect", "infantry"),
        ):
            effect = next(
                assignment.value
                for assignment in template_root.assignments
                if assignment.key == effect_name
            )
            self.assertIsInstance(effect, validator.Block)
            main_infantry_tank = next(
                template
                for template in validator.direct_blocks(effect, "division_template")
                if validator.direct_scalars(template, "name") == ["主力步坦师"]
            )
            regiments = validator.direct_blocks(
                main_infantry_tank, "regiments"
            )[0]
            regiment_keys = [
                assignment.key for assignment in regiments.assignments
            ]
            self.assertEqual(regiment_keys.count(infantry_type), 15)
            self.assertEqual(
                regiment_keys.count(
                    "infantry" if infantry_type == "militia" else "militia"
                ),
                0,
            )
            self.assertEqual(
                regiment_keys.count("medium_sp_artillery_brigade"), 3
            )
            self.assertEqual(
                regiment_keys.count("light_sp_artillery_brigade"), 0
            )

    def test_shared_mio_company_routes_contract(self) -> None:
        scripts = parsed_repository()
        shared_root = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_shared_mio_effects.txt"
        ]
        shared_effect = next(
            assignment.value
            for assignment in shared_root.assignments
            if assignment.key == "PRC_OCS_configure_shared_mios_effect"
        )
        self.assertIsInstance(shared_effect, validator.Block)
        dlc_branch = validator.direct_blocks(shared_effect, "if")[0]
        self.assertEqual(
            validator.direct_blocks(
                dlc_branch, "every_military_industrial_organization"
            ),
            [],
        )
        company_branches = validator.direct_blocks(dlc_branch, "if")
        expected_company_counts = {
            "GER": 25,
            "ENG": 16,
            "JAP": 23,
            "SOV": 17,
            "AST": 13,
            "CZE": 17,
            "ITA": 18,
            "USA": 17,
            "PRC": 7,
        }
        expected_trait_counts = {
            "GER": 319,
            "ENG": 177,
            "JAP": 261,
            "SOV": 191,
            "AST": 168,
            "CZE": 178,
            "ITA": 200,
            "USA": 192,
            "PRC": 85,
        }
        observed_companies = set()
        completed_trait_count = 0
        company_counts_by_prefix = {}
        trait_counts_by_prefix = {}
        for branch in company_branches:
            country_limit = validator.direct_blocks(branch, "limit")[0]
            company = validator.direct_scalars(
                country_limit, "has_military_industrial_organization"
            )
            self.assertEqual(len(company), 1)
            observed_companies.add(company[0])
            mio_blocks = [
                assignment.value
                for assignment in branch.assignments
                if assignment.key == f"mio:{company[0]}"
            ]
            self.assertEqual(len(mio_blocks), 1)
            route = validator.direct_blocks(mio_blocks[0], "if")[0]
            traits = validator.direct_scalars(route, "complete_mio_trait")
            self.assertGreater(len(traits), 0)
            completed_trait_count += len(traits)
            prefix = company[0].split("_", 1)[0]
            company_counts_by_prefix[prefix] = (
                company_counts_by_prefix.get(prefix, 0) + 1
            )
            trait_counts_by_prefix[prefix] = (
                trait_counts_by_prefix.get(prefix, 0) + len(traits)
            )
            route_limit = validator.direct_blocks(route, "limit")[0]
            not_block = validator.direct_blocks(route_limit, "NOT")[0]
            self.assertEqual(
                validator.direct_scalars(
                    not_block, "is_mio_trait_completed"
                ),
                [traits[-1]],
            )
        self.assertEqual(len(observed_companies), 444)
        self.assertEqual(completed_trait_count, 4945)
        for prefix, expected in expected_company_counts.items():
            self.assertEqual(company_counts_by_prefix.get(prefix), expected)
        for prefix, expected in expected_trait_counts.items():
            self.assertEqual(trait_counts_by_prefix.get(prefix), expected)
        self.assertTrue(
            {
                "JAP_kure_naval_arsenal_organization",
                "ITA_officine_meccaniche_organization",
                "USA_detroit_arsenal_organization",
                "USA_tank_destroyer_board_organization",
            }.isdisjoint(observed_companies)
        )

        main_root = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_effects.txt"
        ]
        initialize = next(
            assignment.value
            for assignment in main_root.assignments
            if assignment.key == "PRC_OCS_initialize_effect"
        )
        self.assertEqual(
            validator.direct_scalars(
                initialize, "PRC_OCS_configure_shared_mios_effect"
            ),
            ["yes"],
        )

        mio_root = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_mio_effects.txt"
        ]
        self.assertNotIn(
            "PRC_OCS_boost_all_mios_effect",
            [assignment.key for assignment in mio_root.assignments],
        )
        self.assertEqual(
            validator.direct_scalars(
                initialize, "PRC_OCS_boost_all_mios_effect"
            ),
            [],
        )
        mio_text = "\n".join(
            validator.read_utf8(path)
            for path in (
                validator.ROOT
                / "common"
                / "scripted_effects"
                / "PRC_OCS_mio_effects.txt",
                validator.ROOT
                / "common"
                / "scripted_effects"
                / "PRC_OCS_shared_mio_effects.txt",
            )
        )
        self.assertNotIn("add_mio_size", mio_text)
        self.assertNotIn("add_mio_funds", mio_text)

        decision_root = scripts[
            validator.ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
        ]
        category = decision_root.assignments[0].value
        self.assertIsInstance(category, validator.Block)
        self.assertNotIn(
            "PRC_OCS_complete_shared_mio_traits",
            [assignment.key for assignment in category.assignments],
        )

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
        visible = validator.direct_blocks(decision, "visible")[0]
        available = validator.direct_blocks(decision, "available")[0]
        for block in (visible, available):
            nested_blocks = [
                nested for nested, _ in validator.walk_blocks(block)
            ]
            self.assertEqual(
                [
                    value
                    for nested in nested_blocks
                    for value in validator.direct_scalars(nested, "tag")
                ],
                [],
            )
            self.assertEqual(
                [
                    value
                    for nested in nested_blocks
                    for value in validator.direct_scalars(nested, "original_tag")
                ],
                [],
            )
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

        military_root = scripts[
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_military_effects.txt"
        ]
        evolution_effect = next(
            assignment.value
            for assignment in military_root.assignments
            if assignment.key == "PRC_OCS_evolve_special_project_forces_effect"
        )
        self.assertIsInstance(evolution_effect, validator.Block)
        prc_branch = validator.direct_blocks(evolution_effect, "if")[0]
        generic_branch = validator.direct_blocks(evolution_effect, "else")[0]
        self.assertEqual(
            validator.direct_scalars(
                prc_branch, "PRC_OCS_create_evolved_templates_effect"
            ),
            ["yes"],
        )
        self.assertEqual(
            validator.direct_scalars(
                generic_branch, "PRC_OCS_create_generic_evolved_templates_effect"
            ),
            ["yes"],
        )
        self.assertEqual(
            validator.direct_scalars(
                evolution_effect, "PRC_OCS_create_evolved_variants_effect"
            ),
            [],
        )
        self.assertEqual(
            validator.direct_scalars(
                prc_branch, "PRC_OCS_create_evolved_variants_effect"
            ),
            ["yes"],
        )
        self.assertEqual(
            validator.direct_scalars(
                generic_branch, "PRC_OCS_create_evolved_variants_effect"
            ),
            ["yes"],
        )
        self.assertEqual(
            validator.direct_scalars(
                evolution_effect, "set_country_flag"
            ),
            ["PRC_OCS_special_project_forces_evolved"],
        )

        equipment_path = (
            validator.ROOT
            / "common"
            / "scripted_effects"
            / "PRC_OCS_equipment_effects.txt"
        )
        equipment_root = scripts[equipment_path]
        equipment_text = validator.read_utf8(equipment_path)
        evolved_equipment_text = equipment_text.split(
            "PRC_OCS_create_evolved_variants_effect = {", 1
        )[1]
        evolved_effect = next(
            assignment.value
            for assignment in equipment_root.assignments
            if assignment.key == "PRC_OCS_create_evolved_variants_effect"
        )
        self.assertEqual(
            sum(
                1
                for variant in validator.direct_blocks(
                    evolved_effect, "create_equipment_variant"
                )
                if validator.direct_scalars(variant, "name") == ["装甲支援车"]
            ),
            4,
        )
        self.assertEqual(
            evolved_equipment_text.count('name = "改进型履带登陆车"'), 1
        )
        amphibious_variant = next(
            variant
            for variant in validator.direct_blocks(
                next(
                    assignment.value
                    for assignment in equipment_root.assignments
                    if assignment.key == "PRC_OCS_create_evolved_variants_effect"
                ),
                "create_equipment_variant",
            )
            if validator.direct_scalars(variant, "name")
            == ["改进型履带登陆车"]
        )
        amphibious_upgrades = validator.direct_blocks(
            amphibious_variant, "upgrades"
        )[0]
        self.assertEqual(
            {
                assignment.key: assignment.value
                for assignment in amphibious_upgrades.assignments
            },
            {
                "tank_armor_upgrade": "5",
                "tank_engine_upgrade": "5",
                "tank_reliability_upgrade": "5",
                "mech_cost_upgrade": "5",
            },
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
        main_regiments = validator.direct_blocks(main_infantry_tank, "regiments")[0]
        main_regiment_keys = [
            assignment.key for assignment in main_regiments.assignments
        ]
        self.assertEqual(main_regiment_keys.count("militia"), 15)
        self.assertEqual(main_regiment_keys.count("infantry"), 0)
        self.assertEqual(
            main_regiment_keys.count("medium_sp_artillery_brigade"), 3
        )
        self.assertEqual(
            main_regiment_keys.count("light_sp_artillery_brigade"), 0
        )

        generic_evolved_templates = next(
            assignment.value
            for assignment in template_root.assignments
            if assignment.key == "PRC_OCS_create_generic_evolved_templates_effect"
        )
        self.assertIsInstance(generic_evolved_templates, validator.Block)
        generic_templates = validator.direct_blocks(
            generic_evolved_templates, "division_template"
        )
        self.assertEqual(
            {
                validator.direct_scalars(template, "name")[0]
                for template in generic_templates
            },
            {
                "司令部",
                "装甲师·进化型",
                "海军陆战队装甲师·进化型",
                "主力步坦师·进化型",
            },
        )
        generic_main = next(
            template
            for template in generic_templates
            if validator.direct_scalars(template, "name") == ["主力步坦师·进化型"]
        )
        generic_main_regiments = validator.direct_blocks(
            generic_main, "regiments"
        )[0]
        generic_main_keys = [
            assignment.key for assignment in generic_main_regiments.assignments
        ]
        self.assertEqual(generic_main_keys.count("infantry"), 15)
        self.assertEqual(generic_main_keys.count("militia"), 0)
        self.assertEqual(
            generic_main_keys.count("medium_sp_artillery_brigade"), 3
        )
        self.assertEqual(
            generic_main_keys.count("light_sp_artillery_brigade"), 0
        )
        for template in generic_templates:
            self.assertEqual(
                validator.direct_scalars(template, "division_names_group"), []
            )
        self.assertEqual(
            validator.direct_scalars(generic_main, "template_counter"), []
        )
        self.assertEqual(
            validator.direct_scalars(
                generic_main, "ingame_set_template_counter"
            ),
            [],
        )

    def test_v26_choice_group_map_contract(self) -> None:
        """Every generated reward group maps to its own event, flag and menu."""
        mapping_path = (
            validator.ROOT
            / "docs"
            / "analysis"
            / "v2.6_特殊科研组事件映射.json"
        )
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        self.assertEqual(len(mapping), 26)
        flags = [item["flag"] for item in mapping]
        eids = [item["eid"] for item in mapping]
        self.assertEqual(len(set(flags)), len(flags))
        self.assertEqual(len(set(eids)), len(eids))
        self.assertEqual(eids, sorted(eids))
        for item in mapping:
            self.assertIn(item["specialization"], {"air", "land", "naval", "nuclear"})
        menuless = {
            item["reward"]
            for item in mapping
            if item["menu"] not in {48, 49, 50, 51}
        }
        self.assertEqual(menuless, set())
        shared_project = {}
        for item in mapping:
            shared_project.setdefault(item["project"], []).append(item["reward"])
        multi = {
            project: rewards
            for project, rewards in shared_project.items()
            if len(rewards) > 1
        }
        self.assertEqual(
            set(multi),
            {
                "sp_land_stronghold_network",
                "sp_naval_escort_carrier",
                "sp_naval_modern_battleship",
                "sp_naval_modern_carrier",
                "sp_naval_super_heavy_battleship",
                "sp_naval_support_ships",
                "sp_nuclear_reactor",
            },
        )
        flag_by_reward = {item["reward"]: item["flag"] for item in mapping}
        self.assertEqual(
            flag_by_reward["sp_land_reward_stronghold_network_breakthrough_in_concrete_reinforcement_01"],
            "PRC_OCS_sp_land_reward_stronghold_network_breakthrough_in_concrete_reinforcement_01_choice_done",
        )
        self.assertEqual(
            flag_by_reward["sp_naval_escort_carrier_unique_reward_a"],
            "PRC_OCS_sp_naval_escort_carrier_unique_reward_a_choice_done",
        )
        self.assertEqual(
            flag_by_reward["sp_nuclear_isotope_separation_choice_reward"],
            "PRC_OCS_sp_nuclear_isotope_separation_choice_reward_choice_done",
        )

    def test_v26_dispatch_menu_z_contract(self) -> None:
        """Menu z triggers require every reward flag of the specialization."""
        events_path = validator.ROOT / "events" / "PRC_OCS_choice_events_more.txt"
        mapping = json.loads(
            (
                validator.ROOT
                / "docs"
                / "analysis"
                / "v2.6_特殊科研组事件映射.json"
            ).read_text(encoding="utf-8")
        )
        text = events_path.read_text(encoding="utf-8")
        menu_done_flags = {
            48: "PRC_OCS_land_special_project_choices_done",
            49: "PRC_OCS_nuclear_special_project_choices_done",
            50: "PRC_OCS_air_special_project_choices_done",
            51: "PRC_OCS_naval_special_project_choices_done",
        }
        by_menu: dict[int, list[dict]] = {}
        for item in mapping:
            by_menu.setdefault(item["menu"], []).append(item)
        for menu_id in (48, 49, 50, 51):
            block_start = text.index(f"\n id = PRC_OCS.{menu_id}\n")
            next_id = min(
                (
                    text.index(f"\n id = PRC_OCS.{candidate}\n")
                    for candidate in range(menu_id + 1, 52)
                    if f"\n id = PRC_OCS.{candidate}\n" in text
                ),
                default=len(text),
            )
            block = text[block_start:next_id]
            z_option = block.split(" name = PRC_OCS.%d.z" % menu_id, 1)[1]
            z_trigger = z_option.split("  hidden_effect = {", 1)[0]
            for item in by_menu[menu_id]:
                self.assertIn(f"has_country_flag = {item['flag']}", z_trigger)
            z_effect = z_option.split("  hidden_effect = {", 1)[1]
            self.assertIn(
                f"set_country_flag = {menu_done_flags[menu_id]}", z_effect
            )

    def test_v27_skull_divisions_contract(self) -> None:
        """v2.7 one-click skull divisions: single player-only decision applying
        the daliwan-proven passive-XP idea (7 days), with the obsolete drill
        variant fully removed."""
        scripts = parsed_repository()
        decision_root = scripts[
            validator.ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
        ]
        category = decision_root.assignments[0].value
        self.assertIsInstance(category, validator.Block)
        decisions = {
            assignment.key: assignment.value
            for assignment in category.assignments
        }
        self.assertNotIn("PRC_OCS_full_training", decisions)
        self.assertIn("PRC_OCS_skull_divisions", decisions)
        decision = decisions["PRC_OCS_skull_divisions"]
        self.assertIsInstance(decision, validator.Block)
        self.assertEqual(
            validator.direct_scalars(decision, "days_re_enable"), ["1"]
        )
        self.assertEqual(
            validator.direct_scalars(decision, "fire_only_once"), ["no"]
        )
        available = validator.direct_blocks(decision, "available")[0]
        self.assertEqual(validator.direct_scalars(available, "is_ai"), ["no"])
        self.assertEqual(
            validator.direct_scalars(available, "has_country_flag"), []
        )
        effect_block = validator.direct_blocks(decision, "complete_effect")[0]
        self.assertEqual(
            validator.direct_scalars(effect_block, "custom_effect_tooltip"),
            ["PRC_OCS_skull_divisions_idea"],
        )
        hidden = validator.direct_blocks(effect_block, "hidden_effect")[0]
        timed = validator.direct_blocks(hidden, "add_timed_idea")
        self.assertEqual(len(timed), 1)
        self.assertEqual(
            validator.direct_scalars(timed[0], "idea"),
            ["PRC_OCS_skull_divisions"],
        )
        self.assertEqual(
            validator.direct_scalars(timed[0], "days"), ["7"]
        )
        self.assertIn(
            "country_event = { id = PRC_OCS.53 }",
            validator.read_utf8(
                validator.ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
            ),
        )
        self.assertNotIn("set_training_level", validator.read_utf8(
            validator.ROOT / "common" / "scripted_effects" / "PRC_OCS_military_effects.txt"
        ))

        # Single idea inside the vanilla ideas = { country = { ... } } container.
        ideas_root = scripts[
            validator.ROOT / "common" / "ideas" / "PRC_OCS_military_ideas.txt"
        ]
        ideas_block = next(
            assignment.value
            for assignment in ideas_root.assignments
            if assignment.key == "ideas"
        )
        country = next(
            assignment.value
            for assignment in ideas_block.assignments
            if assignment.key == "country"
        )
        ideas = {
            assignment.key: assignment.value
            for assignment in country.assignments
        }
        self.assertEqual(set(ideas), {"PRC_OCS_skull_divisions"})
        idea = ideas["PRC_OCS_skull_divisions"]
        self.assertIsInstance(idea, validator.Block)
        available_idea = validator.direct_blocks(idea, "available")[0]
        self.assertEqual(
            validator.direct_scalars(available_idea, "is_ai"), ["no"]
        )
        modifier = validator.direct_blocks(idea, "modifier")[0]
        scalar_map = {
            assignment.key: assignment.value
            for assignment in modifier.assignments
        }
        self.assertEqual(scalar_map["experience_gain_army_unit"], "80000")
        self.assertEqual(scalar_map["experience_gain_navy_unit"], "80000")
        self.assertEqual(scalar_map["experience_gain_army_unit_factor"], "80")
        self.assertEqual(scalar_map["experience_gain_navy_unit_factor"], "50")

        events_text = validator.read_utf8(
            validator.ROOT / "events" / "PRC_OCS_events.txt"
        )
        self.assertIn("id = PRC_OCS.53", events_text)
        self.assertNotIn("id = PRC_OCS.52", events_text)
        localisation = (
            validator.read_utf8(validator.ROOT / "localisation" / "english" / "PRC_OCS_l_english.yml")
            + "\n"
            + validator.read_utf8(validator.ROOT / "localisation" / "simp_chinese" / "PRC_OCS_l_simp_chinese.yml")
        )
        for key in (
            "PRC_OCS_skull_divisions",
            "PRC_OCS_skull_divisions_idea",
            "PRC_OCS.53.t",
        ):
            self.assertIn(key, localisation)
        for stale in (
            "PRC_OCS_full_training",
            "PRC_OCS_drill_troops_idea",
            "PRC_OCS.52.t",
        ):
            self.assertNotIn(stale, localisation)

    def test_v27_choice_tooltips_contract(self) -> None:
        """Every grouped option of the choose-your-bonus events carries a
        concrete bilingual custom_effect_tooltip key (v2.7 description
        optimisation)."""
        events_path = validator.ROOT / "events" / "PRC_OCS_choice_events_more.txt"
        events_text = events_path.read_text(encoding="utf-8")
        en_text = validator.read_utf8(
            validator.ROOT / "localisation" / "english" / "PRC_OCS_l_english.yml"
        )
        zh_text = validator.read_utf8(
            validator.ROOT
            / "localisation"
            / "simp_chinese"
            / "PRC_OCS_l_simp_chinese.yml"
        )
        missing = []
        # Group events 22-47 only; dispatch-menu options are navigation, not effects.
        import re

        for eid in range(22, 48):
            block_start = events_text.index(f"\n id = PRC_OCS.{eid}\n")
            next_id = events_text.index(f"\n id = PRC_OCS.{eid + 1}\n")
            block = events_text[block_start:next_id]
            # Option names are PRC_OCS.{eid}.{letter}; derive letters from each option block.
            letters = re.findall(r"name = PRC_OCS\.%d\.([a-z])" % eid, block)
            self.assertTrue(letters)
            for letter in letters:
                tt_key = f"PRC_OCS.{eid}.{letter}_tt"
                if f"custom_effect_tooltip = {tt_key}" not in block:
                    missing.append(f"{tt_key} (event injection)")
                    continue
                if f" {tt_key}:0 " not in en_text:
                    missing.append(f"{tt_key} (en localisation)")
                if f" {tt_key}:0 " not in zh_text:
                    missing.append(f"{tt_key} (zh localisation)")
        self.assertEqual(missing, [])

    def test_stable_version_metadata_contract(self) -> None:
        descriptor = validator.read_utf8(validator.ROOT / "descriptor.mod")
        version = validator.descriptor_value(descriptor, "version")
        self.assertIsNotNone(version)
        errors: list[str] = []
        validator.check_version_metadata(version, errors)
        self.assertEqual(errors, [])

        stale_errors: list[str] = []
        validator.check_version_metadata("9.9", stale_errors)
        self.assertTrue(any("v9.9" in error for error in stale_errors))

    def test_explicit_vanilla_path_is_machine_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "common").mkdir()
            self.assertEqual(hoi4_paths.resolve_vanilla_path(root), root)

    def test_tagged_release_payload_is_frozen(self) -> None:
        """The stable-version tag pins the release inputs of the current
        descriptor version (so an already-released version cannot drift),
        while development/test versions are exempt automatically."""
        descriptor = validator.read_utf8(
            build_release.ROOT / "descriptor.mod"
        )
        version = validator.descriptor_value(descriptor, "version")
        self.assertIsNotNone(version)
        paths = build_release.release_payload_paths(version)
        self.assertIn(build_release.ROOT / "descriptor.mod", paths)
        self.assertIn(
            build_release.ROOT
            / "docs"
            / "baseline"
            / f"README_v{version}_正式版.md",
            paths,
        )
        build_release.verify_tagged_release_payload(version)

    def test_release_staging_normalizes_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            text_path = root / "localisation.yml"
            image_path = root / "thumbnail.png"
            text_path.write_bytes(b"\xef\xbb\xbfline1\r\nline2\rline3\n")
            image_bytes = b"\x89PNG\r\n\x1a\n\r\n"
            image_path.write_bytes(image_bytes)

            build_release.normalize_release_tree(root)

            self.assertEqual(
                text_path.read_bytes(), b"\xef\xbb\xbfline1\nline2\nline3\n"
            )
            self.assertEqual(image_path.read_bytes(), image_bytes)

    def test_test_build_package_routing(self) -> None:
        self.assertTrue(build_release.is_test_version("2.2-test1"))
        self.assertFalse(build_release.is_test_version("2.2"))
        docs = build_release.package_docs("2.2-test1")
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(path.parent.name == "testing" for path in docs))

    def test_versioned_release_helpers(self) -> None:
        self.assertEqual(
            publish_github_release.ascii_asset_name("2.6"),
            "OCS_one_click_sandbox_start_v2.6.zip",
        )
        self.assertEqual(
            publish_workshop.changenote_file("2.6").name,
            "v2.6工坊更新摘要.txt",
        )
        self.assertEqual(
            publish_workshop.vdf_escape('a\\b"c\r\nd'),
            'a\\\\b\\"c\nd',
        )


if __name__ == "__main__":
    unittest.main()
