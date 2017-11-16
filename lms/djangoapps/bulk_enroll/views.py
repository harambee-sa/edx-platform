"""
API views for Bulk Enrollment
"""
import json
from django.contrib.auth import get_user_model

from edx_rest_framework_extensions.authentication import JwtAuthentication
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from bulk_enroll.serializers import BulkEnrollmentSerializer, BulkRegisterEnrollSerializer
from enrollment.views import EnrollmentUserThrottle
from instructor.views.api import students_update_enrollment, create_and_register_users_without_email
from openedx.core.lib.api.authentication import OAuth2Authentication
from openedx.core.lib.api.permissions import IsStaff
from util.disable_rate_limit import can_disable_rate_limit

USER_MODEL = get_user_model()

@can_disable_rate_limit
class BulkEnrollView(APIView):
    """
    **Use Case**

        Enroll multiple users in one or more courses.

    **Example Request**

        POST /api/bulk_enroll/v1/bulk_enroll/ {
            "auto_enroll": true,
            "email_students": true,
            "action": "enroll",
            "courses": "course-v1:edX+Demo+123,course-v1:edX+Demo2+456",
            "identifiers": "brandon@example.com,yamilah@example.com"
        }

        **POST Parameters**

          A POST request can include the following parameters.

          * auto_enroll: When set to `true`, students will be enrolled as soon
            as they register.
          * email_students: When set to `true`, students will be sent email
            notifications upon enrollment.
          * action: Can either be set to "enroll" or "unenroll". This determines the behabior

    **Response Values**

        If the supplied course data is valid and the enrollments were
        successful, an HTTP 200 "OK" response is returned.

        The HTTP 200 response body contains a list of response data for each
        enrollment. (See the `instructor.views.api.students_update_enrollment`
        docstring for the specifics of the response data available for each
        enrollment)
    """

    authentication_classes = JwtAuthentication, OAuth2Authentication
    permission_classes = IsStaff,
    throttle_classes = EnrollmentUserThrottle,

    def post(self, request):
        serializer = BulkEnrollmentSerializer(data=request.data)
        if serializer.is_valid():
            # Setting the content type to be form data makes Django Rest Framework v3.6.3 treat all passed JSON data as
            # POST parameters. This is necessary because this request is forwarded on to the student_update_enrollment
            # view, which requires all of the parameters to be passed in via POST parameters.
            metadata = request._request.META  # pylint: disable=protected-access
            metadata['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

            response_dict = {
                'auto_enroll': serializer.data.get('auto_enroll'),
                'email_students': serializer.data.get('email_students'),
                'action': serializer.data.get('action'),
                'courses': {}
            }
            for course in serializer.data.get('courses'):
                response = students_update_enrollment(self.request, course_id=course)
                response_dict['courses'][course] = json.loads(response.content)
            return Response(data=response_dict, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BulkRegisterEnrollView(APIView):
    """
    **Use Case**

        Register and enroll multiple users in one or more courses.

    **Example Request**
    """
    authentication_classes = JwtAuthentication, OAuth2Authentication
    permission_classes = IsStaff,
    throttle_classes = EnrollmentUserThrottle,

    def post(self, request):
        serializer = BulkRegisterEnrollSerializer(data=request.data)
        results = {}
        if serializer.is_valid():
            metadata = request._request.META  # pylint: disable=protected-access        
            metadata['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

            response_dict = {
                'auto_enroll': serializer.data.get('auto_enroll'),
                'email_students': serializer.data.get('email_students'),
                'action': serializer.data.get('action'),
                'courses': {}
            }
            registration_response = \
                create_and_register_users_without_email(self.request)
            results['registration-info'] = json.loads(
                registration_response.content
            ) 
            for course in serializer.data.get('courses'):
                enrollment_response = \
                    students_update_enrollment(self.request, course_id=course)
                response_dict['courses'][course] = \
                    json.loads(enrollment_response.content)
                results['enrollments'] = response_dict
            return Response(results, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)