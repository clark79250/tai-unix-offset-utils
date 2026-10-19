import unittest

from tai_unix_offset_utils import (
    LEAP_SECONDS,
    atomic_to_unix,
    unix_to_atomic,
)


class TestLeapSecondsTable(unittest.TestCase):
    def test_table_sorted_and_offsets_increase(self):
        timestamps = [e[0] for e in LEAP_SECONDS]
        offsets = [e[1] for e in LEAP_SECONDS]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual(offsets, sorted(set(offsets)))
        self.assertTrue(all(b > a for a, b in zip(offsets, offsets[1:])))

    def test_first_offset_is_eleven(self):
        # The first entry is the 1972-06-30 leap second, offset goes 10->11.
        self.assertEqual(LEAP_SECONDS[0][1], 11)


class TestAtomicToUnix(unittest.TestCase):
    def test_pre_leap_second_region(self):
        # Before the first leap second, offset is 10.
        self.assertEqual(atomic_to_unix(0), -10)
        self.assertEqual(atomic_to_unix(78796799), 78796789)

    def test_first_leap_second_tai(self):
        # The Unix timestamp 78796800 is 1972-07-01 00:00:00 UTC.
        # The leap second is the SI second *before* that, whose TAI value
        # (1970-epoch) is 78796800 + 10 = 78796810, and whose Unix value
        # is 78796799 (the repeated second).
        self.assertEqual(atomic_to_unix(78796810), 78796799)
        # The first SI second of 1972-07-01 UTC has TAI 78796800 + 11.
        self.assertEqual(atomic_to_unix(78796811), 78796800)

    def test_known_offsets(self):
        # At 2017-01-01 00:00:00 UTC (unix 1483228800), offset becomes 37.
        # The TAI value of that instant is 1483228800 + 37 = 1483228837.
        self.assertEqual(atomic_to_unix(1483228837), 1483228800)
        # One TAI second before: offset still 36.
        self.assertEqual(atomic_to_unix(1483228836), 1483228800 - 1)

    def test_negative_tai_raises(self):
        with self.assertRaises(ValueError):
            atomic_to_unix(-1)

    def test_far_future_uses_last_offset(self):
        last_ts, last_offset = LEAP_SECONDS[-1]
        big_tai = last_ts + last_offset + 1000000
        self.assertEqual(atomic_to_unix(big_tai), big_tai - last_offset)


class TestUnixToAtomic(unittest.TestCase):
    def test_non_boundary_single_result(self):
        result = unix_to_atomic(1000000000)  # well past first leap
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        # Round-trip
        self.assertEqual(atomic_to_unix(result[0]), 1000000000)

    def test_pre_leap_region(self):
        result = unix_to_atomic(0)
        self.assertEqual(result, [10])

    def test_leap_second_boundary_two_results(self):
        # 2016-12-31 23:59:60 UTC -> the repeated Unix second is
        # 1483228800 - 1 = 1483228799 (23:59:59 held for two SI seconds).
        boundary = 1483228800 - 1
        result = unix_to_atomic(boundary)
        self.assertEqual(len(result), 2)
        # The two TAI values are boundary+36 and boundary+37.
        self.assertEqual(result, [boundary + 36, boundary + 37])
        # Both should round-trip back to the same Unix ts.
        for tai in result:
            self.assertEqual(atomic_to_unix(tai), boundary)

    def test_first_leap_boundary(self):
        boundary = 78796800 - 1
        result = unix_to_atomic(boundary)
        self.assertEqual(result, [boundary + 10, boundary + 11])

    def test_round_trip_random_values(self):
        for ts in [1, 100, 78796799, 78796801, 2000000000, 1483228799,
                   1483228801]:
            taies = unix_to_atomic(ts)
            for tai in taies:
                self.assertEqual(atomic_to_unix(tai), ts,
                                 f"round-trip failed for ts={ts} tai={tai}")

    def test_negative_unix_raises(self):
        with self.assertRaises(ValueError):
            unix_to_atomic(-1)

    def test_result_is_sorted(self):
        # Always return sorted list for a stable contract.
        boundary = 1483228800 - 1
        result = unix_to_atomic(boundary)
        self.assertEqual(result, sorted(result))


if __name__ == "__main__":
    unittest.main()
