# coding: utf-8
from __future__ import unicode_literals

import time
import os
import tarfile
import StringIO
import tempfile
import collections
from datetime import datetime
import logging
from abc import (
    ABCMeta,
    abstractmethod,
)

import requests
from mako.template import Template
from mako.exceptions import RichTraceback
import slumber


logger = logging.getLogger(__name__)
ITEMS_PER_REQUEST = 50
MONTH_ABBREVS = {'es_ES': {1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr',
        5: 'may', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'sep', 10: 'oct',
        11: 'nov', 12: 'dic'}, 'en_US': {1: 'Jan', 2: 'Feb', 3: 'Mar',
        4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct',
        11: 'Nov', 12: 'Dec'}, 'pt_BR': {1: 'Jan', 2: 'Fev', 3: 'Mar',
        4: 'Abr', 5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out',
        11: 'Nov', 12: 'Dez'}}


class ResourceUnavailableError(Exception):
    def __init__(self, *args, **kwargs):
        super(ResourceUnavailableError, self).__init__(*args, **kwargs)


class Bundle(object):
    def __init__(self, *args, **kwargs):
        """
        Accepts an arbitrary number of logical name - data pairs::

          b = Bundle(('arq1', 'arq1 content as str'))
        """
        self._data = dict(args)

    def _tar(self):
        """
        Generate a tarball containing the data passed at init time.

        Returns a file handler.
        """
        tmp = tempfile.NamedTemporaryFile()
        out = tarfile.open(tmp.name, 'w')

        try:
            for name, data in self._data.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                out.addfile(info, StringIO.StringIO(data.encode('cp1252', 'replace')))
        finally:
            out.close()

        tmp.seek(0)
        return tmp

    def deploy(self, target):
        data = self._tar()

        base_path = os.path.split(os.path.splitext(target)[-2])[0]
        if not os.path.exists(base_path):
            os.makedirs(base_path, 0755)

        with open(target, 'w') as f:
            f.write(data.read())


class Transformer(object):
    """
    Responsible for rendering templates using the given
    dataset.
    """
    def __init__(self, *args, **kwargs):
        """
        Accepts a ``template`` as a string.
        """
        if args:
            self._template = Template(args[0])
        elif 'filename' in kwargs:
            self._template = Template(filename=kwargs['filename'],
                module_directory='/tmp/mako_modules')
        else:
            raise TypeError()

    def transform(self, data):
        """
        Renders a template using the given data.
        ``data`` must be dict.
        """
        if not isinstance(data, dict):
            raise TypeError('data must be dict')

        try:
            return self._template.render(**data)
        except NameError, exc:
            raise ValueError("there are some data missing: {}".format(exc))
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "File %s, line %s, in %s" % (filename, lineno, function)
                print line, "\n"
            print "%s: %s" % (str(traceback.error.__class__.__name__), traceback.error)

    def transform_list(self, data_list, callabl=None):
        """
        Renders a template using the given list of data.
        ``data_list`` must be list or tuple.
        """
        if isinstance(data_list, str) or isinstance(data_list, dict) or \
           isinstance(data_list, set):
            raise TypeError('data must be iterable')

        if not isinstance(data_list, collections.Iterable):
            raise TypeError('data must be iterable')

        res = []
        if callabl:
            callabl(data_list)

        for data in data_list:
            res.append(self.transform(data))

        return '\n'.join(res)

