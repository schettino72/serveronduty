"""
create a sample HG repository of a project to be used for manual tests of SOD
TODO included added/removed tasks

Usage
-----

::

 $ doit -f createsample.py

It will create a folder called 'samplesod'

"""

import os

SRC = os.path.abspath('sample-src')
DST = 'samplesod'
FILES = ('dodo.py', 'config.yaml', 'integrationsetup.py', '.hgignore',)
CP_FILES = ('first_test.py', 'unstable_test.py')

body_ok = """
def run_test():
    assert True
"""

body_fail= """
def run_test():
    assert False
"""

body_unstable = """
import os
def run_test():
    assert 1 == 1
    if not os.path.exists('flag.file'):
        f = open('flag.file', 'w')
        f.write('a')
        f.close()
        assert 3 == 5
    else:
        os.unlink('flag.file')
        assert 1 == 1
"""

def task_sample_repo():
    # clean action
    yield {'name':'clean',
           'actions': [],
           'clean': ['rm -r %s' % DST],
           }

    # 0) create repo
    cp_list = ['cp %s/%s %s/%s' % (SRC, f, DST, f) for f in CP_FILES]
    ln_list = ['ln -s %s/%s %s/%s' % (SRC, f, DST, f) for f in FILES]
    dst_files = ['%s/%s' % (DST, f) for f in (CP_FILES + FILES)]
    yield {'name': 'rev0',
           'actions': ['mkdir %s' % DST] + cp_list + ln_list +
           ['hg init %s' % DST,
            'hg add --repository %s %s' % (DST, " ".join(dst_files)),
            'hg commit --repository %s -m "initial commit"' % DST,
            ]
           }

    # 1) fail
    yield {'name': 'rev1',
           'actions': ['echo "%s" > %s/%s' % (body_fail, DST, 'first_test.py'),
                       'hg commit --repository %s -m "this fail"' % DST]
           }

    # 2) still fail
    yield {'name': 'rev2',
           'actions': ['echo "# useless" >> %s/%s' % (DST, 'first_test.py'),
                       'hg commit --repository %s -m "this fail too"' % DST]
           }

    # 3) fixed
    yield {'name': 'rev3',
           'actions': ['echo "%s" > %s/%s' % (body_ok, DST, 'first_test.py'),
                       'hg commit --repository %s -m "this ok"' % DST]
           }

    # 4) unstable
    yield {'name': 'rev4',
           'actions': ['echo "%s" > %s/%s' % (body_unstable, DST,
                                           'unstable_test.py'),
                       'hg commit --repository %s -m "with unstable"' % DST]
           }
