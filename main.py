#In push-to-bland
import functions_framework
import requests
from firebase_admin import credentials, firestore, initialize_app
from twilio.rest import Client
import random
import yaml
import os

def load_yaml_file(filepath):
    with open(filepath, 'r') as file:
        data = yaml.safe_load(file)
    return data

# Use the function to load the configuration
config = load_yaml_file('config.yaml')

env = os.getenv("deployment_env")

TWILIO_ACCOUNT_SID = config[env]["twilio"]["account_sid"] 
TWILIO_AUTH_TOKEN = config[env]["twilio"]["auth_token"] 

FIREBASE_SEARCH_REQUESTS_DB = config[env]["firebase"]["search_requests_db"]

BLAND_PHONE_NUMBER = config[env]["bland"]["phone_number"]
BLAND_API_KEY = config[env]["bland"]["api_key"]

CF_CALL_COMPLETION = config[env]["cloud_functions"]["call_completion"]

twilio_client = Client(TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN)

# Initialize Firebase Admin SDK with the service account key
cred = credentials.Certificate("firebase_creds.json")  # Update with your service account key file 
initialize_app(cred)
db = firestore.client() # set firestore client


@functions_framework.http
def main(request):
    call_uuid = request.args.get('call_uuid') 
    request_uuid = request.args.get('request_uuid')
    prescription_name = request.args.get('name')
    prescription_dosage = request.args.get('dosage')
    prescription_brand = request.args.get('brand')
    prescription_quantity = request.args.get('quantity')
    prescription_type = request.args.get('type')

    # Step 1. update the prompt
    prompt = f"""
    Goal: You are an assistant calling a pharmacy on behalf of a patient looking to see if the pharmacy can fill a specific prescription.

    Call flow:
    1. Wait on hold until a pharmacist answers the phone and greets you.
    2. Once a human pharmacist has answered the phone speak with the pharmacist to find out if their pharmacy can fill the specified prescription

    Background Information:

    You are looking for the following prescription:
    Medication name: {prescription_name}
    Medication version: {prescription_brand}
    Dosage: {prescription_dosage} milligrams
    Release type: {prescription_type}
    Quantity: {prescription_quantity} tablets

    Role Notes:
    - The pharmacist will have to look up the prescription information on their computer, therefore you should avoid providing too many details about the prescription at once which will overwhelm the pharmacist.
    - You should speak using casual lingo. Do not use the word inquire.
    - You may hear advertisements saying something about downloading an app, please ignore any content regarding this while you are on hold.

    Example Dialog:
    You: Use (tool = wait). Do not say anything, stay completely silent
    Pharmacy IVR Menu System: Would you like to receive a onetime text with a link to download the CVS App.
    You: Use (tool = wait). Do not say anything, stay completely silent
    Pharmacy IVR Menu System: Say yes or Press 1, and confirm your mobile number. Otherwise, say no or Press 2.
    You: Use (tool = button press) press 2
    You: Use (tool = wait) while waiting for the hold music. Wait on hold until a human user answers the phone.
    Pharmacist: CVS. How can I help you...
    You: Hi im looking to see if you could fill a certain prescription.
    Pharmacist: What medication?
    You: {{medication_name}}, the {{type}} version.
    Pharmacist: What dosage?
    You: {{dosage}} milligrams.
    Pharmacist: Are you looking for the generic?
    You: {{brand_or_generic}}
    Pharmacist: How many would you need?
    You: {{quantity}} tablets
    Pharmacist: Okay, let me check that.
    You: Use (tool = wait) while the pharmacist is looking something up
    Pharmacist: Yes, we can fill that.
    Agent-Action: Ended call: Thanks, goodbye.
    """


    # Step 2. post the updates

    voice_list = ["Alexa", "Josh", "June", "Nat", "Derek", "Ravi", "Destiny", "Tenko", "Diego"]

    url = "https://api.bland.ai/inbound/update"

    payload = {
        "phone_number": BLAND_PHONE_NUMBER,
        "prompt": prompt,
        "voice": random.choice(voice_list),
        "record":"true",
        "webhook": CF_CALL_COMPLETION,
        "metadata": {
            "request_uuid": request_uuid,
            "call_uuid": call_uuid
        },
        "wait_for_greeting": "false"
    }
    headers = {
    'Authorization': BLAND_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.request("POST", url, json=payload, headers=headers)
    twiml = f"""
            <Response>
                <Dial>
                    <Number>{BLAND_PHONE_NUMBER}</Number>
                </Dial>
            </Response>
    """
    
    
    search_ref = db.collection(FIREBASE_SEARCH_REQUESTS_DB).document(request_uuid)
    search_ref.document(request_uuid).update({"unfinished_calls" : firestore.Increment(1)})

    return twiml
