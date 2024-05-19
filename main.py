from dotenv import load_dotenv

import os

import boto3

from fastapi import FastAPI
import uvicorn

import comfyui
# import facefusion

load_dotenv()

# Load AWS S3 Access keys from environment variables
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')

boto3.setup_default_session(aws_access_key_id=S3_ACCESS_KEY,
                            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                            region_name='us-east-1')

app = FastAPI()

app.include_router(comfyui.router)
# app.include_router(facefusion.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)