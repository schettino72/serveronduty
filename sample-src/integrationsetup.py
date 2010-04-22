"""sample module used on integration setup of a module.
 referenced by config.yaml
"""

import os
import shutil

def copy_self(integration_path, integration):
    file_name = os.path.abspath(__file__)
    shutil.copy(file_name, integration_path)
