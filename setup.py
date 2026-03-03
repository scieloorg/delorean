import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt'), encoding='utf-8') as f:
    CHANGES = f.read()

requires = [
    'pyramid==2.0.2',
    'pyramid-debugtoolbar>=4,<5',
    'pyramid-mako>=1.1,<2',
    'waitress>=3,<4',
    'requests>=2.32,<3',
    'slumber>=0.7,<1',
    'setuptools<81',
]

setup(name='delorean',
      version='0.1.1',
      description='delorean',
      long_description=README + '\n\n' +  CHANGES,
      long_description_content_type='text/x-rst',
      classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
      ],
      author='',
      author_email='',
      url='',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      python_requires='>=3.14',
      install_requires=requires,
      extras_require={
          'test': [
              'pytest>=8,<9',
              'coverage[toml]>=7,<8',
          ],
      },
      entry_points = """\
      [paste.app_factory]
      main = delorean:main
      """,
      )
