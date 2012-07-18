# coding: utf-8
from __future__ import unicode_literals

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

def dummy_slumber_factory(json_data):
    mocker = Mocker()
    dummy_slumber = mocker.mock()
    dummy_journal = mocker.mock()
    dummy_user = mocker.mock()
    dummy_publisher = mocker.mock()
    dummy_sponsor = mocker.mock()

    # Slumber
    dummy_slumber.API(ANY)
    mocker.result(dummy_slumber)

    # Journals resource
    dummy_slumber.journals
    mocker.result(dummy_journal)

    dummy_journal.get(offset=ANY)
    mocker.result(json_data)

    # Users resource
    dummy_slumber.users(ANY)
    mocker.result(dummy_user)

    dummy_user.get()
    mocker.result(
        {
            'username': 'albert.einstein@scielo.org',
        }
    )

    # Publishers resource
    dummy_slumber.publishers(ANY)
    mocker.result(dummy_publisher)

    dummy_publisher.get()
    mocker.result(
        {
            'name': 'Colégio Brasileiro de Cirurgia Digestiva'
        }
    )

    # Sponsors resource
    dummy_slumber.sponsors(ANY)
    mocker.result(dummy_sponsor)

    dummy_sponsor.get()
    mocker.result(
        {
            'name': 'Colégio Brasileiro de Cirurgia Digestiva - CBCD'
        }
    )

    mocker.replay()
    return dummy_slumber

def dummy_datetime_factory():
    mocker = Mocker()
    dummy_datetime = mocker.mock()

    dummy_datetime.now()
    mocker.result(None)

    dummy_datetime.strftime(ANY, ANY)
    mocker.result('20120712-10:07:34:803942')

    mocker.replay()
    return dummy_datetime


def dummy_titlecollector_factory():
    mocker = Mocker()
    dummy_titlecollector = mocker.mock()

    dummy_titlecollector(ANY)
    mocker.result(dummy_titlecollector)

    iter(dummy_titlecollector)
    mocker.result(({'foo': rec} for rec in range(10)))

    mocker.replay()
    return dummy_titlecollector

def dummy_transformer_factory():
    mocker = Mocker()
    dummy_transformer = mocker.mock()

    dummy_transformer(filename=ANY)
    mocker.result(dummy_transformer)

    dummy_transformer.transform_list(ANY)
    mocker.result('!ID 0\n')

    mocker.replay()
    return dummy_transformer

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

    def _makeOne(self, *args, **kwargs):
        from delorean.domain import DeLorean
        return DeLorean(*args, **kwargs)

    def test_generate_filename(self):
        dl = self._makeOne('http://localhost:8000/api/v1/',
                           datetime_lib=dummy_datetime_factory())
        self.assertEqual(dl._generate_filename('title'),
            'title-20120712-10:07:34:803942.tar')

    def test_generate_title_bundle(self):
        dl = self._makeOne('http://localhost:8000/api/v1/',
                           datetime_lib=dummy_datetime_factory(),
                           titlecollector=dummy_titlecollector_factory(),
                           transformer=dummy_transformer_factory())
        bundle_url = dl.generate_title()
        self.assertEqual(bundle_url,
            'title-20120712-10:07:34:803942.tar')


class DataCollectorTests(unittest.TestCase):
    title_res = u'http://manager.scielo.org/api/v1/journal/brasil/0102-6720'
    valid_microset = u"""{"title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)"}"""

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self, resource_url, **kwargs):
        from delorean.domain import DataCollector
        return DataCollector(resource_url, **kwargs)

    def test_instantiation(self):
        from delorean.domain import DataCollector

        self.assertRaises(TypeError, lambda: self._makeOne(self.title_res))


class TitleCollectorTests(unittest.TestCase):
    title_res = u'http://manager.scielo.org/api/v1/'
    valid_microset = {
        'objects': [
            {'title': 'ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)'},
        ],
        'meta': {'next': None},
    }

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self, resource_url, **kwargs):
        from delorean.domain import TitleCollector
        return TitleCollector(resource_url, **kwargs)

    def test_instantiation(self):
        from delorean.domain import TitleCollector

        dc = self._makeOne(self.title_res,
            slumber_lib=dummy_slumber_factory(self.valid_microset))
        self.assertTrue(isinstance(dc, TitleCollector))

    def test_gen_iterable(self):
        from delorean.domain import TitleCollector

        dc = self._makeOne(self.title_res,
            slumber_lib=dummy_slumber_factory(self.valid_microset))
        it = iter(dc)
        self.assertTrue(hasattr(it, 'next'))

    def test_get_data(self):
        import os
        import json
        from delorean.domain import TitleCollector
        here = os.path.abspath(os.path.dirname(__file__))

        wrapper_struct = {'meta': {'next': None}, 'objects': []}
        d = json.load(open(os.path.join(here, 'tests_assets/journal_meta_beforeproc.json')))
        wrapper_struct['objects'].append(d)

        dc = self._makeOne(self.title_res,
            slumber_lib=dummy_slumber_factory(wrapper_struct))

        desired_journal_struct = json.load(open(os.path.join(here, 'tests_assets/journal_meta_afterproc.json')))

        for record in dc:
            for field, value in record.items():
                self.assertEqual(value, desired_journal_struct[field])


