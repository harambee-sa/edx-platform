<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
"""Code run by pylint before running any tests."""

# Patch the xml libs before anything else.
from safe_lxml import defuse_xml_libs
defuse_xml_libs()
=======
=======
>>>>>>> Proversity/development (#546)
=======
>>>>>>> ENH: bulk grades api to be granularENH: course order byADD: harambee custom backend SSOFIX: show correct course info on instructor dashboardFIX: course re-runFIX: course date settings in studio. section release dates are no reflected and updated from the ADD: missing welsh translationsFIX: invalid gettext call for translating jsUPD: FIX: badgr xblock css
from django.conf import settings


def pytest_configure():
    """
    Use Django's default settings for tests in common/lib.
    """
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    reload(sys)  
    sys.setdefaultencoding('Cp1252')
    settings.configure()
>>>>>>> try sys convert
=======
    settings.configure()
>>>>>>> [ci skip] reverting conftest
=======
    settings.configure()
>>>>>>> Proversity/development (#546)
=======
    settings.configure()
>>>>>>> ENH: bulk grades api to be granularENH: course order byADD: harambee custom backend SSOFIX: show correct course info on instructor dashboardFIX: course re-runFIX: course date settings in studio. section release dates are no reflected and updated from the ADD: missing welsh translationsFIX: invalid gettext call for translating jsUPD: FIX: badgr xblock css
