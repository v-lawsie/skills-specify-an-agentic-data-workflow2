import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "src/generate_report.py"
REPORTS = [
    "reports/customer-account-report.csv",
    "reports/exceptions.csv",
]


class GenerateReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / "data", self.root / "data")

    def run_generator(self):
        return subprocess.run(
            [sys.executable, str(GENERATOR)],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def test_creates_expected_reports_from_clean_directory(self):
        before = {
            path.name: path.read_bytes()
            for path in (self.root / "data").iterdir()
        }
        result = self.run_generator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.root / REPORTS[0]).read_text(),
            "account_id,account_type,region,transaction_count,net_sales_cents\n"
            "A100,Retail,North,3,18000\n"
            "A200,Distributor,West,2,4000\n"
            "A300,Retail,East,2,2000\n"
            "A400,Retail,South,0,0\n"
            "A500,Wholesale,North,1,-1200\n",
        )
        self.assertEqual(
            (self.root / REPORTS[1]).read_text(),
            "transaction_id,account_id,transaction_date,amount_cents,reason\n"
            "T009,X900,2026-09-30,3000,unknown_account\n"
            "T010,X900,2026-09-14,-250,unknown_account\n",
        )
        self.assertEqual(
            {
                path.name: path.read_bytes()
                for path in (self.root / "data").iterdir()
            },
            before,
        )

    def test_generation_is_repeatable(self):
        self.assertEqual(self.run_generator().returncode, 0)
        first_run = {name: (self.root / name).read_bytes() for name in REPORTS}

        result = self.run_generator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            {name: (self.root / name).read_bytes() for name in REPORTS},
            first_run,
        )

    def test_invalid_fixtures_fail_with_explanation_and_no_reports(self):
        cases = [
            ("invalid-amount.csv", "sales-transactions.csv"),
            ("conflicting-transactions.csv", "sales-transactions.csv"),
            ("duplicate-accounts.csv", "customer-accounts.csv"),
        ]
        for fixture_name, target_name in cases:
            with self.subTest(fixture=fixture_name):
                fixture_root = self.root / fixture_name
                shutil.copytree(self.root / "data", fixture_root / "data")
                shutil.copyfile(
                    ROOT / "verification/fixtures" / fixture_name,
                    fixture_root / "data" / target_name,
                )
                result = subprocess.run(
                    [sys.executable, str(GENERATOR)],
                    cwd=fixture_root,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(result.stderr.strip())
                self.assertFalse((fixture_root / REPORTS[0]).exists())
                self.assertFalse((fixture_root / REPORTS[1]).exists())

    def test_invalid_out_of_period_transaction_is_rejected(self):
        transactions = self.root / "data/sales-transactions.csv"
        content = transactions.read_text()
        transactions.write_text(content.replace("2026-08-31,60000", "2026-08-31,12.50"))

        result = self.run_generator()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid amount", result.stderr)
        self.assertFalse((self.root / REPORTS[0]).exists())
        self.assertFalse((self.root / REPORTS[1]).exists())


if __name__ == "__main__":
    unittest.main()
