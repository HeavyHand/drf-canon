"""
django-filter integration, for projects that already use it.
"""

from typing import Any

import django_filters
from django import forms
from django.db.models import QuerySet
from django.http import HttpRequest
from django_filters.rest_framework import DjangoFilterBackend
from django_filters.widgets import SuffixedMultiWidget
from rest_framework.views import APIView

from drf_canon.errors import QueryParamError


class FilterBackend(DjangoFilterBackend):
    """
    ``DjangoFilterBackend`` whose errors name the query parameters as the client sent them.

    django-filter raises a plain ``ValidationError``, which reads as a body error, and reports a bad
    range bound under the filter name (``price``) rather than the parameter (``price_max``). Here both
    come out as ``location: query`` with the parameter the client actually sent.
    """

    def filter_queryset(self, request: HttpRequest, queryset: QuerySet[Any], view: APIView) -> QuerySet[Any]:
        filterset = self.get_filterset(request, queryset, view)
        if filterset is None:
            return queryset
        if not filterset.is_valid():
            raise QueryParamError(_wire_errors(filterset))
        return filterset.qs


def _wire_errors(filterset: django_filters.FilterSet) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    for name, messages in filterset.errors.items():
        field = filterset.form.fields.get(name)
        if isinstance(field, forms.MultiValueField) and isinstance(field.widget, SuffixedMultiWidget):
            errors.update(_bound_errors(filterset.form.data, name, field) or {name: messages})
        else:
            errors[name] = messages
    return errors


def _bound_errors(data: Any, name: str, field: forms.MultiValueField) -> dict[str, list[str]]:
    widget: SuffixedMultiWidget = field.widget
    errors = {}
    for suffix, bound in zip(widget.suffixes, field.fields, strict=True):
        param = widget.suffixed(name, suffix)
        try:
            bound.clean(data.get(param))
        except forms.ValidationError as exc:
            errors[param] = exc.messages
    return errors
