from typing import Any

import pytest
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, serializers, viewsets
from rest_framework.authentication import BasicAuthentication
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter
from rest_framework.views import APIView

from drf_canon.errors.schema import ProblemSerializer
from drf_canon.pagination import PageNumberPagination
from tests.models import Item


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name']


class Pages(PageNumberPagination):
    page_size = 20


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    pagination_class = Pages
    authentication_classes = [BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]


class IsStaff(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_staff)


class StatsView(APIView):
    authentication_classes = [BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    @extend_schema(responses={200: ItemSerializer})
    def get(self, request: Request) -> Response:
        return Response()


class HealthView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request: Request) -> Response:
        return Response()


class CheckoutView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=ItemSerializer,
        responses={
            201: ItemSerializer,
            400: OpenApiResponse(ItemSerializer, description='Custom'),
            409: ProblemSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        return Response()


router = SimpleRouter()
router.register('items', ItemViewSet)
urlpatterns = [
    *router.urls,
    path('stats/', StatsView.as_view()),
    path('health/', HealthView.as_view()),
    path('checkout/', CheckoutView.as_view()),
]


@pytest.fixture(scope='module')
def schema() -> dict[str, Any]:
    return SchemaGenerator(patterns=urlpatterns).get_schema(request=None, public=True)


def codes(schema: dict[str, Any], path: str, method: str) -> list[str]:
    return sorted(schema['paths'][path][method]['responses'])


def test_list_documents_query_errors_and_login(schema: dict[str, Any]) -> None:
    assert codes(schema, '/items/', 'get') == ['200', '400', '401']


def test_detail_documents_not_found(schema: dict[str, Any]) -> None:
    assert codes(schema, '/items/{id}/', 'get') == ['200', '401', '404']
    assert codes(schema, '/items/{id}/', 'patch') == ['200', '400', '401', '404']
    assert codes(schema, '/items/{id}/', 'delete') == ['204', '401', '404']


def test_custom_permission_documents_forbidden(schema: dict[str, Any]) -> None:
    assert codes(schema, '/stats/', 'get') == ['200', '401', '403']


def test_public_endpoint_without_input_has_no_errors(schema: dict[str, Any]) -> None:
    assert codes(schema, '/health/', 'get') == ['200']


def test_errors_are_problem_details(schema: dict[str, Any]) -> None:
    response = schema['paths']['/items/{id}/']['get']['responses']['404']

    assert response['description'] == 'Not found'
    assert response['content'] == {'application/problem+json': {'schema': {'$ref': '#/components/schemas/Problem'}}}
    assert 'Problem' in schema['components']['schemas']


def test_declared_responses_are_kept(schema: dict[str, Any]) -> None:
    responses = schema['paths']['/checkout/']['post']['responses']

    assert responses['400']['description'] == 'Custom'
    assert list(responses['409']['content']) == ['application/problem+json']
