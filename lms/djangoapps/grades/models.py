"""
Models used for robust grading.

Robust grading allows student scores to be saved per-subsection independent
of any changes that may occur to the course after the score is achieved.
We also persist students' course-level grades, and update them whenever
a student's score or the course grading policy changes. As they are
persisted, course grades are also immune to changes in course content.
"""

import json
import logging
from base64 import b64encode
from collections import namedtuple
from hashlib import sha1

from django.db import models
from django.utils.timezone import now
from lazy import lazy
from model_utils.models import TimeStampedModel
from opaque_keys.edx.keys import CourseKey, UsageKey

from coursewarehistoryextended.fields import UnsignedBigIntAutoField, UnsignedBigIntOneToOneField
from openedx.core.djangoapps.xmodule_django.models import CourseKeyField, UsageKeyField
from request_cache import get_cache

import events

log = logging.getLogger(__name__)


BLOCK_RECORD_LIST_VERSION = 1

# Used to serialize information about a block at the time it was used in
# grade calculation.
BlockRecord = namedtuple('BlockRecord', ['locator', 'weight', 'raw_possible', 'graded'])


class BlockRecordList(tuple):
    """
    An immutable ordered list of BlockRecord objects.
    """

    def __new__(cls, blocks, course_key, version=None):  # pylint: disable=unused-argument
        return super(BlockRecordList, cls).__new__(cls, blocks)

    def __init__(self, blocks, course_key, version=None):
        super(BlockRecordList, self).__init__(blocks)
        self.course_key = course_key
        self.version = version or BLOCK_RECORD_LIST_VERSION

    def __eq__(self, other):
        assert isinstance(other, BlockRecordList)
        return hash(self) == hash(other)

    def __hash__(self):
        """
        Returns an integer Type value of the hash of this
        list of block records, as required by python.
        """
        return hash(self.hash_value)

    @lazy
    def hash_value(self):
        """
        Returns a hash value of the list of block records.

        This currently hashes using sha1, and returns a base64 encoded version
        of the binary digest.  In the future, different algorithms could be
        supported by adding a label indicated which algorithm was used, e.g.,
        "sha256$j0NDRmSPa5bfid2pAcUXaxCm2Dlh3TwayItZstwyeqQ=".
        """
        return b64encode(sha1(self.json_value).digest())

    @lazy
    def json_value(self):
        """
        Return a JSON-serialized version of the list of block records, using a
        stable ordering.
        """
        list_of_block_dicts = [block._asdict() for block in self]
        for block_dict in list_of_block_dicts:
            block_dict['locator'] = unicode(block_dict['locator'])  # BlockUsageLocator is not json-serializable
        data = {
            u'blocks': list_of_block_dicts,
            u'course_key': unicode(self.course_key),
            u'version': self.version,
        }
        return json.dumps(
            data,
            separators=(',', ':'),  # Remove spaces from separators for more compact representation
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, blockrecord_json):
        """
        Return a BlockRecordList from previously serialized json.
        """
        data = json.loads(blockrecord_json)
        course_key = CourseKey.from_string(data['course_key'])
        block_dicts = data['blocks']
        record_generator = (
            BlockRecord(
                locator=UsageKey.from_string(block["locator"]).replace(course_key=course_key),
                weight=block["weight"],
                raw_possible=block["raw_possible"],
                graded=block["graded"],
            )
            for block in block_dicts
        )
        return cls(record_generator, course_key, version=data['version'])

    @classmethod
    def from_list(cls, blocks, course_key):
        """
        Return a BlockRecordList from the given list and course_key.
        """
        return cls(blocks, course_key)


