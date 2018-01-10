# pylint: disable=too-many-ancestors
"""
Views for block structure api endpoints.
"""
import logging

from edx_rest_framework_extensions.authentication import JwtAuthentication
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_oauth.authentication import OAuth2Authentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.block_structure.api import\
    clear_course_from_cache

LOGGER = logging.getLogger(__name__)


class ClearCoursesCacheViewSet(ViewSet):

    """
        **Use Cases**
            Given a list of courses id it will clear the courses cache

        **Example Requests**:
            POST /api/content/v1/block-structure/clear-courses-cache/

        **Response Values for POST**
            HttpResponse: 200 if the courses cache was cleared.
            Dict: {
                success_clear_cache_courses: sucessful clear cache courses
                error_clear_cache_courses: failed clear cache courses
            }

    """
    authentication_classes =\
        (OAuth2Authentication, JwtAuthentication, SessionAuthentication)

    permission_classes = (IsAuthenticated,)

    def post(self, request, format=None):

        courses_id = request.data.get('courses_id', None)
        success_clear_cache_courses = []
        error_clear_cache_courses = []
        if courses_id and len(courses_id) > 0:
            for course_id in courses_id:
                try:
                    course_key = CourseKey.from_string(course_id)
                    clear_course_from_cache(course_key)
                    success_clear_cache_courses.append(course_id)
                except InvalidKeyError as e:
                    LOGGER.error(str(e))
                    error_clear_cache_courses.append(course_id)

        return Response(
            {
                "success_clear_cache_courses":success_clear_cache_courses,
                "error_clear_cache_courses": error_clear_cache_courses
            },
            status=status.HTTP_200_OK
        )
