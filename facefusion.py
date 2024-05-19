# import uuid
# import os
# import httpx
# import requests

# import subprocess

# from datetime import datetime

# from fastapi import Request, APIRouter

# import boto3

# from pydantic import BaseModel, Field

# from typing import List, Optional

# router = APIRouter(prefix="/deepfake")

# def upload_file_to_s3(output_path):
#     print("UPLOADING FILE TO S3")

#     print("INITIALIZING S3 CLIENT")
#     s3_client = boto3.client('s3')

#     print("UPLOADING FILEOBJ TO S3")
#     # Open the file in binary mode
#     with open(output_path, 'rb') as data:
#         # Upload the file to S3
#         s3_client.upload_fileobj(data, 'magicalcurie', output_path)

#     # Construct the S3 URI
#     s3_uri = f's3://magicalcurie/{output_path}'

#     print("REMOVING THE LOCAL FILE")
#     # Remove the local file
#     os.remove(output_path)

#     return s3_uri

# def download_and_save_files(
#         uploadcare_uris: List[str], 
#         file_ids: List[str],
#         file_formats: List[str],
#         predefined_path: str) -> None:
#     """
#     Downloads and saves files based on file URIs and file IDs.
#     Args:
#         uploadcare_uris (List[str]): List of file URIs.
#         file_ids (List[str]): List of file IDs.
#         predefined_path (str): Predefined path to save the files.
#         file_format (str): The format of the files to be saved.
#     """
#     print(f"DOWNLOADING AND SAVING FILES")
#     for file_uri, file_id, file_format in zip(uploadcare_uris, file_ids, file_formats):        
#         if file_id:
#             print(f"SETTING THE UNIQUE FILEPATH OF THE FILE")
#             file_path = os.path.join(predefined_path, f"{file_id}.{file_format}")
#             print(f"DOWNLOADING FILE")
#             response = requests.get(file_uri)
#             if response.status_code == 200:
#                 print(f"WRITING FILE TO THE UNIQUE PATH")
#                 with open(file_path, "wb") as f:
#                     f.write(response.content)
#                 print(f"File saved at {file_path}")
#             else:
#                 print(f"Failed to download file from {file_uri}")
#         else:
#             print(f"Zip of uploadcare_uris and file_ids is not properly paired.")


# def remove_files(
#         file_ids: List[str],
#         file_formats: List[str],
#         predefined_path: str) -> None:
#     """
#     Removes files based on file IDs.
#     Args:
#         file_ids (List[str]): List of file IDs.
#         predefined_path (str): Predefined path where the files are stored.
#     """
#     print(f"REMOVING FILES")
#     for file_id, file_format in zip(file_ids, file_formats):
#         print(f"SETTING THE UNIQUE FILEPATH OF THE FILE")
#         file_path = os.path.join(predefined_path, f"{file_id}.{file_format}")
#         try:
#             print(f"REMOVING A FILE")
#             os.remove(file_path)
#             print(f"File removed: {file_path}")
#         except FileNotFoundError:
#             print(f"File not found: {file_path}")

# def run_facefusion(file_ids, file_formats, reference_face_distance, face_enhancer_model, frame_enhancer_blend, predefined_path):
#     print("INITIALIZING PYTHON COMMAND")

#     # Activate Conda environment
#     activate_env = "conda activate facefusion"

#     # Python command to run
#     run_command = [
#         "python", "C:\\Users\\Shadow\\facefusion\\run.py",
#         "--headless", 
#         "--reference-face-distance", str(reference_face_distance), 
#         "--face-enhancer-model", face_enhancer_model, 
#         "--frame-enhancer-blend", str(frame_enhancer_blend)
#     ]

#     # Add a '-s' flag for each image except the last one (target)
#     for source_id, source_format in zip(file_ids[:-1], file_formats[:-1]):
#         source_path = os.path.join(predefined_path, f"{source_id}.{source_format}")
#         run_command.extend(["-s", source_path])

#     # The last file is assumed to be the target
#     target_path = os.path.join(predefined_path, f"{file_ids[-1]}.{file_formats[-1]}")