class VisibleBlocks(models.Model):
    """
    A django model used to track the state of a set of visible blocks under a
    given subsection at the time they are used for grade calculation.

    This state is represented using an array of BlockRecord, stored
    in the blocks_json field. A hash of this json array is used for lookup
    purposes.
    """
    blocks_json = models.TextField()
    hashed = models.CharField(max_length=100, unique=True)
    course_id = CourseKeyField(blank=False, max_length=255, db_index=True)

    _CACHE_NAMESPACE = u"grades.models.VisibleBlocks"

    class Meta(object):
        app_label = "grades"

    def __unicode__(self):
        """
        String representation of this model.
        """
        return u"VisibleBlocks object - hash:{}, raw json:'{}'".format(self.hashed, self.blocks_json)

    @property
    def blocks(self):
        """
        Returns the blocks_json data stored on this model as a list of
        BlockRecords in the order they were provided.
        """
        return BlockRecordList.from_json(self.blocks_json)

    @classmethod
    def bulk_read(cls, course_key):
        """
        Reads and returns all visible block records for the given course from
        the cache.  The cache is initialize with the visible blocks for this
        course if no entry currently exists.has no entry for this course,
        the cache is updated.

        Arguments:
            course_key: The course identifier for the desired records
        """
        prefetched = get_cache(cls._CACHE_NAMESPACE).get(cls._cache_key(course_key), None)
        if prefetched is None:
            prefetched = cls._initialize_cache(course_key)
        return prefetched

    @classmethod
    def cached_get_or_create(cls, blocks):
        prefetched = get_cache(cls._CACHE_NAMESPACE).get(cls._cache_key(blocks.course_key))
        if prefetched is not None:
            model = prefetched.get(blocks.hash_value)
            if not model:
                model = cls.objects.create(
                    hashed=blocks.hash_value, blocks_json=blocks.json_value, course_id=blocks.course_key,
                )
                cls._update_cache(blocks.course_key, [model])
        else:
            model, _ = cls.objects.get_or_create(
                hashed=blocks.hash_value,
                defaults={u'blocks_json': blocks.json_value, u'course_id': blocks.course_key},
            )
        return model

    @classmethod
    def bulk_create(cls, course_key, block_record_lists):
        """
        Bulk creates VisibleBlocks for the given iterator of
        BlockRecordList objects and updates the VisibleBlocks cache
        for the block records' course with the new VisibleBlocks.
        Returns the newly created visible blocks.
        """
        created = cls.objects.bulk_create([
            VisibleBlocks(
                blocks_json=brl.json_value,
                hashed=brl.hash_value,
                course_id=course_key,
            )
            for brl in block_record_lists
        ])
        cls._update_cache(course_key, created)
        return created

    @classmethod
    def bulk_get_or_create(cls, block_record_lists, course_key):
        """
        Bulk creates VisibleBlocks for the given iterator of
        BlockRecordList objects for the given course_key, but
        only for those that aren't already created.
        """
        existent_records = cls.bulk_read(course_key)
        non_existent_brls = {brl for brl in block_record_lists if brl.hash_value not in existent_records}
        cls.bulk_create(course_key, non_existent_brls)

    @classmethod
    def _initialize_cache(cls, course_key):
        """
        Prefetches visible blocks for the given course and stores in the cache.
        Returns a dictionary mapping hashes of these block records to the
        block record objects.
        """
        prefetched = {record.hashed: record for record in cls.objects.filter(course_id=course_key)}
        get_cache(cls._CACHE_NAMESPACE)[cls._cache_key(course_key)] = prefetched
        return prefetched

    @classmethod
    def _update_cache(cls, course_key, visible_blocks):
        """
        Adds a specific set of visible blocks to the request cache.
        This assumes that prefetch has already been called.
        """
        get_cache(cls._CACHE_NAMESPACE)[cls._cache_key(course_key)].update(
            {visible_block.hashed: visible_block for visible_block in visible_blocks}
        )

    @classmethod
    def _cache_key(cls, course_key):
        return u"visible_blocks_cache.{}".format(course_key)


