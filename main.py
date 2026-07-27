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

SERVICES = {
    "private_residential_transactions": {
        "service": "PMI_Resi_Transaction",
        "param_sets": [{"batch": str(i)} for i in range(1, 5)],
    },
    "private_residential_rental_contracts": {
        "service": "PMI_Resi_Rental",
        # Update these if you want more/other quarters
        "param_sets": [
            {"refPeriod": "26q2"},
            {"refPeriod": "26q1"},
            {"refPeriod": "25q4"},
            {"refPeriod": "25q3"},
        ],
    },
    "private_residential_median_rentals": {
        "service": "PMI_Resi_Rental_Median",
        "param_sets": [{}],
    },
    "private_residential_developer_sales": {
        "service": "PMI_Resi_Developer_Sales",
        "param_sets": [{}],
    },
    "private_residential_pipeline": {
        "service": "PMI_Resi_Pipeline",
        "param_sets": [{}],
    },
}


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


def fetch_service(token: str, service: str, extra_params: Dict[str, str]) -> List[Dict[str, Any]]:
    params = {"service": service}
    params.update(extra_params)

    response = requests.get(
        DATA_URL,
        params=params,
        headers={
            "AccessKey": ACCESS_KEY,
            "Token": token,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=120,
    )

    response.raise_for_status()

    text = response.text.strip()
    if text.startswith("<!DOCTYPE html>") or "<html" in text.lower():
        raise RuntimeError(f"{service} returned HTML instead of JSON.")

    data = response.json()

    if data.get("Status") != "Success":
        raise RuntimeError(f"{service} failed: {data}")

    return data.get("Result", [])


def flatten_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flattened = []

    for record in records:
        nested_lists = {
            key: value
            for key, value in record.items()
            if isinstance(value, list)
        }

        base = {
            key: value
            for key, value in record.items()
            if not isinstance(value, list)
        }

        if not nested_lists:
            flattened.append(base)
            continue

        for nested_key, nested_values in nested_lists.items():
            for item in nested_values:
                row = dict(base)

                if isinstance(item, dict):
                    for key, value in item.items():
                        row[key] = value
                else:
                    row[nested_key] = item

                flattened.append(row)

    return flattened


def save_json(records: Any, filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2, ensure_ascii=False)


def save_csv(records: List[Dict[str, Any]], filepath: str) -> None:
    if not records:
        print(f"No CSV records to save: {filepath}")
        return

    fieldnames = sorted({key for record in records for key in record.keys()})

    with open(filepath, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    os.makedirs(DATA_FOLDER, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Generating URA token...")
    token = get_token()

    for output_name, config in SERVICES.items():
        service = config["service"]
        param_sets = config["param_sets"]

        print(f"\nFetching {output_name}...")

        raw_records = []

        for params in param_sets:
            print(f"  Service={service}, params={params}")

            try:
                records = fetch_service(token, service, params)
                print(f"  Received {len(records)} records")
                raw_records.extend(records)
            except Exception as error:
                print(f"  Failed: {error}")

        flat_records = flatten_records(raw_records)

        latest_json = os.path.join(DATA_FOLDER, f"{output_name}_latest.json")
        dated_json = os.path.join(DATA_FOLDER, f"{output_name}_{timestamp}.json")

        latest_csv = os.path.join(DATA_FOLDER, f"{output_name}_latest.csv")
        dated_csv = os.path.join(DATA_FOLDER, f"{output_name}_{timestamp}.csv")

        save_json(raw_records, latest_json)
        save_json(raw_records, dated_json)

        save_csv(flat_records, latest_csv)
        save_csv(flat_records, dated_csv)

        print(f"Saved {output_name}: {len(flat_records)} CSV rows")

    print("\nDone.")


if __name__ == "__main__":
    main()