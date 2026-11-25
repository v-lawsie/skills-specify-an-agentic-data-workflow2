import csv
import re
import sys
from datetime import date
from pathlib import Path

ACCOUNT_FIELDS = ["account_id", "account_type", "region"]
TRANSACTION_FIELDS = [
    "transaction_id", "account_id", "transaction_date", "amount_cents"
]
REPORT_FIELDS = ACCOUNT_FIELDS + ["transaction_count", "net_sales_cents"]
EXCEPTION_FIELDS = TRANSACTION_FIELDS + ["reason"]
INTEGER = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")


class ReportError(ValueError):
    pass


def read_csv(path, expected_fields):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, strict=True)
        if reader.fieldnames != expected_fields:
            raise ReportError(
                f"{path}: expected header {','.join(expected_fields)}"
            )

        rows = []
        for line_number, row in enumerate(reader, 2):
            if set(row) != set(expected_fields):
                raise ReportError(f"{path}:{line_number}: wrong field count")
            if any(
                not isinstance(value, str) or not value or value != value.strip()
                for value in row.values()
            ):
                raise ReportError(
                    f"{path}:{line_number}: fields must be nonempty and unpadded"
                )
            rows.append(row)
    return rows


def load_data(root):
    accounts = {}
    for row in read_csv(root / "data/customer-accounts.csv", ACCOUNT_FIELDS):
        account_id = row["account_id"]
        if account_id in accounts:
            raise ReportError(f"Duplicate account_id: {account_id}")
        accounts[account_id] = row

    transactions = {}
    for row in read_csv(
        root / "data/sales-transactions.csv", TRANSACTION_FIELDS
    ):
        transaction_id = row["transaction_id"]
        amount = row["amount_cents"]
        if not INTEGER.fullmatch(amount):
            raise ReportError(
                f"Transaction {transaction_id}: invalid amount {amount}"
            )
        try:
            parsed_date = date.fromisoformat(row["transaction_date"])
        except ValueError as error:
            raise ReportError(
                f"Transaction {transaction_id}: invalid date "
                f"{row['transaction_date']}"
            ) from error
        if parsed_date.isoformat() != row["transaction_date"]:
            raise ReportError(
                f"Transaction {transaction_id}: use YYYY-MM-DD"
            )

        previous = transactions.get(transaction_id)
        if previous is not None and previous != row:
            raise ReportError(f"Conflicting transaction_id: {transaction_id}")
        transactions[transaction_id] = row

    return accounts, transactions


def create_reports(root):
    accounts, transactions = load_data(root)
    totals = {
        account_id: {"transaction_count": 0, "net_sales_cents": 0}
        for account_id in accounts
    }
    exceptions = []

    for transaction_id, row in sorted(transactions.items()):
        if not "2026-09-01" <= row["transaction_date"] <= "2026-09-30":
            continue
        account_id = row["account_id"]
        amount = int(row["amount_cents"])
        if account_id in accounts:
            totals[account_id]["transaction_count"] += 1
            totals[account_id]["net_sales_cents"] += amount
        else:
            exceptions.append({**row, "reason": "unknown_account"})

    report = [
        {
            **accounts[account_id],
            **{
                field: str(value)
                for field, value in totals[account_id].items()
            },
        }
        for account_id in sorted(accounts)
    ]

    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for path, fields, rows in (
        (reports_dir / "customer-account-report.csv", REPORT_FIELDS, report),
        (reports_dir / "exceptions.csv", EXCEPTION_FIELDS, exceptions),
    ):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def main():
    try:
        create_reports(Path.cwd())
    except (ReportError, OSError, UnicodeError, csv.Error) as error:
        print(f"Report generation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