class PersistentSubsectionGrade(TimeStampedModel):
    """
    A django model tracking persistent grades at the subsection level.
    """

    class Meta(object):
        app_label = "grades"
        unique_together = [
            # * Specific grades can be pulled using all three columns,
            # * Progress page can pull all grades for a given (course_id, user_id)
            # * Course staff can see all grades for a course using (course_id,)
            ('course_id', 'user_id', 'usage_key'),
        ]
        # Allows querying in the following ways:
        # (modified): find all the grades updated within a certain timespan
        # (modified, course_id): find all the grades updated within a timespan for a certain course
        # (modified, course_id, usage_key): find all the grades updated within a timespan for a subsection
        #   in a course
        # (first_attempted, course_id, user_id): find all attempted subsections in a course for a user
        # (first_attempted, course_id): find all attempted subsections in a course for all users
        index_together = [
            ('modified', 'course_id', 'usage_key'),
            ('first_attempted', 'course_id', 'user_id')
        ]

    # primary key will need to be large for this table
    id = UnsignedBigIntAutoField(primary_key=True)  # pylint: disable=invalid-name

    user_id = models.IntegerField(blank=False)
    course_id = CourseKeyField(blank=False, max_length=255)

    # note: the usage_key may not have the run filled in for
    # old mongo courses.  Use the full_usage_key property
    # instead when you want to use/compare the usage_key.
    usage_key = UsageKeyField(blank=False, max_length=255)

    # Information relating to the state of content when grade was calculated
    subtree_edited_timestamp = models.DateTimeField(u'Last content edit timestamp', blank=True, null=True)
    course_version = models.CharField(u'Guid of latest course version', blank=True, max_length=255)

    # earned/possible refers to the number of points achieved and available to achieve.
    # graded refers to the subset of all problems that are marked as being graded.
    earned_all = models.FloatField(blank=False)
    possible_all = models.FloatField(blank=False)
    earned_graded = models.FloatField(blank=False)
    possible_graded = models.FloatField(blank=False)

    # timestamp for the learner's first attempt at content in
    # this subsection. If null, indicates no attempt
    # has yet been made.
    first_attempted = models.DateTimeField(null=True, blank=True)

    # track which blocks were visible at the time of grade calculation
    visible_blocks = models.ForeignKey(VisibleBlocks, db_column='visible_blocks_hash', to_field='hashed')

    @property
    def full_usage_key(self):
        """
        Returns the "correct" usage key value with the run filled in.
        """
        if self.usage_key.run is None:  # pylint: disable=no-member
            return self.usage_key.replace(course_key=self.course_id)
        else:
            return self.usage_key

    def __unicode__(self):
        """
        Returns a string representation of this model.
        """
        return (
            u"{} user: {}, course version: {}, subsection: {} ({}). {}/{} graded, {}/{} all, first_attempted: {}"
        ).format(
            type(self).__name__,
            self.user_id,
            self.course_version,
            self.usage_key,
            self.visible_blocks_id,
            self.earned_graded,
            self.possible_graded,
            self.earned_all,
            self.possible_all,
            self.first_attempted,
        )

    @classmethod
    def read_grade(cls, user_id, usage_key):
        """
        Reads a grade from database

        Arguments:
            user_id: The user associated with the desired grade
            usage_key: The location of the subsection associated with the desired grade

        Raises PersistentSubsectionGrade.DoesNotExist if applicable
        """
        return cls.objects.select_related('visible_blocks', 'override').get(
            user_id=user_id,
            course_id=usage_key.course_key,  # course_id is included to take advantage of db indexes
            usage_key=usage_key,
        )

    @classmethod
    def bulk_read_grades(cls, user_id, course_key):
        """
        Reads all grades for the given user and course.

        Arguments:
            user_id: The user associated with the desired grades
            course_key: The course identifier for the desired grades
        """
        return cls.objects.select_related('visible_blocks', 'override').filter(
            user_id=user_id,
            course_id=course_key,
        )

    @classmethod
    def update_or_create_grade(cls, **params):
        """
        Wrapper for objects.update_or_create.
        """
        cls._prepare_params(params)
        VisibleBlocks.cached_get_or_create(params['visible_blocks'])
        cls._prepare_params_visible_blocks_id(params)
        cls._prepare_params_override(params)

        first_attempted = params.pop('first_attempted')
        user_id = params.pop('user_id')
        usage_key = params.pop('usage_key')

        grade, _ = cls.objects.update_or_create(
            user_id=user_id,
            course_id=usage_key.course_key,
            usage_key=usage_key,
            defaults=params,
        )
        if first_attempted is not None and grade.first_attempted is None:
            grade.first_attempted = first_attempted
            grade.save()

        cls._emit_grade_calculated_event(grade)
        return grade

    @classmethod
    def bulk_create_grades(cls, grade_params_iter, user_id, course_key):
        """
        Bulk creation of grades.
        """
        if not grade_params_iter:
            return

        PersistentSubsectionGradeOverride.prefetch(user_id, course_key)

        map(cls._prepare_params, grade_params_iter)
        VisibleBlocks.bulk_get_or_create([params['visible_blocks'] for params in grade_params_iter], course_key)
        map(cls._prepare_params_visible_blocks_id, grade_params_iter)
        map(cls._prepare_params_override, grade_params_iter)

        grades = [PersistentSubsectionGrade(**params) for params in grade_params_iter]
        grades = cls.objects.bulk_create(grades)
        for grade in grades:
            cls._emit_grade_calculated_event(grade)
        return grades

    @classmethod
    def _prepare_params(cls, params):
        """
        Prepares the fields for the grade record.
        """
        if not params.get('course_id', None):
            params['course_id'] = params['usage_key'].course_key
        params['course_version'] = params.get('course_version', None) or ""
        params['visible_blocks'] = BlockRecordList.from_list(params['visible_blocks'], params['course_id'])

    @classmethod
    def _prepare_params_visible_blocks_id(cls, params):
        """
        Prepares the visible_blocks_id field for the grade record,
        using the hash of the visible_blocks field.  Specifying
        the hashed field eliminates extra queries to get the
        VisibleBlocks record.  Use this variation of preparing
        the params when you are sure of the existence of the
        VisibleBlock.
        """
        params['visible_blocks_id'] = params['visible_blocks'].hash_value
        del params['visible_blocks']

    @classmethod
    def _prepare_params_override(cls, params):
        override = PersistentSubsectionGradeOverride.get_override(params['user_id'], params['usage_key'])
        if override:
            if override.earned_all_override is not None:
                params['earned_all'] = override.earned_all_override
            if override.possible_all_override is not None:
                params['possible_all'] = override.possible_all_override
            if override.earned_graded_override is not None:
                params['earned_graded'] = override.earned_graded_override
            if override.possible_graded_override is not None:
                params['possible_graded'] = override.possible_graded_override

    @staticmethod
    def _emit_grade_calculated_event(grade):
        events.subsection_grade_calculated(grade)


