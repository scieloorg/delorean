# coding: utf-8
from __future__ import unicode_literals
import os
import json
import unittest
import codecs
import tarfile

from mocker import (
    MockerTestCase,
    ANY,
    KWARGS,
)
from pyramid import testing


# Functional tests
###################
class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_app_status(self):
        from .views import app_status
        request = testing.DummyRequest()
        info = app_status(request)
        self.assertEqual(info['app_name'], 'delorean')


# Unit tests
#################
class DeLoreanTests(MockerTestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self, *args, **kwargs):
        from delorean.domain import DeLorean
        return DeLorean(*args, **kwargs)

    def test_generate_filename(self):
        dummy_datetime = self.mocker.mock()

        dummy_datetime.now()
        self.mocker.result(None)

        dummy_datetime.strftime(ANY, ANY)
        self.mocker.result('20120712-10:07:34:803942')

        self.mocker.replay()

        dl = self._makeOne('http://localhost:8000/api/v1/',
                           datetime_lib=dummy_datetime)
        self.assertEqual(dl._generate_filename('title'),
            'title-20120712-10:07:34:803942.tar')

    def test_generate_title_bundle(self):
        dummy_datetime = self.mocker.mock()
        dummy_titlecollector = self.mocker.mock()
        dummy_transformer = self.mocker.mock()

        dummy_datetime.now()
        self.mocker.result(None)

        dummy_datetime.strftime(ANY, ANY)
        self.mocker.result('20120712-10:07:34:803942')

        dummy_titlecollector(ANY, collection=ANY, username=None, api_key=None)
        self.mocker.result(dummy_titlecollector)

        dummy_transformer(filename=ANY)
        self.mocker.result(dummy_transformer)

        dummy_transformer.transform_list(ANY)
        self.mocker.result('!ID 0\n')

        self.mocker.replay()

        dl = self._makeOne('http://localhost:8000/api/v1/',
                           datetime_lib=dummy_datetime,
                           titlecollector=dummy_titlecollector,
                           transformer=dummy_transformer)
        bundle_url = dl.generate_title(collection='brasil')
        self.assertEqual(bundle_url,
            'title-20120712-10:07:34:803942.tar')