class DataCollector(object):
    """
    Responsible for collecting data from RESTful interfaces,
    and making them available as Python datastructures.

    Implements an iterable interface.
    """
    __metaclass__ = ABCMeta

    def __init__(self,
                 resource_url,
                 slumber_lib=slumber,
                 collection=None,
                 username=None,
                 api_key=None):
        self._resource_url = resource_url
        self._slumber_lib = slumber_lib

        self._api = self._slumber_lib.API(resource_url)
        self.resource = getattr(self._api, self._resource_name)

        self._collection = collection

        self._username = username
        self._api_key = api_key

        # memoization to avoid unecessary field lookups
        # Ex.: _memo['publishers']['1'] = 'Unesp'
        self._memo = {}
        self._last_resource = {}

    def fetch_data(self, offset, limit, collection=None):
        kwargs = {}

        if collection:
            kwargs['collection'] = collection

        if all([self._username, self._api_key]):
            kwargs['username'] = self._username
            kwargs['api_key'] = self._api_key

        return self.resource.get(offset=offset, limit=limit, **kwargs)

    def __iter__(self):
        offset = 0
        limit = ITEMS_PER_REQUEST
        err_count = 0

        while True:
            try:  # handles resource unavailability
                page = self.fetch_data(offset=offset, limit=limit, collection=self._collection)
            except requests.exceptions.ConnectionError as exc:
                if err_count < 10:
                    wait_secs = err_count * 5
                    logger.info('Connection failed. Waiting %ss to retry.' % wait_secs)
                    time.sleep(wait_secs)
                    err_count += 1
                    continue
                else:
                    logger.error('Unable to connect to resource (%s).' % exc)
                    raise ResourceUnavailableError(exc)
            else:
                for obj in page['objects']:
                    # we are interested only in non-trashed items.
                    if obj.get('is_trashed'):
                        continue

                    yield self.get_data(obj)

                if not page['meta']['next']:
                    raise StopIteration()
                else:
                    offset += ITEMS_PER_REQUEST
                    err_count = 0

    def _lookup_field(self, endpoint, res_id, field):

        def http_lookup():
            """
            The last accessed resource is cached,
            in order to improve multiple fields lookup
            on the same resouce.
            """
            res_lookup_key = '%s-%s' % (endpoint, res_id)
            if res_lookup_key not in self._last_resource:

                # authorization params
                kwargs = {}
                if all([self._username, self._api_key]):
                    kwargs['username'] = self._username
                    kwargs['api_key'] = self._api_key

                self._last_resource = {}  # release the memory
                self._last_resource[res_lookup_key] = getattr(
                    self._api, endpoint)(res_id).get(**kwargs)

            return self._last_resource[res_lookup_key]

        one_step_before = self._memo.setdefault(
                endpoint, {}).setdefault(
                    res_id, {})

        try:
            return one_step_before[field]
        except KeyError:
            one_step_before[field] = http_lookup()[field]
            return one_step_before[field]

    def _lookup_fields(self, endpoint, res_id, fields):

        attr_list = {}

        for field in fields:
            attr_list[field] = self._lookup_field(endpoint, res_id, field)

        return attr_list

    @abstractmethod
    def get_data(self, obj):
        """
        Get data from the specified resource and returns
        it as Python native datastructures.
        """


