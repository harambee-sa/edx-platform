import jwt
import json
from student.models import Registration, UserProfile
from social_core.backends.oauth import BaseOAuth2
from django.contrib.auth.models import User
import uuid
import logging

log = logging.getLogger(__name__)
class HarambeeOAuth2(BaseOAuth2):
    """
    Harambee OAuth2 authentication backend

    NB: this backend does not receive the user email adress, as harambee does not work with emails.
    instead this receives a guid as user name, this guid in general is to long for the username field,
    thus we create a email as guid + @harambeecloud.com. this email extention must be in line with the email extention
    sent in to the bulk enrollment API.

    If the email extention in the bulk enroll api is not @harambeecloud.com the user accounts between edx and harambee will go out of sync
    and data will be lost.

    """
    name = 'harambee-oauth2'
    REDIRECT_STATE = False
    ID_KEY = 'username'
    STATE_PARAMETER = True
    AUTHORIZATION_URL = 'https://mvpdev.harambeecloud.com/identityserver/connect/authorize'
    ACCESS_TOKEN_URL = 'https://mvpdev.harambeecloud.com/identityserver/connect/token'
    ACCESS_TOKEN_METHOD = 'POST'
    RESPONSE_TYPE = 'code id_token'

    # The order of the default scope is important
    DEFAULT_SCOPE = ['openid', 'profile']

    def auth_params(self, state=None):
        client_id, client_secret = self.get_key_and_secret()
        params = {
            'client_id': client_id,
            'redirect_uri': self.get_redirect_uri(state)
        }
        if self.STATE_PARAMETER and state:
            params['state'] = state
        if self.RESPONSE_TYPE:
            params['response_type'] = self.RESPONSE_TYPE
        params['nonce'] = str(uuid.uuid4().hex) + str(uuid.uuid4().hex)
        params['response_mode'] = 'form_post'
        return params

    def auth_complete_params(self, state=None):
        client_id, client_secret = self.get_key_and_secret()
        return {
            'grant_type': 'authorization_code',  # request auth code
            'code': self.data.get('code', ''),  # server response code
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': self.get_redirect_uri(state)
        }

    def get_user_details(self, response):

        data = jwt.decode(response.get('id_token'), verify=False)

        return {'username': data.get('CandidateGUID'),
                'email': "{g}@harambeecloud.com".format(g=data.get('CandidateGUID')),
                'fullname': "{f} {l}".format(f=data.get('Firstname'), l=data.get('Lastname')),
                'first_name': data.get('Firstname'),
                'meta': {'hallo':'hallo'},
                'last_name': data.get('Lastname')}


    def user_data(self, access_token, *args, **kwargs):
        """Loads user data from service. Implement in subclass"""
        data = jwt.decode(access_token, verify=False)
        return {'username': data.get('CandidateGUID'),
                'email': "{g}@harambeecloud.com".format(g=data.get('CandidateGUID')),
                'fullname': "{f} {l}".format(f=data.get('Firstname'), l=data.get('Lastname')),
                'first_name': data.get('Firstname'),
                'last_name': data.get('Lastname')}


    def pipeline(self, pipeline, pipeline_index=0, *args, **kwargs):
        """
        This is a special override of the pipeline method.
        This will grab the user from the actual ran pipeline and
        add the incomming guid as a username field to the meta field on the user profile
        """
        out = self.run_pipeline(pipeline, pipeline_index, *args, **kwargs)
        if not isinstance(out, dict):
            return out
        user = out.get('user')

        user_profile = user.profile
        new_meta = {'username': user.email.split('@')[0]}

        if len(user_profile.meta) > 0:
            previous_meta = json.loads(user_profile.meta)
            mixed_dicts =\
                (previous_meta.items() + new_meta.items())
            new_meta =\
                {key: value for (key, value) in mixed_dicts}

        user_profile.meta = json.dumps(new_meta)
        user_profile.save()

        if user:
            user.social_user = out.get('social')
            user.is_new = out.get('is_new')

        return user
