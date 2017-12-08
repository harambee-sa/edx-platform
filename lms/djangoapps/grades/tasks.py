"""
This module contains tasks for asynchronous execution of grade updates.
"""

from logging import getLogger

import six
from celery import task
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask
from courseware.model_data import get_score
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.utils import DatabaseError
from lms.djangoapps.course_blocks.api import get_course_blocks
from lms.djangoapps.grades.config.models import ComputeGradesSetting
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangoapps.monitoring_utils import set_custom_metric, set_custom_metrics_for_course_key
from student.models import CourseEnrollment
from submissions import api as sub_api
from track.event_transaction_utils import set_event_transaction_id, set_event_transaction_type
from util.date_utils import from_timestamp
from xmodule.modulestore.django import modulestore

from .config.waffle import DISABLE_REGRADE_ON_POLICY_CHANGE, waffle
from .constants import ScoreDatabaseTableEnum
from .course_grade_factory import CourseGradeFactory
from .exceptions import DatabaseNotReadyError
from .services import GradesService
from .signals.signals import SUBSECTION_SCORE_CHANGED
from .subsection_grade_factory import SubsectionGradeFactory
from .transformer import GradesTransformer

log = getLogger(__name__)

COURSE_GRADE_TIMEOUT_SECONDS = 1200
KNOWN_RETRY_ERRORS = (  # Errors we expect occasionally, should be resolved on retry
    DatabaseError,
    ValidationError,
    DatabaseNotReadyError,
)
RECALCULATE_GRADE_DELAY_SECONDS = 2  # to prevent excessive _has_db_updated failures. See TNL-6424.
RETRY_DELAY_SECONDS = 30
SUBSECTION_GRADE_TIMEOUT_SECONDS = 300


<<<<<<< HEAD
@task(base=LoggedPersistOnFailureTask, routing_key=settings.POLICY_CHANGE_GRADES_ROUTING_KEY)
=======



####################################

import logging
import urllib

import requests 

from django.conf import settings
from django.core.urlresolvers import reverse
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
from openedx.core.djangoapps.content.block_structure.api import get_course_in_cache
from lms.djangoapps.courseware import courses
from lms.djangoapps.courseware.exceptions import CourseAccessRedirect
from lms.djangoapps.grades.api.serializers import GradingPolicySerializer, GradeBulkAPIViewSerializer
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes
from openedx.core.lib.api.permissions import IsStaffOrOwner
from student.models import CourseEnrollment
from student.roles import CourseStaffRole

from lms.djangoapps.courseware.courses import get_course
log = logging.getLogger(__name__)
USER_MODEL = get_user_model()
from lms.djangoapps.instructor_task.tasks_base import BaseInstructorTask
from django.apps import apps

#################################################


class _BaseTask(PersistOnFailureTask, LoggedTask):  # pylint: disable=abstract-method
    """
    Include persistence features, as well as logging of task invocation.
    """
    abstract = True


@task(base=_BaseTask, routing_key=settings.POLICY_CHANGE_GRADES_ROUTING_KEY)
>>>>>>> figuring out tasks
def compute_all_grades_for_course(**kwargs):
    """
    Compute grades for all students in the specified course.
    Kicks off a series of compute_grades_for_course_v2 tasks
    to cover all of the students in the course.
    """
    if waffle().is_enabled(DISABLE_REGRADE_ON_POLICY_CHANGE):
        log.debug('Grades: ignoring policy change regrade due to waffle switch')
    else:
        course_key = CourseKey.from_string(kwargs.pop('course_key'))
        for course_key_string, offset, batch_size in _course_task_args(course_key=course_key, **kwargs):
            kwargs.update({
                'course_key': course_key_string,
                'offset': offset,
                'batch_size': batch_size,
            })
            compute_grades_for_course_v2.apply_async(
                kwargs=kwargs, routing_key=settings.POLICY_CHANGE_GRADES_ROUTING_KEY
            )


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    default_retry_delay=RETRY_DELAY_SECONDS,
    max_retries=1,
    time_limit=COURSE_GRADE_TIMEOUT_SECONDS
)
def compute_grades_for_course_v2(self, **kwargs):
    """
    Compute grades for a set of students in the specified course.

    The set of students will be determined by the order of enrollment date, and
    limited to at most <batch_size> students, starting from the specified
    offset.

    TODO: Roll this back into compute_grades_for_course once all workers have
    the version with **kwargs.
    """
    if 'event_transaction_id' in kwargs:
        set_event_transaction_id(kwargs['event_transaction_id'])

    if 'event_transaction_type' in kwargs:
        set_event_transaction_type(kwargs['event_transaction_type'])

    try:
        return compute_grades_for_course(kwargs['course_key'], kwargs['offset'], kwargs['batch_size'])
    except Exception as exc:   # pylint: disable=broad-except
        raise self.retry(kwargs=kwargs, exc=exc)


