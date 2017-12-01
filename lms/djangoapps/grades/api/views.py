""" API v0 views. """
import logging
import urllib 
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.http import Http404
from django.db.models import Q
from edx_rest_framework_extensions.authentication import JwtAuthentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework_oauth.authentication import OAuth2Authentication
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler
from courseware.access import has_access
#from lms.djangoapps.ccx.utils import prep_course_for_grading
from lms.djangoapps.courseware import courses
from lms.djangoapps.courseware.exceptions import CourseAccessRedirect
from lms.djangoapps.grades.api.serializers import GradingPolicySerializer, GradeBulkAPIViewSerializer
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes
from openedx.core.lib.api.permissions import IsStaffOrOwner
from student.roles import CourseStaffRole

log = logging.getLogger(__name__)
USER_MODEL = get_user_model()

<<<<<<< HEAD
=======

>>>>>>> Proversity/staging (#589)
def get_user_grades(grade_user, course, course_grade):
        
    courseware_summary = course_grade.chapter_grades.values()
    grade_summary = course_grade.summary
    grades_schema = {}
    subsection_schema = {}
    for chapter in courseware_summary: 
        for section in chapter['sections']: 
            earned = section.all_total.earned
            total = section.all_total.possible
            name = section.display_name
            section_id = str(section.location)
            sections_scores  = {}
            i = 0
            problem_scores_dictionary_keys = section.problem_scores_with_keys.items()
            if len(section.problem_scores_with_keys.values()) > 0:
                for score in section.problem_scores_with_keys.values():
                    sections_scores[problem_scores_dictionary_keys[i][0]] = \
                        [float(score.earned),float(score.possible)]
                    i += 1
                if total > 0:
                    grades_schema[section_id] = sections_scores
    return grades_schema


def _build_emails(identifiers, email_extension):
    """
    Itterates over a given list of indetifiers and adds the email extension
    returns completed email list.
    """
    email_list = []
    for identifier in identifiers:
        if "@" in identifier:
            email_list.append(identifier)
        else:
            email_list.append("{id}{ext}".format(id=identifier.strip(), ext=email_extension))
    return email_list

<<<<<<< HEAD
=======

>>>>>>> Proversity/staging (#589)
@view_auth_classes()
class GradeViewMixin(DeveloperErrorViewMixin):
    """
    Mixin class for Grades related views.
    """
    def _get_course(self, course_key_string, user, access_action):
        """
        Returns the course for the given course_key_string after
        verifying the requested access to the course by the given user.
        """
        try:
            course_key = CourseKey.from_string(course_key_string)
        except InvalidKeyError:
            return self.make_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message='The provided course key cannot be parsed.',
                error_code='invalid_course_key'
            )

        try:
            return courses.get_course_with_access(
                user,
                access_action,
                course_key,
                check_if_enrolled=True,
            )
        except Http404:
            log.info('Course with ID "%s" not found', course_key_string)
        except CourseAccessRedirect:
            log.info('User %s does not have access to course with ID "%s"', user.username, course_key_string)
        return self.make_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            developer_message='The user, the course or both do not exist.',
            error_code='user_or_course_does_not_exist',
        )

    def _get_effective_user(self, request, course):
        """
        Returns the user object corresponding to the request's 'username' parameter,
        or the current request.user if no 'username' was provided.
        Verifies that the request.user has access to the requested users's grades.
        Returns a 403 error response if access is denied, or a 404 error response if the user does not exist.
        """

        # Use the request user's if none provided.
        if 'username' in request.GET:
            username = request.GET.get('username')
        else:
            username = request.user.username

        if request.user.username == username:
            # Any user may request her own grades
            return request.user

        # Only a user with staff access may request grades for a user other than herself.
        if not has_access(request.user, CourseStaffRole.ROLE, course):
            log.info(
                'User %s tried to access the grade for user %s.',
                request.user.username,
                username
            )
            return self.make_error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                developer_message='The user requested does not match the logged in user.',
                error_code='user_mismatch'
            )

        try:
            return USER_MODEL.objects.get(username=username)

        except USER_MODEL.DoesNotExist:
            return self.make_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message='The user matching the requested username does not exist.',
                error_code='user_does_not_exist'
            )

    def perform_authentication(self, request):
        """
        Ensures that the user is authenticated (e.g. not an AnonymousUser), unless DEBUG mode is enabled.
        """
        super(GradeViewMixin, self).perform_authentication(request)
        if request.user.is_anonymous():
            raise AuthenticationFailed


