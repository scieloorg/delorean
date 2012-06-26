# coding: utf-8
import unittest

from mocker import (
    Mocker,
    ANY,
)
from pyramid import testing


# Mocks
#################
def dummy_urllib2_factory(json_data):
    class DummyFile(object):
        def read(self):
            return json_data

    mocker = Mocker()
    url_handler = mocker.mock()
    url_handler.urlopen(ANY)
    mocker.result(DummyFile())

    url_handler.URLError
    mocker.result(type('URLError', (Exception,), {}))

    mocker.replay()

    return url_handler


# Functional tests
#################
class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_my_view(self):
        from .views import my_view
        request = testing.DummyRequest()
        info = my_view(request)
        self.assertEqual(info['project'], 'delorean')


# Unit tests
#################
class DeLoreanTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self):
        from delorean.domain import DeLorean
        return DeLorean()

    def test_generate_serial_bundle(self):
        dl = self._makeOne()
        bundle_url = dl.generate_title()
        self.assertEqual(bundle_url,
            u'http://localhost:6543/files/title_2012-06-26_13:25:24.008242.zip')


class DataCollectorTests(unittest.TestCase):
    title_res = u'http://manager.scielo.org/api/v1/journal/brasil/0102-6720'
    valid_microset = u"""{"title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)"}"""

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self, request, resource_url, **kwargs):
        from delorean.domain import DataCollector
        return DataCollector(request, resource_url, **kwargs)

    def test_instantiation(self):
        from delorean.domain import DataCollector
        request = testing.DummyRequest()

        dc = self._makeOne(request, self.title_res,
            url_lib=dummy_urllib2_factory(self.valid_microset))
        self.assertTrue(isinstance(dc, DataCollector))

    def test_get_data(self):
        request = testing.DummyRequest()
        import json

        dc = self._makeOne(request, self.title_res,
            url_lib=dummy_urllib2_factory(self.valid_microset))
        data = dc.get_data()
        self.assertTrue(isinstance(data, dict))
        self.assertEqual(data, json.loads(self.valid_microset))