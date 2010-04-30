import sys
import traceback
import glob
import os

DOIT_CONFIG = {'default_tasks': ['test']}

###########################
# run unit-tests

# create its own process group
os.setpgid(0, 0)

def task_test():
    for tf in glob.glob('*_test.py'):
        yield {'name': tf,
               'actions': [(run_ut, [tf])],
               }

def run_ut(test_file):
    wasSuccessful = True
    module_name = test_file[:-3]
    module = __import__(module_name, globals, locals)
    test_method = getattr(module, 'run_test')
    output = sys.stderr

    output.write('staring test %s.%s\n' % (module_name, 'run_test'))
    try:
        test_method()
    except:
        traceback.print_tb(sys.exc_info()[2])
        wasSuccessful = False
    output.write('%s.%s end\n' % (module_name, 'run_test'))

    return wasSuccessful
