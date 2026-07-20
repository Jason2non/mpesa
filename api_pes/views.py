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

def get_mpesa_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    url = settings.MPESA_TOKEN_URL
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
        "Amount": str(amount),
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
            response_code=res_data.get("ResponseCode"),
            response_description=res_data.get("ResponseDescription"),
            phone_number=phone_number,
            amount=amount,
            status='PENDING'
        )
    return JsonResponse(res_data, status=response.status_code, safe=False)

@csrf_exempt
def mpesa_callback(request):
    if not request.body:
        logger.warning("Received an empty request body at M-Pesa callback endpoint.")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Empty body received"}, status=400)
    try:
        # 2. Safely parse the json stream now that we know it's not blank
        data = json.loads(request.body)
        #print(data)
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON. The payload received was not valid JSON data.")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON format"}, status=400)
    try:
        # 1. Parse raw json stream payload from Safaricom POST request
        data = json.loads(request.body)
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        
        # 2. Extract transaction reference indices
        result_code = stk_callback.get('ResultCode')
        checkout_id = stk_callback.get('CheckoutRequestID')
        result_desc = stk_callback.get('ResultDesc')

        # 3. Retrieve or create a transaction trace reference
        transactions, created = Transactions.objects.get_or_create(
            checkout_request_id=checkout_id
        )
        
        transactions.result_code = result_code
        transactions.result_description = result_desc

        # ResultCode 0 represents user PIN entry validated & cash transfer approved
        if result_code == 0:
            metadata_items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            # Convert Safaricom's list structural model into a standard key-value dictionary mapping
            #metadata = {item['Name']: item.get('Value') for item in metadata_items if 'Value' in item}
            
            metadata = {}
            for item in metadata_items:
                name = item.get('Name')
                # Use .get('Value') so it safely returns None instead of crashing if 'Value' is missing
                value = item.get('Value') 
                if name:
                    metadata[name] = value
            # Map parameters
            transactions.amount = metadata.get('Amount')
            transactions.mpesa_receipt_number = metadata.get('MpesaReceiptNumber')
            transactions.phone_number = str(metadata.get('PhoneNumber'))
            transactions.is_success = True
            transactions.save()
            
            logger.info(f"Payment Confirmed: ID {checkout_id} | Receipt {transactions.mpesa_receipt_number}")
            
            # TODO: Safely execute post-payment tasks here (e.g. ship orders, send transactional mail)
            
        else:
            # Code execution skips to here if user dropped the prompt or lacks sufficient funds
            transactions.is_success = False
            transactions.save()
            logger.warning(f"Payment Unsuccessful: ID {checkout_id} | Code {result_code} | Reason: {result_desc}")

        # 4. Return an instant HTTP 200 JSON confirmation response back to Daraja's gateway
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
    except Exception as e:
        import traceback
        # 1. Capture the exact file, line number, and function where the crash happened
        detailed_traceback = traceback.format_exc()
        # 2. Also print it directly to your Django terminal/console for instant viewing
        print("\n" + "="*50 + "\n[M-PESA DETAILED CRASH LOG]\n" + "="*50)
        print(detailed_traceback)
        print("="*50 + "\n")
        
        # 3. Temporarily return the exact error in the JSON response so you see it in Postman/your client
        return JsonResponse({
            "ResultCode": 1,  # Switched to 1 to tell your testing client it's a failure
            "ResultDesc": "Crash detected inside view logic",
            "PythonError": str(e),
            "LineOfCode": detailed_traceback.split("\n")[-2] if detailed_traceback else "Unknown location"
        }, status=500)

def home(request):
    collect = Transactions.objects.count()
    return HttpResponse (f"Num {collect}")
