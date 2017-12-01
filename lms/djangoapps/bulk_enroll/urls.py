"""
URLs for the Bulk Enrollment API
"""
from django.conf.urls import url

from bulk_enroll.views import BulkEnrollView,  BulkRegisterEnrollView

urlpatterns = [
    url(r'^bulk_enroll', BulkEnrollView.as_view(), name='bulk_enroll'),
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
]
=======
=======
>>>>>>> Proversity/development (#558)
=======
>>>>>>> Proversity/development (#558) (#559)
=======
>>>>>>> Proversity/staging (#564)
=======
>>>>>>> ENH: bulk grades api to be granularENH: course order byADD: harambee custom backend SSOFIX: show correct course info on instructor dashboardFIX: course re-runFIX: course date settings in studio. section release dates are no reflected and updated from the ADD: missing welsh translationsFIX: invalid gettext call for translating jsUPD: FIX: badgr xblock css
    url(r'^bulk_register_enroll', BulkRegisterEnrollView.as_view(), name='bulk_register_enroll'),
)
>>>>>>> Proversity/harambee backend (#553)
