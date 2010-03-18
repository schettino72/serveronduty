from setuptools import setup

setup(name='ServerOnDuty',
      packages=['sodd', 'websod'],
      scripts=('manage.py', 'sodd/run_sodd.py'))
