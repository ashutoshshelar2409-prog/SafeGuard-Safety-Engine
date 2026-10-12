"""
Data Cleaning Module.
Cleans raw data by dropping duplicates, handling missing values, and formatting types.
"""

from typing import List, Dict, Any, Optional, Union
from src.processing.validation import validate_coordinates

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def clean_dataset(
    data: Union[Any, List[Dict[str, Any]]],
    required_columns: List[str],
    numeric_columns: List[str],
    defaults: Optional[Dict[str, Any]] = None
) -> Union[Any, List[Dict[str, Any]]]:
    """
    General data cleaning function supporting Pandas DataFrame or List of Dicts.
    """
    defaults = defaults or {}

    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        cleaned = data.copy()
        cleaned = cleaned.drop_duplicates()
        if defaults:
            cleaned = cleaned.fillna(value=defaults)
        cleaned = cleaned.dropna(subset=required_columns)
        for col in numeric_columns:
            if col in cleaned.columns:
                cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
        cleaned = cleaned.dropna(subset=[c for c in numeric_columns if c in required_columns])
        if "latitude" in cleaned.columns and "longitude" in cleaned.columns:
            valid_mask = cleaned.apply(
                lambda r: validate_coordinates(r["latitude"], r["longitude"]), axis=1
            )
            cleaned = cleaned[valid_mask]
        return cleaned.reset_index(drop=True)

    # Pure Python list of dicts cleaning fallback
    if isinstance(data, list):
        cleaned_list = []
        seen = set()

        for item in data:
            if not isinstance(item, dict):
                continue
            
            # Row key for deduplication
            row_key = tuple(item.get(c) for c in required_columns)
            if row_key in seen:
                continue

            # Fill defaults
            row = dict(item)
            for col, default_val in defaults.items():
                if row.get(col) is None:
                    row[col] = default_val

            # Check missing required
            if any(row.get(c) is None for c in required_columns):
                continue

            # Coerce numeric
            invalid_num = False
            for col in numeric_columns:
                if col in row and row[col] is not None:
                    try:
                        row[col] = float(row[col])
                    except (ValueError, TypeError):
                        invalid_num = True
            if invalid_num:
                continue

            # Check coordinates
            if "latitude" in row and "longitude" in row:
                if not validate_coordinates(row["latitude"], row["longitude"]):
                    continue

            seen.add(row_key)
            cleaned_list.append(row)

        return cleaned_list

    return data


def clean_dataframe(
    df: Any,
    required_columns: List[str],
    numeric_columns: List[str],
    defaults: Optional[Dict[str, Any]] = None
) -> Any:
    """Wrapper function maintaining clean_dataframe alias."""
    return clean_dataset(df, required_columns, numeric_columns, defaults)


def clean_community_reports(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cleans community reports JSON data.
    """
    cleaned = []
    seen_ids = set()

    for report in reports:
        report_id = report.get("report_id")
        if not report_id or report_id in seen_ids:
            continue

        lat = report.get("latitude")
        lng = report.get("longitude")
        if not validate_coordinates(lat, lng):
            continue

        try:
            severity = int(report.get("severity", 1))
            severity = max(1, min(5, severity))
        except (ValueError, TypeError):
            severity = 1

        cleaned_report = {
            "report_id": str(report_id),
            "report_type": str(report.get("report_type", "general")),
            "latitude": float(lat),
            "longitude": float(lng),
            "severity": severity,
            "timestamp": str(report.get("timestamp", "")),
            "description": str(report.get("description", ""))
        }
        
        seen_ids.add(report_id)
        cleaned.append(cleaned_report)

    return cleaned
