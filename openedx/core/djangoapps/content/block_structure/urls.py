"""
Block Sturecture API URLs
"""
from django.conf import settings
from django.conf.urls import patterns, url
from .views import ClearCourseCacheViewSet


urlpatterns = patterns(
    'block_structure.views',
    url(
        r'^clear-course-cache/$',
        ClearCourseCacheViewSet.as_view({'post': 'post'}),
        name="clear-course-cache"
    ),
)
