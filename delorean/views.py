# coding: utf-8
import os
import time

from .domain import DeLorean

from pyramid.view import view_config
from pyramid import httpexceptions

HERE = os.path.abspath(os.path.dirname(__file__))
SCIELOMANAGER_API_URI = 'http://localhost:8000/api/v1/'
RESOURCE_HANDLERS = {
    'title': 'generate_title',
    'section': 'generate_section'
}


@view_config(route_name='home', renderer='jsonp')
def app_status(request):
    # scielomanager availability
    return {'app_name': 'delorean'}


@view_config(route_name="generate", renderer='jsonp')
def bundle_generator(request):
    start_time = time.time()
    resource_name = request.matchdict.get('resource')
    collection = request.GET.get('collection', None)

    dl = DeLorean(SCIELOMANAGER_API_URI)

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
