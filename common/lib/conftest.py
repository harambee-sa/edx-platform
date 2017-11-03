<<<<<<< HEAD
"""Code run by pylint before running any tests."""

# Patch the xml libs before anything else.
from safe_lxml import defuse_xml_libs
defuse_xml_libs()
=======
from django.conf import settings
import sys


def pytest_configure():
    """
    Use Django's default settings for tests in common/lib.
    """
    reload(sys)  
    sys.setdefaultencoding('Cp1252')
    settings.configure()
>>>>>>> try sys convert
