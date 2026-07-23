import os
from core import (
    JMETER_REPORT_FOLDER,
    VERIFY_CONFIG_FOLDER,
    OUTPUT_DIR,
    extract_table_data,
    read_verify_config,
    verify_results,
)

if __name__ == "__main__":
    out = OUTPUT_DIR
    out.mkdir(exist_ok=True)
    current_dir: str = os.path.dirname(os.path.abspath(__file__))

    html_file: str = os.path.join(
        current_dir, JMETER_REPORT_FOLDER,
        "core_PT_1__report-core_PT_1-2026-07-21_154922", "index.html"
    )
    df_report = extract_table_data(html_file, headless=False, output_dir=out)

    config_file = os.path.join(current_dir, VERIFY_CONFIG_FOLDER, "core_PT_1.csv")
    df_config = read_verify_config(config_file)

    failures = verify_results(df_report, df_config)
    if failures:
        print(f"Verification FAILED ({len(failures)} issues):")
        for f in failures:
            print(f"  - {f}")
    else:
        print("Verification PASSED")
