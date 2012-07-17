# coding: utf-8
from __future__ import unicode_literals

import urllib2
import json
import os
import tarfile
import StringIO
import tempfile
import collections
from datetime import datetime
from abc import (
    ABCMeta,
    abstractmethod,
)

from mako.template import Template
import slumber

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
                out.addfile(info, StringIO.StringIO(data))
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

    def __iter__(self):
        offset=0

        while True:
            page = self.resource.get(offset=offset)

            for obj in page['objects']:
                # we are interested only in non-trashed items.
                if obj.get('is_trashed'):
                    continue

                yield self.get_data(obj)

            if not page['meta']['next']:
                raise StopIteration()
            else:
                offset += 20

    @abstractmethod
    def get_data(self, obj):
        """
        Get data from the specified resource and returns
        it as Python native datastructures.
        """

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
        obj['creator'] = self._api.users(userid).get()['username']

        # lookup publishers
        publishers = []
        for publisher in obj['publishers']:
            pubid = publisher.strip('/').split('/')[-1]
            publishers.append(self._api.publishers(pubid).get()['name'])
        obj['publishers'] = publishers

        # lookup sponsors
        sponsors = []
        for sponsor in obj['sponsors']:
            spoid = sponsor.strip('/').split('/')[-1]
            sponsors.append(self._api.sponsors(spoid).get()['name'])
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
                 transformer=Transformer):

        self._datetime_lib = datetime_lib
        self._api_uri = api_uri
        self._titlecollector = titlecollector
        self._transformer = transformer

    def _generate_filename(self, prefix, filetype='tar', fmt='%Y%m%d-%H:%M:%S:%f'):
        now = self._datetime_lib.strftime(self._datetime_lib.now(), fmt)
        return '{0}.{1}'.format('-'.join([prefix, now]), filetype)

    def generate_title(self):
        """
        Starts the Title bundle generation, and returns the expected
        resource name. This method returns asynchronously, so the
        consumer will need to wait until the resource turns available.
        """
        HERE = os.path.abspath(os.path.dirname(__file__))

        expected_resource_name = self._generate_filename('title')
        iter_data = self._titlecollector(self._api_uri)
        transformer = self._transformer(filename=os.path.join(HERE,
            'templates/title_db_entry.txt'))
        id_string = transformer.transform_list(iter_data)

        return expected_resource_name