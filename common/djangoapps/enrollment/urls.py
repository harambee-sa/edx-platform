"""
URLs for the Enrollment API

"""
from django.conf import settings
from django.conf.urls import url

from .views import (
    EnrollmentView,
    EnrollmentListView,
    EnrollmentCourseDetailView,
    EnrollmentCoursePassedView
)


urlpatterns = patterns(
    'enrollment.views',
    url(
        r'^enrollment/{username},{course_key}$'.format(
            username=settings.USERNAME_PATTERN, course_key=settings.COURSE_ID_PATTERN
        ),
        EnrollmentView.as_view(),
        name='courseenrollment'
    ),
    url(
        r'^enrollment/{course_key}$'.format(course_key=settings.COURSE_ID_PATTERN),
        EnrollmentView.as_view(),
        name='courseenrollment'
    ),

    url(r'^enrollment$', EnrollmentListView.as_view(), name='courseenrollments'),

    url(
        r'^course/{course_key}$'.format(course_key=settings.COURSE_ID_PATTERN),
        EnrollmentCourseDetailView.as_view(),
        name='courseenrollmentdetails'
    ),
    url(
        r'^course/{course_key}/passed$'.format(course_key=settings.COURSE_ID_PATTERN),
        EnrollmentCoursePassedView.as_view(),
        name='courseenrollmentpassed'
    ),
)

