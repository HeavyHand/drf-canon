from decimal import Decimal

import django_filters
import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from drf_canon.errors import QueryParamError
from drf_canon.filtering import FilterBackend
from drf_canon.ordering import OrderingFilter
from tests.models import Item

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


def request(query: str = '') -> Request:
    return Request(factory.get(f'/items/?{query}'))


@pytest.fixture(autouse=True)
def items() -> None:
    Item.objects.bulk_create(
        [Item(name='a', price=Decimal(30)), Item(name='b', price=Decimal(10)), Item(name='c', price=Decimal(20))]
    )


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class ItemFilter(django_filters.FilterSet):
    price = django_filters.RangeFilter()
    ids = NumberInFilter(field_name='id')

    class Meta:
        model = Item
        fields = ['name']


class ItemView(APIView):
    filterset_class = ItemFilter
    ordering_fields = ['name', 'price']


def order(query: str) -> list[str]:
    queryset = OrderingFilter().filter_queryset(request(query), Item.objects.all(), ItemView())
    return [item.name for item in queryset]


def filter_items(query: str) -> list[str]:
    queryset = FilterBackend().filter_queryset(request(query), Item.objects.order_by('name'), ItemView())
    return [item.name for item in queryset]


def test_ordering_works_as_in_drf() -> None:
    assert order('ordering=-price') == ['a', 'c', 'b']


def test_unknown_ordering_is_a_query_error() -> None:
    with pytest.raises(QueryParamError) as exc_info:
        order('ordering=price,-rating')

    assert str(exc_info.value.detail['ordering']) == 'Unknown ordering -rating. Allowed: name, price.'


def test_trailing_comma_in_ordering_is_not_an_error() -> None:
    assert order('ordering=price,') == ['b', 'c', 'a']


def test_filters_work_as_in_django_filter() -> None:
    assert filter_items('price_min=15') == ['a', 'c']


def test_filter_error_is_a_query_error() -> None:
    with pytest.raises(QueryParamError) as exc_info:
        filter_items('ids=1,two')

    assert list(exc_info.value.detail) == ['ids']


def test_range_error_points_at_the_bound_the_client_sent() -> None:
    with pytest.raises(QueryParamError) as exc_info:
        filter_items('price_min=10&price_max=abc')

    assert list(exc_info.value.detail) == ['price_max']
