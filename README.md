# tai-unix-offset-utils

Maintains the table of leap seconds and converts between Unix timestamps and International Atomic Time (1970-epoch TAI).

```python
from tai_unix_offset_utils import LEAP_SECONDS, atomic_to_unix, unix_to_atomic

# A Unix timestamp that is NOT a leap-second boundary -> one TAI value.
print(unix_to_atomic(1000000000))   # e.g. [1000000032]

# A Unix timestamp that IS a positive-leap-second boundary -> two TAI values.
print(unix_to_atomic(1483228800))   # [1483228836, 1483228837]

# TAI -> Unix is always single-valued.
print(atomic_to_unix(1483228837))   # 1483228800
```

## Why this exists

Converting between Unix time and TAI looks trivial — just add or subtract the accumulated leap-second count — but the bookkeeping around the exact instant of a leap second is where naive implementations go wrong. During a positive leap second the Unix clock holds the same integer value for two consecutive SI seconds, so a Unix-to-TAI conversion at that boundary is genuinely two-valued. This library makes that ambiguity explicit rather than silently returning one branch and losing information.

The trade-off: `unix_to_atomic` always returns a list (length 1 in the normal case, length 2 on a leap-second boundary). That is slightly more ceremony for callers than a bare scalar, but it keeps the return type stable and forces the caller to acknowledge the ambiguity. If you only ever convert in the TAI-to-Unix direction, you never see it.

## Conventions (stated plainly)

- Unix timestamps are scalar seconds since 1970-01-01T00:00:00 UTC.
- TAI timestamps are scalar seconds since 1970-01-01T00:00:00 *TAI* (not the canonical 1958 epoch). The difference between the two scales at any instant is exactly the number of leap seconds inserted up to that instant, plus the initial 10-second offset established in 1972.
- `LEAP_SECONDS` is a sequence of `(unix_timestamp, cumulative_offset)` pairs. The offset is the value of (TAI − Unix) that applies for all Unix timestamps ≥ the pair's timestamp, up to the next pair.

## Edge you will hit

Dates before 1972. Before 1972 the TAI–UTC relationship was rate-based, not a clean integer offset, and this library does not model it. Timestamps before the first tabulated leap second (Unix 78796800, i.e. 1972-07-01 00:00:00 UTC) are handled by assuming the initial 10-second offset applies throughout — accurate enough for post-1972 work, wrong for historical precision. If you need pre-1972 accuracy you need a different library.

The leap-second table is current as of 2017-01-01 (offset 37). New leap seconds are announced by the IERS months in advance; when one is announced, add a new entry to `LEAP_SECONDS` and increment the offset by 1. The library does not fetch updates automatically — that would be a network dependency, and this library has none.
