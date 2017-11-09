# pylint: disable=too-many-ancestors
"""
Views for microsites api end points.
"""
import cStringIO  
from collections import OrderedDict
import copy
import logging
from PIL import Image
import sys, yaml
import urllib2
import urlparse 

from django.apps import apps
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile, File
from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from edx_rest_framework_extensions.authentication import JwtAuthentication

from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_oauth.authentication import OAuth2Authentication
from rest_framework.viewsets import ViewSet

from microsite_configuration.models import \
    Microsite, MicrositeOrganizationMapping

from microsite_configuration.serializers import \
    MicrositeSerializer, MicrositeModelSerializer

from organizations import api as organizations_api
from organizations import exceptions as org_exceptions
from organizations.models import Organization

from openedx.core.djangoapps.user_api.errors import \
    UserNotFound, UserNotAuthorized

log = logging.getLogger(__name__)

def download_image(url):
    """
    Downloads an image
    Returns a PIL Image, otherwise raises an exception.
    """
    r = urllib2.Request(url)
    try:
        request = urllib2.urlopen(r, timeout=10)
        image_data = cStringIO.StringIO(request.read()) # StringIO is a file
        img = Image.open(image_data) # Creates an instance of PIL Image class
        if img.format in ('PNG', 'png'):
            return img
        else:
            return None
    except urllib2.HTTPError as e:
        log.error(e)
        raise
        


def save_org_logo(url, org_short_name):
    """
    Download and save remote organization logo
    """
    try:
        image = download_image(url)
        filename = urlparse.urlparse(url).path.split('/')[-1]
        tempfile = image
        tempfile_io = cStringIO.StringIO() # Creates file-like object in mem
        tempfile.save(tempfile_io, format=image.format)
        try:
            org = Organization.objects.get(short_name=org_short_name)
        except org_exceptions.InvalidCourseKeyException:
            raise
        else:    
            org.logo.save(
                filename,
                ContentFile(tempfile_io.getvalue()),
                save=False
            )
            org.save()
       
    except Exception as e:
        log.error(e)
        raise
        
def generate_error_response(string):
    """
    Generate Response with error message about missing request data
    """
    return Response(
        {"error": "{} is None, please add to request body.".format(string)},
        status=status.HTTP_400_BAD_REQUEST
    )


"""        
    The following 3 methods are helper functions to:       
        1: generate a proper json object for the microsite values       
        2: generate a yaml file that gets saved on the server that will be used
           to generate config files for the microsites to run through lms and
           for the nginx site configurations.                 
        The file location is controlled via EDXAPP_MICROSITE_CONFIG_FILE kept
        in server_vars.yml               
"""

def update_map( map, key, values):
    """
    Updated the given map with the key:value pair provided
    """
    if isinstance(values, OrderedDict):
        new_map = {}
        for i in values:
            update_map(new_map, i, values[i])
        map.update({key:new_map})
    else:
        map.update({key:values})


def build_inner_map(microsite):
    """
    simple utility to serve as intermediate between save_to_file and
    update_map to allow for the transformation of a single microsite value set.
    """
    inner_map = {}

    for item in microsite:
        update_map(inner_map, item, microsite[item])
    return inner_map