@task(base=LoggedPersistOnFailureTask)
def compute_grades_for_course(course_key, offset, batch_size, **kwargs):  # pylint: disable=unused-argument
    """
    Compute and save grades for a set of students in the specified course.

    The set of students will be determined by the order of enrollment date, and
    limited to at most <batch_size> students, starting from the specified
    offset.
    """
    course_key = CourseKey.from_string(course_key)
    enrollments = CourseEnrollment.objects.filter(course_id=course_key).order_by('created')
    student_iter = (enrollment.user for enrollment in enrollments[offset:offset + batch_size])
    for result in CourseGradeFactory().iter(users=student_iter, course_key=course_key, force_update=True):
        if result.error is not None:
            raise result.error


def generate_xblock_structure_url(course_str, block_key, user):
    """
    Generate url/link to JSON representation of xblock
    """
    xblock_structure_url = '{}/api/courses/v1/blocks/?course_id={}&block_id={}&username={}'.format(
        settings.LMS_ROOT_URL,
        urllib.quote_plus(str(course_str)),
        block_key,
        user.username
    )

    return xblock_structure_url



def get_user_grades_task(user_id, course_str):
    """
    Get a single user's grades for  course. 
    """ 
    user = USER_MODEL.objects.get(id=user_id)
    course_key = CourseKey.from_string(str(course_str))
    course = courses.get_course(course_key)
    course_grade = CourseGradeFactory().update(user, course)
    course_structure = get_course_in_cache(course.id)
    courseware_summary = course_grade.chapter_grades.values()
    grade_summary = course_grade.summary
    grades_schema = {}
    courseware_summary = course_grade.chapter_grades.items()
    chapter_schema = {}
    for key, chapter in courseware_summary:
        subsection_schema = {}
        for section in chapter['sections']:
            section_children = course_structure.get_children(section.location)
            verticals = course_structure.get_children(section.location)
            vertical_schema = {}
            for vertical_key in verticals:
                sections_scores  = {}
                problem_keys = course_structure.get_children(vertical_key)
                for problem_key in problem_keys:
                    if problem_key in section.problem_scores:
                        problem_score = section.problem_scores[problem_key]
                        xblock_content_url = reverse(
                            'courseware.views.views.render_xblock',
                            kwargs={'usage_key_string': unicode(problem_key)},
                        )
                        xblock_structure_url = generate_xblock_structure_url(course_str, problem_key, user)
                        sections_scores[str(problem_key)] = {
                           "date" : problem_score.first_attempted if problem_score.first_attempted is not None else "Not attempted",
                           "earned" :problem_score.earned,
                           "possible" :problem_score.possible,
                           "xblock_content_url": "{}{}".format(settings.LMS_ROOT_URL, xblock_content_url),
                           "xblock_structure_url": "{}{}".format(settings.LMS_ROOT_URL,xblock_structure_url)
                        }
                    else:
                        sections_scores[str(problem_key)] = "This block has no grades"
                vertical_structure_url = generate_xblock_structure_url(course_str, vertical_key, user)
                vertical_schema[str(vertical_key)] = {'problem_blocks': sections_scores, "vertical_structure_url": vertical_structure_url}
            subsection_structure_url = generate_xblock_structure_url(course_str, section.location, user)
            subsection_schema[str(section.location)] =  {
                "verticals": vertical_schema,
                "section_score": course_grade.score_for_module(section.location),
                "subsection_structure_url": subsection_structure_url
            }
        chapter_structure_url = generate_xblock_structure_url(course_str, key, user)
        chapter_schema[str(key)] = {
            "sections": subsection_schema,
            "chapter_structure_url": chapter_structure_url
        }

    return chapter_schema


