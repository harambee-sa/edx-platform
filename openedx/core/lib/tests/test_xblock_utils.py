"""
Tests for xblock_utils.py
"""
from __future__ import unicode_literals, absolute_import

import ddt
import uuid

from django.test.client import RequestFactory

from courseware.models import StudentModule  # pylint: disable=import-error
from lms.djangoapps.lms_xblock.runtime import quote_slashes
from xblock.fragment import Fragment
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from openedx.core.lib.xblock_utils import (
    wrap_fragment,
    request_token,
    wrap_xblock,
    replace_jump_to_id_urls,
    replace_course_urls,
    replace_static_urls,
    grade_histogram,
    sanitize_html_id
)


@ddt.ddt
class TestXblockUtils(SharedModuleStoreTestCase):
    """Tests for xblock utility functions."""

    @classmethod
    def setUpClass(cls):
        super(TestXblockUtils, cls).setUpClass()
        cls.course_mongo = CourseFactory.create(
            default_store=ModuleStoreEnum.Type.mongo,
            org='TestX',
            number='TS01',
            run='2015'
        )
        cls.course_split = CourseFactory.create(
            default_store=ModuleStoreEnum.Type.split,
            org='TestX',
            number='TS02',
            run='2015'
        )

    def setUp(self):
        super(TestXblockUtils, self).setUp()

    def create_fragment(self, content=None):
        """Create a fragment."""
        fragment = Fragment(content)
        fragment.add_css('body {background-color:red;}')
        fragment.add_javascript('alert("Hi!");')
        return fragment

    def test_wrap_fragment(self):
        """Verify that wrap_fragment adds new content."""
        new_content = '<p>New Content<p>'
        fragment = self.create_fragment()
        wrapped_fragment = wrap_fragment(fragment, new_content)
        self.assertEqual('<p>New Content<p>', wrapped_fragment.content)
        self.assertEqual('body {background-color:red;}', wrapped_fragment.resources[0].data)
        self.assertEqual('alert("Hi!");', wrapped_fragment.resources[1].data)

    def test_request_token(self):
        """Verify that a proper token is returned."""
        request_with_token = RequestFactory().get('/')
        request_with_token._xblock_token = '123'  # pylint: disable=protected-access
        token = request_token(request_with_token)
        self.assertEqual(token, '123')

        request_without_token = RequestFactory().get('/')
        token = request_token(request_without_token)
        # Test to see if the token is an uuid1 hex value
        test_uuid = uuid.UUID(token, version=1)
        self.assertEqual(token, test_uuid.hex)

    @ddt.data('course_mongo', 'course_split')
    def test_wrap_xblock(self, course_id):
        """Verify that new content is added and the resources are the same."""
        fragment = self.create_fragment(u"<h1>Test!</h1>")
        course = getattr(self, course_id)
        test_wrap_output = wrap_xblock(
            runtime_class='TestRuntime',
            block=course,
            view='baseview',
            frag=fragment,
            context=None,
            usage_id_serializer=lambda usage_id: quote_slashes(unicode(usage_id)),
            request_token=uuid.uuid1().get_hex()
        )
        self.assertIsInstance(test_wrap_output, Fragment)
        self.assertIn('xblock-baseview', test_wrap_output.content)
        self.assertIn('data-runtime-class="TestRuntime"', test_wrap_output.content)
        if course_id == 'course_mongo':
            self.assertIn(
                'data-usage-id="i4x:;_;_TestX;_TS01;_course;_2015"',
                test_wrap_output.content
            )
        else:
            self.assertIn(
                'data-usage-id="block-v1:TestX+TS02+2015+type@course+block@course"',
                test_wrap_output.content
            )
        self.assertIn('<h1>Test!</h1>', test_wrap_output.content)
        self.assertEqual(test_wrap_output.resources[0].data, u'body {background-color:red;}')
        self.assertEqual(test_wrap_output.resources[1].data, 'alert("Hi!");')

    @ddt.data('course_mongo', 'course_split')
    def test_replace_jump_to_id_urls(self, course_id):
        """Verify that the jump-to URL has been replaced."""
        course = getattr(self, course_id)
        test_replace = replace_jump_to_id_urls(
            course_id=course.id,
            jump_to_id_base_url='/base_url/',
            block=course,
            view='baseview',
            frag=Fragment('<a href="/jump_to_id/id">'),
            context=None
        )
        self.assertIsInstance(test_replace, Fragment)
        self.assertEqual(test_replace.content, '<a href="/base_url/id">')

    @ddt.data('course_mongo', 'course_split')
    def test_replace_course_urls(self, course_id):
        """Verify that the course URL has been replaced."""
        course = getattr(self, course_id)
        test_replace = replace_course_urls(
            course_id=course.id,
            block=course,
            view='baseview',
            frag=Fragment('<a href="/course/id">'),
            context=None
        )
        self.assertIsInstance(test_replace, Fragment)
        if course_id == 'course_mongo':
            self.assertEqual(test_replace.content, '<a href="/courses/TestX/TS01/2015/id">')
        else:
            self.assertEqual(test_replace.content, '<a href="/courses/course-v1:TestX+TS02+2015/id">')

    @ddt.data('course_mongo', 'course_split')
    def test_replace_static_urls(self, course_id):
        """Verify that the static URL has been replaced."""
        course = getattr(self, course_id)
        test_replace = replace_static_urls(
            data_dir=None,
            course_id=course.id,
            block=course,
            view='baseview',
            frag=Fragment('<a href="/static/id">'),
            context=None
        )
        self.assertIsInstance(test_replace, Fragment)
        if course_id == 'course_mongo':
            self.assertEqual(test_replace.content, '<a href="/c4x/TestX/TS01/asset/id">')
        else:
            self.assertEqual(test_replace.content, '<a href="/asset-v1:TestX+TS02+2015+type@asset+block/id">')

    @ddt.data('course_mongo', 'course_split')
    def test_grade_histogram(self, course_id):
        """Verify that a histogram has been created."""
        course = getattr(self, course_id)
        usage_key = course.id.make_usage_key('problem', 'first_problem')
        StudentModule.objects.create(
            student_id=1,
            grade=100,
            module_state_key=usage_key
        )
        StudentModule.objects.create(
            student_id=2,
            grade=50,
            module_state_key=usage_key
        )

        grades = grade_histogram(usage_key)
        self.assertEqual(grades[0], (50.0, 1))
        self.assertEqual(grades[1], (100.0, 1))

    def test_sanitize_html_id(self):
        """Verify that colons and dashes are replaced."""
        dirty_string = 'I:have-un:allowed_characters'
        clean_string = sanitize_html_id(dirty_string)

        self.assertEqual(clean_string, 'I_have_un_allowed_characters')
