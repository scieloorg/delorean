# coding: utf-8
import os
import time

from .domain import DeLorean

from pyramid.view import view_config
from pyramid import httpexceptions

HERE = os.path.abspath(os.path.dirname(__file__))
RESOURCE_HANDLERS = {
    'title': 'generate_title',
    'issue': 'generate_issue',
    'section': 'generate_section'
}

ENV_SETTINGS_MAP = {
    'delorean.manager_access_username': 'DELOREAN_MANAGER_ACCESS_USERNAME',
    'delorean.manager_access_api_key': 'DELOREAN_MANAGER_ACCESS_API_KEY',
    'delorean.manager_access_uri': 'DELOREAN_MANAGER_ACCESS_URI',
}


def _get_setting(settings, key):
    value = settings.get(key)
    if value:
        return value
    return os.environ.get(ENV_SETTINGS_MAP[key])


@view_config(route_name='home', renderer='jsonp')
def app_status(request):
    # scielomanager availability
    return {'app_name': 'delorean'}


@view_config(route_name="generate", renderer='jsonp')
def bundle_generator(request):
    start_time = time.time()
    resource_name = request.matchdict.get('resource')
    collection = request.GET.get('collection', None)
    settings = request.registry.settings
    username = _get_setting(settings, 'delorean.manager_access_username')
    api_key = _get_setting(settings, 'delorean.manager_access_api_key')
    api_uri = _get_setting(settings, 'delorean.manager_access_uri')

    if not all([username, api_key, api_uri]):
        raise httpexceptions.HTTPInternalServerError(
            comment='missing configuration')

    dl = DeLorean(api_uri, username=username, api_key=api_key)

    try:
        bundle_url = getattr(dl, RESOURCE_HANDLERS[resource_name])(
            os.path.join(HERE, 'public'), collection=collection)
    except KeyError:
        raise httpexceptions.HTTPNotFound()

    return {
        'resource_name': resource_name,
        'expected_bundle_url': request.static_url(
            'delorean:public/%s' % bundle_url
        ),
        'elapsed_time': time.time() - start_time,
    }
