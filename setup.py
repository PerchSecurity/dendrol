from __future__ import with_statement
from __future__ import unicode_literals, absolute_import
import os

from setuptools import setup
from io import open


PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
PACKAGE_DIR = os.path.join(PROJECT_DIR, u'dendrol')

README_PATH = os.path.join(PROJECT_DIR, u'README.md')
VERSION_PATH = os.path.join(PACKAGE_DIR, u'version.py')


def get_readme():
    with open(README_PATH) as fp:
        return fp.read()


def get_version():
    with open(VERSION_PATH) as fp:
        source = fp.read()

    context = {}
    exec(source, context)
    return context[u'__version__']


setup(
    name=u'dendrol',
    version=get_version(),
    packages=[u'dendrol', u'dendrol.lang'],
    url=u'https://github.com/usePF/dendrol',
    license=u'MIT',
    author=u'Perch Security',
    author_email=u'hello@perchsecurity.com',
    maintainer=u'Zach "theY4Kman" Kanzler',
    maintainer_email=u'z@perchsecurity.com',
    description=u'The STIX2 Pattern expression library for humans',
    long_description=get_readme(),
    long_description_content_type=u"text/markdown",
    install_requires=[
        # TODO: laxer req versions
        u'antlr4-python2-runtime==4.7',
        u'PyYAML>=3.12,<4',
        u'future',
        u'pathlib',
    ],
    extras_require={
        u'test': [
            u'icdiff',
            u'pytest>=3.8,<4.0',
        ],
        u'dev': [
            u'dendrol[test]',
            u'click>=7.0',
            u'requests>=2.20.1',
            u'tqdm>=4.28.1',
        ]
    },
    tests_require=[
        u'dendrol[test]',
    ],
    classifiers=[
        u'Development Status :: 3 - Alpha',
        u'License :: OSI Approved :: MIT License',
        u'Programming Language :: Python :: 3 :: Only',
        u'Programming Language :: Python :: 3.6',
        u'Programming Language :: Python :: 3.7',
        u'Topic :: Security',
    ],
)