class PersistentCourseGrade(TimeStampedModel):
    """
    A django model tracking persistent course grades.
    """

    class Meta(object):
        app_label = "grades"
        # Indices:
        # (course_id, user_id) for individual grades
        # (course_id) for instructors to see all course grades, implicitly created via the unique_together constraint
        # (user_id) for course dashboard; explicitly declared as an index below
        # (passed_timestamp, course_id) for tracking when users first earned a passing grade.
        # (modified): find all the grades updated within a certain timespan
        # (modified, course_id): find all the grades updated within a certain timespan for a course
        unique_together = [
            ('course_id', 'user_id'),
        ]
        index_together = [
            ('passed_timestamp', 'course_id'),
            ('modified', 'course_id')
        ]

    # primary key will need to be large for this table
    id = UnsignedBigIntAutoField(primary_key=True)  # pylint: disable=invalid-name
    user_id = models.IntegerField(blank=False, db_index=True)
    course_id = CourseKeyField(blank=False, max_length=255)

    # Information relating to the state of content when grade was calculated
    course_edited_timestamp = models.DateTimeField(u'Last content edit timestamp', blank=True, null=True)
    course_version = models.CharField(u'Course content version identifier', blank=True, max_length=255)
    grading_policy_hash = models.CharField(u'Hash of grading policy', blank=False, max_length=255)

    # Information about the course grade itself
    percent_grade = models.FloatField(blank=False)
    letter_grade = models.CharField(u'Letter grade for course', blank=False, max_length=255)

    # Information related to course completion
    passed_timestamp = models.DateTimeField(u'Date learner earned a passing grade', blank=True, null=True)

    _CACHE_NAMESPACE = u"grades.models.PersistentCourseGrade"

    def __unicode__(self):
        """
        Returns a string representation of this model.
        """
        return u', '.join([
            u"{} user: {}".format(type(self).__name__, self.user_id),
            u"course version: {}".format(self.course_version),
            u"grading policy: {}".format(self.grading_policy_hash),
            u"percent grade: {}%".format(self.percent_grade),
            u"letter grade: {}".format(self.letter_grade),
            u"passed timestamp: {}".format(self.passed_timestamp),
        ])

    @classmethod
    def prefetch(cls, course_id, users):
        """
        Prefetches grades for the given users for the given course.
        """
        get_cache(cls._CACHE_NAMESPACE)[cls._cache_key(course_id)] = {
            grade.user_id: grade
            for grade in
            cls.objects.filter(user_id__in=[user.id for user in users], course_id=course_id)
        }

    @classmethod
    def read(cls, user_id, course_id):
        """
        Reads a grade from database

        Arguments:
            user_id: The user associated with the desired grade
            course_id: The id of the course associated with the desired grade

        Raises PersistentCourseGrade.DoesNotExist if applicable
        """
        try:
            prefetched_grades = get_cache(cls._CACHE_NAMESPACE)[cls._cache_key(course_id)]
            try:
                return prefetched_grades[user_id]
            except KeyError:
                # user's grade is not in the prefetched list, so
                # assume they have no grade
                raise cls.DoesNotExist
        except KeyError:
            # grades were not prefetched for the course, so fetch it
            return cls.objects.get(user_id=user_id, course_id=course_id)

    @classmethod
    def update_or_create(cls, user_id, course_id, **kwargs):
        """
        Creates a course grade in the database.
        Returns a PersistedCourseGrade object.
        """
        passed = kwargs.pop('passed')

        if kwargs.get('course_version', None) is None:
            kwargs['course_version'] = ""

        grade, _ = cls.objects.update_or_create(
            user_id=user_id,
            course_id=course_id,
            defaults=kwargs
        )
        if passed and not grade.passed_timestamp:
            grade.passed_timestamp = now()
            grade.save()

        cls._emit_grade_calculated_event(grade)
        cls._update_cache(course_id, user_id, grade)
        return grade

    @classmethod
    def _update_cache(cls, course_id, user_id, grade):
        course_cache = get_cache(cls._CACHE_NAMESPACE).get(cls._cache_key(course_id))
        if course_cache is not None:
            course_cache[user_id] = grade

    @classmethod
    def _cache_key(cls, course_id):
        return u"grades_cache.{}".format(course_id)

    @staticmethod
    def _emit_grade_calculated_event(grade):
        events.course_grade_calculated(grade)


