"""dodo file. run pychecker and unittests."""

import glob

DOIT_CONFIG = {'default_tasks': ['checker', 'ut'],
               'continue': True}


codeFiles = glob.glob("*.py")
codeFiles.remove('dbapiext.py') # not mine :P
testFiles = glob.glob("tests/test_*.py")
to_strip = len('tests/test_')
pyFiles = codeFiles + testFiles


def task_checker():
    """run pyflakes on all project files"""
    for file in pyFiles:
        yield {'actions': ["pyflakes %s"% file],
               'name':file,
               'dependencies':(file,),
               'title': (lambda task: task.name)}

def task_ut():
    """run unit-tests"""
    for test in testFiles:
        yield {'name': test,
               'actions': ["py.test -v %s" % test],
               'dependencies': [test, test[to_strip:]],
               'verbosity': 2}




def task_coverage():
    """show coverage for all modules including tests"""
    return {'actions':["coverage run `which py.test`",
                   "coverage report --show-missing %s" % " ".join(pyFiles)],
            'verbosity': 2}

def task_coverage_module():
    """show coverage for individual modules"""
    for test in testFiles:
        if not test.startswith('tests/test_'):
            continue
        source = test[to_strip:]
        yield {'name': test,
               'actions':["coverage run `which py.test` %s" % test,
                   "coverage report --show-missing %s %s" % (source, test)],
               'verbosity': 2}
