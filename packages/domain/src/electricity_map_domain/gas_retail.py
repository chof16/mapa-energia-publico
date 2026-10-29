"""Gas monthly evidence aggregation, independent of electricity R2 identifiers."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MonthlyValue:
    month: str
    status: str
    value: Decimal | None = None
    upper_bound: Decimal | None = None


@dataclass(frozen=True)
class QuarterlyValue:
    status: str
    value: Decimal | None
    upper_bound: Decimal | None
    missing_months: tuple[str, ...]
    input_statuses: tuple[str, ...]


def aggregate_quarter(period: str, metric: str, rows: list[MonthlyValue]) -> QuarterlyValue:
    """Select the final client month; require exactly three sales months.

    The caller must partition by source revision, entity, scope and unit first.
    Source statuses survive in input_statuses even when the result is unavailable.
    """
    if len(period) != 6 or not period[:4].isdigit() or period[4] != "T" or period[5] not in "1234":
        raise ValueError("Invalid quarter")
    if metric not in {"clients", "sales"}:
        raise ValueError("Invalid metric")
    end = int(period[5]) * 3
    months = tuple(f"{period[:4]}-{month:02}" for month in range(end - 2, end + 1))
    by_month = {}
    for row in rows:
        if row.month not in months or row.month in by_month:
            raise ValueError("Out-of-quarter or repeated monthly observation")
        if row.status not in {"exact", "zero", "missing", "suppressed", "source_error", "bounded"}:
            raise ValueError("Invalid observation status")
        if row.status in {"exact", "zero"}:
            if row.value is None or not row.value.is_finite() or row.value < 0 or row.upper_bound is not None:
                raise ValueError("Invalid exact observation")
            if (row.status == "zero") != (row.value == 0):
                raise ValueError("Zero must remain explicit")
        elif row.value is not None:
            raise ValueError("Unavailable observations cannot have exact values")
        if row.status == "bounded":
            if row.upper_bound is None or not row.upper_bound.is_finite() or row.upper_bound <= 0:
                raise ValueError("Invalid exclusive upper bound")
        elif row.upper_bound is not None:
            raise ValueError("Only bounded observations have an upper bound")
        by_month[row.month] = row
    required = months[-1:] if metric == "clients" else months
    missing = tuple(month for month in required if month not in by_month)
    statuses = tuple(by_month[month].status if month in by_month else "missing" for month in required)
    for unavailable in ("source_error", "suppressed", "missing"):
        if unavailable in statuses:
            return QuarterlyValue(unavailable, None, None, missing, statuses)
    selected = [by_month[month] for month in required]
    if "bounded" in statuses:
        upper = sum((row.upper_bound if row.status == "bounded" else row.value for row in selected), Decimal(0))
        return QuarterlyValue("bounded", None, upper, (), statuses)
    value = sum((row.value for row in selected), Decimal(0))
    return QuarterlyValue("zero" if value == 0 else "exact", value, None, (), statuses)