#     # Output file details
#     output_id = uuid.uuid4()
#     output_format = file_formats[-1]  # Assuming output format is the same as the target's format
#     output_path = os.path.join(predefined_path, f"{output_id}.{output_format}")

#     # Complete the command with target and output paths
#     run_command.extend(["-t", target_path, "-o", output_path])
    
#     # Combine commands to run in the same subprocess
#     full_command = f"{activate_env} && " + " ".join(run_command)

#     print(full_command)
    
#     print("RUNNING THE PROCESS AND CALLING FACEFUSION")
#     # Execute the full command within the Conda environment
#     subprocess.run(full_command, shell=True, check=True)

#     return output_path

# class Message(BaseModel):
#     user_id: str
#     status: Optional[str] = None
#     uploadcare_uris: Optional[List[str]] = None # the last one is the target uri
#     created_at: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
#     message_id: Optional[str] = None
#     reference_face_distance: Optional[float] = None
#     face_enhancer_model: Optional[str] = None
#     frame_enhancer_blend: Optional[int] = None
#     s3_uri: Optional[List[str]] = None

# async def send_webhook_acknowledgment(
#         user_id: str, 
#         message_id: str, 
#         status: str, 
#         webhook_url: str, 
#         s3_uri: str = None) -> None:
#     """
#     Sends an acknowledgment message via webhook.

#     Args:
#         user_id (str): The unique identifier for the user.
#         message_id (str): The unique identifier for the message.
#         status (str): The status of the message.
#         webhook_url (str): The URL of the webhook endpoint.
#         s3_uri (str): The S3 URI associated with the message.

#     Returns:
#         None
#     """
#     print("SENDING WEBHOOK ACKNOWLEDGMENT")
#     try:
#         print("CREATING DICTIONARY TO STORE THE FIELDS")
#         # Create a dictionary to store the fields
#         message_fields = {
#             'user_id': user_id,
#             'message_id': message_id,
#             'status': status
#         }

#         if s3_uri is not None:
#             print("ADDING S3_URI FIELD TO MESSAGE MODEL")
#             message_fields['s3_uri'] = s3_uri

#         print("CREATING MESSAGE MODEL")
#         # Create the Message object
#         message = Message(**message_fields)

#         print(f"MAKING POST REQUEST TO THE WEBHHOK {webhook_url}")
#         async with httpx.AsyncClient() as client:
#             response = await client.post(webhook_url, json=message.__dict__)
#             if response.status_code == 200:
#                 print("Webhook request successful!")
#             else:
#                 print(f"Webhook request failed with status code {response.status_code}")
#     except Exception as e:
#         print(f"Error sending acknowledgment: {str(e)}")

# @router.post("/generate")
# async def generate_deepfake(request: Request):
#     print("EXTRACTING PAYLOAD")
#     payload = await request.json()
#     user_id = payload.get('user_id', {})
#     uploadcare_uris = payload.get('uploadcare_uris', {})
#     file_ids = payload.get('file_ids', {})
#     file_formats = payload.get('file_formats', {})
#     message_id = payload.get('message_id', {})
#     reference_face_distance = payload.get('reference_face_distance', {})
#     face_enhancer_model = payload.get('face_enhancer_model', {})
#     frame_enhancer_blend = payload.get('frame_enhancer_blend', {})

#     webhook_url = 'https://garfish-cute-typically.ngrok-free.app/deepfake/ff-webhook'

#     await send_webhook_acknowledgment(user_id, message_id, 'in progress', webhook_url)

#     try:
#         predefined_path = 'C:\\Users\\Shadow\\Desktop'

#         download_and_save_files(uploadcare_uris, file_ids, file_formats, predefined_path)

#         output_path = run_facefusion(file_ids,
#                        file_formats,
#                        reference_face_distance,
#                        face_enhancer_model,
#                        frame_enhancer_blend,
#                        predefined_path)

#         s3_uri = upload_file_to_s3(output_path)

#         await send_webhook_acknowledgment(user_id, message_id, 'completed', webhook_url, s3_uri)
#     except Exception as e:
#         print(e)
#         await send_webhook_acknowledgment(user_id, message_id, 'failed', webhook_url)

#     remove_files(file_ids, file_formats, predefined_path)