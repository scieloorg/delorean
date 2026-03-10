import os


DEFAULT_BUNDLE_DIR = '/tmp/delorean-public'


def get_bundle_dir():
    return os.environ.get('DELOREAN_BUNDLE_DIR', DEFAULT_BUNDLE_DIR)
