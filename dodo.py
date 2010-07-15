# check sodd/doit to run tests, this files just installs flot by now

DOIT_CONFIG = {'default_tasks': []}

def task_install_flot():
    """Installs flot (javacript plotting fot jQuery)"""
    flot_url = "http://flot.googlecode.com/files/"
    flot_tar = "flot-0.6.tar.gz"
    static_location = "websod/static"
    return {'actions': ['wget --directory-prefix %s %s%s' %
                        (static_location, flot_url, flot_tar),
                        'tar --directory %s -xzf %s/%s' %
                        (static_location, static_location, flot_tar),
                        ],
            'file_dep': [True], # run-once
            'targets': ["%s/flot" % static_location],
            }
