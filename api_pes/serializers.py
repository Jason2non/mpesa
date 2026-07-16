from rest_framework import serializers


class StkPushSerializer(serialers.Serializer):
    def stkpush():
        phone = serializers.IntegerField(max_digits=12)
        amount = serializers.DecimalField(max_digits=10, decimal_places=2)

        return f"Phone number {phone}, Amount:{amount}"
