import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Standardized API exception handler.
    Guarantees a predictable structure across 400, 401, 403, 404, 405, 500:
    {
        "success": False,
        "status_code": 4xx,
        "message": "Human readable message",
        "errors": { ... }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        errors = response.data
        message = "An error occurred while processing the request."

        if isinstance(errors, dict):
            if "detail" in errors:
                message = str(errors["detail"])
            elif errors:
                first_key = next(iter(errors))
                first_val = errors[first_key]
                if isinstance(first_val, list) and first_val:
                    message = f"{first_key}: {first_val[0]}"
                else:
                    message = f"{first_key}: {first_val}"
        elif isinstance(errors, list) and errors:
            message = str(errors[0])

        response.data = {
            "success": False,
            "status_code": response.status_code,
            "message": message,
            "errors": errors,
        }
        return response

    # Unhandled server errors (500)
    logger.exception("Unhandled server exception: %s", exc)
    from django.conf import settings
    server_error_detail = str(exc) if settings.DEBUG else "An unexpected internal server error occurred."
    return Response(
        {
            "success": False,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Internal server error. Please try again later.",
            "errors": {"server": server_error_detail},
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

