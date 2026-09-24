from rest_framework import serializers


class RateMovieSerializer(serializers.Serializer):
    rating = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=5)
    liked = serializers.BooleanField(required=False, default=False)
    watched_date = serializers.DateField(required=False, allow_null=True)
