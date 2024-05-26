import os
import httpx
import requests

import boto3

from datetime import datetime

from pydantic import BaseModel, Field

from typing import List, Optional

class Message(BaseModel):
    user_id: str
    status: Optional[str] = None
    uploadcare_uris: Optional[List[str]] = None # the last one is the target uri
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    message_id: Optional[str] = None
    # reference_face_distance: Optional[float] = None
    # face_enhancer_model: Optional[str] = None
    # frame_enhancer_blend: Optional[int] = None
    s3_uris: Optional[List[str]] = None


def download_and_save_files(uris: List[str], 
                            file_ids: List[str],
                            file_formats: List[str],
                            predefined_path: str) -> None:
    """
    Downloads and saves files based on file URIs and file IDs.
    Args:
        uploadcare_uris (List[str]): List of file URIs.
        file_ids (List[str]): List of file IDs.
        predefined_path (str): Predefined path to save the files.
        file_format (str): The format of the files to be saved.
    """
    print(f"DOWNLOADING AND SAVING FILES FOR FACEFUSION")
    for i in range(len(file_ids)):
        print(f"DOWNLOAD FOR FILE {i+1}...")

        file_uri = uris[i]
        print(f"GOT THE FILE URI: {file_uri}")

        file_id = file_ids[i]
        print(f"GOT THE FILE ID: {file_id}")

        file_format = file_formats[i]
        print(f"GOT THE FILE FORMAT: {file_format}")

        print(f"SETTING THE UNIQUE FILEPATH OF THE FILE")
        file_path = os.path.join(predefined_path, f"{file_id}.{file_format}")

        print(f"DOWNLOADING FILE FROM {file_uri}")
        response = requests.get(file_uri)

        if response.status_code == 200:
            print(f"GOT THE FILE FROM UPLOADCARE")
            with open(file_path, "wb") as f:
                f.write(response.content)
            print(f"SAVED FILE TO {file_path}")
        else:
            print(f"NO FILE FOUND FOR {file_uri}")


def remove_files(
        file_ids: List[str],
        file_formats: List[str],
        predefined_path: str) -> None:
    """
    Removes files based on file IDs.
    Args:
        file_ids (List[str]): List of file IDs.
        predefined_path (str): Predefined path where the files are stored.
    """
    print(f"REMOVING FILES")
    for i in range(len(file_ids)):
        print(f"GETTING FILE ID")
        file_id = file_ids[i]

        file_format = file_formats[i]
        print(f"GOT THE GOT THE FILE FORMAT: {file_format}")

        print(f"SETTING THE UNIQUE FILEPATH OF THE FILE")
        file_path = os.path.join(predefined_path, f"{file_id}.{file_format}")
        try:
            print(f"REMOVING A FILE")
            os.remove(file_path)
            print(f"FILE REMOVED: {file_path}")
        except FileNotFoundError:
            print(f"FILE FOR REMOVAL NOT FOUND: {file_path}")


def upload_file_to_s3(output_path):
    print("UPLOADING FILE TO S3")
    s3_client = boto3.client('s3')

    print("CONNECTED TO THE S3 CLIENT")

    print("UPLOADING FILEOBJ TO S3")
    # Open the file in binary mode
    with open(output_path, 'rb') as data:
        # Upload the file to S3
        s3_client.upload_fileobj(data, 'magicalcurie', output_path)

    # Construct the S3 URI
    s3_uri = f"{os.getenvb('S3_URI')}/{output_path}"

    print("REMOVING THE LOCAL FILE")
    # Remove the local file
    os.remove(output_path)

    return s3_uri


async def send_webhook_acknowledgment(
        user_id: str, 
        message_id: str, 
        status: str, 
        s3_uri: str = None) -> None:
    """
    Sends an acknowledgment message via webhook.

    Args:
        user_id (str): The unique identifier for the user.
        message_id (str): The unique identifier for the message.
        status (str): The status of the message.
        webhook_url (str): The URL of the webhook endpoint.
        s3_uri (str): The S3 URI associated with the message.

    Returns:
        None
    """
    webhook_url = f"{os.getenv('FACEFUSION_BACKEND_URL')}/deepfake/facefusion-webhook"
    
    print("SENDING WEBHOOK ACKNOWLEDGMENT")
    try:
        print("CREATING DICTIONARY TO STORE THE FIELDS")
        # Create a dictionary to store the fields
        message_fields = {
            'user_id': user_id,
            'message_id': message_id,
            'status': status
        }

        if s3_uri is not None:
            print("ADDING S3_URI FIELD TO MESSAGE MODEL")
            message_fields['s3_uri'] = s3_uri

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