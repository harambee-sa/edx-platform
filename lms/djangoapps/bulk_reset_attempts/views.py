"""
API views for Bulk Enrollment
"""
import json
from django.contrib.auth import get_user_model

from edx_rest_framework_extensions.authentication import JwtAuthentication
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from bulk_reset_attempts.serializers import BulkResetStudentAttemptsSerializer
from openedx.core.lib.api.authentication import OAuth2Authentication
from openedx.core.lib.api.permissions import IsStaff
from django.db.models import Q
from django.db import IntegrityError, transaction

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from courseware.courses import get_course_with_access, get_course_by_id, get_course
import lms.djangoapps.instructor.enrollment as enrollment
from courseware.models import StudentModule
from submissions import api as sub_api
from  lms.djangoapps.instructor_task.api import submit_reset_problem_attempts_for_all_students
from lms.djangoapps.instructor.views.api import _build_emails
from django.utils.translation import ugettext as _

from django.contrib.auth.models import User


def get_identifiers(identifiers, email_extension):
    all_students = False
    list_of_identifiers = []

    if identifiers[0].replace(" ", "") == "all":
        all_students = True
    else:
        if email_extension is not None:
            list_of_identifiers =\
                _build_emails(identifiers, email_extension)
        else:
            list_of_identifiers = identifiers

    return (all_students, list_of_identifiers,)


def get_students(identifiers):
    list_of_students = []
    errors = {}
    has_errors = False
    for identifier in identifiers:
        identifier = identifier.replace(" ", "")
        try:
            user = User.objects.get(
                Q(username=identifier) | 
                Q(email=identifier)
            )
            list_of_students.append(user)
        except User.DoesNotExist:
            has_errors = True
            error_message = 'User does not exist'
            errors.update({identifier: error_message})

    return (list_of_students, has_errors, errors)


class BulkResetStudentAttemptsView(APIView):
    authentication_classes = JwtAuthentication, OAuth2Authentication
    permission_classes = IsStaff,
    
    def post(self, request):
        serializer = BulkResetStudentAttemptsSerializer(data=request.data)
        results = {"course": "", "errors": {}, "problems": {}}
        if serializer.is_valid():
            course_id = serializer.data.get('course_id')
            results["course"] = course_id
            try:
                course_key = CourseKey.from_string(course_id)
                try:
                    course = CourseOverview.get_from_id(course_key)
                    identifiers = serializer.data.get('identifiers')
                    problems = serializer.data.get('problems')
                    reset_state = serializer.data.get('reset_state')
                    email_extension = serializer.data.get('email_extension')

                    all_students, list_of_identifiers =\
                        get_identifiers(identifiers, email_extension)

                    list_of_students = []
                    if not all_students:
                        list_of_students, has_errors, get_students_errors =\
                            get_students(list_of_identifiers)

                        if has_errors:
                            results["errors"].update(get_students_errors)

                    for problem in problems:
                        problem = problem.replace(" ", "")
                        try:
                            module_state_key =\
                                UsageKey.from_string(
                                    problem
                                ).map_into_course(
                                    course_key
                                )

                            results["problems"].update({problem: {}})
                            if all_students:
                                results['problems'].update({
                                    problem: {
                                        "message": "Reset attempts for 'all' students is in development. Nothing has been resetted."
                                    }
                                })
                                # submit_reset_problem_attempts_for_all_students(
                                #     request, module_state_key
                                # )

                                # results['problems'].update(
                                #     {
                                #         problem: {
                                #             "students": "all",
                                #             "task": "created"
                                #         }
                                #     }
                                # )
                            else:
                                for student in list_of_students:
                                    try:
                                        enrollment.reset_student_attempts(
                                            course_key,
                                            student,
                                            module_state_key,
                                            requesting_user=request.user,
                                            delete_module=reset_state
                                        )

                                        message = "Problem resetted"
                                        results["problems"][problem].update({
                                            student.username: message
                                        })
                                    except StudentModule.DoesNotExist:
                                        error_message =\
                                            _("Module does not exist.")

                                        results["problems"][problem].update({
                                            student.username: error_message
                                        })
                                    except sub_api.SubmissionError:
                                        error_message =\
                                            _("An error occurred while "
                                            "deleting the score.")

                                        results["problems"][problem].update({
                                            student.username: error_message
                                        })

                        except InvalidKeyError:
                            error_message = _("The problem does not exist")
                            results["errors"].update({problem: error_message})

                    return Response(results, status=status.HTTP_200_OK)
                                
                except CourseOverview.DoesNotExist:
                    error_message =\
                        _("Course '{}' does not exist".format(course_id))

                    return\
                        Response(
                            {"error": error_message},
                            status=status.HTTP_400_BAD_REQUEST
                        )

            except InvalidKeyError:
                error_message = _("Invalid course id: '{}'".format(course_id))
                return\
                    Response(
                        {"error": error_message},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        else:
            return\
                Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
