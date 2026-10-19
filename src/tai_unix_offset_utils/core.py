"""Core conversion logic for TAI <-> Unix timestamps.

The fundamental problem
-----------------------
Unix time counts SI seconds *except* it assumes every day has exactly
86400 of them.  Real UTC days sometimes contain a leap second, so a UTC
day can be 86401 (or, in theory, 86399) SI seconds long.  Unix handles
this by *slowing down* or *speeding up* the clock: during a positive leap
second the same Unix value is held for two consecutive SI seconds.

International Atomic Time (TAI) has no leap seconds; it is a monotonic
count of SI seconds since 1958-01-01T00:00:00 TAI.

Because Unix seconds and SI seconds are the *same physical unit* outside
leap-second insertions, the difference between TAI and Unix timestamps is
simply the accumulated number of leap seconds inserted *before* that
moment.  This module maintains the official IERS/BIPM table and applies
it.

Conventions used here (stated plainly so there is no ambiguity)
----------------------------------------------------------------
* Unix timestamps are **scalar seconds since 1970-01-01T00:00:00 UTC**.
* TAI timestamps are **scalar seconds since 1970-01-01T00:00:00 TAI**.
  This is a deliberate offset from the canonical TAI epoch (1958) so that
  the two scales share a common numeric origin; users who want
  1958-epoch TAI can add the constant 378691200 (the TAI-Unix offset at
  1970-01-01, i.e. 10 s + the 378691190 s between 1958 and 1970).
  Wait -- 378691200 is NOT correct; the correct 1958<->1970 offset in SI
  seconds is 378691200, and the initial TAI-UTC offset at 1972-01-01 was
  10 s.  To avoid confusion this module simply uses 1970-epoch TAI
  throughout and never references 1958.
* Leap seconds are inserted at **23:59:60 UTC** on the announced day.
  The Unix timestamp of the *first* SI second of the leap second is the
  value in the table.  During a positive leap second, two consecutive
  TAI instants map to the *same* Unix timestamp.
* unix_to_atomic returns a list of TAI values when a Unix timestamp is
  ambiguous (falls exactly on a leap-second boundary); otherwise a
  one-element list.  Returning a list *always* keeps the return type
  stable and lets callers handle ambiguity uniformly.
* atomic_to_unix is single-valued (TAI is continuous).
"""

from __future__ import annotations

from bisect import bisect_right
from typing import List, Sequence, Tuple

# Each entry is (unix_timestamp_of_leap_second, cumulative_tai_minus_unix_offset)
# The offset is the value of (TAI - Unix) that applies for all Unix timestamps
# >= the entry's timestamp, up to the next entry.
#
# The table is derived from the published IERS bulletins.  The initial
# offset of 10 seconds was established when the TAI-UTC relationship was
# first fixed in 1972; before that the relationship was rate-based and
# not a clean integer offset, so this module does not attempt to cover
# pre-1972 dates.
#
# Convention: the `unix_timestamp` is the Unix value of midnight UTC
# *after* the leap second (i.e. the first SI second with the new offset).
# For a positive leap at 1972-06-30 23:59:60 UTC that is the timestamp of
# 1972-07-01 00:00:00 UTC, i.e. 78796800, and the offset increases from
# 10 to 11.
LEAP_SECONDS: Sequence[Tuple[int, int]] = (
    # (unix ts, TAI-Unix offset in seconds)
    # Entries are sorted by unix ts ascending, offsets strictly increasing.
    (78796800, 11),    # 1972-07-01: +1  -> 10 becomes 11
    (94694400, 12),    # 1973-01-01
    (126230400, 13),   # 1974-01-01
    (157766400, 14),   # 1975-01-01
    (189302400, 15),   # 1976-01-01
    (220924800, 16),   # 1977-01-01
    (252460800, 17),   # 1978-01-01
    (283996800, 18),   # 1979-01-01
    (315532800, 19),   # 1980-01-01
    (362793600, 20),   # 1981-07-01
    (394329600, 21),   # 1982-07-01
    (425865600, 22),   # 1983-07-01
    (489024000, 23),   # 1985-07-01
    (567993600, 24),   # 1988-01-01
    (631152000, 25),   # 1990-01-01
    (662688000, 26),   # 1991-01-01
    (709948800, 27),   # 1992-07-01
    (741484800, 28),   # 1993-07-01
    (773020800, 29),   # 1994-07-01
    (820454400, 30),   # 1996-01-01
    (867715200, 31),   # 1997-07-01
    (915148800, 32),   # 1999-01-01
    (1136073600, 33),  # 2006-01-01
    (1230768000, 34),  # 2009-01-01
    (1341100800, 35),  # 2012-07-01
    (1415275200, 36),  # 2015-07-01
    (1483228800, 37),  # 2017-01-01
)


