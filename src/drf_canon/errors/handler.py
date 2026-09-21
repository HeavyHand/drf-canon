from collections.abc import Callable
from http import HTTPStatus
from typing import Any, TypedDict, TypeVar

from django.utils.translation import ngettext
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler as drf_exception_handler

from drf_canon.errors.exceptions import BODY, ProblemError
from drf_canon.errors.problems import VALIDATION_ERROR, problem_for_status

CONTENT_TYPE = 'application/problem+json'
ABOUT_BLANK = 'about:blank'

_View = TypeVar('_View', bound=Callable[..., Any])


class Violation(TypedDict):
    location: str
    pointer: str
    detail: str


class ProblemResponse(Response):
    """
    A Problem Details response, rendered as JSON whatever renderer the client negotiated.

    DRF assigns the negotiated renderer after the exception handler returns, so a browser asking for
    HTML would otherwise get the browsable API page under a ``problem+json`` content type.
    """

    @property
    def rendered_content(self) -> Any:
        self.accepted_renderer = JSONRenderer()
        return super().rendered_content


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """
    DRF exception handler that answers with RFC 9457 Problem Details.

    Point ``REST_FRAMEWORK['EXCEPTION_HANDLER']`` at it, or opt views in one by one with
    ``ProblemDetailsMixin`` and ``@problem_details``. A project with a handler of its own keeps it and
    passes its result through ``to_problem`` instead.

    Runs DRF's own handler first, so everything it does still happens: ``Http404`` and Django's
    ``PermissionDenied`` are translated, the transaction of an atomic request is rolled back, and
    ``WWW-Authenticate`` / ``Retry-After`` are set.

    Returns:
      The Problem Details response, or None for an exception DRF does not handle, so that it
      surfaces as a server error.
    """
    return to_problem(exc, drf_exception_handler(exc, context))


def to_problem(exc: Exception, response: Response | None) -> Response | None:
    """
    Turns the error response any exception handler built for ``exc`` into Problem Details.

    For projects that already have an exception handler doing logging, request ids or statuses of
    their own. Keep it, and pass its result through:

        def exception_handler(exc, context):
            return to_problem(exc, project_exception_handler(exc, context))

    The response keeps its headers. The type comes from the exception when it says more than the
    status (``ProblemError``, ``ValidationError``), otherwise from the status, with ``about:blank``
    for a status outside the catalogue. A string ``detail`` in the original body is carried over.

    Returns:
      The Problem Details response. None, a non-error response and a response that already is
      Problem Details are returned untouched.
    """
    if response is None or isinstance(response, ProblemResponse) or response.status_code < 400:
        return response

    errors: list[Violation] = []
    if isinstance(exc, ProblemError):
        problem = exc.problem
        body = _body(problem.type, problem.title, problem.status, exc.detail)
        if exc.errors is not None:
            errors = get_violations(exc.errors, exc.location)
    elif isinstance(exc, ValidationError):
        errors = get_violations(exc.detail, getattr(exc, 'location', BODY))
        summary = ngettext(
            '%(count)d field failed validation',
            '%(count)d fields failed validation',
            len(errors),
        ) % {'count': len(errors)}
        body = _body(VALIDATION_ERROR.type, VALIDATION_ERROR.title, VALIDATION_ERROR.status, summary)
    else:
        status = response.status_code
        catalogued = problem_for_status(status)
        if catalogued is None:
            body = _body(ABOUT_BLANK, HTTPStatus(status).phrase, status, None)
        else:
            body = _body(catalogued.type, catalogued.title, status, None)
        if isinstance(response.data, dict) and isinstance(response.data.get('detail'), str):
            body['detail'] = str(response.data['detail'])

    if errors:
        body['errors'] = errors

    problem_response = ProblemResponse(body, status=body['status'], content_type=CONTENT_TYPE)
    for header, value in response.headers.items():
        if header.lower() != 'content-type':
            problem_response[header] = value
    return problem_response


def get_violations(detail: Any, location: str, pointer: str = '') -> list[Violation]:
    """
    Flattens an error detail shaped like ``ValidationError.detail`` into per-field violations.

    Pointers are JSON Pointers (RFC 6901) built from the keys as the client sent them. Serializer-level
    messages point at the object that holds them, ``''`` being the input as a whole.
    """
    if isinstance(detail, dict):
        violations = []
        for key, value in detail.items():
            child = pointer if key == api_settings.NON_FIELD_ERRORS_KEY else f'{pointer}/{_escape(key)}'
            violations.extend(get_violations(value, location, child))
        return violations
    if isinstance(detail, list | tuple):
        violations = []
        for index, item in enumerate(detail):
            # a list holds either messages about this field or one entry per item of a many=True field
            child = pointer if isinstance(item, str) else f'{pointer}/{index}'
            violations.extend(get_violations(item, location, child))
        return violations
    return [{'location': location, 'pointer': pointer, 'detail': str(detail)}]


class ProblemDetailsMixin:
    """
    Answers every error of a class-based view as Problem Details, whatever the project-wide handler is.
    """

    def get_exception_handler(self) -> Callable[[Exception, dict[str, Any]], Response | None]:
        return exception_handler


def problem_details(view: _View) -> _View:
    """
    Answers every error of a function-based view as Problem Details. Goes above ``@api_view``:

        @problem_details
        @api_view(['GET'])
        def languages(request): ...

    Raises:
      TypeError: If the decorated function did not come out of ``@api_view``.
    """
    cls = getattr(view, 'cls', None)
    if cls is None:
        raise TypeError('@problem_details must be applied above @api_view')
    cls.get_exception_handler = ProblemDetailsMixin.get_exception_handler
    return view


def _body(type_: str, title: Any, status: int, detail: Any) -> dict[str, Any]:
    return {'type': type_, 'title': str(title), 'status': status, 'detail': str(title if detail is None else detail)}


def _escape(token: object) -> str:
    return str(token).replace('~', '~0').replace('/', '~1')
