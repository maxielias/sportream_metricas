"""Example: fetch activity-details and extract samples per activity.

Run:
    python -m examples.activity_samples_example
or
    & .venv/Scripts/python.exe examples\activity_samples_example.py
"""
import json
from activity_details import fetch_activity_details, extract_all_samples


def main():
    # Option A: get ActivityDetails objects from DB and call .samples_df()
    items = fetch_activity_details(limit=10)
    print(f"Fetched {len(items)} activity-details items from DB")

    concatenated = []
    for item in items:
        df = item.samples_df()
        if not df.empty:
            df["source_activity_id"] = item.id
            concatenated.append(df)

    if concatenated:
        all_samples_df = __import__("pandas").concat(concatenated, ignore_index=True)
        print("Samples from DB items:")
        print(all_samples_df.head())
    else:
        print("No samples found in fetched activity-details.")

    # Option B: process a JSON file containing activity data
    try:
        with open("sample_activity_payload.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        df_all = extract_all_samples(data)
        print("Samples extracted from sample_activity_payload.json:")
        print(df_all.head())
    except FileNotFoundError:
        print("No sample_activity_payload.json found in repo root — skip file example.")


if __name__ == "__main__":
    main()
