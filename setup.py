from setuptools import setup

setup(name='ServerOnDuty',
      packages=['sodd', 'websod'],
      scripts=['bin/sod'],
      install_requires=['Flask',
                        'CherryPy==3.1.2',
                        'SQLAlchemy==0.5.8',
                        'doit',
                        'simplejson==1.9.2',
                        'PyYAML==3.09',
                        # dev requires
                        'py==1.2.1',
                        'coverage==3.2',
                        'pyflakes',
                        'mock==0.6.0',
                        ],
      )