class IssueCollector(DataCollector):
    _resource_name = 'issues'

    def get_data(self, obj):

        # Formating date from 2012-07-18T17:47:09.564504 to 20120718
        obj['created'] = obj['created'][:10].replace('-', '')
        obj['updated'] = obj['updated'][:10].replace('-', '')

        # lookup journal
        journalid = obj['journal'].strip('/').split('/')[-1]
        obj['journal'] = self._lookup_fields('journals', journalid, ['title',
                                                                     'short_title',
                                                                     'publisher_name',
                                                                     'publication_city',
                                                                     'sponsors',
                                                                     'print_issn',
                                                                     'eletronic_issn',
                                                                     'scielo_issn',
                                                                     'resource_uri',
                                                                     'acronym',
                                                                     'title_iso',
                                                                     'use_license'
                                                                     ])

        # Formating publication date, must have 00 for the days digits.
        pub_month = "%02d" % obj['publication_end_month'] or u'00'
        obj['publication_date'] = unicode(obj['publication_year']) + pub_month + u'00'

        sections = {}
        # lookup sections
        for section in obj['sections']:
            sectionid = section.strip('/').split('/')[-1]
            x = self._lookup_fields('sections', sectionid, ['resource_uri',
                                                            'titles',
                                                            'code'
                                                            ])

            for translation in x['titles']:
                sections.setdefault(translation[0], [])
                title = {
                    "title": translation[1],
                    "resource_id": x['resource_uri'].strip('/').split('/')[-1],
                    "code": x['code']
                }
                sections[translation[0]].append(title)

        obj['sections'] = sections

        # Issue Label ShortTitle

        obj['display'] = {}
        obj['display']['pt'] = u"^lpt"
        obj['display']['en'] = u"^len"
        obj['display']['es'] = u"^les"

        # Short Title
        if 'short_title' in obj['journal'] and obj['journal']['short_title']:
            obj['display']['pt'] += u'^t' + unicode(obj['journal']['short_title'])
            obj['display']['en'] += u'^t' + unicode(obj['journal']['short_title'])
            obj['display']['es'] += u'^t' + unicode(obj['journal']['short_title'])

        # Volume
        if 'volume' in obj  and obj['volume']:
            obj['display']['pt'] += u'^vvol.' + unicode(obj['volume'])
            obj['display']['en'] += u'^vvol.' + unicode(obj['volume'])
            obj['display']['es'] += u'^vvol.' + unicode(obj['volume'])

        # Volume Supplement
        if 'suppl_volume' in obj and obj['suppl_volume']:
            obj['display']['pt'] += u'^wsupl.' + unicode(obj['suppl_volume'])
            obj['display']['en'] += u'^wsuppl.' + unicode(obj['suppl_volume'])
            obj['display']['es'] += u'^wsupl.' + unicode(obj['suppl_volume'])

        # Number
        if 'number' in obj and obj['number']:
            obj['display']['pt'] += u'^nno.' + unicode(obj['number'])
            obj['display']['en'] += u'^nn.' + unicode(obj['number'])
            obj['display']['es'] += u'^nno.' + unicode(obj['number'])

        # Number Supplement
        if 'suppl_number' in obj and obj['suppl_number']:
            obj['display']['pt'] += u'^ssupl.' + unicode(obj['suppl_number'])
            obj['display']['en'] += u'^ssuppl.' + unicode(obj['suppl_number'])
            obj['display']['es'] += u'^ssupl.' + unicode(obj['suppl_number'])

        # City
        if 'publication_city' in obj['journal'] and obj['journal']['publication_city']:
            obj['display']['pt'] += u'^c' + unicode(obj['journal']['publication_city'])
            obj['display']['en'] += u'^c' + unicode(obj['journal']['publication_city'])
            obj['display']['es'] += u'^c' + unicode(obj['journal']['publication_city'])

        for lang in ['pt_BR', 'en_US', 'es_ES']:
            numeric_start_month = obj['publication_start_month']
            numeric_end_month = obj['publication_end_month'] or u'00'

            if numeric_start_month in range(1, 13):
                start_month = MONTH_ABBREVS[lang][numeric_start_month]
            else:
                start_month = ''

            if numeric_end_month in range(1, 13):
                end_month = MONTH_ABBREVS[lang][numeric_end_month]
            else:
                end_month = ''

            if numeric_start_month != numeric_end_month:
                sub_m = './'.join([month for month in [start_month, end_month] if month])
            else:
                sub_m = start_month

            obj['display'][lang[:2]] += u'^m' + sub_m + u'.'

        # Year
        obj['display']['pt'] += u'^a' + unicode(obj['publication_year'])
        obj['display']['en'] += u'^a' + unicode(obj['publication_year'])
        obj['display']['es'] += u'^a' + unicode(obj['publication_year'])

        obj['order'] = str(obj['publication_year']) + str(obj['order'])

        return obj


class TitleCollector(DataCollector):
    _resource_name = 'journals'

    def get_data(self, obj):
        del(obj['collections'])
        del(obj['issues'])
        del(obj['resource_uri'])

        # dateiso format
        obj['created'] = obj['created'][:10].replace('-', '')
        obj['updated'] = obj['updated'][:10].replace('-', '')

        # get id from a string like: /api/v1/users/1/
        userid = obj['creator'].strip('/').split('/')[-1]

        obj['creator'] = self._lookup_field('users', userid, 'username')

        # lookup sponsors
        sponsors = []
        for sponsor in obj['sponsors']:
            spoid = sponsor.strip('/').split('/')[-1]
            sponsors.append(self._lookup_field('sponsors', spoid, 'name'))
        obj['sponsors'] = sponsors

        # pub_status_history
        pub_status_history = [[]]
        pub_status_history_reverse = list(reversed(obj['pub_status_history']))
        for event in pub_status_history_reverse:
            date = event['date'][:10].replace('-', '')
            if event['status'] == 'current':
                status = 'C'
            elif event['status'] == 'deceased':
                status = 'D'
            elif event['status'] == 'suspended':
                status = 'S'
            else:
                status = '?'

            if len(pub_status_history[-1]) < 2:
                pub_status_history[-1].append({'date': date, 'status': status})
            else:
                pub_status_history.append([{'date': date, 'status': status}])

        obj['pub_status_history'] = list(reversed(pub_status_history))

        # other titles
        other_titles = {}
        for title in obj['other_titles']:
            value = other_titles.setdefault(title[0], [])
            value.append(title[1])
        obj['other_titles'] = other_titles

        return obj


