from setuptools import find_packages, setup

import perf

setup(
    name='perf',
    version=perf.__version__,
    description='OpenAPI Performance testing module',
    author='Joe Mader',
    author_email='jmader@jmader.com',
    packages=find_packages(exclude=['*.tests', '*.tests.*']),
    install_requires=[
        'numpy',
        'prettytable',
        'requests'
    ]
)
