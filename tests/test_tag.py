"""
Tests that _tag.py, kept by hand, stays as it was generated
"""

import unittest

from aioboinc._tag import Tag

TAGS = [(name, value) for name, value in vars(Tag).items() if not name.startswith("_")]


class TagTest(unittest.TestCase):

    def test_each_name_is_its_tag_in_upper_case(self):
        for name, value in TAGS:
            with self.subTest(name=name):
                self.assertEqual(name, value.upper())

    def test_the_tags_are_sorted(self):
        values = [value for _, value in TAGS]
        self.assertEqual(values, sorted(values))
