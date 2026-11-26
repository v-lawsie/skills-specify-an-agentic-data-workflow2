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


def read_csv(path, fields):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, strict=True)
        if reader.fieldnames != fields:
            raise ReportError(f"{path}: expected header {','.join(fields)}")
        rows = []
        for line_number, row in enumerate(reader, 2):
            if set(row) != set(fields):
                raise ReportError(f"{path}:{line_number}: wrong field count")
            if any(not isinstance(value, str) or not value or value != value.strip()
                   for value in row.values()):
                raise ReportError(
                    f"{path}:{line_number}: fields must be nonempty and unpadded"
                )
            rows.append(row)
    return rows


def load_accounts(path):
    accounts = {}
    for row in read_csv(path, ACCOUNT_FIELDS):
        account_id = row["account_id"]
        if account_id in accounts:
            raise ReportError(f"Duplicate account_id: {account_id}")
        accounts[account_id] = row
    return accounts


def load_transactions(path):
    transactions = {}
    for row in read_csv(path, TRANSACTION_FIELDS):
        transaction_id = row["transaction_id"]
        amount = row["amount_cents"]
        if INTEGER.fullmatch(amount) is None:
            raise ReportError(
                f"Transaction {transaction_id}: invalid amount_cents {amount}"
            )
        raw_date = row["transaction_date"]
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as error:
            raise ReportError(
                f"Transaction {transaction_id}: invalid date {raw_date}"
            ) from error
        if parsed_date.isoformat() != raw_date:
            raise ReportError(
                f"Transaction {transaction_id}: date must use YYYY-MM-DD"
            )
        previous = transactions.get(transaction_id)
        if previous is not None and previous != row:
            raise ReportError(f"Conflicting transaction_id: {transaction_id}")
        transactions[transaction_id] = row
    return transactions


def generate_reports(account_path, transaction_path):
    accounts = load_accounts(account_path)
    transactions = load_transactions(transaction_path)
    totals = {
        account_id: {"transaction_count": 0, "net_sales_cents": 0}
        for account_id in accounts
    }
    exceptions = []

    for transaction_id, row in sorted(transactions.items()):
        if not "2026-09-01" <= row["transaction_date"] <= "2026-09-30":
            continue
        amount = int(row["amount_cents"])
        account_id = row["account_id"]
        if account_id in accounts:
            totals[account_id]["transaction_count"] += 1
            totals[account_id]["net_sales_cents"] += amount
        else:
            exceptions.append({**row, "reason": "unknown_account"})

    report = [
        {
            **accounts[account_id],
            "transaction_count": str(totals[account_id]["transaction_count"]),
            "net_sales_cents": str(totals[account_id]["net_sales_cents"]),
        }
        for account_id in sorted(accounts)
    ]
    return report, exceptions


def write_report(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    root = Path.cwd()
    try:
        report, exceptions = generate_reports(
            root / "data/customer-accounts.csv",
            root / "data/sales-transactions.csv",
        )
        output_dir = root / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        write_report(output_dir / "customer-account-report.csv", REPORT_FIELDS, report)
        write_report(output_dir / "exceptions.csv", EXCEPTION_FIELDS, exceptions)
    except (OSError, UnicodeError, csv.Error, ReportError) as error:
        print(f"Report generation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
