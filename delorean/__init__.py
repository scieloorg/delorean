import os

from pyramid.config import Configurator
from pyramid.renderers import JSONP

from .settings import get_bundle_dir


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    config.add_renderer('jsonp', JSONP(param_name='callback'))

    bundle_dir = get_bundle_dir()
    if not os.path.exists(bundle_dir):
        os.makedirs(bundle_dir, 0o755)
    config.add_static_view('public', bundle_dir, cache_max_age=3600)

    config.add_route('home', '/')
    config.add_route('generate', '/generate/{resource}')
    config.scan()
    return config.make_wsgi_app()
