import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, List

import requests


ACCESS_KEY = os.getenv("URA_ACCESS_KEY", "").strip()

TOKEN_URL = "https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1"
DATA_URL = "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1"

DATA_FOLDER = "data"

# URA private residential transactions are usually split into batches.
BATCHES = [1, 2, 3, 4]


def get_token() -> str:
    if not ACCESS_KEY:
        raise ValueError("Missing URA_ACCESS_KEY environment variable.")

    response = requests.get(
        TOKEN_URL,
        headers={
            "AccessKey": ACCESS_KEY,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    if data.get("Status") != "Success":
        raise RuntimeError(f"Token generation failed: {data}")

    return data["Result"].strip()


def fetch_private_residential_transactions(
    token: str,
    batch: int,
) -> List[Dict[str, Any]]:
    response = requests.get(
        DATA_URL,
        params={
            "service": "PMI_Resi_Transaction",
            "batch": str(batch),
        },
        headers={
            "AccessKey": ACCESS_KEY,
            "Token": token,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=90,
    )

    response.raise_for_status()

    text = response.text.strip()
    if text.startswith("<!DOCTYPE html>") or "<html" in text.lower():
        raise RuntimeError("URA returned HTML instead of JSON.")

    data = response.json()

    if data.get("Status") != "Success":
        raise RuntimeError(f"URA request failed for batch {batch}: {data}")

    return data.get("Result", [])


def flatten_transactions(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []

    for project_record in records:
        transactions = project_record.get("transaction", [])

        project_info = {
            key: value
            for key, value in project_record.items()
            if key != "transaction"
        }

        if not transactions:
            rows.append(project_info)
            continue

        for transaction in transactions:
            row = {}

            row.update(project_info)

            for key, value in transaction.items():
                row[key] = value

            rows.append(row)

    return rows


def save_csv(records: List[Dict[str, Any]], filepath: str) -> None:
    if not records:
        print(f"No records to save: {filepath}")
        return

    fieldnames = sorted({key for record in records for key in record.keys()})

    with open(filepath, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def save_json(records: List[Dict[str, Any]], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2, ensure_ascii=False)


def main() -> None:
    os.makedirs(DATA_FOLDER, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Generating URA token...")
    token = get_token()

    raw_records = []

    for batch in BATCHES:
        print(f"Fetching private residential transactions batch {batch}...")
        batch_records = fetch_private_residential_transactions(token, batch)
        print(f"Batch {batch}: {len(batch_records)} project records")
        raw_records.extend(batch_records)

    flat_records = flatten_transactions(raw_records)

    print(f"Total project records: {len(raw_records)}")
    print(f"Total flattened transaction rows: {len(flat_records)}")

    latest_csv = os.path.join(
        DATA_FOLDER,
        "ura_private_residential_transactions_latest.csv",
    )

    dated_csv = os.path.join(
        DATA_FOLDER,
        f"ura_private_residential_transactions_{timestamp}.csv",
    )

    dated_json = os.path.join(
        DATA_FOLDER,
        f"ura_private_residential_transactions_{timestamp}.json",
    )

    save_csv(flat_records, latest_csv)
    save_csv(flat_records, dated_csv)
    save_json(raw_records, dated_json)

    print(f"Saved: {latest_csv}")
    print(f"Saved: {dated_csv}")
    print(f"Saved: {dated_json}")


if __name__ == "__main__":
    main()