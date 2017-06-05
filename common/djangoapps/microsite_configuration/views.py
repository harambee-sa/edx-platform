# pylint: disable=too-many-ancestors
"""
Views for microsites api end points.
"""
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django.apps import apps
from django.contrib.sites.models import Site
from edx_rest_framework_extensions.authentication import JwtAuthentication
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_oauth.authentication import OAuth2Authentication
from microsite_configuration.models import Microsite, MicrositeOrganizationMapping
from microsite_configuration.serializers import MicrositeSerializer, MicrositeModelSerializer
from organizations import api as organizations_api
from organizations import exceptions as org_exceptions
from openedx.core.djangoapps.user_api.errors import UserNotFound, UserNotAuthorized



class MicrositesViewSet(ViewSet):

    """
        **Use Cases**
            Microsite view to fetch microsite data and create a new microsite


        **Example Requests**:
            GET /api/microsites/v1/microsites/
            POST /api/microsites/v1/microsites/

        **Response Values for GET**
            If the user is logged in and enrolled, the response contains:
            List of all Microsites
            {
                id:  int
                key: ORG
                values: dict
                site: id
            }

        **Response Values for POST**

            This creates a new Microsite
            request should have the following structure

            {
            "domain_prefix": "staging.ttro",
            "SITE_NAME": "staging.ttro.proversity.io",
            "platform_name": "TTRO",
            "course_org_filter": "TTR",
            "show_homepage_promo_video": false,
            "course_about_show_social_links": false,
            "css_overrides_file": "TTR/css/overrides.css",
            "favicon_path": "TTR/images/favicon.ico",
            "ENABLE_MKTG_URLS": false
            }

         Inserts a new organization into app/local state given the following dictionary:

         {
             'name': string,
             'short_name': string,
             'description': string,
             'logo': (not required),
         }
         Returns an updated dictionary including a new 'id': integer field/value
    """
    queryset = Microsite.objects.all()  # pylint: disable=no-member
    serializer_class = MicrositeSerializer
    lookup_field = 'key'
    authentication_classes = (OAuth2Authentication, JwtAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)


    def get(self, request, format=None):
        microsites = Microsite.objects.all()
        serializer = MicrositeModelSerializer(microsites, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):

        serializer = MicrositeSerializer(data=request.data)
        Site = apps.get_model('sites', 'Site')

        # Parse the request.data as json
        json_values = request.data
        site_url = json_values['SITE_NAME']
        site_name = json_values['domain_prefix']

        # Need to check if staging is in the site name, strip staging from the name
        if 'staging' in site_name:
            site_name = site_name.replace('staging.', '')

        site = Site(domain=site_url, name=site_name)
        site.save()
        org_data = {
            'name': json_values['platform_name'],
            'short_name': json_values['course_org_filter'],
            'description': json_values['platform_name'],
            'logo': ''
        }

        # Need to check if org exits, if not add organization
        try:
            organizations_api.get_organization_by_short_name(org_data['short_name'])
        except org_exceptions.InvalidOrganizationException:
            organizations_api.add_organization(org_data)
        # Need to check if the microsite key is a duplicate
        try:
            microsite = Microsite(key=org_data['short_name'], values=json_values, site=site)
            microsite.save()
        except IntegrityError:
            return Response(
                {"Integrity error": "Duplicate entry for microsite key {key}".format(key=org_data['short_name'])},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Map the organization and microsite
        mapping = MicrositeOrganizationMapping(organization=org_data['short_name'], microsite=microsite)
        mapping.save()

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MicrositesDetailView(ViewSet):

    '''
        **Use Cases**
            Microsite view to fetch microsite and update an existing microsite
        **Example Requests**:
            GET /api/microsites/v1/microsites/{pk}
            PUT /api/microsites/v1/microsites/{pk}

        **Response Values for GET**
            If the user is logged in the response contains:
            The microsite
            {
                id:  {pk}
                key: ORG
                values: dict
                site: id
            }

         **Response Values for PUT**
            This updates an existing Microsite
            request.data received from consola has the following structure

            {
                "domain_prefix": "staging.ttro",
                "SITE_NAME": "staging.ttro.proversity.io",
                "platform_name": "TTRO",
                "course_org_filter": "TTR",
                "show_homepage_promo_video": false,
                "course_about_show_social_links": false,
                "css_overrides_file": "TTR/css/overrides.css",
                "favicon_path": "TTR/images/favicon.ico",
                "ENABLE_MKTG_URLS": false
            }
    '''

    authentication_classes = (
        OAuth2Authentication,
        JwtAuthentication,
        SessionAuthentication
    )

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk, format=None):
        try:
            queryset = Microsite.objects.all()
            microsite = get_object_or_404(queryset, pk=pk)
            serializer = MicrositeModelSerializer(microsite)
        except UserNotAuthorized:
            return Response(status=status.HTTP_403_FORBIDDEN)
        except UserNotFound:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(serializer.data)


    def put(self, request, pk, format=None):

        update_data = {
            "domain_prefix": request.data['domain_prefix'],
            "SITE_NAME": request.data['SITE_NAME'],
            "course_org_filter": request.data['course_org_filter'],
        }
        
        # Get the microsite

        microsite = Microsite.objects.get(pk=pk)
        serializer = MicrositeSerializer(data=request.data)
        if microsite is None:
            return Response(
                {"error": "The microsite was not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        elif microsite.key != update_data['course_org_filter']:
            return Response(
                {"error": "You can not change the course_org_filter value for this microsite."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If there is a new site url, we need to create a new site and update the mapping
        elif microsite.site.domain != update_data["SITE_NAME"]:
            site_url = update_data["SITE_NAME"]
            site_name = update_data['domain_prefix']
            site = Site(domain=site_url, name=site_name)
            site.save()
            Microsite.objects.filter(pk=pk).update(site=site)

        Microsite.objects.filter(pk=pk).update(values=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "The microsite was updated"},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)