@task(base=_BaseTask)
def get_user_course_response_task(users, course_str, depth, **kwargs):
    """
    Get a list of users grades' for a course
    """
    user_grades = {}
    grades_schema = {}
    course_key = CourseKey.from_string(str(course_str))
    print "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHh"
    course = courses.get_course(course_key)
    for user in users:
        course_grade = CourseGradeFactory().update(user, course)
        if depth=="all":
            grades_schema = get_user_grades(user.id, course_str)
        else:
            grades_schema = "Showing course grade summary, specify depth=all in query params."
        user_grades[user.username] = {
           'name': "{} {}".format(user.first_name, user.last_name),
           'email': user.email,
           'start_date':course.start,
           'end_date': course.end if not None else "This course has no end date.",
           'all_grades': grades_schema,
           "passed": course_grade.passed,
           "percent": course_grade.percent
        }


    return user_grades

@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    time_limit=SUBSECTION_GRADE_TIMEOUT_SECONDS,
    max_retries=2,
    default_retry_delay=RETRY_DELAY_SECONDS,
    routing_key=settings.RECALCULATE_GRADES_ROUTING_KEY
)
def recalculate_subsection_grade_v3(self, **kwargs):
    """
    Latest version of the recalculate_subsection_grade task.  See docstring
    for _recalculate_subsection_grade for further description.
    """
    _recalculate_subsection_grade(self, **kwargs)


def _recalculate_subsection_grade(self, **kwargs):
    """
    Updates a saved subsection grade.

    Keyword Arguments:
        user_id (int): id of applicable User object
        anonymous_user_id (int, OPTIONAL): Anonymous ID of the User
        course_id (string): identifying the course
        usage_id (string): identifying the course block
        only_if_higher (boolean): indicating whether grades should
            be updated only if the new raw_earned is higher than the
            previous value.
        expected_modified_time (serialized timestamp): indicates when the task
            was queued so that we can verify the underlying data update.
        score_deleted (boolean): indicating whether the grade change is
            a result of the problem's score being deleted.
        event_transaction_id (string): uuid identifying the current
            event transaction.
        event_transaction_type (string): human-readable type of the
            event at the root of the current event transaction.
        score_db_table (ScoreDatabaseTableEnum): database table that houses
            the changed score. Used in conjunction with expected_modified_time.
    """
    try:
        course_key = CourseLocator.from_string(kwargs['course_id'])
        scored_block_usage_key = UsageKey.from_string(kwargs['usage_id']).replace(course_key=course_key)

        set_custom_metrics_for_course_key(course_key)
        set_custom_metric('usage_id', unicode(scored_block_usage_key))

        # The request cache is not maintained on celery workers,
        # where this code runs. So we take the values from the
        # main request cache and store them in the local request
        # cache. This correlates model-level grading events with
        # higher-level ones.
        set_event_transaction_id(kwargs.get('event_transaction_id'))
        set_event_transaction_type(kwargs.get('event_transaction_type'))

        # Verify the database has been updated with the scores when the task was
        # created. This race condition occurs if the transaction in the task
        # creator's process hasn't committed before the task initiates in the worker
        # process.
        has_database_updated = _has_db_updated_with_new_score(self, scored_block_usage_key, **kwargs)

        if not has_database_updated:
            raise DatabaseNotReadyError

        _update_subsection_grades(
            course_key,
            scored_block_usage_key,
            kwargs['only_if_higher'],
            kwargs['user_id'],
            kwargs['score_deleted'],
        )
    except Exception as exc:   # pylint: disable=broad-except
        if not isinstance(exc, KNOWN_RETRY_ERRORS):
            log.info("tnl-6244 grades unexpected failure: {}. task id: {}. kwargs={}".format(
                repr(exc),
                self.request.id,
                kwargs,
            ))
        raise self.retry(kwargs=kwargs, exc=exc)