def save_to_file():
    """
    get all microsites from the database and loop over them contructing a 
    dictionary by the use of build_inner_map, each microsite is parsed with 
    build_inner_map and then added to a main "outer" dictionary for compiling
    of the yaml file. After all microsites have been parsed the main dictonary
    is dumped to a yaml file.
    """
    microsites = Microsite.objects.all()
    data = {}
    outer_map = {}
    for microsite in microsites:
        outer_map.update({microsite.key: build_inner_map(microsite.values)})

    data.update({"PLATFORM_EDXAPP_MICROSITE_CONFIGURATION":outer_map})
    
    f = open(settings.MICROSITE_CONFIG_FILE, 'w+')
    f.write("---\n")
    yaml.safe_dump(
        data,
        f,
        default_flow_style=False,
        encoding='utf-8',
        allow_unicode=True
    )
    f.close()

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

         Inserts new organization into app/local state given the following:

         {
             'name': string,
             'short_name': string,
             'description': string,
             'logo': (not required),
         }
         Returns updated dictionary including a new 'id': integer field/value
    """

    queryset = Microsite.objects.all()
    serializer_class = MicrositeSerializer
    lookup_field = 'key'
    authentication_classes =\
        (OAuth2Authentication, JwtAuthentication, SessionAuthentication)

    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        microsites = Microsite.objects.all()

        for microsite in microsites:
            microsite.values = build_inner_map(microsite.values)

        serializer = MicrositeModelSerializer(microsites, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):

        # Parse the request.data as json
        
        site_url = request.data.get('SITE_NAME', None)
        site_name = request.data.get('domain_prefix', None)
        platform_name = request.data.get('platform_name', None)
        course_org_filter = request.data.get('course_org_filter', None)
        Site = apps.get_model('sites', 'Site')

        if site_url is None:
            return generate_error_response('SITE_NAME')
        elif site_name is None:
            return generate_error_response('domain_prefix')
        elif platform_name is None:
            return generate_error_response('platform_name')
        elif course_org_filter is None:
            return generate_error_response('course_org_filter')
        else:
            # Check if staging is in the site name, strip staging from the name
            if 'staging' in site_name:
                site_name = site_name.replace('staging.', '')
            # need to check if site exists, do not duplicate
            try:
                Site.objects.filter(domain=site_url)
                site = Site(domain=site_url, name=site_name)
                site.save()
            except IntegrityError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            org_data = {
                'name': platform_name,
                'short_name': course_org_filter,
                'description': platform_name,
            }
            messages = {}
            # Check if org exits, if not add organization
            try:
                organizations_api.get_organization_by_short_name(course_org_filter)
            except org_exceptions.InvalidOrganizationException as e:
                try:
                    organizations_api.add_organization(org_data)
                except org_exceptions.InvalidOrganizationException:
                    return Response(
                        {"error": str(e)},
                        status=status.HTTP_400_BAD_REQUEST
                    )  
    
            if 's3_logo_url' in request.data:
                s3_logo_url = request.data.get('s3_logo_url', None)
                try:
                    save_org_logo(s3_logo_url, course_org_filter)
                    messages['logo-image-error'] = "No error."
                except Exception as e:
                    messages['logo-image-error'] = '{}'.format(e)
            # Need to check if the microsite key is a duplicate
            try:
                microsite = Microsite(
                    key= course_org_filter,
                    values=request.data,
                    site=site
                )
                microsite.save()
            except IntegrityError as e:
                print "line 286"
                return Response(
                    { "error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Map the organization and microsite
            mapping = MicrositeOrganizationMapping(
                organization=org_data['short_name'],
                microsite=microsite
            )
            mapping.save()
            serializer = MicrositeSerializer(data=request.data)
        
            if serializer.is_valid():
                serializer.save()
                save_to_file()
                messages['id'] = microsite.id
                return Response(messages, status=status.HTTP_201_CREATED)

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

    authentication_classes =\
        (OAuth2Authentication, JwtAuthentication, SessionAuthentication)

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk, format=None):
        try:
            queryset = Microsite.objects.all()
            microsite = get_object_or_404(queryset, pk=pk)
            microsite.values = build_inner_map(microsite.values)
            serializer = MicrositeModelSerializer(microsite)
        except UserNotAuthorized:
            return Response(status=status.HTTP_403_FORBIDDEN)
        except UserNotFound:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(serializer.data)

    def delete(self, request, pk, format=None):

        # Get the mircosite
        microsite = Microsite.objects.get(pk=pk)
        microsite_id = {"id": microsite.id}
        domain = microsite.site.domain
        associated_site = Site.objects.get(domain=domain)
        
        # Delete the site which deletes the microsite and org mapping
        associated_site.delete()
        
        return Response(
            microsite_id, 
            status=status.HTTP_200_OK
        )

    def put(self, request, pk, format=None):

        messages = {}

        # Parse the request.data as json
        site_url = request.data.get('SITE_NAME', None)
        site_name = request.data.get('domain_prefix', None)
        platform_name = request.data.get('platform_name', None)
        course_org_filter = request.data.get('course_org_filter', None)

        if site_url is None:
            return generate_error_response('SITE_NAME')
        elif site_name is None:
            return generate_error_response('domain_prefix')
        elif platform_name is None:
            return generate_error_response('platform_name')
        elif course_org_filter is None:
            return generate_error_response('course_org_filter')

        # Get the microsite
        microsite = Microsite.objects.get(pk=pk)
        domain = microsite.site.domain
        
        if microsite is None:
            return Response(
                {"error": "The microsite was not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        elif microsite.key != course_org_filter:
            return Response(
                {"error": "The course_org_filter cannot be changed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If new site url, we need to create a new site and update the mapping
        elif microsite.site.domain != site_url:
            if not Site.objects.filter(domain=site_url):
                new_site = Site(domain=site_url, name=site_name)
                new_site.save()
                Microsite.objects.filter(pk=pk).update(site=new_site)
                old_site = Site.objects.filter(domain=domain)
                old_site.delete()
            else:
                return Response(
                    {'error': 'That site url already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        Microsite.objects.filter(pk=pk).update(values=request.data)

        if 's3_logo_url' in request.data:
            s3_logo_url = request.data.get('s3_logo_url', None)
            try:
                save_org_logo(s3_logo_url, course_org_filter)
                messages['logo-image-error'] = "No error."
            except Exception as e:
                messages['logo-image-error'] = '{}'.format(e)
                
        serializer = MicrositeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            messages['id'] = microsite.id
            save_to_file()
            return Response(
                messages,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)