from django.db import models
from django.core.validators import RegexValidator
# Create your models here.


phone_validator = RegexValidator(
    regex=r'^(?:2547\d{8}|07\d{8})$',
    message="Enter a valid Kenyan phone number."
)
class Transactions(models.Model):
    status = [
        ("success","Success"),
        ("pending","Pending"),
        ("failed","Failed")
    ]
    user = models.CharField(max_length=15)
    phone_number = models.CharField(max_length=15, validators=[phone_validator])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_number = models.CharField(max_length=20)
    status = models.CharField(max_length=90, choices=status, default='Pending')
    result_desc = models.CharField(max_length=120, default='Testing')
    is_success = models.BooleanField(default=False, null=True)
    merchant_request_id = models.CharField(max_length=100, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=100, unique=True)
    response_code = models.CharField(max_length=12, null=True, blank=True)
    response_description=models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_number = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, default='PENDING')
    result_desc = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.checkout_request_id} - {self.status}"