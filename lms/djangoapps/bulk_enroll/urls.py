"""
URLs for the Bulk Enrollment API
"""
from django.conf.urls import url, patterns

from bulk_enroll.views import BulkEnrollView,  BulkRegisterEnrollView

urlpatterns = patterns(
    'bulk_enroll.views',
    url(r'^bulk_enroll', BulkEnrollView.as_view(), name='bulk_enroll'),
    url(r'^bulk_register_enroll', BulkRegisterEnrollView.as_view(), name='bulk_register_enroll'),
)
