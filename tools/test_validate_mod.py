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
        self.assertEqual(evolved_equipment_text.count('name = "装甲支援车"'), 4)
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

    def test_test_build_package_routing(self) -> None:
        self.assertTrue(build_release.is_test_version("2.2-test1"))
        self.assertFalse(build_release.is_test_version("2.2"))
        docs = build_release.package_docs("2.2-test1")
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(path.parent.name == "testing" for path in docs))


if __name__ == "__main__":
    unittest.main()
