# coding: utf-8
import urllib2
import json

class DataCollector(object):
    def __init__(self, request, resource_url, url_lib=urllib2):
        self._request = request
        self._resource_url = resource_url
        self._url_lib = url_lib

        try:
            self._data = self._url_lib.urlopen(self._resource_url)
        except url_lib.URLError:
            raise ValueError("invalid resource url: '%s'".format(
                self._resource_url))

    def get_data(self):
        return json.loads(self._data.read())

class DeLorean(object):
    u"""
    Máquina do tempo para geração de bases de dados compatíveis com
    o legado do SciELO, partindo de APIs REST das novas apps.
    """
    def generate_title(self):
        return u'http://localhost:6543/files/title_2012-06-26_13:25:24.008242.zip'
