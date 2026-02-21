from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional


def normalize_time_series_data(
    data: List[Dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
    date_field: str = "date",
) -> List[Dict[str, Any]]:
    """
    Fill missing dates in time series data with zero values

    Args:
        data: List of dictionaries containing time series data
        start_date: Start date for the range
        end_date: End date for the range
        date_field: Name of the date field in the data

    Returns:
        List with all dates filled, missing dates have zero values
    """
    if not data:
        return []

    # Convert data to dictionary for quick lookup
    data_dict = {item[date_field]: item for item in data}

    # Generate date range
    current_date = start_date.date()
    end_date_only = end_date.date()
    normalized_data = []

    while current_date <= end_date_only:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str in data_dict:
            normalized_data.append(data_dict[date_str])
        else:
            # Create zero entry
            zero_entry = {date_field: date_str}
            # Add zero values for all numeric fields
            for key, value in data[0].items():
                if key != date_field and isinstance(value, (int, float)):
                    zero_entry[key] = 0
                elif key != date_field:
                    zero_entry[key] = value if isinstance(value, str) else "Unknown"
            normalized_data.append(zero_entry)

        current_date += timedelta(days=1)

    return normalized_data


def aggregate_top_n_with_others(
    data: List[Dict[str, Any]], metric_field: str, dimension_field: str, top_n: int = 5
) -> List[Dict[str, Any]]:
    """
    Aggregate data to show top N items and group the rest as "Others"

    Args:
        data: List of dictionaries containing the data
        metric_field: Field name containing the metric to aggregate
        dimension_field: Field name containing the dimension values
        top_n: Number of top items to show individually

    Returns:
        List with top N items and "Others" entry if applicable
    """
    if len(data) <= top_n:
        return data

    # Sort by metric in descending order
    sorted_data = sorted(data, key=lambda x: x.get(metric_field, 0), reverse=True)

    # Take top N items
    top_items = sorted_data[:top_n]

    # Aggregate remaining items
    others_sum = sum(item.get(metric_field, 0) for item in sorted_data[top_n:])

    if others_sum > 0:
        others_entry = {dimension_field: "Others", metric_field: others_sum}
        # Copy other fields from first item as template
        for key, value in sorted_data[0].items():
            if key not in [dimension_field, metric_field]:
                if isinstance(value, (int, float)):
                    others_entry[key] = sum(
                        item.get(key, 0) for item in sorted_data[top_n:]
                    )
                else:
                    others_entry[key] = "Others"
        top_items.append(others_entry)

    return top_items


def format_stats_response_with_metadata(
    stats_data: Dict[str, Any], include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Format stats response with additional metadata and computed fields

    Args:
        stats_data: Raw stats data from the query builder
        include_metadata: Whether to include additional metadata

    Returns:
        Enhanced stats response with metadata
    """
    if not include_metadata:
        return stats_data

    response = stats_data.copy()

    # Add response metadata
    response["generated_at"] = datetime.now(timezone.utc).isoformat()
    response["api_version"] = "v1"

    # Calculate additional metrics from summary if available
    summary = response.get("summary", {})
    if summary:
        total_clicks = summary.get("total_clicks", 0)
        unique_clicks = summary.get("unique_clicks", 0)

        # Calculate click-through rate approximation
        if total_clicks > 0:
            unique_rate = (unique_clicks / total_clicks) * 100
            response["computed_metrics"] = {
                "unique_click_rate": round(unique_rate, 2),
                "repeat_click_rate": round(100 - unique_rate, 2),
                "average_clicks_per_visitor": round(
                    total_clicks / unique_clicks if unique_clicks > 0 else 0, 2
                ),
            }

    # Enhance metrics data with percentages
    metrics = response.get("metrics", {})
    for metric_key, metric_data in metrics.items():
        if isinstance(metric_data, list) and metric_data:
            total = sum(
                item.get(list(item.keys())[-1], 0)
                for item in metric_data
                if isinstance(item, dict)
            )
            if total > 0:
                for item in metric_data:
                    if isinstance(item, dict):
                        value_key = list(item.keys())[
                            -1
                        ]  # Get the last key (usually the metric value)
                        value = item.get(value_key, 0)
                        item[f"{value_key}_percentage"] = round(
                            (value / total) * 100, 2
                        )

    return response


def validate_date_range(
    start_date: Optional[datetime], end_date: Optional[datetime], max_days: int = 90
) -> Dict[str, Any]:
    """
    Validate date range parameters

    Args:
        start_date: Start date
        end_date: End date
        max_days: Maximum allowed days in range

    Returns:
        Validation result with is_valid flag and error message if invalid
    """
    if not start_date and not end_date:
        return {"is_valid": True}

    if start_date and end_date:
        if start_date > end_date:
            return {"is_valid": False, "error": "start_date must be before end_date"}

        date_range = (end_date - start_date).days
        if date_range > max_days:
            return {
                "is_valid": False,
                "error": f"date range cannot exceed {max_days} days",
            }

    # Check if dates are in the future
    now = datetime.now(timezone.utc)
    if start_date and start_date.replace(microsecond=0) > now.replace(microsecond=0):
        return {"is_valid": False, "error": "start_date cannot be in the future"}

    if end_date and end_date.replace(microsecond=0) > now.replace(microsecond=0):
        return {"is_valid": False, "error": "end_date cannot be in the future"}

    return {"is_valid": True}
