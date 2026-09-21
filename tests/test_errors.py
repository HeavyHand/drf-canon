import json
from typing import Any

import pytest
from django.http import Http404
from rest_framework import serializers
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView
from rest_framework.views import exception_handler as drf_exception_handler

from drf_canon.errors import (
    CONFLICT,
    HeaderError,
    Problem,
    ProblemDetailsMixin,
    ProblemError,
    ProblemResponse,
    QueryParamError,
    get_violations,
    problem_details,
    to_problem,
)

NO_AVAILABILITY = Problem('no-availability', 'No availability', 409)

factory = APIRequestFactory()


class ReservationSerializer(serializers.Serializer):
    seats = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs['seats'] > 2:
            raise ProblemError(NO_AVAILABILITY, 'Only 2 seats left', errors={'seats': 'Exceeds availability'})
        return attrs


class OrderSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reservations = ReservationSerializer(many=True)


class RaisingView(ProblemDetailsMixin, APIView):
    """Raises whatever the test passes in ``exc``."""

    exc: Exception = RuntimeError('exc is not set')

    def get(self, request: Request) -> Response:
        raise self.exc


class OrderView(ProblemDetailsMixin, APIView):
    parser_classes = [JSONParser]

    def post(self, request: Request) -> Response:
        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=201)


def render(response: Response) -> tuple[Response, dict[str, Any]]:
    response.render()
    return response, json.loads(response.content)


def raise_in_view(exc: Exception, **extra: Any) -> tuple[Response, dict[str, Any]]:
    view = RaisingView.as_view(exc=exc, **extra)
    return render(view(factory.get('/')))


def post_order(data: Any) -> tuple[Response, dict[str, Any]]:
    return render(OrderView.as_view()(factory.post('/', data, format='json')))


def test_validation_error_points_at_every_failed_field() -> None:
    response, body = post_order({'email': 'nope', 'reservations': [{'seats': 1}, {'seats': 0}]})

    assert response.status_code == 400
    assert response['Content-Type'] == 'application/problem+json'
    assert body == {
        'type': '/problems/validation-error',
        'title': 'Request parameters are invalid',
        'status': 400,
        'detail': '2 fields failed validation',
        'errors': [
            {'location': 'body', 'pointer': '/email', 'detail': 'Enter a valid email address.'},
            {
                'location': 'body',
                'pointer': '/reservations/1/seats',
                'detail': 'Ensure this value is greater than or equal to 1.',
            },
        ],
    }


def test_problem_raised_in_a_serializer_keeps_its_status() -> None:
    response, body = post_order({'email': 'a@example.com', 'reservations': [{'seats': 5}]})

    assert response.status_code == 409
    assert body == {
        'type': '/problems/no-availability',
        'title': 'No availability',
        'status': 409,
        'detail': 'Only 2 seats left',
        'errors': [{'location': 'body', 'pointer': '/seats', 'detail': 'Exceeds availability'}],
    }


def test_problem_without_detail_reads_as_its_title() -> None:
    response, body = raise_in_view(ProblemError(CONFLICT))

    assert response.status_code == 409
    assert body == {
        'type': '/problems/conflict',
        'title': 'Conflicting resource state',
        'status': 409,
        'detail': 'Conflicting resource state',
    }


@pytest.mark.parametrize(
    ('exc', 'location'),
    [(QueryParamError({'page': 'Must be positive'}), 'query'), (HeaderError({'X-Tenant': 'Required'}), 'header')],
)
def test_input_error_reports_its_location(exc: ValidationError, location: str) -> None:
    _, body = raise_in_view(exc)

    assert body['errors'][0]['location'] == location


@pytest.mark.parametrize(
    ('exc', 'status', 'type_', 'detail'),
    [
        (NotFound('No such city'), 404, '/problems/not-found', 'No such city'),
        (Http404(), 404, '/problems/not-found', 'Not found.'),
    ],
)
def test_framework_exception_maps_to_catalogue(exc: Exception, status: int, type_: str, detail: str) -> None:
    response, body = raise_in_view(exc)

    assert response.status_code == status
    assert body['type'] == type_
    assert body['detail'] == detail


def test_unauthenticated_keeps_www_authenticate() -> None:
    response, body = raise_in_view(
        Exception('unreachable'),
        authentication_classes=[BasicAuthentication],
        permission_classes=[IsAuthenticated],
    )

    assert response.status_code == 401
    assert body['type'] == '/problems/unauthenticated'
    assert response['WWW-Authenticate'] == 'Basic realm="api"'


