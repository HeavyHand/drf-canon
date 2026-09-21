from collections.abc import Iterable
from typing import Any

from django.db.models import QuerySet
from django.utils.translation import gettext
from rest_framework import filters
from rest_framework.request import Request
from rest_framework.views import APIView

from drf_canon.errors import QueryParamError


class OrderingFilter(filters.OrderingFilter):
    """
    DRF's ``OrderingFilter`` that rejects an unknown field instead of dropping it.

    DRF quietly ignores ``?ordering=nope`` and answers in the default order, so a typo on the client
    goes unnoticed. Here it is a ``400`` that lists the fields the view allows.
    """

    def remove_invalid_fields(
        self,
        queryset: QuerySet[Any],
        fields: Iterable[str],
        view: APIView,
        request: Request,
    ) -> list[str]:
        terms = [term for term in fields if term]
        valid = super().remove_invalid_fields(queryset, terms, view, request)
        invalid = [term for term in terms if term not in valid]
        if invalid:
            allowed = [name for name, _ in self.get_valid_fields(queryset, view, {'request': request})]
            message = gettext('Unknown ordering {invalid}. Allowed: {allowed}.').format(
                invalid=', '.join(invalid),
                allowed=', '.join(allowed),
            )
            raise QueryParamError({self.ordering_param: message})
        return valid
