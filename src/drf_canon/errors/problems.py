import re
from dataclasses import dataclass

from django.utils.functional import Promise

from drf_canon.settings import canon_setting

_SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


@dataclass(frozen=True)
class Problem:
    """
    A class of API error: what it is called, how it reads and which status it carries.

    Declare one per cause the client handles differently, in the ``problems.py`` of the app it belongs
    to, and raise it with ``ProblemError``:

        OUT_OF_STOCK = Problem('out-of-stock', 'Out of stock', 409)

    Args:
      slug: kebab-case name of the cause. The response ``type`` is the configured base plus the slug.
      title: Short summary of the class, the same for every occurrence.
      status: HTTP status the problem always carries, 4xx or 5xx.

    Raises:
      ValueError: If the slug is not kebab-case or the status is not an error status.
    """

    slug: str
    title: str | Promise
    status: int

    def __post_init__(self) -> None:
        if not _SLUG.fullmatch(self.slug):
            raise ValueError(f'Problem slug must be kebab-case, got {self.slug!r}')
        if not 400 <= self.status <= 599:
            raise ValueError(f'Problem status must be 4xx or 5xx, got {self.status}')

    @property
    def type(self) -> str:
        return f'{canon_setting("PROBLEM_TYPE_BASE")}{self.slug}'


VALIDATION_ERROR = Problem('validation-error', 'Request parameters are invalid', 400)
UNAUTHENTICATED = Problem('unauthenticated', 'Authentication required', 401)
PERMISSION_DENIED = Problem('permission-denied', 'Permission denied', 403)
NOT_FOUND = Problem('not-found', 'Resource not found', 404)
METHOD_NOT_ALLOWED = Problem('method-not-allowed', 'Method not allowed', 405)
CONFLICT = Problem('conflict', 'Conflicting resource state', 409)
THROTTLED = Problem('throttled', 'Too many requests', 429)
INTERNAL_ERROR = Problem('internal-error', 'Internal server error', 500)
UPSTREAM_UNAVAILABLE = Problem('upstream-unavailable', 'Upstream service unavailable', 503)

CATALOGUE = (
    VALIDATION_ERROR,
    UNAUTHENTICATED,
    PERMISSION_DENIED,
    NOT_FOUND,
    METHOD_NOT_ALLOWED,
    CONFLICT,
    THROTTLED,
    INTERNAL_ERROR,
    UPSTREAM_UNAVAILABLE,
)

_BY_STATUS = {problem.status: problem for problem in CATALOGUE}


def problem_for_status(status: int) -> Problem | None:
    """
    Returns the catalogue problem an error status maps to, or None when the catalogue has none.
    """
    return _BY_STATUS.get(status)