class UserGradeView(GradeViewMixin, GenericAPIView):
    """
    **Use Case**
        * Get the current course grades for a user in a course.
        The currently logged-in user may request her own grades, or a user with staff access to the course may request
        any enrolled user's grades.
    **Example Request**
        GET /api/grades/v0/course_grade/{course_id}/users/?username={username}
    **GET Parameters**
        A GET request may include the following parameters.
        * course_id: (required) A string representation of a Course ID.
        * username: (optional) A string representation of a user's username.
          Defaults to the currently logged-in user's username.
    **GET Response Values**
        If the request for information about the course grade
        is successful, an HTTP 200 "OK" response is returned.
        The HTTP 200 response has the following values.
        * username: A string representation of a user's username passed in the request.
        * course_id: A string representation of a Course ID.
        * passed: Boolean representing whether the course has been
                  passed according the course's grading policy.
        * percent: A float representing the overall grade for the course
        * letter_grade: A letter grade as defined in grading_policy (e.g. 'A' 'B' 'C' for 6.002x) or None
    **Example GET Response**
        [{
            "username": "bob",
            "course_key": "edX/DemoX/Demo_Course",
            "passed": false,
            "percent": 0.03,
            "letter_grade": None,
        }]
    """
    def get(self, request, course_id):
        """
        Gets a course progress status.
        Args:
            request (Request): Django request object.
            course_id (string): URI element specifying the course location.
        Return:
            A JSON serialized representation of the requesting user's current grade status.
        """

        course = self._get_course(course_id, request.user, 'load')
        if isinstance(course, Response):
            # Returns a 404 if course_id is invalid, or request.user is not enrolled in the course
            return course

        grade_user = self._get_effective_user(request, course)
        if isinstance(grade_user, Response):
            # Returns a 403 if the request.user can't access grades for the requested user,
            # or a 404 if the requested user does not exist.
            return grade_user

        #prep_course_for_grading(course, request)
        course_grade = CourseGradeFactory().update(grade_user, course)
        courseware_summary = course_grade.chapter_grades.values()
        grade_summary = course_grade.summary

        grades_schema = {}
        for chapter in courseware_summary:
            for section in chapter['sections']:
                earned = section.all_total.earned
                total = section.all_total.possible
                name = section.display_name
                if len(section.problem_scores.values()) > 0:
                    if total > 0:
                        grades_schema[str(name)] = "{0:.0%}".format( float(earned)/total) 


        return Response({
            'username': grade_user.username,
            'course_key': course_id,
            'passed': course_grade.passed,
            'percent': course_grade.percent,
            'letter_grade': course_grade.letter_grade,
            'section_scores': grades_schema
        })


