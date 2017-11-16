"""
URLs for the Bulk Enrollment API
"""
from django.conf.urls import url

from bulk_enroll.views import BulkEnrollView,  BulkRegisterEnrollView

urlpatterns = [
    url(r'^bulk_enroll', BulkEnrollView.as_view(), name='bulk_enroll'),
<<<<<<< HEAD
]
=======
    url(r'^bulk_register_enroll', BulkRegisterEnrollView.as_view(), name='bulk_register_enroll'),
)
>>>>>>> Proversity/harambee backend (#553)