class TransformerTests(unittest.TestCase):
    tpl_basic = u'Pra frente, ${country}'
    tpl_basic_id = u'!ID ${i}\n!v100!${title}'
    tpl_basic_compound = u"""
    !ID 0
    !v100!${title}
    % for l in languages:
    !v350!${l['iso_code']}
    % endfor
    """.strip()

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self, *args, **kwargs):
        from delorean.domain import Transformer
        return Transformer(*args, **kwargs)

    def test_instantiation(self):
        from delorean.domain import Transformer
        t = self._makeOne(self.tpl_basic)
        self.assertTrue(isinstance(t, Transformer))

    def test_basic_transformation(self):
        t = self._makeOne(self.tpl_basic)
        result = t.transform({'country': 'Brasil'})
        self.assertEqual(result, u'Pra frente, Brasil')

    def test_transformation_missing_data(self):
        t = self._makeOne(self.tpl_basic)
        self.assertRaises(ValueError, t.transform, {})

    def test_transformation_wrong_typed_data(self):
        t = self._makeOne(self.tpl_basic)
        types = [[], 1, (), 'str', set()]
        for typ in types:
            self.assertRaises(TypeError, t.transform, typ)

    def test_basic_list_transformation(self):
        t = self._makeOne(self.tpl_basic)
        data_list = [{'country': 'Brasil'}, {'country': 'Egito'}]
        result = t.transform_list(data_list)
        expected_result = u'Pra frente, Brasil\nPra frente, Egito'
        self.assertEqual(result, expected_result)

    def test_transformation_missing_data_list(self):
        t = self._makeOne(self.tpl_basic)
        self.assertRaises(ValueError, t.transform_list,
            [{'country': 'Brasil'}, {}])

    def test_transformation_wrong_typed_data_list(self):
        t = self._makeOne(self.tpl_basic)
        types = [1, 'str', {}, set()]
        for typ in types:
            self.assertRaises(TypeError, t.transform_list, typ)

    def test_transformation_iterable_data(self):
        t = self._makeOne(self.tpl_basic)

        def item_factory():
            for i in range(2):
                yield {'country': 'Brasil%s' % i}

        result = t.transform_list(item_factory())
        expected_result = u'Pra frente, Brasil0\nPra frente, Brasil1'
        self.assertEqual(result, expected_result)


    def test_transformation_with_callable(self):
        """
        !ID 0
        !v100!Revista Brasileira
        !ID 1
        !v100!Revista Mexicana
        """
        t = self._makeOne(self.tpl_basic_id)

        def add_index(data_list):
            i = 0
            for item in data_list:
                item.update({'i':i})
                i += 1

        result = t.transform_list(
            [{'title': 'Revista Brasileira'},
             {'title': 'Revista Mexicana'}], add_index)
        self.assertEqual([part.strip() for part in result.split('\n')],
            u'!ID 0\n!v100!Revista Brasileira\n!ID 1\n!v100!Revista Mexicana'.split('\n'))

    def test_compound_transformation(self):
        t = self._makeOne(self.tpl_basic_compound)
        d = {
          'title': "ABCD. Arquivos Brasileiros",
          'languages': [
            {'iso_code': 'en'},
            {'iso_code': 'pt'},
          ],
        }
        result = t.transform(d)
        self.assertEqual([part.strip() for part in result.split('\n')],
            u'!ID 0\n!v100!ABCD. Arquivos Brasileiros\n!v350!en\n!v350!pt\n'.split('\n'))

    def test_compound_transformation_filebased(self):
        import os
        here = os.path.abspath(os.path.dirname(__file__))
        t = self._makeOne(filename=os.path.join(here, 'tests_assets/basic_compound.txt'))
        d = {
          'title': "ABCD. Arquivos Brasileiros",
          'languages': [
            {'iso_code': 'en'},
            {'iso_code': 'pt'},
          ],
        }
        result = t.transform(d)
        self.assertEqual([part.strip() for part in result.split('\n')],
            u'!ID 0\n!v100!ABCD. Arquivos Brasileiros\n!v350!en\n!v350!pt\n'.split('\n'))

    def test_title_db_generation(self):
        """
        Compares the generated with the expected id file
        line-by-line.
        """
        import os, json, codecs

        here = os.path.abspath(os.path.dirname(__file__))
        t = self._makeOne(filename=os.path.join(here, 'templates/title_db_entry.txt'))
        d = json.load(open(os.path.join(here, 'tests_assets/journal_meta_afterproc.json')))
        generated_id = t.transform(d).splitlines()
        canonical_id = codecs.open(os.path.join(here, 'tests_assets/journal_meta.id'), 'r', 'iso8859-1').readlines()

        del(generated_id[0]) #removing a blank line

        removed_fields = []
        for i in xrange(len(generated_id)):
            if canonical_id[i] in removed_fields:
               del(canonical_id[i])
            self.assertEqual(generated_id[i].strip(), canonical_id[i].strip())

        self.assertEqual(len(generated_id), len(canonical_id))

class BundleTests(unittest.TestCase):
    basic_data = [(u'arq_a', u'Arq A content'),
                  (u'arq_b', u'Arq B content')]

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self, *args, **kwargs):
        from delorean.domain import Bundle
        return Bundle(*args, **kwargs)

    def test_instantiation(self):
        from delorean.domain import Bundle
        p = self._makeOne(*self.basic_data)
        self.assertTrue(isinstance(p, Bundle))

    def test_generate_tarball(self):
        import tarfile
        data_as_dict = dict(self.basic_data)
        p = self._makeOne(*self.basic_data)
        tar_handler = p._tar()
        self.assertTrue(hasattr(tar_handler, 'read'))
        self.assertTrue(hasattr(tar_handler, 'name'))

        t = tarfile.open(tar_handler.name, 'r')
        for member in t.getmembers():
            self.assertTrue(member.name in data_as_dict)

    def test_deploy_data(self):
        p = self._makeOne(*self.basic_data)
        p.deploy('/tmp/files/zippedfile.tar')


