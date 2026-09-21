from rest_framework import serializers

from drf_canon.errors.exceptions import LOCATIONS


class ViolationSerializer(serializers.Serializer):
    location = serializers.ChoiceField(
        choices=LOCATIONS,
        help_text='Part of the request the pointer refers to.',
    )
    pointer = serializers.CharField(
        help_text='JSON Pointer (RFC 6901) to the offending value inside that part of the request.',
    )
    detail = serializers.CharField(help_text='What is wrong with the value, for humans.')


class ProblemSerializer(serializers.Serializer):
    """
    RFC 9457 Problem Details, for describing error responses in OpenAPI.
    """

    type = serializers.CharField(help_text='Identifier of the problem class. The only member to branch on.')
    title = serializers.CharField(help_text='Summary of the problem class, the same for every occurrence.')
    status = serializers.IntegerField(help_text='Copy of the HTTP status.')
    detail = serializers.CharField(help_text='What went wrong this time, for humans. May be translated.')
    # the serializer metaclass pops declared fields, so this does not shadow Serializer.errors
    errors = ViolationSerializer(  # type: ignore[assignment]
        many=True,
        required=False,
        help_text='Per-field breakdown, when there is one.',
    )
