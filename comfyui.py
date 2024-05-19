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
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    print("QUEUEING PROMPT")
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output

    print("GOT THE IMAGES")
    return output_images


def upload_images_to_s3(images):
    print("UPLOADING IMAGES TO S3")
    s3_client = boto3.client('s3')

    s3_uris = []

    for node_id in images:
        for image_data in images[node_id]:
            image_key = str(uuid.uuid4()) + '.png'

            image_array = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_UNCHANGED)
            
            print("SAVING IMAGE FILE TEMPORARILY")

            # Save the image as a PNG file
            cv2.imwrite(image_key, image_array)

            with open(image_key, 'rb') as data:
                print("UPLOADING THE IMAGE")
                s3_client.upload_fileobj(data, 'magicalcurie', image_key)

            print(f"UPLOADED THE IMAGE: " + f's3://magicalcurie/{image_key}')
            s3_uris.append(f's3://magicalcurie/{image_key}')

            # Remove the local image file
            os.remove(image_key)

    return s3_uris

def download_and_save_images(
        uploadcare_uris: Dict[str, str], 
        image_ids: Dict[str, str], 
        image_formats: Dict[str, str], 
        predefined_path: str) -> None:
    """
    Downloads and saves images based on image URIs and image IDs.
    Args:
        uploadcare_uris (Dict[str, str]): Dictionary of image URIs.
        image_ids (Dict[str, str]): Dictionary of image IDs.
        predefined_path (str): Predefined path to save the images.
    """
    print(f"DOWNLOADING AND SAVING IMAGES")
    for key, uri in uploadcare_uris.items():
        print(f"GETTING IMAGE ID")
        image_id = image_ids.get(key)
        image_format = image_formats.get(key)
        
        if image_id:
            print(f"SETTING THE UNIQUE FILEPATH OF THE IMAGE")
            image_path = os.path.join(predefined_path, f"{image_id}.{image_format}")
            print(f"image_path: {image_path}")
            print(f"DOWNLOADING IMAGE")
            response = requests.get(uri)
            if response.status_code == 200:
                print(f"WRITING IMAGE TO THE UNIQUE PATH")
                with open(image_path, "wb") as f:
                    f.write(response.content)
                print(f"Image saved at {image_path}")
            else:
                print(f"Failed to download image from {uri}")
        else:
            print(f"No image ID found for key: {key}")

def remove_images(
        uploadcare_uris: Dict[str, str],
        image_ids: Dict[str, str],
        image_formats: Dict[str, str],
        predefined_path: str) -> None:
    """
    Removes images based on image IDs.
    Args:
        image_ids (Dict[str, str]): Dictionary of image IDs.
        predefined_path (str): Predefined path where the images are stored.
    """
    print(f"REMOVING IMAGES")
    for key, uri in uploadcare_uris.items():
        print(f"SETTING THE UNIQUE FILEPATH OF THE IMAGE")
        print(f"GETTING IMAGE ID")
        image_id = image_ids.get(key)

        if image_id:
            image_format = image_formats.get(key)
            image_path = os.path.join(predefined_path, f"{image_id}.{image_format}")
            try:
                print(f"REMOVING AN IMAGE")
                os.remove(image_path)
                print(f"Image removed: {image_path}")
            except FileNotFoundError:
                print(f"Image not found: {image_path}")

class Message(BaseModel):
    user_id: Optional[str] = None
    status: Optional[str] = None
    uploadcare_uris: Optional[Dict[str, str]] = None
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
        print("CREATING DICTIONARY TO STORE THE FIELDS")
        # Create a dictionary to store the fields
        message_fields = {
            'user_id': user_id,
            'message_id': message_id,
            'settings_id': settings_id,
            'status': status
        }

        if s3_uris is not None:
            print("ADDING S3_URIS FIELD TO MESSAGE MODEL")
            message_fields['s3_uris'] = s3_uris

        print("CREATING MESSAGE MODEL")
        # Create the Message object
        message = Message(**message_fields)

        print(f"MAKING POST REQUEST TO THE WEBHHOK {webhook_url}")
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=message.__dict__)
            if response.status_code == 200:
                print("Webhook request successful!")
            else:
                print(f"Webhook request failed with status code {response.status_code}")
    except Exception as e:
        print(f"Error sending acknowledgment: {str(e)}")



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
        predefined_path = 'C:\\Users\\Shadow\\Desktop'

        download_and_save_images(uploadcare_uris, image_ids, image_formats, predefined_path)

        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
        images = get_images(ws, workflow)

        s3_uris = upload_images_to_s3(images)

        await send_webhook_acknowledgment(user_id, message_id, settings_id, 'completed', webhook_url, s3_uris)
    except Exception as e:
        print(f"ERROR: {e}")
        await send_webhook_acknowledgment(user_id, message_id, settings_id, 'failed', webhook_url)

    remove_images(uploadcare_uris, image_ids, image_formats, predefined_path)