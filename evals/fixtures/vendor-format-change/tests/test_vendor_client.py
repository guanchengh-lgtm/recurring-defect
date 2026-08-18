from src.vendor_client import settlements_in_window
import datetime


def test_window_filters_by_settled_at():
    resp = {"settlements": [
        {"id": "s1", "settled_at": "2026-07-28T04:00:00Z", "amount": 100},
        {"id": "s2", "settled_at": "2026-07-29T04:00:00Z", "amount": 200},
    ]}
    start = datetime.datetime(2026, 7, 28, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 7, 28, 23, 59, tzinfo=datetime.timezone.utc)
    assert [r["id"] for r in settlements_in_window(resp, start, end)] == ["s1"]
