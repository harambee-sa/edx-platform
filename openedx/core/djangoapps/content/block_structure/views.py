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
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.block_structure.api import\
    clear_course_from_cache

LOGGER = logging.getLogger(__name__)


class ClearCourseCacheViewSet(ViewSet):

    """
        **Use Cases**
            Given a course id it will clear the course cache

        **Example Requests**:
            POST /api/content/v1/block-structure/clear-course-cache/

        **Response Values for POST**
            HttpResponse: 200 if the course cache was cleared.
            HttpResponse: 400 if course id not provided or is wrong.

    """
    authentication_classes =\
        (OAuth2Authentication, JwtAuthentication, SessionAuthentication)

    permission_classes = (IsAuthenticated,)

    def post(self, request, format=None):

        course_id = request.data.get('course_id', None)
        if course_id:
            try:
                course_key = CourseKey.from_string(course_id)
                clear_course_from_cache(course_key)
                return Response(
                    {"course_id": course_id},
                    status=status.HTTP_200_OK
                )
            except InvalidKeyError as e:
                LOGGER.error(str(e))
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

        LOGGER.error("Course ID is required")
        return Response(
            {"message":"Course ID is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
