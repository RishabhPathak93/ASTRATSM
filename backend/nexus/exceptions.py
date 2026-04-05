"""nexus/exceptions.py - Uniform error response shape"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('nexus')


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        view   = context.get('view', None)
        errors = response.data

        # Normalise to {code, message, errors}
        if isinstance(errors, list):
            detail  = errors[0] if errors else 'An error occurred.'
            errors_ = errors
        elif isinstance(errors, dict):
            detail  = errors.get('detail', 'Validation error.')
            errors_ = {k: v for k, v in errors.items() if k != 'detail'}
        else:
            detail  = str(errors)
            errors_ = {}

        response.data = {
            'status':  'error',
            'code':    response.status_code,
            'message': str(detail),
            'errors':  errors_,
        }

        if response.status_code >= 500:
            logger.error(
                'Server error in %s: %s',
                view.__class__.__name__ if view else 'unknown',
                exc,
                exc_info=True,
            )

    return response
