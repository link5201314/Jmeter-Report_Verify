import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from core import (
    BASE_DIR,
    OUTPUT_DIR,
    VERIFY_CONFIG_FOLDER,
    extract_table_data,
    read_verify_config,
    verify_results_detail,
    list_report_folders,
    list_verify_configs,
)


# ---------------------------------------------------------------------------
# list_report_folders
# ---------------------------------------------------------------------------

class TestListReportFolders:
    def test_finds_folders_with_index(self, tmp_path: Path) -> None:
        sub = tmp_path / "report_A"
        sub.mkdir()
        (sub / "index.html").write_text("<html>")
        (tmp_path / "no_html").mkdir()
        result = list_report_folders(str(tmp_path))
        assert result == ["report_A"]

    def test_nonexistent_dir(self) -> None:
        assert list_report_folders("/nonexistent/path") == []


# ---------------------------------------------------------------------------
# list_verify_configs
# ---------------------------------------------------------------------------

class TestListVerifyConfigs:
    def test_lists_csv_files(self, tmp_path: Path) -> None:
        (tmp_path / "aaa.csv").write_text("x")
        (tmp_path / "bbb.csv").write_text("x")
        (tmp_path / "ccc.txt").write_text("x")
        result = list_verify_configs(str(tmp_path))
        assert result == ["aaa", "bbb"]

    def test_real_config_dir(self) -> None:
        configs = list_verify_configs()
        assert len(configs) >= 1
        assert "core_PT_1" in configs


# ---------------------------------------------------------------------------
# read_verify_config
# ---------------------------------------------------------------------------

class TestReadVerifyConfig:
    def test_reads_real_csv(self) -> None:
        csv_path = str(BASE_DIR / VERIFY_CONFIG_FOLDER / "core_PT_1.csv")
        df = read_verify_config(csv_path)
        assert len(df) == 25
        assert df["expected_pass_samples"].dtype in ("int64", "int32")
        assert df.loc[0, "script_name"] == "CAC_01"

    def test_commas_removed(self) -> None:
        csv_path = str(BASE_DIR / VERIFY_CONFIG_FOLDER / "core_PT_1.csv")
        df = read_verify_config(csv_path)
        row = df[df["script_name"] == "CAR_01"].iloc[0]
        assert int(row["expected_pass_samples"]) == 15497


# ---------------------------------------------------------------------------
# verify_results_detail
# ---------------------------------------------------------------------------

def _make_report(rows: list[tuple[str, int, int, int]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["Label", "#Samples", "FAIL", "90th pct"])
    df["pass_cnt"] = df["#Samples"] - df["FAIL"]
    return df


def _make_config(
    script_name: str,
    name_rule: str,
    pct_90th: int = 5000,
    expected_pass: int = 100,
) -> pd.DataFrame:
    return pd.DataFrame([{
        "script_name": script_name,
        "name_rule": name_rule,
        "90th_pct": pct_90th,
        "expected_pass_samples": expected_pass,
    }])


class TestVerifyResultsDetail:
    def test_pass(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 200, 0, 100),
            ("DRV_01-2_0_POST", 300, 0, 200),
        ])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=300)
        detail = verify_results_detail(report, config)
        assert len(detail) == 1
        assert detail[0]["script_name"] == "DRV_01"
        assert detail[0]["actual_pct_90th"] == "PASS"
        assert detail[0]["actual_pass"] == 300
        assert detail[0]["check_result"] == "PASS"

    def test_fail_p90(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 200, 0, 6000),
            ("DRV_01-2_0_POST", 300, 0, 4000),
        ])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=300)
        detail = verify_results_detail(report, config)
        assert len(detail) == 1
        assert detail[0]["actual_pct_90th"] == 6000
        assert "P90" in str(detail[0]["check_result"]) or "90th" in str(detail[0]["check_result"])

    def test_fail_pass_cnt(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 50, 0, 100),
        ])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=300)
        detail = verify_results_detail(report, config)
        assert len(detail) == 1
        assert detail[0]["actual_pass"] == 50
        assert "pass_cnt" in str(detail[0]["check_result"])

    def test_no_match(self) -> None:
        report = _make_report([("XXX_01", 100, 0, 100)])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=100)
        detail = verify_results_detail(report, config)
        assert len(detail) == 1
        assert "No matching labels" in str(detail[0]["check_result"])
        assert detail[0]["actual_pass"] == "-"
        assert detail[0]["actual_pct_90th"] == "N/A"

    def test_name_rule_error(self) -> None:
        report = _make_report([
            ("CAR_01-【Final】_GET", 500, 0, 100),
            ("CAR_01-【Final】_POST", 600, 0, 200),
        ])
        config = _make_config("CAR_01", "final", pct_90th=5000, expected_pass=500)
        detail = verify_results_detail(report, config)
        assert len(detail) == 1
        assert "Multiple 【Final】" in str(detail[0]["check_result"])
        assert detail[0]["actual_pass"] == "-"

    def test_all_fields_present(self) -> None:
        report = _make_report([("A_01-1_0_GET", 100, 0, 200)])
        config = _make_config("A_01", "seq")
        detail = verify_results_detail(report, config)
        required_keys = {"script_name", "name_rule", "expected_pct_90th",
                         "actual_pct_90th", "expected_pass", "actual_pass",
                         "check_result"}
        assert required_keys.issubset(detail[0].keys())


# ---------------------------------------------------------------------------
# extract_table_data — signature / param tests (no real browser)
# ---------------------------------------------------------------------------

class TestExtractTableDataSignature:
    @patch("core.sync_playwright")
    def test_default_headless_true(self, mock_pw: MagicMock) -> None:
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_pw.return_value.__enter__ = MagicMock(return_value=MagicMock(
            chromium=MagicMock(launch=MagicMock(return_value=mock_browser)),
        ))
        mock_pw.return_value.__exit__ = MagicMock(return_value=False)
        mock_browser.new_page.return_value = mock_page

        # Mock the locator chain
        mock_page.locator.return_value.nth.return_value.locator.return_value.all_inner_texts.return_value = [
            "#Samples", "Label", "90th pct", "FAIL"
        ]
        mock_page.locator.return_value.nth.return_value.locator.return_value.count.return_value = 0

        try:
            extract_table_data("file:///fake/index.html", headless=True)
        except Exception:
            pass

        # Verify launch was called with headless=True
        mock_pw.return_value.__enter__.return_value.chromium.launch.assert_called_once()
        call_kwargs = mock_pw.return_value.__enter__.return_value.chromium.launch.call_args
        assert call_kwargs[1].get("headless") is True or call_kwargs[0][0] is True
