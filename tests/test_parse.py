"""
Tests for the sets that tell the parser the type of each element
"""

import unittest
from itertools import combinations

from aioboinc import _parse

TAG_SETS = {
    name: getattr(_parse, name)
    for name in ("INTEGER_TAG", "FLOAT_TAG", "BOOL_TAG", "TIME_TAG", "TIMEDELTA_TAG", "LIST_TAG")
}


class TagSetsTest(unittest.TestCase):

    def test_no_tag_is_in_two_sets(self):
        # The parser of the set registered last would win without a word
        for (a, tags_a), (b, tags_b) in combinations(TAG_SETS.items(), 2):
            with self.subTest(a=a, b=b):
                self.assertEqual(tags_a & tags_b, set())
