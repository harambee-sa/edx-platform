<<<<<<< HEAD
"""Code run by pylint before running any tests."""

# Patch the xml libs before anything else.
from safe_lxml import defuse_xml_libs
defuse_xml_libs()
=======
from django.conf import settings


def pytest_configure():
    """
    Use Django's default settings for tests in common/lib.
    """
<<<<<<< HEAD
    reload(sys)  
    sys.setdefaultencoding('Cp1252')
    settings.configure()
>>>>>>> try sys convert
=======
    settings.configure()
>>>>>>> [ci skip] reverting conftest
