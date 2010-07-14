from setuptools import setup

setup(name='ServerOnDuty',
      packages=['sodd', 'websod'],
      scripts=['bin/sod'],
      install_requires=['Werkzeug==0.6',
                        'CherryPy==3.1.2',
                        'Mako==0.2.5',
                        'SQLAlchemy==0.5.8',
                        'doit',
                        'simplejson==1.9.2',
                        'PyYAML==3.09',
                        # dev requires
                        'py==1.2.1',
                        'coverage==3.2',
                        'pyflakes==0.2.1',
                        'mock==0.6.0',
                        ],
      )
