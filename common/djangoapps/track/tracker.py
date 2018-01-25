"""
Module that tracks analytics events by sending them to different
configurable backends.

The backends can be configured using Django settings as the example
below::

  TRACKING_BACKENDS = {
      'tracker_name': {
          'ENGINE': 'class.name.for.backend',
          'OPTIONS': {
              'host': ... ,
              'port': ... ,
              ...
          }
      }
  }

"""

import inspect
import requests
import json
from importlib import import_module

from django.conf import settings
from dogapi import dog_stats_api
import logging
import time

from track.backends import BaseBackend

__all__ = ['send']


backends = {}

log = logging.getLogger('TRACKER')
def _initialize_backends_from_django_settings():
    """
    Initialize the event tracking backends according to the
    configuration in django settings

    """
    backends.clear()

    config = getattr(settings, 'TRACKING_BACKENDS', {})

    for name, values in config.iteritems():
        # Ignore empty values to turn-off default tracker backends
        if values:
            engine = values['ENGINE']
            options = values.get('OPTIONS', {})
            backends[name] = _instantiate_backend_from_name(engine, options)


def _instantiate_backend_from_name(name, options):
    """
    Instantiate an event tracker backend from the full module path to
    the backend class. Useful when setting backends from configuration
    files.

    """
    # Parse backend name

    try:
        parts = name.split('.')
        module_name = '.'.join(parts[:-1])
        class_name = parts[-1]
    except IndexError:
        raise ValueError('Invalid event track backend %s' % name)

    # Get and verify the backend class

    try:
        module = import_module(module_name)
        cls = getattr(module, class_name)
        if not inspect.isclass(cls) or not issubclass(cls, BaseBackend):
            raise TypeError
    except (ValueError, AttributeError, TypeError, ImportError):
        raise ValueError('Cannot find event track backend %s' % name)

    backend = cls(**options)

    return backend


@dog_stats_api.timed('track.send')
def send(event):
    """
    Send an event object to all the initialized backends.

    """
    dog_stats_api.increment('track.send.count')

    for name, backend in backends.iteritems():
        with dog_stats_api.timer('track.send.backend.{0}'.format(name)):
            backend.send(event)
            
     if settings.ANALITICA_ACTIVE:
        event['time'] = time.time()
        event['event']['created_at'] = time.time()
        event['event']['submitted_at'] = time.time()

        try:
            r =\
               requests.post(
                   settings.ANALITICA_TRACK_URL,
                   headers={'Authorization': settings.ANALITICA_TOKEN},
                   json=event
               )
           if r.status_code != 200:
                log.error("Failed to post to the tracking backend with error {e}".format(e=r.json()))

        except (Exception):
            log.error("TRACK FAIL: Message could not be posted message = {}".format(e=event))
            log.error("TRACK FAIL: Message could not be posted message = {e}".format(e=event))
            pass


_initialize_backends_from_django_settings()