class PersistentSubsectionGradeOverride(models.Model):
    """
    A django model tracking persistent grades overrides at the subsection level.
    """
    class Meta(object):
        app_label = "grades"

    grade = UnsignedBigIntOneToOneField(PersistentSubsectionGrade, related_name='override')

    # Created/modified timestamps prevent race-conditions when using with async rescoring tasks
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    # earned/possible refers to the number of points achieved and available to achieve.
    # graded refers to the subset of all problems that are marked as being graded.
    earned_all_override = models.FloatField(null=True, blank=True)
    possible_all_override = models.FloatField(null=True, blank=True)
    earned_graded_override = models.FloatField(null=True, blank=True)
    possible_graded_override = models.FloatField(null=True, blank=True)

    _CACHE_NAMESPACE = u"grades.models.PersistentSubsectionGradeOverride"

    @classmethod
    def prefetch(cls, user_id, course_key):
        get_cache(cls._CACHE_NAMESPACE)[(user_id, str(course_key))] = {
            override.grade.usage_key: override
            for override in
            cls.objects.filter(grade__user_id=user_id, grade__course_id=course_key)
        }

    @classmethod
    def get_override(cls, user_id, usage_key):
        prefetch_values = get_cache(cls._CACHE_NAMESPACE).get((user_id, str(usage_key.course_key)), None)
        if prefetch_values is not None:
            return prefetch_values.get(usage_key)
        try:
            return cls.objects.get(
                grade__user_id=user_id,
                grade__course_id=usage_key.course_key,
                grade__usage_key=usage_key,
            )
        except PersistentSubsectionGradeOverride.DoesNotExist:
            pass


def prefetch(user, course_key):
    PersistentSubsectionGradeOverride.prefetch(user.id, course_key)
    VisibleBlocks.bulk_read(course_key)

