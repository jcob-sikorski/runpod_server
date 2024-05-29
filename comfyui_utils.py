import uuid
import os
import httpx
import requests
import cv2
import numpy as np

import boto3

from pydantic import BaseModel

from typing import List, Optional

def upload_images_to_s3(images):
    print("UPLOADING IMAGES TO S3")
    s3_client = boto3.client('s3')

    print("CONNECTED TO THE S3 CLIENT")
    s3_uris = []

    for image_data in images:
        image_key = str(uuid.uuid4()) + '.png'

        print(f"GOT THE IMAGE KEY: {image_key}")

        image_array = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_UNCHANGED)
            
        print(f"SAVING IMAGE ARRAY TO: {image_key}")

        # Save the image as a PNG file
        cv2.imwrite(image_key, image_array)

        print("OPENING TMP SAVED IMAGE...")
        with open(image_key, 'rb') as data:
            print("OPENED IMAGE")

            print("UPLOADING THE IMAGE TO S3")
            s3_client.upload_fileobj(data, 'magicalcurie', image_key)

        print(f"UPLOADED THE IMAGE to S3: " + f"{os.getenv('CDN_URL')}/{image_key}")
        s3_uris.append(f"{os.getenv('CDN_URL')}/{image_key}")

        print("REMOVED THE LOCAL IMAGE FILE")
        # Remove the local image file
        os.remove(image_key)

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