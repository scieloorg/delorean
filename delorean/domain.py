# coding: utf-8
import urllib2
import json
import string
import os
import zipfile
import datetime


class Bundle(object):
    def __init__(self, *args, **kwargs):
        # dependencie injection
        if 'zip_lib' not in kwargs:
            zip_lib = zipfile
        if 'datetime_lib' not in kwargs:
            datetime_lib = datetime

        self._data = args
        self._zip_lib = zip_lib
        self._datetime_lib = datetime_lib

    def deploy(self, target, extracted_filename=None):
        if not extracted_filename:
            # use the target name
            extracted_filename = os.path.split(os.path.splitext(target)[-2])[-1]

        # zip metadata
        zi = self._zip_lib.ZipInfo(extracted_filename)
        zi.date_time = datetime.datetime.timetuple(
           self._datetime_lib.datetime.now())
        zi.external_attr = 0755 << 16L

        base_path = os.path.split(os.path.splitext(target)[-2])[0]
        if not os.path.exists(base_path):
            os.makedirs(base_path, 0755)

        with self._zip_lib.ZipFile(target, 'w') as f:
            for data in self._data:
                f.writestr(zi, data)


class Transformer(object):
    """
    Responsible for rendering templates using the given
    dataset.
    """
    def __init__(self, template):
        """
        Accepts a ``template`` as a string.
        """
        self._template = string.Template(template)

    def transform(self, data):
        """
        Renders a template using the given data.
        ``data`` must be dict.
        """
        if not isinstance(data, dict):
            raise TypeError('data must be dict')

        try:
            return self._template.substitute(data)
        except KeyError, exc:
            raise ValueError("there are some data missing: {}".format(exc))

    def transform_list(self, data_list, callabl=None):
        """
        Renders a template using the given list of data.
        ``data_list`` must be list or tuple.
        """
        if not isinstance(data_list, list) and not isinstance(data_list, tuple):
            raise TypeError('data must be list or tuple')

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
    """
    def __init__(self, resource_url, url_lib=urllib2):
        self._resource_url = resource_url
        self._url_lib = url_lib

        try:
            self._data = self._url_lib.urlopen(self._resource_url)
        except url_lib.URLError:
            raise ValueError("invalid resource url: '%s'".format(
                self._resource_url))

    def get_data(self):
        """
        Get data from the specified resource and returns
        it as Python native datastructures.
        """
        return json.loads(self._data.read())

class DeLorean(object):
    """
    Represents a time machine, generating databases
    compatible with SciELO legacy apps (ISIS dbs)
    from RESTFul data sources.
    """
    def generate_title(self):
        return u'http://localhost:6543/files/title_2012-06-26_13:25:24.008242.zip'
