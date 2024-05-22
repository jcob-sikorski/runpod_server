import websocket
import uuid
import json
import urllib.request
import urllib.parse
import os
import httpx
import requests
import cv2
import numpy as np

from fastapi import Request, APIRouter

import boto3

from pydantic import BaseModel

from typing import List, Dict, Optional

router = APIRouter(prefix="/image-generation")

client_id = str(uuid.uuid4())
server_address = "127.0.0.1:8188"

def queue_prompt(prompt):
    print("QUEUEING PROMPT")
    p = {"prompt": prompt, "client_id": client_id}
    print(f"GOT THE PRMOPT {prompt}")
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    print(f"SENT A REQUEST TO COMFY: {req}")
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    print(f"GETTING IMAGE --filename: {filename} --subfolder: {subfolder} --folder_type: {folder_type}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    print(f"URL VALUES: {url_values}")
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        print("READING RESPONSE")
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        # Read response content
        response_content = response.read()
        print(f"GOT HISTORY FOR PROMPT ID {prompt_id}: {response_content}")
        # Decode the JSON content
        return json.loads(response_content)

def get_images(ws, prompt):
    print("QUEUEING PROMPT")
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            print("IS AN INSTANCE - GETTING THE OUTPUT")
            message = json.loads(out)
            print(f"OUTPUT MESSAGE: {message}")
            if message['type'] == 'executing':
                print("MESSAGE TYPE IS EXECUTING")
                data = message['data']
                print(f"GOT MESSAGE DATA {data}")
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    print("EXECUTION IS DONE")
                    break #Execution is done
        else:
            print("IS NOT AN INSTANCE - CONTINUING POLLING")
            continue #previews are binary data
    
    try:
        print("GETTING THE HISTORY FOR THE REQUESTED PROMPT")
        history = get_history(prompt_id)[prompt_id]

        status = history['status']['status_str']
        print(f"GENERATION STATUS: {status}")

        completed = history['status']['completed']
        print(f"GENERATION COMPLETED: {completed}")

        if status == "success" and completed:
            output_images = []
            for o in history['outputs']:
                print(f"GOT OUTPUT: {o}")
                node_output = history['outputs'][o]
                print(f"NODE OUTPUT {node_output}")
                if 'images' in node_output:
                    print("IMAGES FOUND IN NODE OUTPUT")
                    for image in node_output['images']:
                        print(f"GOT AN IMAGE {image}")
                        output_images.append(image['filename'])
                else:
                    print("IMAGES NOT FOUND IN NODE OUTPUT")

            print(f"OUTPUT IMAGES: {output_images}")
            return output_images
        else:
            print(f"COULDN'T GENERATE IMAGES FOR PROMPT ID: {prompt_id}")
    except json.JSONDecodeError as e:
        print(f"JSON DECODE ERROR: {e}")
    except Exception as e:
        print(f"WHILE READING EXECUTION HISTORY EXCEPTION OCCURED: {e}")


def upload_images_to_s3(images):
    print("UPLOADING IMAGES TO S3")
    s3_client = boto3.client('s3')

    print("CONNECTED TO THE S3 CLIENT")
    s3_uris = []

    for image_path in images:
        print(f"GOT THE IMAGE PATH: {image_path}")

        print("OPENING TMP SAVED IMAGE...")
        with open(image_path, 'rb') as data:
            print("OPENED IMAGE")

            print("UPLOADING THE IMAGE TO S3")
            s3_client.upload_fileobj(data, 'magicalcurie', image_path)

        print(f"UPLOADED THE IMAGE to S3: " + f'https://magicalcurie.s3.amazonaws.com/{image_path}')
        s3_uris.append(f'https://magicalcurie.s3.amazonaws.com/{image_path}')

        print("REMOVED THE LOCAL IMAGE FILE")
        # Remove the local image file
        os.remove(image_path)

    print(f"URIS FOR IMAGES UPLOADED TO S3: {s3_uris}")
    return s3_uris

def download_and_save_images(
        uploadcare_uris: List[str], 
        image_ids: List[str], 
        image_formats: List[str], 
        predefined_path: str) -> None:
    """
    Downloads and saves images based on image URIs and image IDs.
    Args:
        uploadcare_uris (List[str]): List of 3 image URIs.
        image_ids (List[str]): List of 3 image IDs.
        predefined_path (str): Predefined path to save the images.
    """
    print(f"DOWNLOADING AND SAVING OPTIONAL IPA IMAGES")
    for i in range(2):
        print(f"DOWNLOAD FOR IPA {i+1}...")
        image_id = image_ids[i]
        print(f"GOT THE IMAGE ID: {image_id}")

        image_format = image_formats[i]
        print(f"GOT THE IMAGE FORMAT: {image_format}")
        
        if image_id:
            print("IMAGE ID IS DEFINED")
            print(f"SETTING THE UNIQUE FILEPATH OF THE IMAGE")
            image_path = os.path.join(predefined_path, f"{image_id}.{image_format}")

            print(f"DOWNLOADING IMAGE FROM {image_path}")
            response = requests.get(uploadcare_uris[i])

            if response.status_code == 200:
                print("GOT THE IPA IMAGE FROM UPLOADCARE")
                with open(image_path, "wb") as f:
                    f.write(response.content)
                print(f"SAVED IMAGE TO {image_path}")
            else:
                print(f"FAILED TO GET UPLOADCARE IMAGE: {uploadcare_uris[i]}")
        else:
            print(f"NO IMAGE FOUND FOR IPA {i+1}")

def remove_images(
        uploadcare_uris: List[str],
        image_ids: List[str],
        image_formats: List[str],
        predefined_path: str) -> None:
    """
    Removes images based on image IDs.
    Args:
        image_ids (Dict[str, str]): Dictionary of image IDs.
        predefined_path (str): Predefined path where the images are stored.
    """
    print(f"REMOVING IMAGES")
    for i in range(2):
        print(f"GETTING IMAGE ID")
        image_id = image_ids[i]

        if image_id:
            print("IMAGE ID IS DEFINED")

            image_format = image_formats[i]
            print(f"GOT THE IMAGE FORMAT: {image_format}")

            image_path = os.path.join(predefined_path, f"{image_id}.{image_format}")
            try:
                print(f"REMOVING IMAGE FROM {image_path}...")
                os.remove(image_path)
                print(f"IMAGE REMOVED: {image_path}")
            except FileNotFoundError:
                print(f"IMAGE FOR REMOVAL NOT FOUND: {image_path}")

class Message(BaseModel):
    user_id: Optional[str] = None
    status: Optional[str] = None
    uploadcare_uris: Optional[List[str]] = None
    created_at: Optional[str] = None
    message_id: Optional[str] = None
    settings_id: Optional[str] = None
    s3_uris: Optional[List[str]] = None

async def send_webhook_acknowledgment(user_id: str, 
                                      message_id: str, 
                                      settings_id: str, 
                                      status: str, 
                                      webhook_url: str, 
                                      s3_uris: Optional[List[str]] = None) -> None:
    """
    Sends an acknowledgment message via webhook.

    Args:
        user_id (str): The unique identifier for the user.
        message_id (str): The unique identifier for the message.
        status (str): The status of the message.
        webhook_url (str): The URL of the webhook endpoint.
        s3_uris (Optional[List[str]]): The S3 URIs associated with the message.

    Returns:
        None
    """
    print("SENDING WEBHOOK ACKNOWLEDGMENT")
    try:
        # Create a dictionary to store the fields
        message_fields = {
            'user_id': user_id,
            'message_id': message_id,
            'settings_id': settings_id,
            'status': status
        }

        print(f"CREATED DICTIONARY TO STORE THE FIELDS: {message_fields}")
        
        if s3_uris is not None:
            print("S3 URIS NOT NULL")

            print("ADDING S3_URIS FIELD TO MESSAGE MODEL")
            message_fields['s3_uris'] = s3_uris

        print("CREATING MESSAGE MODEL")
        # Create the Message object
        message = Message(**message_fields)

        print(f"MAKING POST REQUEST TO THE WEBHHOK {webhook_url}")
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=message.__dict__)
            if response.status_code == 200:
                print("WEBHOOK POST REQUEST WAS SUCCESSFUL")
            else:
                print(f"WEBHOOK POST REQUEST FAILED: {response.status_code}")
    except Exception as e:
        print(f"ERROR WHILE SETTING UP WEBHOOK POST REQUEST: {str(e)}")



