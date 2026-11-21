"""
Tests for the sets that tell the parser the type of each element
"""

import unittest
from itertools import combinations

from aioboinc import _parse

TAG_SETS = {
    name: set(getattr(_parse, name))
    for name in (
        "INTEGER_TAG",
        "FLOAT_TAG",
        "BOOL_TAG",
        "TIME_TAG",
        "TIMEDELTA_TAG",
        "LIST_TAG",
        # A dict of the parser of the value by tag
        "BY_RESOURCE_TAG",
        "RESOURCE_NAMES_TAG",
    )
}


class TagSetsTest(unittest.TestCase):

    def test_no_tag_is_in_two_sets(self):
        # One would win over the other without a word: the set registered last, or the per
        # resource handling over the type of the element
        for (a, tags_a), (b, tags_b) in combinations(TAG_SETS.items(), 2):
            with self.subTest(a=a, b=b):
                self.assertEqual(tags_a & tags_b, set())
