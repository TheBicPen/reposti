from bot import num_in_ranges, add_range
import unittest


class TestNumInRanges(unittest.TestCase):

    def test_empty(self):
        self.assertFalse(num_in_ranges([], 2))

    def test_in_single_range(self):
        self.assertTrue(num_in_ranges([[1, 3]], 2))

    def test_not_in_single_range(self):
        self.assertFalse(num_in_ranges([[5, 20]], 2))

    def test_between_ranges(self):
        self.assertFalse(num_in_ranges([[0, 1], [3, 5]], 2))

    def test_in_many_ranges(self):
        self.assertTrue(num_in_ranges([[0, 3], [5, 6]], 2))

    def test_above_ranges(self):
        self.assertFalse(num_in_ranges([[-3, -1], [-1, 1]], 2))

    def test_below_ranges(self):
        self.assertFalse(num_in_ranges([[3, 11], [13, 18]], 2))

    def test_lower_bound_ranges(self):
        self.assertTrue(num_in_ranges([[3, 12], [13, 18]], 13))

    def test_at_max(self):
        self.assertTrue(num_in_ranges([[3, 8], [15, 17]], 17))

    def test_at_min(self):
        self.assertTrue(num_in_ranges([[14, 15], [18, 19]], 14))

    def test_upper_bound_ranges(self):
        self.assertTrue(num_in_ranges([[3, 12], [13, 18]], 12))

    def test_in_odd_ranges(self):
        self.assertTrue(num_in_ranges([[3, 4], [6, 12], [14, 18]], 12))

    def test_in_singleton_range_of_many(self):
        self.assertTrue(num_in_ranges([[3, 4], [12, 12], [14, 18]], 12))

    def test_in_singleton_range_of_one(self):
        self.assertTrue(num_in_ranges([[12, 12]], 12))

    def test_in_singleton_range_of_one_odd(self):
        self.assertTrue(num_in_ranges([[19, 19]], 19))


class TestAddRange(unittest.TestCase):

    def test_add_to_nonempty(self):
        r = [[1, 2]]
        add_range(r, [5, 6])
        self.assertSequenceEqual([[1, 2], [5, 6]], r)

    def test_add_to_empty(self):
        r = []
        add_range(r, [3, 7])
        self.assertSequenceEqual([[3, 7]], r)

    def test_add_new_min(self):
        r = [[4, 8], [10, 15]]
        add_range(r, [1, 3])
        self.assertSequenceEqual([[1, 3], [4, 8], [10, 15]], r)

    def test_add_new_max(self):
        r = [[4, 8], [10, 15]]
        add_range(r, [18, 30])
        self.assertSequenceEqual([[4, 8], [10, 15], [18, 30]], r)

    def test_add_lower_overlap(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [12, 16])
        self.assertSequenceEqual([[5, 10], [12, 20], [25, 30]], r)

    def test_add_upper_overlap(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [17, 21])
        self.assertSequenceEqual([[5, 10], [15, 21], [25, 30]], r)

    def test_add_max_overlap(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [27, 31])
        self.assertSequenceEqual([[5, 10], [15, 20], [25, 31]], r)

    def test_add_min_overlap(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [1, 5])
        self.assertSequenceEqual([[1, 10], [15, 20], [25, 30]], r)

    def test_superset(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [13, 22])
        self.assertSequenceEqual([[5, 10], [13, 22], [25, 30]], r)

    def test_subset(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [6, 8])
        self.assertSequenceEqual([[5, 10], [15, 20], [25, 30]], r)

    def test_merge_in_both(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [16, 28])
        self.assertSequenceEqual([[5, 10], [15, 30]], r)

    def test_merge_in_none(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [14, 31])
        self.assertSequenceEqual([[5, 10], [14, 31]], r)

    def test_merge_in_lower(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [16, 31])
        self.assertSequenceEqual([[5, 10], [15, 31]], r)

    def test_merge_in_upper(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [13, 25])
        self.assertSequenceEqual([[5, 10], [13, 30]], r)

    def test_merge_all_in_both(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [6, 25])
        self.assertSequenceEqual([[5, 30]], r)

    def test_merge_all_superset(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [4, 31])
        self.assertSequenceEqual([[4, 31]], r)

    def test_equal(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [15, 20])
        self.assertSequenceEqual([[5, 10], [15, 20], [25, 30]], r)

    def test_equal_singleton(self):
        r = [[5, 10], [15, 15], [25, 30]]
        add_range(r, [15, 15])
        self.assertSequenceEqual([[5, 10], [15, 15], [25, 30]], r)

    def test_subset_singleton(self):
        r = [[5, 10], [15, 20], [25, 30]]
        add_range(r, [17, 17])
        self.assertSequenceEqual([[5, 10], [15, 20], [25, 30]], r)


if __name__ == '__main__':
    unittest.main()
