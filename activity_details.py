from dataclasses import dataclass, asdict
from typing import Any, List, Optional
import pandas as pd

from db_connection import get_postgresdb_from_neon_keys, PostgresDB


@dataclass
class ActivityDetails:
    """Model for rows from `webhooks` where `type = 'activity-details'`.

    We keep a flexible payload field because `webhooks.payload` is usually JSON.
    If your `webhooks` table has different column names, adjust the mapping in
    `from_record`.
    """
    id: Optional[int]
    type: Optional[str]
    created_at: Optional[Any]
    data: Optional[dict]
    raw: dict = None

    @classmethod
    def from_record(cls, record: dict) -> "ActivityDetails":
        """Build ActivityDetails from a DB row expressed as a dict.

        The function tries common column names and places the rest in `raw`.
        """
        # common column names we expect
        id_ = record.get("id") or record.get("webhook_id")
        type_ = record.get("type")
        created_at = record.get("created_at") or record.get("created")
        # `data` may be stored as json/jsonb or as text
        data = record.get("data")
        # Also accept older name `payload` if present
        if data is None:
            data = record.get("payload")
        # Ensure data is a dict if it's JSON string
        if isinstance(data, str):
            try:
                import json

                data = json.loads(data)
            except Exception:
                # leave as-is if not parseable
                pass

        return cls(id=id_, type=type_, created_at=created_at, data=data, raw=record)

    def samples_df(self) -> pd.DataFrame:
        """Return a cleaned samples DataFrame for this activity detail.

        This calls the module helper `extract_samples_from_detail` using
        the `data` field of this `ActivityDetails` instance.
        """
        if not self.data or not isinstance(self.data, dict):
            return pd.DataFrame()
        # The detail may be nested under 'activityDetails' or may itself be
        # the activity detail structure. Prefer the detail itself.
        detail = self.data
        # if the activity detail is wrapped inside an 'activityDetails' list,
        # take the first element
        if isinstance(detail.get("activityDetails"), list) and len(detail.get("activityDetails")) > 0:
            detail = detail.get("activityDetails")[0]
        return extract_samples_from_detail(detail)


def fetch_activity_details(
    db: Optional[PostgresDB] = None,
    path: str = "neondb_keys.json",
    limit: int = 100,
    since: Optional[str] = None,
) -> List[ActivityDetails]:
    """Query `webhooks` for rows with `type = 'activity-details'` and
    return a list of `ActivityDetails`.

    Parameters:
    - db: optional PostgresDB instance. If omitted, it will be created
      from `path` using `get_postgresdb_from_neon_keys`.
    - limit: max rows to return.
    - since: optional ISO datetime string to filter `created_at >= since`.
    """
    created_local = False
    if db is None:
        db = get_postgresdb_from_neon_keys(path)
        created_local = True

    # select explicit columns to match your table schema: id, type, data, created_at
    q = "SELECT * FROM webhooks WHERE type = 'activity-details'"
    params = []
    if since:
        q += " AND created_at >= %s"
        params.append(since)
    q += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with db:
        df = db.to_dataframe(q, params=tuple(params))

    # convert DataFrame rows to ActivityDetails
    results: List[ActivityDetails] = []
    for _, row in df.iterrows():
        record = {col: row[col] for col in df.columns}
        results.append(ActivityDetails.from_record(record))

    if created_local:
        db.close()
    return results


def fetch_activity_details_df(
    db: Optional[PostgresDB] = None, path: str = "neondb_keys.json", limit: int = 100, since: Optional[str] = None
) -> pd.DataFrame:
    """Return a pandas DataFrame with the queried activity-details rows."""
    created_local = False
    if db is None:
        db = get_postgresdb_from_neon_keys(path)
        created_local = True

    q = "SELECT id, type, data, created_at FROM webhooks WHERE type = 'activity-details'"
    params = []
    if since:
        q += " AND created_at >= %s"
        params.append(since)
    q += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with db:
        df = db.to_dataframe(q, params=tuple(params))

    if created_local:
        db.close()
    return df


def extract_samples_from_detail(detail: dict) -> pd.DataFrame:
    """Extract and clean `samples` DataFrame from a single activity detail dict.

    - Parses JSON-like `data['samples']` into a DataFrame.
    - Computes `distanceDiff` and `secondsDiff` per sample.
    - Fills zero/na `speedMetersPerSecond` using distance/seconds when possible.
    - Converts `timerDurationInSeconds` to datetime (`timerDuration`).
    """
    samples = detail.get("samples") or []
    if not samples:
        return pd.DataFrame()

    df = pd.DataFrame(samples)

    # ensure numeric columns
    for col in ("totalDistanceInMeters", "timerDurationInSeconds", "speedMetersPerSecond"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # distance and time diffs
    if "totalDistanceInMeters" in df.columns:
        df["distanceDiff"] = df["totalDistanceInMeters"].diff()
        df.loc[df.index[0], "distanceDiff"] = df.loc[df.index[0], "totalDistanceInMeters"]
    else:
        df["distanceDiff"] = pd.NA

    if "timerDurationInSeconds" in df.columns:
        df["secondsDiff"] = df["timerDurationInSeconds"].diff()
        df.loc[df.index[0], "secondsDiff"] = df.loc[df.index[0], "timerDurationInSeconds"]
    else:
        df["secondsDiff"] = pd.NA

    # filter out non-positive distance diffs
    if "distanceDiff" in df.columns:
        df = df[df["distanceDiff"] > 0]

    # fill missing or zero speed by computing distance/seconds
    if "speedMetersPerSecond" in df.columns:
        mask = (df["speedMetersPerSecond"].isna()) | (df["speedMetersPerSecond"] == 0)
        # avoid division by zero: coerce seconds to numeric and treat 0 as NA
        safe_seconds = pd.to_numeric(df["secondsDiff"].replace({0: pd.NA}), errors="coerce")
        # compute candidate speeds (distance / seconds) and only assign where valid
        computed_speed = df["distanceDiff"].astype(float).divide(safe_seconds)
        set_mask = mask & computed_speed.notna()
        df.loc[set_mask, "speedMetersPerSecond"] = computed_speed.loc[set_mask]

    # timerDuration as datetime (unit seconds)
    if "timerDurationInSeconds" in df.columns:
        df["timerDuration"] = pd.to_datetime(df["timerDurationInSeconds"], unit="s", errors="coerce")

    return df


def extract_all_samples(data: dict) -> pd.DataFrame:
    """Process all `activityDetails` in `data` and return concatenated samples DataFrame.

    Adds columns `activity_index` and `activity_id` (if present in detail).
    """
    activity_details = data.get("activityDetails") or []
    rows = []
    for idx, detail in enumerate(activity_details):
        df = extract_samples_from_detail(detail)
        if df.empty:
            continue
        # annotate with activity info
        df = df.copy()
        df["activity_index"] = idx
        activity_id = detail.get("activityId") or detail.get("id")
        df["activity_id"] = activity_id
        rows.append(df)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)