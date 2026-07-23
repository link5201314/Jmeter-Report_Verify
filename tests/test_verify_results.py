import pandas as pd

from core import verify_results, _select_pass_row, _extract_step_tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(rows: list[tuple[str, int, int, int]]) -> pd.DataFrame:
    """Build a report DataFrame from (label, samples, fail, pct_90th) tuples."""
    df = pd.DataFrame(rows, columns=["Label", "#Samples", "FAIL", "90th pct"])
    df["pass_cnt"] = df["#Samples"] - df["FAIL"]
    return df


def _make_config(
    script_name: str,
    name_rule: str,
    pct_90th: int = 5000,
    expected_pass: int = 100,
) -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "script_name": script_name,
            "name_rule": name_rule,
            "90th_pct": pct_90th,
            "expected_pass_samples": expected_pass,
        }]
    )


# ---------------------------------------------------------------------------
# _extract_step_tuple
# ---------------------------------------------------------------------------

class TestExtractStepTuple:
    def test_simple_step(self) -> None:
        assert _extract_step_tuple("CAR_01-1_2_GET", "CAR_01") == (1, 2)

    def test_no_step(self) -> None:
        assert _extract_step_tuple("CAR_01_something", "CAR_01") == (-1,)


# ---------------------------------------------------------------------------
# _select_pass_row — seq
# ---------------------------------------------------------------------------

class TestSelectPassRowSeq:
    def test_picks_highest_step(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 200, 0, 100),
            ("DRV_01-2_0_POST", 300, 0, 200),
            ("DRV_01-3_0_GET", 150, 0, 150),
        ])
        row, err = _select_pass_row(report, "DRV_01", "seq")
        assert err is None
        assert row is not None
        assert row["Label"] == "DRV_01-3_0_GET"
        assert row["pass_cnt"] == 150


# ---------------------------------------------------------------------------
# _select_pass_row — final
# ---------------------------------------------------------------------------

class TestSelectPassRowFinal:
    def test_picks_final_label(self) -> None:
        report = _make_report([
            ("CAR_01-1_0_GET", 200, 0, 100),
            ("CAR_01-2_0_POST", 300, 0, 200),
            ("CAR_01-<Final>_GET", 500, 0, 300),
        ])
        row, err = _select_pass_row(report, "CAR_01", "final")
        assert err is None
        assert row is not None
        assert "<Final>" in row["Label"]
        assert row["pass_cnt"] == 500

    def test_no_final_label(self) -> None:
        report = _make_report([
            ("CAR_01-1_0_GET", 200, 0, 100),
        ])
        row, err = _select_pass_row(report, "CAR_01", "final")
        assert row is None
        assert "No <Final> label" in err  # type: ignore[union-attr]

    def test_multiple_final_labels(self) -> None:
        report = _make_report([
            ("CAR_01-<Final>_GET", 500, 0, 100),
            ("CAR_01-<Final>_POST", 600, 0, 200),
        ])
        row, err = _select_pass_row(report, "CAR_01", "final")
        assert row is None
        assert "Multiple <Final> labels" in err  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# _select_pass_row — single
# ---------------------------------------------------------------------------

class TestSelectPassRowSingle:
    def test_picks_first_match(self) -> None:
        report = _make_report([
            ("FES_01", 737, 0, 500),
        ])
        row, err = _select_pass_row(report, "FES_01", "single")
        assert err is None
        assert row is not None
        assert row["Label"] == "FES_01"
        assert row["pass_cnt"] == 737

    def test_no_match(self) -> None:
        report = _make_report([])
        row, err = _select_pass_row(report, "FES_01", "single")
        assert row is None
        assert "No matching labels" in err  # type: ignore[union-attr]

    def test_multiple_matches(self) -> None:
        report = _make_report([
            ("FES_01", 737, 0, 500),
            ("FES_01_extra", 200, 0, 300),
        ])
        row, err = _select_pass_row(report, "FES_01", "single")
        assert row is None
        assert "Multiple labels" in err  # type: ignore[union-attr]
        assert "expected exactly one" in err  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# verify_results — integration
# ---------------------------------------------------------------------------

