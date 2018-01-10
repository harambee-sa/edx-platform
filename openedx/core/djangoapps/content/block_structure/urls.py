"""
Block Sturecture API URLs
"""
from django.conf import settings
from django.conf.urls import patterns, url
from .views import ClearCoursesCacheViewSet


urlpatterns = patterns(
    'block_structure.views',
    url(
        r'^clear-courses-cache/$',
        ClearCoursesCacheViewSet.as_view({'post': 'post'}),
        name="clear-courses-cache"
    ),
)
