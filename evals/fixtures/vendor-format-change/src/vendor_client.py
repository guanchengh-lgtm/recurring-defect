import datetime
import logging

log = logging.getLogger(__name__)


def parse_settled_at(raw):
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception as exc:
        log.debug("could not parse settled_at %r: %s", raw, exc)
        return None


def settlements_in_window(response, start, end):
    out = []
    for row in response["settlements"]:
        ts = parse_settled_at(row["settled_at"])
        if ts is not None and start <= ts <= end:
            out.append(row)
    return out
