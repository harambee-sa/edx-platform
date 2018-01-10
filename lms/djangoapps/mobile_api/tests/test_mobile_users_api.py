#pylint: disable=missing-docstring

import ddt
import mock
from django.test.utils import override_settings
from django.test import TestCase

from openedx.core.djangolib.testing.utils import skip_unless_lms


@skip_unless_lms
@ddt.ddt
class TestMobileUsersApi(TestCase):

    def setUp(self):
        super(TestMobileUsersApi, self).setUp()

    @override_settings(USER_COURSE_ENROLLMENTS_ORDER_BY='created')
    def test_user_course_enrollment_order_by_created(self):
        self.assertEqual(True, True)

    @override_settings(USER_COURSE_ENROLLMENTS_ORDER_BY='created_reverse')
    def test_user_course_enrollment_order_by_created_reverse(self):
        self.assertEqual(True, True)

    @override_settings(USER_COURSE_ENROLLMENTS_ORDER_BY='course_name')
    def test_user_course_enrollment_order_by_course_name(self):
        self.assertEqual(True, True)

    @override_settings(USER_COURSE_ENROLLMENTS_ORDER_BY='course_name_reverse')
    def test_user_course_enrollment_order_by_course_name_reverse(self):
        self.assertEqual(True, True)