class TestVerifyResultsSeq:
    def test_pass(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 200, 0, 100),
            ("DRV_01-2_0_POST", 300, 0, 200),
        ])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=300)
        assert verify_results(report, config) == []

    def test_fail_pass_cnt(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 200, 0, 100),
            ("DRV_01-2_0_POST", 50, 0, 200),
        ])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=300)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "pass_cnt" in failures[0]

    def test_fail_p90(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 200, 0, 6000),
            ("DRV_01-2_0_POST", 300, 0, 200),
        ])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=300)
        failures = verify_results(report, config)
        assert any("90th pct" in f for f in failures)

    def test_no_match(self) -> None:
        report = _make_report([
            ("XXX_01-1_0_GET", 200, 0, 100),
        ])
        config = _make_config("DRV_01", "seq", pct_90th=5000, expected_pass=300)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "No matching labels" in failures[0]


class TestVerifyResultsFinal:
    def test_pass(self) -> None:
        report = _make_report([
            ("CAR_01-1_0_GET", 200, 0, 100),
            ("CAR_01-<Final>_GET", 500, 0, 300),
        ])
        config = _make_config("CAR_01", "final", pct_90th=5000, expected_pass=500)
        assert verify_results(report, config) == []

    def test_fail_pass_cnt(self) -> None:
        report = _make_report([
            ("CAR_01-1_0_GET", 200, 0, 100),
            ("CAR_01-<Final>_GET", 100, 0, 300),
        ])
        config = _make_config("CAR_01", "final", pct_90th=5000, expected_pass=500)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "pass_cnt" in failures[0]

    def test_no_final_label(self) -> None:
        report = _make_report([
            ("CAR_01-1_0_GET", 200, 0, 100),
        ])
        config = _make_config("CAR_01", "final", pct_90th=5000, expected_pass=500)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "No <Final> label" in failures[0]

    def test_multiple_final_labels(self) -> None:
        report = _make_report([
            ("CAR_01-<Final>_GET", 500, 0, 100),
            ("CAR_01-<Final>_POST", 600, 0, 200),
        ])
        config = _make_config("CAR_01", "final", pct_90th=5000, expected_pass=500)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "Multiple <Final> labels" in failures[0]


class TestVerifyResultsSingle:
    def test_pass(self) -> None:
        report = _make_report([
            ("FES_01", 737, 0, 500),
        ])
        config = _make_config("FES_01", "single", pct_90th=5000, expected_pass=737)
        assert verify_results(report, config) == []

    def test_fail_pass_cnt(self) -> None:
        report = _make_report([
            ("FES_01", 100, 0, 500),
        ])
        config = _make_config("FES_01", "single", pct_90th=5000, expected_pass=737)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "pass_cnt" in failures[0]

    def test_no_match(self) -> None:
        report = _make_report([
            ("XXX_01", 100, 0, 500),
        ])
        config = _make_config("FES_01", "single", pct_90th=5000, expected_pass=737)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "No matching labels" in failures[0]

    def test_multiple_matches(self) -> None:
        report = _make_report([
            ("FES_01", 737, 0, 500),
            ("FES_01_extra", 200, 0, 300),
        ])
        config = _make_config("FES_01", "single", pct_90th=5000, expected_pass=737)
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "Multiple labels" in failures[0]
        assert "expected exactly one" in failures[0]


# ---------------------------------------------------------------------------
# Multiple scripts in one config
# ---------------------------------------------------------------------------

class TestVerifyResultsMixed:
    def test_mixed_name_rules(self) -> None:
        report = _make_report([
            ("DRV_01-1_0_GET", 200, 0, 100),
            ("DRV_01-2_0_POST", 300, 0, 200),
            ("FES_01", 500, 0, 400),
        ])
        config = pd.DataFrame([
            {"script_name": "DRV_01", "name_rule": "seq", "90th_pct": 5000, "expected_pass_samples": 300},
            {"script_name": "FES_01", "name_rule": "single", "90th_pct": 5000, "expected_pass_samples": 700},
        ])
        failures = verify_results(report, config)
        assert len(failures) == 1
        assert "FES_01" in failures[0]
