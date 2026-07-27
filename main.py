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
YEARS_TO_FETCH = [2021, 2022, 2023, 2024, 2025, 2026]

RESIDENTIAL_KEYWORDS = [
    "residential",
    "dwelling",
    "dwelling house",
    "terrace",
    "terrace house",
    "landed",
    "landed housing",
    "housing",
    "apartment",
    "condominium",
    "flat",
    "bungalow",
    "semi-detached",
    "detached",
    "attic",
    "good class bungalow",
    "cluster housing",
    "strata landed",
    "serviced apartment",
]


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


def fetch_planning_decisions(token: str, year: int) -> List[Dict[str, Any]]:
    response = requests.get(
        DATA_URL,
        params={
            "service": "Planning_Decision",
            "year": str(year),
        },
        headers={
            "AccessKey": ACCESS_KEY,
            "Token": token,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=60,
    )

    response.raise_for_status()

    text = response.text.strip()
    if text.startswith("<!DOCTYPE html>") or "<html" in text.lower():
        raise RuntimeError("URA returned HTML instead of JSON.")

    data = response.json()

    if data.get("Status") != "Success":
        raise RuntimeError(f"URA request failed: {data}")

    return data.get("Result", [])


def is_residential(record: Dict[str, Any]) -> bool:
    text = " ".join(
        str(value).lower()
        for value in record.values()
        if value is not None
    )

    return any(keyword in text for keyword in RESIDENTIAL_KEYWORDS)


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

    all_records = []
    residential_records = []

    for year in YEARS_TO_FETCH:
        print(f"Fetching {year}...")
        records = fetch_planning_decisions(token, year)

        all_records.extend(records)
        residential_records.extend(
            record for record in records
            if is_residential(record)
        )

    print(f"Total records: {len(all_records)}")
    print(f"Residential records: {len(residential_records)}")

    csv_path = os.path.join(
        DATA_FOLDER,
        f"ura_residential_planning_decisions_{timestamp}.csv",
    )

    latest_csv_path = os.path.join(
        DATA_FOLDER,
        "ura_residential_planning_decisions_latest.csv",
    )

    json_path = os.path.join(
        DATA_FOLDER,
        f"ura_residential_planning_decisions_{timestamp}.json",
    )

    save_csv(residential_records, csv_path)
    save_csv(residential_records, latest_csv_path)
    save_json(residential_records, json_path)

    print(f"Saved: {csv_path}")
    print(f"Saved: {latest_csv_path}")
    print(f"Saved: {json_path}")


if __name__ == "__main__":
    main()