def test_throttled_keeps_retry_after() -> None:
    class Closed(BaseThrottle):
        def allow_request(self, request: Request, view: APIView) -> bool:
            return False

        def wait(self) -> float:
            return 30

    response, body = raise_in_view(Exception('unreachable'), throttle_classes=[Closed])

    assert response.status_code == 429
    assert body['type'] == '/problems/throttled'
    assert response['Retry-After'] == '30'


def test_method_not_allowed() -> None:
    response, body = render(RaisingView.as_view()(factory.delete('/')))

    assert response.status_code == 405
    assert body['type'] == '/problems/method-not-allowed'


def test_status_outside_catalogue_is_about_blank() -> None:
    request = factory.post('/', 'plain', content_type='text/plain')
    response, body = render(OrderView.as_view()(request))

    assert response.status_code == 415
    assert body['type'] == 'about:blank'
    assert body['title'] == 'Unsupported Media Type'


def test_unhandled_exception_is_left_alone() -> None:
    with pytest.raises(RuntimeError):
        raise_in_view(RuntimeError('boom'))


def test_error_renders_as_json_for_a_browser() -> None:
    view = RaisingView.as_view(exc=NotFound(), renderer_classes=[BrowsableAPIRenderer, JSONRenderer])
    response, body = render(view(factory.get('/', HTTP_ACCEPT='text/html')))

    assert response['Content-Type'] == 'application/problem+json'
    assert body['type'] == '/problems/not-found'


def test_type_base_is_configurable(settings: Any) -> None:
    settings.DRF_CANON = {'PROBLEM_TYPE_BASE': 'https://api.example.com/problems/'}

    _, body = raise_in_view(ProblemError(NO_AVAILABILITY))

    assert body['type'] == 'https://api.example.com/problems/no-availability'


def test_project_wide_handler(settings: Any) -> None:
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'EXCEPTION_HANDLER': 'drf_canon.errors.exception_handler'}

    class PlainView(APIView):
        def get(self, request: Request) -> Response:
            raise NotFound()

    response, body = render(PlainView.as_view()(factory.get('/')))

    assert response['Content-Type'] == 'application/problem+json'
    assert body['type'] == '/problems/not-found'


def test_problem_details_decorator() -> None:
    @problem_details
    @api_view(['GET'])
    def languages(request: Request) -> Response:
        raise NotFound()

    _, body = render(languages(factory.get('/')))

    assert body['type'] == '/problems/not-found'


def test_problem_details_decorator_below_api_view_fails_loudly() -> None:
    with pytest.raises(TypeError, match='above @api_view'):
        problem_details(lambda request: None)


def test_violations_escape_pointer_tokens_and_attach_object_messages() -> None:
    detail = {'non_field_errors': ['Dates overlap'], 'a/b': ['Bad'], 'm~n': {'0': ['Bad']}}

    assert get_violations(detail, 'body') == [
        {'location': 'body', 'pointer': '', 'detail': 'Dates overlap'},
        {'location': 'body', 'pointer': '/a~1b', 'detail': 'Bad'},
        {'location': 'body', 'pointer': '/m~0n/0', 'detail': 'Bad'},
    ]


@pytest.mark.parametrize(('slug', 'status'), [('NoAvailability', 409), ('no_availability', 409), ('ok', 200)])
def test_problem_rejects_bad_definitions(slug: str, status: int) -> None:
    with pytest.raises(ValueError, match='Problem'):
        Problem(slug, 'Title', status)


class Duplicate(Exception):
    pass


def project_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, Duplicate):
        response: Response | None = Response({'detail': 'Email is taken'}, status=409)
    else:
        response = drf_exception_handler(exc, context)
    if response is not None:
        response['X-Request-Id'] = 'abc'
    return response


def chained_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    return to_problem(exc, project_exception_handler(exc, context))


class ChainedView(RaisingView):
    def get_exception_handler(self) -> Any:
        return chained_handler


def test_to_problem_keeps_what_the_project_handler_did() -> None:
    response, body = render(ChainedView.as_view(exc=Duplicate())(factory.get('/')))

    assert response.status_code == 409
    assert response['X-Request-Id'] == 'abc'
    assert body == {
        'type': '/problems/conflict',
        'title': 'Conflicting resource state',
        'status': 409,
        'detail': 'Email is taken',
    }


def test_to_problem_still_reads_the_exception() -> None:
    _, body = render(ChainedView.as_view(exc=QueryParamError({'page': 'Must be positive'}))(factory.get('/')))

    assert body['errors'] == [{'location': 'query', 'pointer': '/page', 'detail': 'Must be positive'}]


def test_to_problem_leaves_other_responses_alone() -> None:
    ok = Response({'ok': True})
    problem = ProblemResponse({'type': 'about:blank'}, status=400)

    assert to_problem(Exception(), None) is None
    assert to_problem(Exception(), ok) is ok
    assert to_problem(NotFound(), problem) is problem
