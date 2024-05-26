from dotenv import load_dotenv

import os

import boto3

from fastapi import FastAPI
import uvicorn

import comfyui
import facefusion

import subprocess

# Activate the facefusion environment using conda
activation_command = "conda activate facefusion"
subprocess.run(activation_command, shell=False, check=True)

# Determine the environment (default to production)
env = os.getenv('ENV', 'production')

# Map the environment to the corresponding .env file
if env == 'development':
    env_file = '.env.development'
elif env == 'staging':
    env_file = '.env.staging'
else:
    env_file = '.env.production'

# Load the .env file
load_dotenv(env_file)

# Load AWS S3 Access keys from environment variables
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')

boto3.setup_default_session(aws_access_key_id=S3_ACCESS_KEY,
                            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                            region_name='us-east-1')

app = FastAPI()

app.include_router(comfyui.router)
app.include_router(facefusion.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)