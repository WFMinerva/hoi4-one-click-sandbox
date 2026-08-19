#!/usr/bin/env python3
"""check_logs 的单元测试：白名单过滤、新错误告警、标记提取、铁律与豁免、版本降级。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import check_logs


def _write_logs(root: Path, files: dict[str, str]) -> Path:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (logs / name).write_text(content, encoding="utf-8")
    return logs


class WhitelistFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = check_logs.load_whitelist()

    def test_known_noise_lines_are_filtered(self) -> None:
        lines = [
            "[13:58:17][1936.01.01.12][gamelobby.cpp:1779]: Exception in: remotefile.cpp ... Failed allocate data buffer.",
            "[13:58:17][1936.01.01.12][gamelobby.cpp:1779]: another gamelobby noise",
            "[10:00:00][game.cpp:1]: Conflict Risk 123",
            "[10:00:00][mod.cpp:2]: ugc_1326075315.mod Invalid supported_version = \"1.*.*\"",
        ]
        result = check_logs.filter_log(lines, self.entries)
        self.assertEqual(result["total_lines"], 4)
        self.assertEqual(result["whitelisted"], 4)
        self.assertEqual(result["unmatched"], {})

    def test_own_mod_version_error_is_not_swallowed(self) -> None:
        """白名单按 ugc id 收窄：本 MOD 自身的 Invalid supported_version 必须仍被报出。"""
        lines = [
            "[10:00:00][mod.cpp:2]: Invalid supported_version = \"1.*.*\" in OCS_one_click_sandbox_start_v2_0.mod",
        ]
        result = check_logs.filter_log(lines, self.entries)
        self.assertEqual(result["whitelisted"], 0)
        self.assertEqual(len(result["unmatched"]), 1)

    def test_unknown_error_is_flagged_and_signatured(self) -> None:
        lines = [
            "[13:57:56][no_game_date][effect.cpp:445]: Invalid effect 'x' in events/PRC_OCS_choice_events_naval.txt line : 54",
            "[13:58:01][no_game_date][effect.cpp:445]: Invalid effect 'x' in events/PRC_OCS_choice_events_naval.txt line : 78",
        ]
        result = check_logs.filter_log(lines, self.entries)
        self.assertEqual(result["whitelisted"], 0)
        self.assertEqual(len(result["unmatched"]), 1)
        (sig, bucket), = result["unmatched"].items()
        self.assertIn("Invalid effect 'x'", sig)
        self.assertEqual(bucket["count"], 2)

    def test_game_log_error_like_mode_ignores_operational_lines(self) -> None:
        lines = [
            "4469 defines loaded",
            "Executing History from -1.1.1.1 to 2.1.1.1",
            "Loaded 13414 provinces.",
            "Resetting game",
            "Conflict Risk 123",
            "[10:00:00][mod.cpp:1]: Failed to load something important",
        ]
        result = check_logs.filter_log(lines, self.entries, mode="error_like")
        self.assertEqual(result["whitelisted"], 1)  # Conflict Risk
        self.assertEqual(len(result["unmatched"]), 1)  # Failed ... 才计
        self.assertIn("Failed to load", next(iter(result["unmatched"])))


class MarkerTest(unittest.TestCase):
    def test_redact_identity_masks_machine_paths(self) -> None:
        """归档防泄漏：正反斜杠两种路径形态都要脱敏（2026-08-20 首轮归档实测补）。"""
        env = {"USERNAME": "Tester", "USERPROFILE": r"C:\Users\Tester", "COMPUTERNAME": "TESTPC"}
        with mock.patch.dict(os.environ, env, clear=False):
            out = check_logs._redact_identity(
                r"C:\Users\Tester\Documents\game.log C:/Users/Tester/Documents/e.log TESTPC \tester-pc")
        self.assertNotIn("Tester", out)
        self.assertNotIn("TESTPC", out)
        self.assertIn("C:\\Users\\<REDACTED>", out)  # 身份被抹、路径骨架保留（与归档制度口径一致）
        self.assertIn("C:/Users/<REDACTED>", out)   # 正斜杠变体同样脱敏
        self.assertIn("<REDACTED>", out)

    def test_markers_extracted_across_logs(self) -> None:
        lines_by_log = {
            "game.log": ["[10:00:00][game.cpp:1]: OCS_TEST PASS init_flag",
                          "[10:00:00][game.cpp:1]: OCS_TEST FAIL mio_funds"],
            "error.log": [],
            "text.log": [],
            "setup.log": [],
        }
        markers = check_logs.collect_markers(lines_by_log)
        self.assertEqual(markers["total"], 2)
        self.assertEqual(markers["distinct_cases"], 2)
        self.assertEqual([f["case"] for f in markers["failed"]], ["mio_funds"])

    def test_verdict_zero_markers_invalid_without_exemption(self) -> None:
        markers = {"total": 0, "failed": [], "cases": []}
        verdict, reasons = check_logs.build_verdict(markers, None, exempt=False)
        self.assertEqual(verdict, "INVALID")
        verdict2, _ = check_logs.build_verdict(markers, None, exempt=True)
        self.assertEqual(verdict2, "PASS")

    def test_verdict_case_list_mismatch_fails(self) -> None:
        markers = {"total": 1, "failed": [], "cases": [{"case": "init_flag"}]}
        verdict, _ = check_logs.build_verdict(markers, ["init_flag", "mio_funds"], exempt=False)
        self.assertEqual(verdict, "FAIL")

    def test_verdict_all_pass_with_case_list(self) -> None:
        markers = {"total": 2, "failed": [],
                   "cases": [{"case": "init_flag"}, {"case": "mio_funds"}]}
        verdict, reasons = check_logs.build_verdict(markers, ["init_flag", "mio_funds"], exempt=False)
        self.assertEqual(verdict, "PASS")
        self.assertTrue(any("用例清单数" in r for r in reasons))

    def test_verdict_duplicate_markers_fail_count_rule(self) -> None:
        """同一轮跑两遍套件（重复标记）必须 FAIL：标记数铁律按数量而非去重集合。"""
        markers = {"total": 4, "failed": [],
                   "cases": [{"case": "init_flag"}, {"case": "mio_funds"},
                             {"case": "init_flag"}, {"case": "mio_funds"}]}
        verdict, reasons = check_logs.build_verdict(markers, ["init_flag", "mio_funds"], exempt=False)
        self.assertEqual(verdict, "FAIL")
        self.assertTrue(any("≠用例清单数" in r for r in reasons))


class CaseFileTest(unittest.TestCase):
    def test_case_file_parsing_skips_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.txt"
            path.write_text("# 注释\ninit_flag\nmio_funds\n", encoding="utf-8")
            cases = check_logs.read_case_file(path)
        self.assertEqual(cases, ["init_flag", "mio_funds"])

    def test_case_file_none_returns_none(self) -> None:
        self.assertIsNone(check_logs.read_case_file(None))

    def test_case_source_parses_marker_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "selftest.txt"
            path.write_text(
                'if = { limit = { has_country_flag = x }\n'
                '  log = "OCS_TEST PASS init_flag"\n'
                'else = { log = "OCS_TEST FAIL init_flag" }\n'
                'log = "OCS_TEST FAIL mio_size_max"\n',
                encoding="utf-8")
            cases = check_logs.read_case_source(path)
        self.assertEqual(cases, ["init_flag", "mio_size_max"])

    def test_case_source_empty_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.txt"
            path.write_text("nothing here\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                check_logs.read_case_source(path)


class VersionAndSetupTest(unittest.TestCase):
    def test_version_binding_degrades_to_manual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            version = check_logs.read_game_version(logs)
        self.assertTrue(version["manual_fallback"])
        self.assertEqual(version["source"], "manual")

    def test_version_binding_reads_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            (logs / "code_revisions.log").write_text(
                "game_hash_long: a729d47bd1c5\n game_hash_short: a729d47bd\ngame_timestamp: 2026-06-29 15:17:03 +0200\n",
                encoding="utf-8")
            version = check_logs.read_game_version(logs)
        self.assertFalse(version["manual_fallback"])
        self.assertEqual(version["game_hash_short"], "a729d47bd")


class EndToEndTest(unittest.TestCase):
    def test_full_run_verdict_and_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = _write_logs(root, {
                "error.log": "[13:58:17][1936.01.01.12][gamelobby.cpp:1779]: Exception in: remotefile.cpp Failed allocate data buffer.\n",
                "game.log": "[10:00:00][game.cpp:1]: Conflict Risk\n[10:00:00][game.cpp:1]: OCS_TEST PASS init_flag\n",
                "text.log": "",
                "setup.log": "loading PRC_OCS events 1\nloading PRC_OCS decisions 2\n",
                "code_revisions.log": "game_hash_short: a729d47bd\n",
            })
            case_file = root / "cases.txt"
            case_file.write_text("init_flag\n", encoding="utf-8")
            out = root / "result.json"
            rc = check_logs.main(["--logs", str(logs), "--round", "unit-test",
                                  "--case-file", str(case_file), "--out", str(out)])
            self.assertEqual(rc, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["verdict"], "PASS")
            self.assertTrue(data["whitelist"]["clean"])
            self.assertEqual(data["markers"]["total"], 1)
            self.assertEqual(data["setup_log"]["prc_ocs_lines"], 2)

    def test_unknown_error_lowers_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = _write_logs(root, {
                "error.log": "[13:57:56][no_game_date][effect.cpp:445]: Invalid effect 'enable_equipment_modules' in events/x.txt line : 54\n",
                "game.log": "[10:00:00][game.cpp:1]: OCS_TEST PASS init_flag\n",
                "text.log": "",
                "setup.log": "loading PRC_OCS events 1\n",
            })
            out = root / "result.json"
            rc = check_logs.main(["--logs", str(logs), "--round", "unit-test", "--out", str(out)])
            self.assertNotEqual(rc, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["verdict"], "FAIL")
            self.assertFalse(data["whitelist"]["clean"])
            self.assertTrue(any("enable_equipment_modules" in s["signature"]
                                for s in data["whitelist"]["new_signatures"]))

    def test_zero_markers_without_exemption_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = _write_logs(root, {
                "error.log": "",
                "game.log": "Conflict Risk\n",
                "text.log": "",
                "setup.log": "loading PRC_OCS events 1\n",
            })
            out = root / "result.json"
            rc = check_logs.main(["--logs", str(logs), "--round", "unit-test", "--out", str(out)])
            self.assertNotEqual(rc, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["verdict"], "INVALID")


if __name__ == "__main__":
    unittest.main()
