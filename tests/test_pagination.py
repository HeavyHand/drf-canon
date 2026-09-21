from typing import Any

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from drf_canon.errors import QueryParamError
from drf_canon.pagination import CursorPagination, PageNumberPagination
from tests.models import Item

factory = APIRequestFactory()


class Pages(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class Cursor(CursorPagination):
    page_size = 2
    page_size_query_param = 'page_size'
    ordering = '-pk'


def request(query: str = '') -> Request:
    return Request(factory.get(f'/items/?{query}'))


def paginate(paginator: Any, data: Any, query: str = '') -> dict[str, Any]:
    page = paginator.paginate_queryset(data, request(query))
    return dict(paginator.get_paginated_response(page).data)


def test_pages_work_as_in_drf() -> None:
    body = paginate(Pages(), list(range(45)), 'page=2')

    assert body == {
        'count': 45,
        'next': 'http://testserver/items/?page=3',
        'previous': 'http://testserver/items/',
        'results': list(range(20, 40)),
    }


def test_last_page_string_still_works() -> None:
    assert paginate(Pages(), list(range(45)), 'page=last')['results'] == list(range(40, 45))


def test_page_size_is_capped() -> None:
    assert len(paginate(Pages(), list(range(250)), 'page_size=500')['results']) == 100


def test_page_size_param_is_ignored_unless_enabled() -> None:
    paginator = Pages()
    paginator.page_size_query_param = None

    assert len(paginate(paginator, list(range(45)), 'page_size=abc')['results']) == 20


def test_pagination_is_off_without_page_size() -> None:
    assert PageNumberPagination().paginate_queryset(list(range(5)), request()) is None


def test_page_past_the_end_is_empty() -> None:
    assert paginate(Pages(), list(range(45)), 'page=7') == {'count': 45, 'next': None, 'previous': None, 'results': []}


@pytest.mark.parametrize('query', ['page=0', 'page=-1', 'page=two', 'page_size=0', 'page_size=1.5'])
def test_malformed_parameter_is_a_query_error(query: str) -> None:
    with pytest.raises(QueryParamError) as exc_info:
        paginate(Pages(), list(range(45)), query)

    assert list(exc_info.value.detail) == [query.split('=')[0]]


@pytest.mark.django_db
def test_cursor_works_as_in_drf() -> None:
    Item.objects.bulk_create(Item(name=str(n)) for n in range(5))

    first = paginate(Cursor(), Item.objects.all())
    second = paginate(Cursor(), Item.objects.all(), first['next'].split('?')[1])

    assert [item.name for item in first['results']] == ['4', '3']
    assert [item.name for item in second['results']] == ['2', '1']


@pytest.mark.django_db
@pytest.mark.parametrize('query', ['cursor=garbage', 'page_size=0'])
def test_malformed_cursor_is_a_query_error(query: str) -> None:
    with pytest.raises(QueryParamError) as exc_info:
        paginate(Cursor(), Item.objects.all(), query)

    assert list(exc_info.value.detail) == [query.split('=')[0]]
