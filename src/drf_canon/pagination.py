from collections.abc import Sequence
from typing import Any

from django.core.paginator import EmptyPage, Page
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import pagination
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.views import APIView

from drf_canon.errors import QueryParamError

POSITIVE_INTEGER = _('Must be a positive integer.')


class _StrictPageSize:
    page_size: int | None
    page_size_query_param: str | None
    max_page_size: int | None

    def get_page_size(self, request: Request) -> int | None:
        if not self.page_size_query_param:
            return self.page_size
        size = _positive_int(request, self.page_size_query_param) or self.page_size
        if size is not None and self.max_page_size:
            return min(size, self.max_page_size)
        return size


class PageNumberPagination(_StrictPageSize, pagination.PageNumberPagination):
    """
    DRF's ``PageNumberPagination`` that answers a malformed request with a ``400``.

    DRF answers ``?page=abc`` and a page past the end with ``404``, and falls back to the default when
    ``page_size`` is malformed. Here a page or page size that is not a positive integer is a ``400``
    pointing at the parameter, and a page past the end is an empty page, as an empty list is not an
    error. Everything else, including settings and attributes, works as in DRF.
    """

    def paginate_queryset(
        self,
        queryset: QuerySet[Any] | Sequence[Any],
        request: Request,
        view: APIView | None = None,
    ) -> list[Any] | None:
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = self.django_paginator_class(queryset, page_size)
        raw = request.query_params.get(self.page_query_param)
        if raw in self.last_page_strings:
            number = paginator.num_pages
        else:
            number = _positive_int(request, self.page_query_param) or 1
        try:
            self.page = paginator.page(number)
        except EmptyPage:
            self.page = Page([], number, paginator)

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True
        return list(self.page)

    def get_previous_link(self) -> str | None:
        # past the end there is no page to step back to: the previous number is past the end as well
        if self.page is not None and self.page.number > self.page.paginator.num_pages:
            return None
        return super().get_previous_link()


class CursorPagination(_StrictPageSize, pagination.CursorPagination):
    """
    DRF's ``CursorPagination`` that answers a malformed cursor or page size with a ``400``, not a ``404``.
    """

    def decode_cursor(self, request: Request) -> pagination.Cursor | None:
        try:
            return super().decode_cursor(request)
        except NotFound as exc:
            raise QueryParamError({self.cursor_query_param: exc.detail}) from exc


def _positive_int(request: Request, name: str) -> int | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise QueryParamError({name: POSITIVE_INTEGER})
    return value
