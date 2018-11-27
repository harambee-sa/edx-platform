import unicodecsv as csv

from django.utils import timezone
from xmodule.modulestore.exceptions import ItemNotFoundError

from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

from lms.djangoapps.grades.models import PersistentCourseGrade

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


def csv_course_report(f):
    field_names = [
        'Candidate RSA ID number',
        'Candidate First Name',
        'Candidate Last Name',
        'Enrollment Date',
        '% Complete to date',
        'Completion Date',
        'Duration between enrollment and completion',
    ]
    writer = csv.DictWriter(f, fieldnames=field_names)
    for course_overview in CourseOverview.objects.all():
        course_title = [course_overview.id, course_overview.display_name]
        course_title.extend([''] * (len(field_names) - 2))
        writer.writerow(dict(zip(field_names, course_title)))
        writer.writeheader()

        for enrollment in course_overview.courseenrollment_set.filter(is_active=True):
            row_values = []

            user = enrollment.user
            row_values.append(user.username)
            row_values.append(user.first_name)
            row_values.append(user.last_name)

            row_values.append(timezone.localtime(enrollment.created))

            grades_num = 0
            grades_total = 0
            course_grade = CourseGradeFactory().read(user, course_key=course_overview.id)
            try:
                for courseware in course_grade.chapter_grades.values():
                    sections = courseware['sections']
                    for section in sections:
                        if section.problem_scores.values():
                            grades_num += 1
                            total = section.all_total.possible
                            earned = section.all_total.earned
                            if total > 0 and earned > 0:
                                grades_total += float(earned) / total
                grade = u'{}%'.format(round(grades_total/grades_num*100, 2)) if grades_total > 0 else None
                row_values.append(grade)
            except ItemNotFoundError:
                row_values.append('grade not found')

            try:
                persistent_grade = PersistentCourseGrade.objects.get(user_id=user.id, course_id=course_overview.id)
                if persistent_grade.passed_timestamp:
                    row_values.append(timezone.localtime(persistent_grade.passed_timestamp))
                    row_values.append(persistent_grade.passed_timestamp - enrollment.created)
            except PersistentCourseGrade.DoesNotExist:
                pass

            row_values.extend([''] * (len(field_names) - len(row_values)))
            writer.writerow(dict(zip(field_names, row_values)))

        writer.writerow(dict(zip(field_names, [''] * len(field_names))))