class GradesBulkAPIView(ListAPIView):

    """
    **Use Case**
        * Get the current course grades for a list of users in a list of courses.
    **Example Request**
        POST /api/grades/v0/course_grade/bulk/
    
          
    **POST Response Values**
        If the request for information about the course grade
        is successful, an HTTP 200 "OK" response is returned.
        The HTTP 200 response has the following values.
        * username: A string representation of a user's username passed in the request.
        * course_id: A string representation of a Course ID.
        * passed: Boolean representing whether the course has been
                  passed according the course's grading policy.
        * percent: A float representing the overall grade for the course
    **Example POST Response**
        {
          "course-v1:T3+T3+2014_T1": {
            "dummy": {
              "letter_grade": null,
              "percent": 0,
              "email": "lidija@proversity.org",
              "passed": false,
              "name": " "
            },
            "staff": {
              "letter_grade": null,
              "percent": 0,
              "email": "staff@example.com",
              "passed": false,
              "name": " "
            }
          },
          "course-v1:edX+DemoX+Demo_Course": {
            "dummy": {
              "letter_grade": "Pass",
              "percent": 0.66,
              "email": "lidija@proversity.org",
              "passed": true,
              "name": " "
            },
            "staff": {
              "letter_grade": "Pass",
              "percent": 0.72,
              "email": "staff@example.com",
              "passed": true,
              "name": " "
            }
          }
        }
    """
    http_method_names = ['post']
    authentication_classes = (
        OAuth2Authentication,
        JwtAuthentication,
        SessionAuthentication
    )
    serializer_class = GradeBulkAPIViewSerializer
    permission_classes = (IsAuthenticated, IsStaffOrOwner)
    
    def post(self,  request):

        query_params = self.request.query_params
        depth = query_params.get('depth', None)  
        # create the list based on the post parameters

        serializer = GradeBulkAPIViewSerializer(data=request.data)
        
        try:
            course_ids = request.data['course_ids']
        except KeyError:
            course_ids = None
        try:
            usernames = request.data['usernames']
        except KeyError:
            usernames = None
        try:
            email_extension = request.data['email_extension']
        except KeyError:
            email_extension = None      

        # compile list of email adresses
    
        if email_extension is not None:
            list_of_emails_or_usernames =\
                _build_emails(usernames, email_extension)
        else:
            list_of_emails_or_usernames = usernames

        # Set up a dictionaries/list to contain the user grades and course grades
        # catching the incorrect courses in a "course_failure" list
        course_results = {}
        course_success = {}
        course_failure = []
        user_grades = {}

        for course_str in course_ids:
            try:
                course_key = CourseKey.from_string(str(course_str))
                course = courses.get_course(course_key)

                # query database for all users holding these emails
                # Django's "filter" takes care of "User not found"
                user_list = USER_MODEL.objects.filter(
                    Q(username__in=usernames) |
                    Q(email__in=list_of_emails_or_usernames),
                    courseenrollment__course_id=CourseKey.from_string(course_str)
                ).order_by('username').select_related('profile')
                for user in user_list:
                    try:
                        course_grade = CourseGradeFactory().update(user, course)
                        if depth == 'all':
                            grades_schema =  get_user_grades(user, course, course_grade)
                        else:
                            grades_schema = 'Specify depth=all in query parameters.'
                        user_grades[user.username] = {
                            'name': "{} {}".format(user.first_name, user.last_name),
                            'email': user.email,
                            'passed': course_grade.passed,
                            'percent': course_grade.percent,
                            'all_grades': grades_schema
                        }
                    except Exception as e:
                        log.error(e)
                        pass

                course_success[course_str] = user_grades
                user_grades = {}
                            
            except InvalidKeyError:
                log.error('Invalid key, {} does not exist'.format(course_str))
                course_failure.append("{} does not exist".format(course_str))
                pass
            except ValueError:
                log.error('Value error, {} could not be found.'.format(course_str))
                course_failure.append("{} does not exist".format(course_str))

                pass
        course_results["successes"] = course_success
        course_results["failures"] = course_failure
            
        return Response(course_results)


class CourseGradingPolicy(GradeViewMixin, ListAPIView):
    """
    **Use Case**
        Get the course grading policy.
    **Example requests**:
        GET /api/grades/v0/policy/{course_id}/
    **Response Values**
        * assignment_type: The type of the assignment, as configured by course
          staff. For example, course staff might make the assignment types Homework,
          Quiz, and Exam.
        * count: The number of assignments of the type.
        * dropped: Number of assignments of the type that are dropped.
        * weight: The weight, or effect, of the assignment type on the learner's
          final grade.
    """

    allow_empty = False

    def get(self, request, course_id, **kwargs):
        course = self._get_course(course_id, request.user, 'staff')
        if isinstance(course, Response):
            return course
        return Response(GradingPolicySerializer(course.raw_grader, many=True).data)