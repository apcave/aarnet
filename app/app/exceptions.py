from django.db import DatabaseError
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Return structured API responses for invalid or database-driven failures."""
    response = exception_handler(exc, context)

    if response is not None:
        return response

    if isinstance(exc, (OperationalError, DatabaseError)):
        return Response(
            {
                'detail': 'A database error occurred while processing this request. Please check the payload and retry.',
                'error_type': type(exc).__name__,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, (TypeError, ValueError, AttributeError, KeyError, IndexError, LookupError)):
        return Response(
            {'detail': 'The request payload is invalid or malformed. Please correct the supplied data.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if hasattr(exc, 'detail'):
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {'detail': 'An unexpected error occurred while processing this request.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
