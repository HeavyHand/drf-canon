"""
drf-spectacular integration, for projects that already use it.
"""

from typing import Any

from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema
from drf_spectacular.plumbing import ComponentRegistry
from drf_spectacular.utils import OpenApiResponse
from rest_framework import permissions

from drf_canon.errors.handler import CONTENT_TYPE
from drf_canon.errors.schema import ProblemSerializer

_OPEN = (permissions.AllowAny, permissions.IsAuthenticated, permissions.IsAuthenticatedOrReadOnly)


class AutoSchema(SpectacularAutoSchema):
    """
    drf-spectacular's ``AutoSchema`` that documents the errors every endpoint can return.

    Each operation gets the Problem Details responses that follow from how it is built: ``400`` when
    it takes a body or query parameters, ``404`` when its path has parameters, ``401`` and ``403`` when
    its permissions call for them. Responses declared with ``@extend_schema`` are left as they are,
    and a ``ProblemSerializer`` declared there is documented as ``application/problem+json``.
    """

    def get_operation(
        self,
        path: str,
        path_regex: str,
        path_prefix: str,
        method: str,
        registry: ComponentRegistry,
    ) -> dict[str, Any] | None:
        operation: dict[str, Any] | None = super().get_operation(path, path_regex, path_prefix, method, registry)
        if operation is None:
            return None

        responses = operation['responses']
        for status, description in self._error_responses(operation):
            if status not in responses:
                response = OpenApiResponse(response=ProblemSerializer, description=description)
                responses[status] = self._get_response_for_code(response, status)
        return operation

    def _get_response_for_code(
        self,
        serializer: Any,
        status_code: str,
        media_types: Any = None,
        direction: Any = 'response',
    ) -> dict[str, Any]:
        response = serializer.response if isinstance(serializer, OpenApiResponse) else serializer
        is_problem = response is ProblemSerializer or isinstance(response, ProblemSerializer)
        if is_problem and media_types is None:
            media_types = [CONTENT_TYPE]
        result: dict[str, Any] = super()._get_response_for_code(serializer, status_code, media_types, direction)
        return result

    def _error_responses(self, operation: dict[str, Any]) -> list[tuple[str, str]]:
        parameters = operation.get('parameters', [])
        errors = []
        if 'requestBody' in operation or any(parameter['in'] == 'query' for parameter in parameters):
            errors.append(('400', 'Invalid request'))

        perms = self.view.get_permissions()
        public = not perms or any(
            isinstance(perm, permissions.AllowAny)
            or (isinstance(perm, permissions.IsAuthenticatedOrReadOnly) and self.method in permissions.SAFE_METHODS)
            for perm in perms
        )
        if not public:
            # without an authenticator to challenge the client, DRF answers a missing login with 403
            if self.view.get_authenticators():
                errors.append(('401', 'Authentication required'))
            else:
                errors.append(('403', 'Permission denied'))
        if any(not isinstance(perm, _OPEN) for perm in perms):
            errors.append(('403', 'Permission denied'))

        if any(parameter['in'] == 'path' for parameter in parameters):
            errors.append(('404', 'Not found'))
        return errors