class DataCollectorTests(MockerTestCase):
    title_res = u'http://manager.scielo.org/api/v1/journal/brasil/0102-6720'
    valid_microset = u"""{"title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)"}"""
    valid_full_microset = {
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
        from delorean.domain import DataCollector

        class ConcreteDataCollector(DataCollector):
            _resource_name = 'journals'

            def get_data(self, data):
                return data

        return ConcreteDataCollector(resource_url, **kwargs)

    def test_instantiation(self):
        from delorean.domain import DataCollector
        self.assertRaises(TypeError, lambda: DataCollector(self.title_res))

    def test_fetch_all_data(self):
        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        dummy_journal.get(offset=0, limit=50)
        self.mocker.result(self.valid_full_microset)

        self.mocker.replay()

        dc = self._makeOne(self.title_res,
                           slumber_lib=dummy_slumber)

        res = dc.fetch_data(0, 50)
        self.assertIsInstance(res, dict)
        self.assertTrue('objects' in res)
        self.assertTrue(len(res['objects']), 1)

    def test_fetch_data_from_collection(self):
        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        dummy_journal.get(offset=0, limit=50, collection='brasil')
        self.mocker.result(self.valid_full_microset)

        self.mocker.replay()

        dc = self._makeOne(self.title_res,
                           slumber_lib=dummy_slumber,
                           collection='brasil')

        res = dc.fetch_data(0, 50, collection='brasil')
        self.assertIsInstance(res, dict)
        self.assertTrue('objects' in res)
        self.assertTrue(len(res['objects']), 1)


class TitleCollectorTests(MockerTestCase):
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

        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        self.mocker.replay()

        dc = self._makeOne(self.title_res,
                           slumber_lib=dummy_slumber,
                           collection='brasil')
        self.assertTrue(isinstance(dc, TitleCollector))

    def test_gen_iterable(self):
        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        self.mocker.replay()

        dc = self._makeOne(self.title_res,
            slumber_lib=dummy_slumber)
        it = iter(dc)
        self.assertTrue(hasattr(it, 'next'))

    def test_get_data(self):
        here = os.path.abspath(os.path.dirname(__file__))
        journal_data = {'meta': {'next': None}, 'objects': []}
        d = json.load(open(os.path.join(here,
            'tests_assets/journal_meta_beforeproc.json')))

        journal_data['objects'].append(d)

        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()
        dummy_user = self.mocker.mock()
        dummy_sponsor = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        dummy_journal.get(limit=50, offset=0) # Journal Metadata request
        self.mocker.result(journal_data)

        dummy_slumber.journals(ANY)
        self.mocker.result(dummy_journal)

        dummy_journal.get()
        self.mocker.result({'title': 'Previous title'})

        dummy_slumber.users(ANY)
        self.mocker.result(dummy_user)

        dummy_user.get()
        self.mocker.result(
            {
                'username': 'albert.einstein@scielo.org',
            }
        )

        dummy_slumber.sponsors(ANY)
        self.mocker.result(dummy_sponsor)

        dummy_sponsor.get()
        self.mocker.result(
            {
                'name': 'Colégio Brasileiro de Cirurgia Digestiva - CBCD'
            }
        )

        self.mocker.replay()

        dc = self._makeOne(self.title_res,
            slumber_lib=dummy_slumber)

        desired_journal_struct = json.load(open(os.path.join(here, 'tests_assets/journal_meta_afterproc.json')))

        for record in dc:
            for field, value in record.items():
                self.assertEqual(value, desired_journal_struct[field])


class SectionCollectorTests(MockerTestCase):
    section_res = u'http://manager.scielo.org/api/v1/'

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _makeOne(self, resource_url, **kwargs):
        from delorean.domain import SectionCollector
        return SectionCollector(resource_url, **kwargs)

    def test_instantiation(self):
        from delorean.domain import SectionCollector

        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        self.mocker.replay()

        dc = self._makeOne(self.section_res,
            slumber_lib=dummy_slumber)
        self.assertTrue(isinstance(dc, SectionCollector))

    def test_gen_iterable(self):
        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        self.mocker.replay()

        dc = self._makeOne(self.section_res,
            slumber_lib=dummy_slumber)
        it = iter(dc)
        self.assertTrue(hasattr(it, 'next'))

    def test_get_data(self):
        here = os.path.abspath(os.path.dirname(__file__))
        journal_data = {'meta': {'next': None}, 'objects': []}

        d = json.load(open(os.path.join(here, 'tests_assets/section_meta_beforeproc.json')))
        journal_data['objects'].append(d)

        section_data = {
                "code": "ABCD030",
                "titles": [
                    ["pt", "Artigos de Revisão"],
                    ["en", "Review Articles"]
                ],
                "id": "5676"
            }

        dummy_slumber = self.mocker.mock()
        dummy_journal = self.mocker.mock()
        dummy_section = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.journals
        self.mocker.result(dummy_journal)

        dummy_journal.get(offset=ANY, limit=ANY)
        self.mocker.result(journal_data)

        dummy_slumber.sections(ANY)
        self.mocker.result(dummy_section)
        self.mocker.count(10)

        dummy_section.get()
        self.mocker.result(section_data)
        self.mocker.count(10)

        self.mocker.replay()

        dc = self._makeOne(self.section_res,
            slumber_lib=dummy_slumber)

        desired_section_struct = json.load(open(os.path.join(here, 'tests_assets/section_meta_afterproc.json')))

        for record in dc:
            for field, value in desired_section_struct.items():
                if field == 'sections':
                        self.assertTrue(record['sections'][0] in value)


class IssueCollectorTests(MockerTestCase):
    issue_res = u'http://manager.scielo.org/api/v1/'
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
        from delorean.domain import IssueCollector
        return IssueCollector(resource_url, **kwargs)

    def test_instantiation(self):
        from delorean.domain import IssueCollector

        dummy_slumber = self.mocker.mock()
        dummy_issues = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.issues
        self.mocker.result(dummy_issues)

        self.mocker.replay()

        dc = self._makeOne(self.issue_res,
            slumber_lib=dummy_slumber)
        self.assertTrue(isinstance(dc, IssueCollector))

    def test_gen_iterable(self):
        dummy_slumber = self.mocker.mock()
        dummy_issues = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.issues
        self.mocker.result(dummy_issues)

        self.mocker.replay()

        dc = self._makeOne(self.issue_res,
            slumber_lib=dummy_slumber)
        it = iter(dc)
        self.assertTrue(hasattr(it, 'next'))

    def test_get_data(self):

        here = os.path.abspath(os.path.dirname(__file__))

        issue_data = {'meta': {'next': None}, 'objects': []}
        d = json.load(open(os.path.join(here, 'tests_assets/issue_meta_beforeproc.json')))
        issue_data['objects'].append(d)

        journal_data = {
            "title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)",
            "short_title": "ABCD, arq. bras. cir. dig.",
            "eletronic_issn": "",
            "print_issn": "0102-6720",
            "scielo_issn": "print",
            "publisher_name": "Colégio Brasileiro de Cirurgia Digestiva",
            "publication_city": "São Paulo",
            "sponsors": [
                "Brazilian Archives of Digestive Surgery"
            ],
            "resource_uri": "/api/v1/journals/2647/",
            "acronym": "ABCD",
            "title_iso": "ABCD, arq. bras. cir. dig",
            "use_license": {
                "disclaimer": "Licencia Creative Commons",
                "id": "1",
                "license_code": "BY-NC",
                "reference_url": None,
                "resource_uri": "/api/v1/uselicenses/1/"}
            }

        section_data = {
            "resource_uri": "/api/v1/sections/67221/",
            "titles":
                [
                    ["pt", "Técnica"],
                    ["en", "Technic"]
                ],
            "code": "CBCD-f28r"
        }

        dummy_slumber = self.mocker.mock()
        dummy_issue = self.mocker.mock()
        dummy_journal = self.mocker.mock()
        dummy_section = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.issues
        self.mocker.result(dummy_issue)

        dummy_issue.get(offset=ANY, limit=ANY)
        self.mocker.result(issue_data)

        dummy_slumber.journals(ANY)
        self.mocker.result(dummy_journal)
        self.mocker.count(1)

        dummy_journal.get()
        self.mocker.result(journal_data)
        self.mocker.count(1)

        dummy_slumber.sections(ANY)
        self.mocker.result(dummy_section)
        self.mocker.count(5)

        dummy_section.get()
        self.mocker.result(section_data)
        self.mocker.count(5)

        self.mocker.replay()

        dc = self._makeOne(self.issue_res,
            slumber_lib=dummy_slumber)

        desired_issue_struct = json.load(open(os.path.join(here, 'tests_assets/issue_meta_afterproc.json')))

        for record in dc:
            for field, value in desired_issue_struct.items():
                if not field in ('journal', 'sections', 'display'):
                    self.assertEqual(value, record[field])

                if field == 'journal':
                    for jfield, jvalue in value.items():
                        self.assertEqual(jvalue, record['journal'][jfield])

                if field == 'sections':
                    for sfield, svalue in value.items():
                        for idx, title in enumerate(svalue):
                            self.assertEqual(sorted(title), sorted(record['sections'][sfield][idx]))

                if field == 'display':
                    for dfield, dvalue in value.items():
                        self.assertEqual(dvalue, record['display'][dfield])

    def test_get_data_pub_monthly(self):

        here = os.path.abspath(os.path.dirname(__file__))

        issue_data = {'meta': {'next': None}, 'objects': []}
        d = json.load(open(os.path.join(here, 'tests_assets/issue_meta_beforeproc_pub_monthly.json')))
        issue_data['objects'].append(d)

        journal_data = {
            "title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)",
            "short_title": "ABCD, arq. bras. cir. dig.",
            "eletronic_issn": "",
            "print_issn": "0102-6720",
            "scielo_issn": "print",
            "publisher_name": "Colégio Brasileiro de Cirurgia Digestiva",
            "publication_city": "São Paulo",
            "sponsors": [
                "Brazilian Archives of Digestive Surgery"
            ],
            "resource_uri": "/api/v1/journals/2647/",
            "acronym": "ABCD",
            "title_iso": "ABCD, arq. bras. cir. dig",
            "use_license": {
                "disclaimer": "Licencia Creative Commons",
                "id": "1",
                "license_code": "BY-NC",
                "reference_url": None,
                "resource_uri": "/api/v1/uselicenses/1/"}
            }

        section_data = {
            "resource_uri": "/api/v1/sections/67221/",
            "titles":
                [
                    ["pt", "Técnica"],
                    ["en", "Technic"]
                ],
            "code": "CBCD-f28r"
        }

        dummy_slumber = self.mocker.mock()
        dummy_issue = self.mocker.mock()
        dummy_journal = self.mocker.mock()
        dummy_section = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.issues
        self.mocker.result(dummy_issue)

        dummy_issue.get(offset=ANY, limit=ANY)
        self.mocker.result(issue_data)

        dummy_slumber.journals(ANY)
        self.mocker.result(dummy_journal)
        self.mocker.count(1)

        dummy_journal.get()
        self.mocker.result(journal_data)
        self.mocker.count(1)

        dummy_slumber.sections(ANY)
        self.mocker.result(dummy_section)
        self.mocker.count(5)

        dummy_section.get()
        self.mocker.result(section_data)
        self.mocker.count(5)

        self.mocker.replay()

        dc = self._makeOne(self.issue_res,
            slumber_lib=dummy_slumber)

        desired_issue_struct = json.load(open(os.path.join(here, 'tests_assets/issue_meta_afterproc_pub_monthly.json')))

        for record in dc:
            for field, value in desired_issue_struct.items():
                if not field in ('journal', 'sections', 'display'):
                    self.assertEqual(value, record[field])

                if field == 'journal':
                    for jfield, jvalue in value.items():
                        self.assertEqual(jvalue, record['journal'][jfield])

                if field == 'sections':
                    for sfield, svalue in value.items():
                        for idx, title in enumerate(svalue):
                            self.assertEqual(sorted(title), sorted(record['sections'][sfield][idx]))

                if field == 'display':
                    for dfield, dvalue in value.items():
                        self.assertEqual(dvalue, record['display'][dfield])

    def test_get_data_special(self):

        here = os.path.abspath(os.path.dirname(__file__))

        issue_data = {'meta': {'next': None}, 'objects': []}
        d = json.load(open(os.path.join(here, 'tests_assets/issue_spe_meta_beforeproc.json')))
        issue_data['objects'].append(d)

        journal_data = {
            "title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)",
            "short_title": "ABCD, arq. bras. cir. dig.",
            "eletronic_issn": "",
            "print_issn": "0102-6720",
            "scielo_issn": "print",
            "publisher_name": "Colégio Brasileiro de Cirurgia Digestiva",
            "publication_city": "São Paulo",
            "sponsors": [
                "Brazilian Archives of Digestive Surgery"
            ],
            "resource_uri": "/api/v1/journals/2647/",
            "acronym": "ABCD",
            "title_iso": "ABCD, arq. bras. cir. dig",
            "use_license": {
                "disclaimer": "Licencia Creative Commons",
                "id": "1",
                "license_code": "BY-NC",
                "reference_url": None,
                "resource_uri": "/api/v1/uselicenses/1/"}
            }

        section_data = {
            "resource_uri": "/api/v1/sections/67221/",
            "titles":
                [
                    ["pt", "Técnica"],
                    ["en", "Technic"]
                ],
            "code": "CBCD-f28r"
        }

        dummy_slumber = self.mocker.mock()
        dummy_issue = self.mocker.mock()
        dummy_journal = self.mocker.mock()
        dummy_section = self.mocker.mock()

        dummy_slumber.API(ANY)
        self.mocker.result(dummy_slumber)

        dummy_slumber.issues
        self.mocker.result(dummy_issue)

        dummy_issue.get(offset=ANY, limit=ANY)
        self.mocker.result(issue_data)

        dummy_slumber.journals(ANY)
        self.mocker.result(dummy_journal)
        self.mocker.count(1)

        dummy_journal.get()
        self.mocker.result(journal_data)
        self.mocker.count(1)

        dummy_slumber.sections(ANY)
        self.mocker.result(dummy_section)
        self.mocker.count(5)

        dummy_section.get()
        self.mocker.result(section_data)
        self.mocker.count(5)

        self.mocker.replay()

        dc = self._makeOne(self.issue_res,
            slumber_lib=dummy_slumber)

        desired_issue_struct = json.load(open(os.path.join(here, 'tests_assets/issue_spe_meta_afterproc.json')))

        for record in dc:
            for field, value in desired_issue_struct.items():
                if not field in ('journal', 'sections', 'display'):
                    self.assertEqual(value, record[field])

                if field == 'journal':
                    for jfield, jvalue in value.items():
                        self.assertEqual(jvalue, record['journal'][jfield])

                if field == 'sections':
                    for sfield, svalue in value.items():
                        for idx, title in enumerate(svalue):
                            self.assertEqual(sorted(title), sorted(record['sections'][sfield][idx]))

                if field == 'display':
                    for dfield, dvalue in value.items():
                        self.assertEqual(dvalue, record['display'][dfield])

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
                item.update({'i': i})
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
        here = os.path.abspath(os.path.dirname(__file__))
        t = self._makeOne(filename=os.path.join(here, 'templates/title_db_entry.txt'))
        d = json.load(open(os.path.join(here, 'tests_assets/journal_meta_afterproc.json')))
        generated_id = t.transform(d).splitlines()
        canonical_id = codecs.open(os.path.join(here, 'tests_assets/journal_meta.id'), 'r', 'iso8859-1').readlines()

        del(generated_id[0])  # removing a blank line

        for i in xrange(len(generated_id)):
            self.assertEqual(generated_id[i].strip(), canonical_id[i].strip())

        self.assertEqual(len(generated_id), len(canonical_id))

    def test_title_db_generation_with_no_public_status(self):
        """
        Compares the generated with the expected id file
        line-by-line.
        """
        here = os.path.abspath(os.path.dirname(__file__))
        t = self._makeOne(filename=os.path.join(here, 'templates/title_db_entry.txt'))
        d = json.load(open(os.path.join(here, 'tests_assets/journal_meta_afterproc.json')))
        d['pub_status'] = u'inprogress'
        generated_id = t.transform(d).splitlines()
        canonical_id = codecs.open(os.path.join(here, 'tests_assets/journal_meta_notpublic.id'), 'r', 'iso8859-1').readlines()

        del(generated_id[0])  # removing a blank line

        for i in xrange(len(generated_id)):
            self.assertEqual(generated_id[i].strip(), canonical_id[i].strip())

        self.assertEqual(len(generated_id), len(canonical_id))

    def test_issue_db_generation(self):
        """
        Compares the generated with the expected id file
        line-by-line.
        """
        here = os.path.abspath(os.path.dirname(__file__))
        t = self._makeOne(filename=os.path.join(here, 'templates/issue_db_entry.txt'))
        d = json.load(open(os.path.join(here, 'tests_assets/issue_meta_afterproc.json')))
        generated_id = t.transform(d).splitlines()
        canonical_id = codecs.open(os.path.join(here, 'tests_assets/issue_meta.id'), 'r', 'iso8859-1').readlines()

        del(generated_id[0])  # removing a blank line

        for i in xrange(len(canonical_id)):
            self.assertEqual(generated_id[i].strip(), canonical_id[i].strip())

        self.assertEqual(len(generated_id), len(canonical_id))

    def test_issue_db_generation_special(self):
        """
        Compares the generated with the expected id file
        line-by-line.
        """
        here = os.path.abspath(os.path.dirname(__file__))
        t = self._makeOne(filename=os.path.join(here, 'templates/issue_db_entry.txt'))
        d = json.load(open(os.path.join(here, 'tests_assets/issue_spe_meta_afterproc.json')))
        generated_id = t.transform(d).splitlines()
        canonical_id = codecs.open(os.path.join(here, 'tests_assets/issue_spe_meta.id'), 'r', 'iso8859-1').readlines()

        del(generated_id[0])  # removing a blank line

        for i in xrange(len(canonical_id)):
            self.assertEqual(generated_id[i].strip(), canonical_id[i].strip())

        self.assertEqual(len(generated_id), len(canonical_id))

    def test_section_db_generation(self):
        """
        Compares the generated with the expected id file
        line-by-line.
        """
        here = os.path.abspath(os.path.dirname(__file__))
        t = self._makeOne(filename=os.path.join(here, 'templates/section_db_entry.txt'))
        d = json.load(open(os.path.join(here, 'tests_assets/section_meta_afterproc.json')))
        generated_id = t.transform(d).splitlines()
        canonical_id = codecs.open(os.path.join(here, 'tests_assets/section_meta.id'), 'r', 'iso8859-1').readlines()

        del(generated_id[0])  # removing a blank line

        for i in xrange(len(canonical_id)):
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

class ResourceUnavailableErrorTests(unittest.TestCase):

    def test_raise(self):
        from delorean.domain import ResourceUnavailableError
        self.assertTrue(issubclass(ResourceUnavailableError, BaseException))
