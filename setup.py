import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open('README.rst').read()
CHANGES = open('CHANGES.txt').read()

requires = ['pycassa', 'thrift05', 'setuptools','ordereddict','rdflib']
tests_requires = requires + ['nose', 'mock']

setup(name='agamemnon',
      version='0.2.1.4',
      description='A graph database built on top of cassandra',
	  scripts=['bin/generate_indices'],
      long_description=README + "\n\n" + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        ],
      author='Tom Howe',
      author_email='trhowe@ci.uchicago.edu',
      url='https://github.com/globusonline/agamemnon',
      license='LICENSE.txt',
      keywords='cassandra',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      setup_requires=['nose>=0.11'],
      install_requires=requires,
      tests_require=tests_requires,
      test_suite="nose.collector",
      )