def _has_db_updated_with_new_score(self, scored_block_usage_key, **kwargs):
    """
    Returns whether the database has been updated with the
    expected new score values for the given problem and user.
    """
    if kwargs['score_db_table'] == ScoreDatabaseTableEnum.courseware_student_module:
        score = get_score(kwargs['user_id'], scored_block_usage_key)
        found_modified_time = score.modified if score is not None else None

    elif kwargs['score_db_table'] == ScoreDatabaseTableEnum.submissions:
        score = sub_api.get_score(
            {
                "student_id": kwargs['anonymous_user_id'],
                "course_id": unicode(scored_block_usage_key.course_key),
                "item_id": unicode(scored_block_usage_key),
                "item_type": scored_block_usage_key.block_type,
            }
        )
        found_modified_time = score['created_at'] if score is not None else None
    else:
        assert kwargs['score_db_table'] == ScoreDatabaseTableEnum.overrides
        score = GradesService().get_subsection_grade_override(
            user_id=kwargs['user_id'],
            course_key_or_id=kwargs['course_id'],
            usage_key_or_id=kwargs['usage_id']
        )
        found_modified_time = score.modified if score is not None else None

    if score is None:
        # score should be None only if it was deleted.
        # Otherwise, it hasn't yet been saved.
        db_is_updated = kwargs['score_deleted']
    else:
        db_is_updated = found_modified_time >= from_timestamp(kwargs['expected_modified_time'])

    if not db_is_updated:
        log.info(
            u"Grades: tasks._has_database_updated_with_new_score is False. Task ID: {}. Kwargs: {}. Found "
            u"modified time: {}".format(
                self.request.id,
                kwargs,
                found_modified_time,
            )
        )

    return db_is_updated


def _update_subsection_grades(course_key, scored_block_usage_key, only_if_higher, user_id, score_deleted):
    """
    A helper function to update subsection grades in the database
    for each subsection containing the given block, and to signal
    that those subsection grades were updated.
    """
    student = User.objects.get(id=user_id)
    store = modulestore()
    with store.bulk_operations(course_key):
        course_structure = get_course_blocks(student, store.make_course_usage_key(course_key))
        subsections_to_update = course_structure.get_transformer_block_field(
            scored_block_usage_key,
            GradesTransformer,
            'subsections',
            set(),
        )

        course = store.get_course(course_key, depth=0)
        subsection_grade_factory = SubsectionGradeFactory(student, course, course_structure)

        for subsection_usage_key in subsections_to_update:
            if subsection_usage_key in course_structure:
                subsection_grade = subsection_grade_factory.update(
                    course_structure[subsection_usage_key],
                    only_if_higher,
                    score_deleted
                )
                SUBSECTION_SCORE_CHANGED.send(
                    sender=None,
                    course=course,
                    course_structure=course_structure,
                    user=student,
                    subsection_grade=subsection_grade,
                )


def _course_task_args(course_key, **kwargs):
    """
    Helper function to generate course-grade task args.
    """
    from_settings = kwargs.pop('from_settings', True)
    enrollment_count = CourseEnrollment.objects.filter(course_id=course_key).count()
    if enrollment_count == 0:
        log.warning("No enrollments found for {}".format(course_key))

    if from_settings is False:
        batch_size = kwargs.pop('batch_size', 100)
    else:
        batch_size = ComputeGradesSetting.current().batch_size

    for offset in six.moves.range(0, enrollment_count, batch_size):
        yield (six.text_type(course_key), offset, batch_size)
