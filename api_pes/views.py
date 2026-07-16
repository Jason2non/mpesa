import requests
import json
import base64
import logging
from datetime import datetime
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .models import Transactions
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework import serializers
from django.conf import settings


logger = logging.getLogger(__name__)

"""def get_mpesa_token():
    token_string = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
    encoded_auth = base64.b64encode(token_string.encode()).decode("utf-8")
    headers = {"Authorization": f"Basic {encoded_auth}"}

    response = requests.post(settings.MPESA_TOKEN_URL, headers=headers)

    print("TOKEN STATUS:", response.status_code)
    print("TOKEN RESPONSE:", response.text)

    response.raise_for_status()
    return response.json()["access_token"]"""
"""
def get_mpesa_token():
    response = requests.get(
        "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET)
    )
    response.raise_for_status()
    return response.json()["access_token"]"""

def get_mpesa_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET

    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    response = requests.get(url, auth=(consumer_key, consumer_secret))

    print("TOKEN STATUS:", response.status_code)
    print("TOKEN RAW BODY:", repr(response.text))

    response.raise_for_status()
    data = response.json()

    access_token = data.get("access_token")
    if not access_token:
        raise ValueError(f"No access_token in response: {data}")

    return access_token

"""def get_mpesa_token():
    token_string = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
    encoded_auth = base64.b64encode(token_string.encode()).decode('utf-8')
    headers = {"Authorization": f"Basic {encoded_auth}"}
    response = requests.get(settings.MPESA_TOKEN_URL, headers=headers)
    return response.json().get("access_token")
"""
def generate_stk_password_and_timestamp():
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(data_to_encode.encode()).decode('utf-8')
    return password, timestamp

@csrf_exempt 
def initiate_stk_push(request):
    if request.method != "GET":
        return JsonResponse({"error": "Only POST methods are allowed"}, status=405)

    phone_number = "254740676986"
    amount = 1

    access_token = get_mpesa_token()
    password, timestamp = generate_stk_password_and_timestamp()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": "KENYA_TECH",
        "TransactionDesc": "Invoice Payment"
    }

    print("URL:", repr(settings.MPESA_INITIATE_URL))
    print("Token:", repr(access_token))

    response = requests.post(settings.MPESA_INITIATE_URL, json=payload, headers=headers)

    print("STATUS:", response.status_code)
    print("RAW BODY:", repr(response.text))

    try:
        res_data = response.json()
    except ValueError:
        return JsonResponse(
            {"error": "Non-JSON response from Safaricom",
             "status": response.status_code,
             "body": response.text},
            status=502
        )

    if res_data.get("ResponseCode") == "0":
        Transactions.objects.create(
            merchant_request_id=res_data.get("MerchantRequestID"),
            checkout_request_id=res_data.get("CheckoutRequestID"),
            phone_number=phone_number,
            amount=amount,
            status='PENDING'
        )

    return JsonResponse(res_data, status=response.status_code, safe=False)

@csrf_exempt
def mpesa_callback(request):
    if request.method == "POST":
        callback_data = json.loads(request.body)
        stk_callback = callback_data['Body']['stkCallback']
        result_code = stk_callback['ResultCode']
        checkout_request_id = stk_callback['CheckoutRequestID']
        try:
            transaction = Transactions.objects.get(checkout_request_id=checkout_request_id)
            if result_code == 0:
                metadata = stk_callback['CallbackMetadata']['Item']
                get_val = lambda name: next((item.get('Value') for item in metadata if item.get('Name') == name),None)
                transaction.receipt_number = get_val('MpesaReceiptNumber')
                transaction.status = 'SUCCESS'
                transaction.result_desc = stk_callback['ResultDesc']
            else:
                transaction.status = 'FAILED'
            transaction.result_desc = stk_callback['ResultDesc']
            transaction.save()
        except Transactions.DoesNotExist:
            pass 
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted Successfully"})

def home(request):
    collect = Transactions.objects.count()
    return HttpResponse (f"Items on the list {collect}")

