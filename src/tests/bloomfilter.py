"""
Test bloomfilter packages.

This module is imported from core tests module and ran by nose.
"""

import hashlib
import random  # nosec
import string
import StringIO
import unittest
from importlib import import_module

# import inventory


def have_package(pkg_name):
    try:
        return getattr(have_package, pkg_name)
    except AttributeError:
        pass
    try:
        pkg = import_module(pkg_name)
    except ImportError:
        pkg = False
    setattr(have_package, pkg_name, pkg)
    return pkg


pybloomfilter = have_package('pybloomfilter')
pybloom = have_package('pybloom_live') or have_package('pybloom')
pybloof = have_package('pybloof')


if pybloof:
    class BloomfilterPybloof(pybloof.StringBloomFilter):
        def __init__(self, capacity, error_rate=0.001):
            self.capacity = capacity
            self.error_rate = error_rate
            kwargs = pybloof.bloom_calculator(capacity, error_rate)
            super(BloomfilterPybloof, self).__init__(**kwargs)

    pybloof.BloomFilter = BloomfilterPybloof


# TODO: make this an option
# _inventory = inventory.Inventory()
_inventory = list(set(
    hashlib.sha512(
        ''.join(random.choice(string.lowercase) for x in range(32))
    ).digest()[32:] for _ in range(100000)
))

_hashes_absent = _inventory[-50000:]
_inventory = [[item] for item in _inventory[:50000]]
_hashes_present = [
    random.choice(_inventory)[0] for _ in range(10000)
]
_filters = {}


class BloomfilterTestCase(object):
    """Base class for bloomfilter test case"""
    def setUp(self):
        print('\n')
        if self.filter is None:
            self.skipTest('package not found')

    def _filter_class(self):
        filter_cls = getattr(self, 'filter_cls', 'BloomFilter')
        return getattr(self._filter_mod, filter_cls)

    def _export(self):
        return self.filter.to_base64()

    def _import(self, data):
        return self._filter_class().from_base64(data)

    @property
    def filter(self):
        filter_obj = _filters.get(self._filter_mod)
        if filter_obj is None:
            if not self._filter_mod:
                return
            filtersize = 1000 * (int(len(_inventory) / 1000.) + 1)
            errorrate = 1 / 1000.
            filter_obj = _filters[self._filter_mod] = self._filter_class(
            )(filtersize, errorrate)
            print(
                'Filter class: %s\n'
                'Filter capacity: %i and error rate: %.3f%%\n' % (
                    type(filter_obj), filter_obj.capacity,
                    100 * filter_obj.error_rate
                )
            )
        return filter_obj

    def test_0_add(self):
        """Add all Inventory hashes to the filter"""
        for row in _inventory:
            self.filter.add(row[0])

    def test_absence(self):
        """Check absence of hashes in the filter"""
        errors = sum(sample in self.filter for sample in _hashes_absent)
        # print('Errors: %s from %s' % (errors, len(_hashes_absent)))
        self.assertLessEqual(errors, len(_hashes_absent) / 1000. + 1)

    def test_presence(self):
        """Check presence of hashes in the filter"""
        for sample in _hashes_present:
            self.assertTrue(sample in self.filter)

    def test_portability(self):
        """Check filter's export/import ability"""
        filter_copy = self._import(self._export())
        self.assertTrue(random.choice(_hashes_present) in filter_copy)
        self.assertFalse(random.choice(_hashes_absent) in filter_copy)


class TestPybloomfiltermmap(BloomfilterTestCase, unittest.TestCase):
    _filter_mod = pybloomfilter


class TestPybloom(BloomfilterTestCase, unittest.TestCase):
    _filter_mod = pybloom

    def _export(self):
        output = StringIO.StringIO()
        self.filter.tofile(output)
        return output.getvalue().encode('base64')

    def _import(self, data):
        return self._filter_class().fromfile(
            StringIO.StringIO(data.decode('base64'))
        )


class TestPybloof(BloomfilterTestCase, unittest.TestCase):
    _filter_mod = pybloof