class SectionCollector(DataCollector):
    _resource_name = 'journals'

    def get_data(self, obj):
        del(obj['collections'])
        del(obj['issues'])
        del(obj['resource_uri'])
        del(obj['sponsors'])
        del(obj['creator'])
        del(obj['pub_status_history'])

        # lookup sections
        sections = []
        for section in obj['sections']:
            sectionid = section.strip('/').split('/')[-1]
            sections.append(self._lookup_fields('sections', sectionid, ['id', 'code', 'titles']))
        obj['sections'] = sections

        return obj


class DeLorean(object):
    """
    Represents a time machine, generating databases
    compatible with SciELO legacy apps (ISIS dbs)
    from RESTFul data sources.
    """
    def __init__(self,
                 api_uri,
                 username=None,
                 api_key=None,
                 datetime_lib=datetime,
                 titlecollector=TitleCollector,
                 issuecollector=IssueCollector,
                 sectioncollector=SectionCollector,
                 transformer=Transformer):

        self._datetime_lib = datetime_lib
        self._api_uri = api_uri
        self._titlecollector = titlecollector
        self._issuecollector = issuecollector
        self._sectioncollector = sectioncollector
        self._transformer = transformer
        self.username = username
        self.api_key = api_key

    def _generate_filename(self,
                           prefix,
                           filetype='tar',
                           fmt='%Y%m%d-%H:%M:%S:%f'):
        """
        Generates a string to be used as the bundle filename.
        Format: <prefix>-<data-fmt>.<filetype>>
        """
        now = self._datetime_lib.strftime(self._datetime_lib.now(), fmt)
        return '{0}.{1}'.format('-'.join([prefix, now]), filetype)

    def generate_title(self, target='/tmp/', collection=None):
        """
        Starts the Title bundle generation, and returns the expected
        resource name.
        """
        HERE = os.path.abspath(os.path.dirname(__file__))
        expected_resource_name = self._generate_filename('title')

        # data generator
        iter_data = self._titlecollector(self._api_uri,
                                         collection=collection,
                                         username=self.username,
                                         api_key=self.api_key)

        # id file rendering
        transformer = self._transformer(filename=os.path.join(HERE,
            'templates/title_db_entry.txt'))
        id_string = transformer.transform_list(iter_data)

        # packaging
        packmeta = [('title.id', id_string)]
        pack = Bundle(*packmeta)
        pack.deploy(os.path.join(target, expected_resource_name))

        return expected_resource_name

    def generate_issue(self, target='/tmp/', collection=None):
        """
        Starts the Issue bundle generation, and returns the expected
        resource name.
        """
        HERE = os.path.abspath(os.path.dirname(__file__))
        expected_resource_name = self._generate_filename('issue')

        # data generator
        iter_data = self._issuecollector(self._api_uri,
                                         collection=collection,
                                         username=self.username,
                                         api_key=self.api_key)

        # id file rendering
        transformer = self._transformer(filename=os.path.join(HERE,
            'templates/issue_db_entry.txt'))
        id_string = transformer.transform_list(iter_data)

        # packaging
        packmeta = [('issue.id', id_string)]
        pack = Bundle(*packmeta)
        pack.deploy(os.path.join(target, expected_resource_name))

        return expected_resource_name

    def generate_section(self, target='/tmp/', collection=None):
        """
        Starts the Section bundle generation, and returns the expected
        resource name.
        """
        HERE = os.path.abspath(os.path.dirname(__file__))
        expected_resource_name = self._generate_filename('section')

        # data generator
        iter_data = self._sectioncollector(self._api_uri,
                                           collection=collection,
                                           username=self.username,
                                           api_key=self.api_key)

        # id file rendering
        transformer = self._transformer(filename=os.path.join(HERE,
            'templates/section_db_entry.txt'))
        id_string = transformer.transform_list(iter_data)

        # packaging
        packmeta = [('section.id', id_string)]
        pack = Bundle(*packmeta)
        pack.deploy(os.path.join(target, expected_resource_name))

        return expected_resource_name
