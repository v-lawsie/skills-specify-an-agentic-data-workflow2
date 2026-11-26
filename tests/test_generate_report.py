import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from src.generate_report import (
    EXCEPTION_FIELDS,
    REPORT_FIELDS,
    ReportError,
    generate_reports,
    write_report,
)


ROOT = Path(__file__).resolve().parents[1]


class GenerateReportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data = self.root / "data"
        self.data.mkdir()
        shutil.copy(ROOT / "data/customer-accounts.csv", self.data)
        shutil.copy(ROOT / "data/sales-transactions.csv", self.data)
        self.account_path = self.data / "customer-accounts.csv"
        self.transaction_path = self.data / "sales-transactions.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def read_rows(self, path):
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_generates_expected_customers_exceptions_and_totals(self):
        report, exceptions = generate_reports(self.account_path, self.transaction_path)
        by_id = {row["account_id"]: row for row in report}
        self.assertEqual(
            (by_id["A100"]["transaction_count"], by_id["A100"]["net_sales_cents"]),
            ("3", "18000"),
        )
        self.assertEqual(
            (by_id["A200"]["transaction_count"], by_id["A200"]["net_sales_cents"]),
            ("2", "4000"),
        )
        self.assertEqual(
            (by_id["A400"]["transaction_count"], by_id["A400"]["net_sales_cents"]),
            ("0", "0"),
        )
        self.assertEqual(
            [row["transaction_id"] for row in exceptions], ["T009", "T010"]
        )
        known = sum(int(row["net_sales_cents"]) for row in report)
        unmatched = sum(int(row["amount_cents"]) for row in exceptions)
        self.assertEqual((known, unmatched, known + unmatched), (22800, 2750, 25550))

    def test_generation_is_repeatable_from_missing_reports_without_source_changes(self):
        source_before = {
            path: path.read_bytes()
            for path in (self.account_path, self.transaction_path)
        }
        report, exceptions = generate_reports(self.account_path, self.transaction_path)
        output_dir = self.root / "reports"
        output_dir.mkdir()
        write_report(output_dir / "customer-account-report.csv", REPORT_FIELDS, report)
        write_report(output_dir / "exceptions.csv", EXCEPTION_FIELDS, exceptions)
        first_outputs = {
            path.name: path.read_bytes() for path in output_dir.iterdir()
        }
        report, exceptions = generate_reports(self.account_path, self.transaction_path)
        write_report(output_dir / "customer-account-report.csv", REPORT_FIELDS, report)
        write_report(output_dir / "exceptions.csv", EXCEPTION_FIELDS, exceptions)
        self.assertEqual(
            first_outputs, {path.name: path.read_bytes() for path in output_dir.iterdir()}
        )
        self.assertEqual(
            source_before,
            {path: path.read_bytes() for path in source_before},
        )

    def test_invalid_fixtures_fail_before_creating_reports(self):
        cases = (
            ("duplicate-accounts.csv", self.account_path, "customer-accounts.csv"),
            ("invalid-amount.csv", self.transaction_path, "sales-transactions.csv"),
            ("conflicting-transactions.csv", self.transaction_path, "sales-transactions.csv"),
        )
        for fixture, target, original_name in cases:
            with self.subTest(fixture=fixture):
                shutil.copy(ROOT / "data" / original_name, target)
                shutil.copy(ROOT / "verification/fixtures" / fixture, target)
                with self.assertRaises(ReportError):
                    generate_reports(self.account_path, self.transaction_path)
                self.assertFalse((self.root / "reports").exists())
                shutil.copy(ROOT / "data" / original_name, target)


if __name__ == "__main__":
    unittest.main()
