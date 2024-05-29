import os

import subprocess

from fastapi import Request, APIRouter

from uuid import uuid4

import facefusion_utils as utils

import boto3

from tqdm import tqdm

router = APIRouter(prefix="/facefusion")

def run_facefusion(file_ids, file_formats, predefined_path):
    print("INITIALIZING PYTHON COMMAND")

    conda_init_script = ["conda", "init", "bash"]
    subprocess.run(conda_init_script, shell=False, check=True)

    # Construct the command to activate the Conda environment
    activate_command = ["/workspace/miniconda3/bin/activate", "facefusion"]

    # Run the activation command
    subprocess.run(activate_command, shell=False, check=True)

    os.chdir("../facefusion")

    # Define the run command
    run_command = [
        "python3",
        "run.py",
        "--headless",
        "--execution-providers", "cuda",
        "--execution-thread-count", "16",
        "--execution-queue-count", "4",
        "--video-memory-strategy", "tolerant",
        "--frame-processors", "face_swapper", "face_enhancer",
        "--reference-face-distance", "1.0",
        "--output-video-preset", "ultrafast"
    ]


    # Create the sources list
    source_path = os.path.join(predefined_path, f"{file_ids[0]}.{file_formats[0]}")

    # Extend the run_command list with the sources
    run_command.extend(["--source", source_path])

    # The last file is assumed to be the target
    target_path = os.path.join(predefined_path, f"{file_ids[-1]}.{file_formats[-1]}")

    # Output file details
    output_id = str(uuid4())
    output_format = file_formats[-1]  # Assuming output format is the same as the target's format
    filename = f"{output_id}.{output_format}"
    output_path = os.path.join(predefined_path, filename)

    # Complete the command with target and output paths
    run_command.extend(["--target", target_path, "--output", output_path])

    print("RUNNING THE PROCESS AND CALLING FACEFUSION")

    # Execute the full command within the Conda environment
    subprocess.run(run_command, shell=False, check=True)

    return filename

@router.post("/")
async def generate_deepfake(request: Request):
    print("EXTRACTING PAYLOAD")
    payload = await request.json()
    source_uris = payload.get('source_uris', {})
    target_uri = payload.get('target_uri', {})
    file_formats = payload.get('file_formats', {})
    job_id = payload.get('job_id', {})
    user_id = payload.get('user_id', {})

    print(f"Source URIs: {source_uris}")
    print(f"Target URI: {target_uri}")
    print(f"File Formats: {file_formats}")
    print(f"Job ID: {job_id}")
    print(f"User ID: {user_id}")

    file_ids = []

    uris = source_uris + [target_uri]

    for _ in uris:
        file_ids.append(str(uuid4()))

    try:
        await utils.send_webhook_acknowledgment(user_id=user_id, 
                                                job_id=job_id, 
                                                status='in progress')
    
        predefined_path = '/workspace/files/'

        utils.download_and_save_files(uris, 
                                      file_ids, 
                                      file_formats, 
                                      predefined_path)

        output_filename = run_facefusion(file_ids,
                                         file_formats,
                                         predefined_path)

        if output_filename:
            bucketname = 'magicalcurie'
            s3dir = '/'
            file = predefined_path+output_filename
            totalsize = os.stat(file).st_size

            with tqdm(desc='upload', ncols=60,
                    total=totalsize, unit='B', unit_scale=1) as pbar:
                utils.fast_upload(boto3.Session(), bucketname, s3dir, file, pbar.update)

            await utils.send_webhook_acknowledgment(user_id=user_id, 
                                                    job_id=job_id, 
                                                    status='completed', 
                                                    output_url=f"{os.getenv('CDN_URL')}/{file}")
        else:
            raise Exception("GENERATED NO VIDEO DEEPFAKES")
    except Exception as e:
        print(e)
        await utils.send_webhook_acknowledgment(user_id, job_id, 'failed')

    utils.remove_files(file_ids, 
                       file_formats, 
                       predefined_path)