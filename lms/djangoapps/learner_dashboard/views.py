<<<<<<< HEAD
"""Learner dashboard views"""
=======
f>>"""Learner dashboard views"""
import waffle
>>>>>>> never use edx pattern library
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from edxmako.shortcuts import render_to_response

from lms.djangoapps.learner_dashboard.programs import ProgramsFragmentView, ProgramDetailsFragmentView
from openedx.core.djangoapps.programs.models import ProgramsApiConfig


@login_required
@require_GET
def program_listing(request):
    """View a list of programs in which the user is engaged."""
    programs_config = ProgramsApiConfig.current()
    programs_fragment = ProgramsFragmentView().render_to_fragment(request, programs_config=programs_config)

    context = {
        'disable_courseware_js': True,
        'programs_fragment': programs_fragment,
        'nav_hidden': True,
        'show_dashboard_tabs': True,
        'show_program_listing': programs_config.enabled,
        'uses_pattern_library': True,
    }

    return render_to_response('learner_dashboard/programs.html', context)


@login_required
@require_GET
def program_details(request, program_uuid):
    """View details about a specific program."""
    programs_config = ProgramsApiConfig.current()
    program_fragment = ProgramDetailsFragmentView().render_to_fragment(
        request, program_uuid, programs_config=programs_config
    )

    context = {
        'program_fragment': program_fragment,
        'show_program_listing': programs_config.enabled,
        'show_dashboard_tabs': True,
        'nav_hidden': True,
        'disable_courseware_js': True,
<<<<<<< HEAD
        'uses_pattern_library': True,
<<<<<<< HEAD
=======
        'user_preferences': get_user_preferences(request.user),
        'program_data': program_data,
        'course_data': course_data,
        'certificate_data': certificate_data
=======
        'uses_pattern_library': False,
        'user_preferences': get_user_preferences(request.user)
>>>>>>> never use edx pattern library
>>>>>>> never use edx pattern library
    }

    return render_to_response('learner_dashboard/program_details.html', context)
