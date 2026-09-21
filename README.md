# drf-canon

RFC 9457 Problem Details for Django REST framework, applied to every error your API returns.

DRF answers errors in several shapes: `{"detail": ...}` for exceptions, `{"field": [...]}` for
validation, and whatever each view builds by hand. None of them carries a machine-readable
identifier, so clients end up parsing translated text. drf-canon puts every error, including the
ones DRF raises on its own, into one standard envelope.

No dependencies beyond Django and DRF. Requires Python 3.10+, Django 4.2+ and DRF 3.15+.

## Errors

Every error becomes [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457.html):

```http
HTTP/1.1 400 Bad Request
Content-Type: application/problem+json

{
  "type": "/problems/validation-error",
  "title": "Request parameters are invalid",
  "status": 400,
  "detail": "2 fields failed validation",
  "errors": [
    {"location": "body", "pointer": "/email", "detail": "Enter a valid email address."},
    {"location": "body", "pointer": "/items/1/quantity", "detail": "Ensure this value is greater than or equal to 1."}
  ]
}
```

- `type` identifies the problem class and is the only member clients should branch on.
- `title` is the same for every occurrence of a class, `detail` describes this one.
- `errors` lists every failed field at once. `location` says which part of the request the
  `pointer` refers to: `body`, `query`, `path` or `header`.

### Setup

```bash
pip install drf-canon
```

```python
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'drf_canon.errors.exception_handler',
}
```

Adopting it in an existing API? Leave the setting alone and opt views in one at a time:

```python
from drf_canon.errors import ProblemDetailsMixin, problem_details


class OrderViewSet(ProblemDetailsMixin, viewsets.ModelViewSet): ...


@problem_details
@api_view(['GET'])
def health(request): ...
```

Errors DRF raises on its own, such as `401`, `403`, `404`, `405` and `429`, come out in the same
format, with `WWW-Authenticate` and `Retry-After` preserved.

### Your own problems

The common types cover most errors. Declare your own only when the client has to react to it
differently than to the plain status: a shop's app shows "out of stock" differently from any other
conflict, so that one deserves a type.

Keep them in a `problems.py` next to the app they belong to, one module per app, and import them
where they are raised:

```python
# orders/problems.py
from drf_canon.errors import Problem

OUT_OF_STOCK = Problem('out-of-stock', 'Out of stock', 409)
ORDER_ALREADY_PAID = Problem('order-already-paid', 'Order is already paid', 409)
```

The slug becomes part of your public contract: keep it unique across the project and never reuse
it for a different meaning. A problem needs a new meaning, it needs a new slug.

Raise it with `ProblemError`, from a view or from a serializer's `validate`:

```python
# orders/serializers.py
from drf_canon.errors import ProblemError

from orders.problems import OUT_OF_STOCK


class CartItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        stock = attrs['product'].stock
        if attrs['quantity'] > stock:
            raise ProblemError(OUT_OF_STOCK, f'Only {stock} left', errors={'quantity': 'Exceeds the stock'})
        return attrs
```

```json
{
  "type": "/problems/out-of-stock",
  "title": "Out of stock",
  "status": 409,
  "detail": "Only 2 left",
  "errors": [{"location": "body", "pointer": "/quantity", "detail": "Exceeds the stock"}]
}
```

`detail` and `errors` are optional; without `detail` the response repeats the title. Pointers in
`errors` are relative to the serializer that raises, so raise from the top-level one when the path
matters.

```python
# orders/views.py
from drf_canon.errors import ProblemError

from orders.problems import ORDER_ALREADY_PAID


class OrderViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        if order.paid_at is not None:
            raise ProblemError(ORDER_ALREADY_PAID)
        ...
```

A common type works the same way when a declared one would add nothing:
`raise ProblemError(CONFLICT, 'The order is being processed')`.

Bad query parameters, path parameters and headers get their own exceptions, so the client knows
where to look:

```python
from drf_canon.errors import QueryParamError

raise QueryParamError({'since': 'Use the YYYY-MM-DD format.'})
```

### Common problem types

| Status | `type`                           | `title`                        |
|--------|----------------------------------|--------------------------------|
| 400    | `/problems/validation-error`     | Request parameters are invalid |
| 401    | `/problems/unauthenticated`      | Authentication required        |
| 403    | `/problems/permission-denied`    | Permission denied              |
| 404    | `/problems/not-found`            | Resource not found             |
| 405    | `/problems/method-not-allowed`   | Method not allowed             |
| 409    | `/problems/conflict`             | Conflicting resource state     |
| 429    | `/problems/throttled`            | Too many requests              |
| 500    | `/problems/internal-error`       | Internal server error          |
| 503    | `/problems/upstream-unavailable` | Upstream service unavailable   |

Any other error status gets `about:blank`, the type RFC 9457 reserves for problems that carry
nothing beyond their HTTP status.

`type` is a relative URI by default. Clients should compare it as a string, not resolve it. To
publish absolute URIs, set a base:

```python
DRF_CANON = {
    'PROBLEM_TYPE_BASE': 'https://api.example.com/problems/',
}
```

### OpenAPI

`drf_canon.errors.schema.ProblemSerializer` describes the envelope:

```python
@extend_schema(responses={201: OrderSerializer, 400: ProblemSerializer, 409: ProblemSerializer})
```

## License

MIT