@router.post("/")
async def create_item(request: Request):
    payload = await request.json() 
    workflow = payload.get('workflow', {})
    uploadcare_uris = payload.get('uploadcare_uris', {})
    image_ids = payload.get('image_ids', {})
    image_formats = payload.get('image_formats', {})
    message_id = payload.get('message_id', {})
    settings_id = payload.get('settings_id', {})
    user_id = payload.get('user_id', {})

    webhook_url = 'https://garfish-cute-typically.ngrok-free.app/image-generation/webhook'

    print(image_formats)

    await send_webhook_acknowledgment(user_id, message_id, settings_id, 'in progress', webhook_url)

    try:
        predefined_path = '/workspace/images/'

        download_and_save_images(uploadcare_uris, image_ids, image_formats, predefined_path)

        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
        images = get_images(ws, workflow)
        
        if images:
            s3_uris = upload_images_to_s3(images)

            await send_webhook_acknowledgment(user_id, message_id, settings_id, 'completed', webhook_url, s3_uris)
        else:
            raise Exception("GENERATED NO IMAGES")
    except Exception as e:
        print(f"ERROR: {e}")
        await send_webhook_acknowledgment(user_id, message_id, settings_id, 'failed', webhook_url)

    remove_images(uploadcare_uris, image_ids, image_formats, predefined_path)