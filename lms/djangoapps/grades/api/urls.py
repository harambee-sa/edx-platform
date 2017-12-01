"""
Grades API URLs.
"""

from django.conf import settings
from django.conf.urls import url

from lms.djangoapps.grades.api import views

urlpatterns = [
    url(
        r'^v0/course_grade/bulk/$',
        views.GradesBulkAPIView.as_view(), name='bulk_user_grades'
    ),
    url(
        r'^v0/course_grade/bulk/$',
        views.GradesBulkAPIView.as_view(), name='bulk_user_grades'
    ),
    url(
        r'^v0/course_grade/{course_id}/users/$'.format(
            course_id=settings.COURSE_ID_PATTERN,
        ),
        views.UserGradeView.as_view(), name='user_grade_detail'
    ),
    url(
        r'^v0/courses/{course_id}/policy/$'.format(
            course_id=settings.COURSE_ID_PATTERN,
        ),
        views.CourseGradingPolicy.as_view(), name='course_grading_policy'
    ),
<<<<<<< HEAD
<<<<<<< HEAD
]
=======
)
>>>>>>> Returning work we wissed due to upgrade
=======
)
>>>>>>> ENH: bulk grades api to be granularENH: course order byADD: harambee custom backend SSOFIX: show correct course info on instructor dashboardFIX: course re-runFIX: course date settings in studio. section release dates are no reflected and updated from the ADD: missing welsh translationsFIX: invalid gettext call for translating jsUPD: FIX: badgr xblock css
