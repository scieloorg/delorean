# coding: utf-8
import urllib2
import json
import os
import zipfile
import datetime
import tarfile
import StringIO
import tempfile

from mako.template import Template

class Bundle(object):
    def __init__(self, *args, **kwargs):
        """
        Accepts an arbitrary number of logical name - data pairs::

          b = Bundle(('arq1', 'arq1 content as str'))
        """

        # dependencie injection
        if 'zip_lib' not in kwargs:
            zip_lib = zipfile
        if 'datetime_lib' not in kwargs:
            datetime_lib = datetime

        self._data = dict(args)
        self._zip_lib = zip_lib
        self._datetime_lib = datetime_lib

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
