from pathlib import Path

from setuptools import setup


PROJECT_DIR = Path(__file__).parent.resolve()
PACKAGE_DIR = PROJECT_DIR / 'dendrol'

README_PATH = PROJECT_DIR / 'README.md'
VERSION_PATH = PACKAGE_DIR / 'version.py'


def get_readme() -> str:
    with open(README_PATH) as fp:
        return fp.read()


def get_version() -> str:
    with open(VERSION_PATH) as fp:
        source = fp.read()

    context = {}
    exec(source, context)
    return context['__version__']


setup(
    name='dendrol',
    version=get_version(),
    packages=['dendrol', 'dendrol.lang'],
    url='https://github.com/usePF/dendrol',
    license='MIT',
    author='Perch Security',
    author_email='hello@perchsecurity.com',
    maintainer='Zach "theY4Kman" Kanzler',
    maintainer_email='z@perchsecurity.com',
    description='The STIX2 Pattern expression library for humans',
    long_description=get_readme(),
    long_description_content_type="text/markdown",
    install_requires=[
        # TODO: laxer req versions
        'antlr4-python3-runtime==4.7',
        'PyYAML==3.12',
    ],
    extras_require={
        'test': [
            'icdiff',
            'pytest>=3.8,<4.0',
        ],
        'dev': [
            'dendrol[test]',
            'click>=7.0',
            'requests>=2.20.1',
            'tqdm>=4.28.1',
        ]
    },
    tests_require=[
        'dendrol[test]',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Security',
    ],
)
