from typing import List

import os

import httpx

import requests

import boto3
import botocore
import boto3.s3.transfer as s3transfer

from interfaces import Message


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

        # Send a GET request to the URL
        with requests.get(file_uri, stream=True) as response:
            response.raise_for_status()  # Check if the request was successful
            # Open a local file in write-binary mode
            with open(file_path, 'wb') as file:
                # Iterate over the response in chunks
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)  # Write each chunk to the file

            print(f"SAVED FILE TO {file_path}")

def fast_upload(session, 
                bucketname, 
                s3dir, 
                file, 
                filename, 
                progress_func, 
                workers=20):
    botocore_config = botocore.config.Config(max_pool_connections=workers)
    s3client = session.client('s3', config=botocore_config)
    transfer_config = s3transfer.TransferConfig(
        use_threads=True,
        max_concurrency=workers,
    )
    s3t = s3transfer.create_transfer_manager(s3client, transfer_config)
    
    dst = os.path.join(s3dir, os.path.basename(filename))
    s3t.upload(
        file, bucketname, dst,
        subscribers=[
            s3transfer.ProgressCallbackInvoker(progress_func),
        ],
    )
    
    s3t.shutdown()  # wait for all the upload tasks to finish

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


async def send_webhook_acknowledgment(
        user_id: str, 
        job_id: str, 
        status: str, 
        output_url: str = None) -> None:
    """
    Sends an acknowledgment message via webhook.

    Args:
        user_id (str): The unique identifier for the user.
        job_id (str): The unique identifier for the message.
        status (str): The status of the message.
        webhook_url (str): The URL of the webhook endpoint.
        s3_uri (str): The S3 URI associated with the message.

    Returns:
        None
    """
    webhook_url = f"{os.getenv('FACEFUSION_BACKEND_URL')}/facefusion-deepfake/webhook"
    
    print("SENDING WEBHOOK ACKNOWLEDGMENT")
    try:
        print("CREATING DICTIONARY TO STORE THE FIELDS")
        # Create a dictionary to store the fields
        message_fields = {
            'user_id': user_id,
            'job_id': job_id,
            'status': status
        }

        if output_url is not None:
            print("ADDING S3_URI FIELD TO MESSAGE MODEL")
            message_fields['output_url'] = output_url

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