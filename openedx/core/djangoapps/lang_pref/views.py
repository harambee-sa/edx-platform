"""
Language Preference Views
"""

import json

from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import LANGUAGE_SESSION_KEY
from django.views.decorators.csrf import ensure_csrf_cookie

<<<<<<< HEAD
from openedx.core.djangoapps.lang_pref import COOKIE_DURATION, LANGUAGE_KEY
=======
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY, COOKIE_DURATION
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
>>>>>>> get LANGUAGE_CODE from configuration helper


@ensure_csrf_cookie
def update_session_language(request):
    """
    Update the language session key.
    """
    response = HttpResponse(200)
    if request.method == 'PATCH':
        data = json.loads(request.body)
        language = data.get(LANGUAGE_KEY, configuration_helpers.get_value('LANGUAGE_CODE'))
        if request.session.get(LANGUAGE_SESSION_KEY, None) != language:
            request.session[LANGUAGE_SESSION_KEY] = unicode(language)
        response.set_cookie(
            settings.LANGUAGE_COOKIE,
            language,
            domain=settings.SESSION_COOKIE_DOMAIN,
            max_age=COOKIE_DURATION
        )
    return response
