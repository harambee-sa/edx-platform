"""
Unit tests for gating.signals module
"""
from mock import patch

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.django import modulestore

from gating.signals import handle_score_changed


class TestHandleScoreChanged(ModuleStoreTestCase):
    """
    Test case for handle_score_changed django signal handler
    """
    def setUp(self):
        super(TestHandleScoreChanged, self).setUp()
        self.course = CourseFactory.create(org='TestX', number='TS01', run='2016_Q1')
        self.test_user_id = 0
        self.test_usage_key = 'i4x://the/content/key/12345678'

    @patch('gating.signals.gating_api.evaluate_prerequisite')
    def test_gating_enabled(self, mock_evaluate):
        """ Test evaluate_prerequisite is called when course.enable_subsection_gating is True """
        self.course.enable_subsection_gating = True
        modulestore().update_item(self.course, 0)
        handle_score_changed(
            sender=None,
            points_possible=1,
            points_earned=1,
            user_id=self.test_user_id,
            course_id=unicode(self.course.id),
            usage_id=self.test_usage_key
        )
        mock_evaluate.assert_called_with(self.test_user_id, self.course, self.test_usage_key)

    @patch('gating.signals.gating_api.evaluate_prerequisite')
    def test_gating_disabled(self, mock_evaluate):
        """ Test evaluate_prerequisite is not called when course.enable_subsection_gating is False """
        handle_score_changed(
            sender=None,
            points_possible=1,
            points_earned=1,
            user_id=self.test_user_id,
            course_id=unicode(self.course.id),
            usage_id=self.test_usage_key
        )
        mock_evaluate.assert_not_called()