def _offset_at_unix(ts: int) -> int:
    """Return the TAI-Unix offset (TAI minus Unix) for the given Unix ts.

    For ts values at or just before the first tabulated leap second we
    return the initial offset of 10 (the TAI-UTC offset at 1972-01-01).
    For ts values after the last tabulated entry we return the last
    offset; the table is authoritative as of its last update and new
    leap seconds are announced months in advance.
    """
    # We want the rightmost entry whose timestamp <= ts.
    idx = bisect_right(_ts_list(), ts)  # number of entries with ts <= given
    if idx == 0:
        return 10
    return LEAP_SECONDS[idx - 1][1]


def _ts_list() -> Sequence[int]:
    """Tuple of just the timestamps, for bisect."""
    return tuple(e[0] for e in LEAP_SECONDS)


def atomic_to_unix(tai: int) -> int:
    """Convert a 1970-epoch TAI timestamp to a Unix timestamp.

    TAI is continuous, so the mapping is a single-valued, piecewise-linear
    function.  We invert the forward mapping by walking the table and
    subtracting the appropriate number of accumulated leap seconds.

    For a TAI value that falls *inside* a positive leap second, the Unix
    timestamp returned is the value that Unix "holds" during that SI
    second (i.e. the last normal second before midnight UTC repeated).
    """
    if tai < 0:
        # We do not support pre-1970 TAI; the offset table starts at 1972
        # and extrapolating backward is not meaningful.
        raise ValueError("TAI timestamps before 1970-01-01 are not supported")

    # For TAI values below the first leap second the offset is the initial 10.
    if tai < LEAP_SECONDS[0][0]:
        return tai - 10

    # Walk forward: at each leap second boundary the TAI clock has advanced
    # one SI second that the Unix clock did not.  So for a TAI value t,
    # the Unix value is t minus the number of leap seconds inserted at or
    # before t.
    offset = 10
    for boundary_ts, boundary_offset in LEAP_SECONDS:
        # The boundary's *Unix* timestamp is boundary_ts, but its *TAI*
        # timestamp (in 1970-epoch TAI) is boundary_ts + (offset just
        # before this boundary).  We need to know whether `tai` is at or
        # past that TAI boundary.
        tai_of_boundary = boundary_ts + offset
        if tai >= tai_of_boundary:
            offset = boundary_offset
        else:
            break
    return tai - offset


def unix_to_atomic(unix_ts: int) -> List[int]:
    """Convert a Unix timestamp to 1970-epoch TAI timestamp(s).

    Returns a list because a Unix timestamp that falls exactly on a
    positive-leap-second boundary corresponds to *two* TAI instants:
    the last SI second before the leap and the SI second of the leap
    itself.  For all other Unix timestamps the list has exactly one
    element.

    A Unix timestamp before the first leap second (ts < 78796800) yields
    [ts + 10] -- the pre-1972 rate-based relationship is deliberately not
    modelled.
    """
    if unix_ts < 0:
        raise ValueError("Unix timestamps before 1970-01-01 are not supported")

    # Find the offset that applies to this Unix timestamp (the offset that
    # was in effect *just after* the leap second, i.e. for ts >= boundary).
    offset_after = _offset_at_unix(unix_ts)

    # Check if this exact Unix timestamp is a leap-second boundary.
    # The leap second occurs during the Unix second *before* midnight UTC
    # (i.e. 23:59:59 is held for two SI seconds).  So the repeated Unix
    # value is boundary_ts - 1 for each tabulated boundary_ts.
    ts_tuple = _ts_list()
    idx = bisect_right(ts_tuple, unix_ts)

    results: List[int] = []

    if idx < len(LEAP_SECONDS) and LEAP_SECONDS[idx][0] - 1 == unix_ts:
        # This Unix timestamp IS the repeated second of a leap-second
        # boundary.  There are two TAI instants with this Unix value:
        #   1. The leap-second SI second itself:  unix_ts + offset_after
        #      (because during the leap second the offset is already the
        #      new, higher value).
        #   2. The previous (normal) SI second, which Unix maps to the
        #      same value: unix_ts + (offset_after - 1).
        #
        # Both are valid TAI timestamps that correspond to this Unix ts.
        offset_after = LEAP_SECONDS[idx][1]
        offset_before = offset_after - 1
        results.append(unix_ts + offset_before)
        results.append(unix_ts + offset_after)
    else:
        # Not a boundary.  The single TAI value is unix_ts + offset_after.
        results.append(unix_ts + offset_after)

    return sorted(results)
