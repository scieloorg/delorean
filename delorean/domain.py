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
                out.addfile(info, StringIO.StringIO(data.encode('utf-8')))
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

    def __init__(self, resource_url, slumber_lib=slumber):
        self._resource_url = resource_url
        self._slumber_lib = slumber_lib

        self._api = self._slumber_lib.API(resource_url)
        self.resource = getattr(self._api, self._resource_name)

        # memoization to avoid unecessary field lookups
        # Ex.: _memo['publishers']['1'] = 'Unesp'
        self._memo = {}
        self._last_resource = {}

    def __iter__(self):
        offset = 0
        limit = ITEMS_PER_REQUEST
        err_count = 0

        while True:
            try:  # handles resource unavailability
                page = self.resource.get(offset=offset, limit=limit)
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
                self._last_resource = {}  # release the memory
                self._last_resource[res_lookup_key] = getattr(
                    self._api, endpoint)(res_id).get()

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
        import locale
        import calendar

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
                                                                     'electronic_issn',
                                                                     'scielo_issn',
                                                                     'resource_uri',
                                                                     'acronym',
                                                                     'title_iso',
                                                                     'use_license'
                                                                     ])

        # Formating publication date, must have 00 for the days digits.
        pub_month = "%02d" % obj['publication_end_month']
        obj['publication_date'] = str(obj['publication_year']) + pub_month + '00'

        sections = {}
        # lookup sections
        for section in obj['sections']:
            sectionid = section.strip('/').split('/')[-1]
            x = self._lookup_fields('sections', sectionid, ['resource_uri',
                                                            'titles'
                                                            ])

            for translation in x['titles']:
                sections.setdefault(translation[0], [])
                title = {
                    "title": translation[1],
                    "resource_id": x['resource_uri'].strip('/').split('/')[-1]
                }
                sections[translation[0]].append(title)

        obj['sections'] = sections

        # Issue Label ShortTitle

        obj['display'] = {}
        obj['display']['pt'] = "^lpt"
        obj['display']['en'] = "^len"
        obj['display']['es'] = "^les"

        # Short Title
        if 'short_title' in obj['journal']:
            obj['display']['pt'] += '^t' + obj['journal']['short_title']
            obj['display']['en'] += '^t' + obj['journal']['short_title']
            obj['display']['es'] += '^t' + obj['journal']['short_title']

        # Volume
        if 'volume' in obj:
            obj['display']['pt'] += '^vvol.' + obj['volume']
            obj['display']['en'] += '^vvol.' + obj['volume']
            obj['display']['es'] += '^vvol.' + obj['volume']

        # Volume Supplement
        if 'suppl_volume' in obj:
            obj['display']['pt'] += '^wsupl.' + obj['suppl_volume']
            obj['display']['en'] += '^wsuppl.' + obj['suppl_volume']
            obj['display']['es'] += '^wsupl.' + obj['suppl_volume']

        # Number
        if 'number' in obj:
            obj['display']['pt'] += '^nno.' + obj['number']
            obj['display']['en'] += '^nn.' + obj['number']
            obj['display']['es'] += '^nno.' + obj['number']

        # Number Supplement
        if 'suppl_number' in obj:
            obj['display']['pt'] += '^ssupl.' + obj['suppl_number']
            obj['display']['en'] += '^ssuppl.' + obj['suppl_number']
            obj['display']['es'] += '^ssupl.' + obj['suppl_number']

        # City
        if 'publication_city' in obj['journal']:
            obj['display']['pt'] += '^c' + obj['journal']['publication_city']
            obj['display']['en'] += '^c' + obj['journal']['publication_city']
            obj['display']['es'] += '^c' + obj['journal']['publication_city']

        # Period
        locale.setlocale(locale.LC_ALL, 'pt_BR'.encode('utf8'))
        obj['display']['pt'] += '^m' + calendar.month_abbr[obj['publication_start_month']] + './' + calendar.month_abbr[obj['publication_end_month']] + '.'
        locale.setlocale(locale.LC_ALL, 'en_US'.encode('utf8'))
        obj['display']['en'] += '^m' + calendar.month_abbr[obj['publication_start_month']] + './' + calendar.month_abbr[obj['publication_end_month']] + '.'
        locale.setlocale(locale.LC_ALL, 'es_ES'.encode('utf8'))
        obj['display']['es'] += '^m' + calendar.month_abbr[obj['publication_start_month']] + './' + calendar.month_abbr[obj['publication_end_month']] + '.'

        # Resetando locale para default.
        locale.setlocale(locale.LC_ALL, '')

        # Year
        obj['display']['pt'] += '^y' + str(obj['publication_year'])
        obj['display']['en'] += '^y' + str(obj['publication_year'])
        obj['display']['es'] += '^y' + str(obj['publication_year'])

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
                 datetime_lib=datetime,
                 titlecollector=TitleCollector,
                 sectioncollector=SectionCollector,
                 transformer=Transformer):

        self._datetime_lib = datetime_lib
        self._api_uri = api_uri
        self._titlecollector = titlecollector
        self._sectioncollector = sectioncollector
        self._transformer = transformer

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

    def generate_title(self, target='/tmp/'):
        """
        Starts the Title bundle generation, and returns the expected
        resource name.
        """
        HERE = os.path.abspath(os.path.dirname(__file__))
        expected_resource_name = self._generate_filename('title')

        # data generator
        iter_data = self._titlecollector(self._api_uri)

        # id file rendering
        transformer = self._transformer(filename=os.path.join(HERE,
            'templates/title_db_entry.txt'))
        id_string = transformer.transform_list(iter_data)

        # packaging
        packmeta = [('title.id', id_string)]
        pack = Bundle(*packmeta)
        pack.deploy(os.path.join(target, expected_resource_name))

        return expected_resource_name

    def generate_section(self, target='/tmp/'):
        """
        Starts the Section bundle generation, and returns the expected
        resource name.
        """
        HERE = os.path.abspath(os.path.dirname(__file__))
        expected_resource_name = self._generate_filename('section')

        # data generator
        iter_data = self._sectioncollector(self._api_uri)

        # id file rendering
        transformer = self._transformer(filename=os.path.join(HERE,
            'templates/section_db_entry.txt'))
        id_string = transformer.transform_list(iter_data)

        # packaging
        packmeta = [('section.id', id_string)]
        pack = Bundle(*packmeta)
        pack.deploy(os.path.join(target, expected_resource_name))

        return expected_resource_name


















