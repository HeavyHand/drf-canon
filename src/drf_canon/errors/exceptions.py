from typing import Any

from rest_framework.exceptions import APIException, ValidationError

from drf_canon.errors.problems import Problem

BODY = 'body'
QUERY = 'query'
PATH = 'path'
HEADER = 'header'
LOCATIONS = (BODY, QUERY, PATH, HEADER)


class ProblemError(APIException):
    """
    Answers the request with the given problem.

    Can be raised anywhere below the view, serializer ``validate`` methods included: DRF lets any
    exception other than ``ValidationError`` out of ``is_valid``.

        raise ProblemError(OUT_OF_STOCK, 'Only 2 left', errors={'quantity': 'Exceeds the stock'})

    Args:
      problem: Class of the error. Sets the status.
      detail: What went wrong this time, for humans. Defaults to the problem title.
      errors: Per-field breakdown, shaped like ``ValidationError.detail``.
      location: Part of the request the keys of ``errors`` refer to.
    """

    def __init__(
        self,
        problem: Problem,
        detail: Any = None,
        errors: Any = None,
        location: str = BODY,
    ) -> None:
        super().__init__(str(problem.title) if detail is None else detail)
        self.problem = problem
        self.status_code = problem.status
        self.errors = errors
        self.location = location


class QueryParamError(ValidationError):
    """
    A ``ValidationError`` whose keys name query parameters: ``QueryParamError({'page': 'Must be positive'})``.
    """

    location = QUERY


class PathParamError(ValidationError):
    """
    A ``ValidationError`` whose keys name URL path parameters.
    """

    location = PATH


class HeaderError(ValidationError):
    """
    A ``ValidationError`` whose keys name request headers.
    """

    location = HEADER
