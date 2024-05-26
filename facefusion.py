import uuid
import os

import subprocess

from fastapi import Request, APIRouter

from uuid import uuid4

import facefusion_utils

router = APIRouter(prefix="/facefusion")

def run_facefusion(file_ids, file_formats, predefined_path):
    print("INITIALIZING PYTHON COMMAND")

    run_command = [
        "python3", "/workspace/miniconda3/envs/facefusion/run.py",
        "--headless",
        "--execution-providers cuda",
        "--execution-thread-count 128",
        "--execution-queue-count 32",
        "--video-memory-strategy tolerant",
        "--frame-processors face_swapper face_enhancer",
        "--reference-face-distance 1.5",
        "--output-video-preset ultrafast"
    ]


    sources = ""
    for source_id, source_format in zip(file_ids[:-1], file_formats[:-1]):
        source_path = os.path.join(predefined_path, f"{source_id}.{source_format}")
        sources += source_path + " "

    run_command.extend([f"--source {sources}"])


    # The last file is assumed to be the target
    target_path = os.path.join(predefined_path, f"{file_ids[-1]}.{file_formats[-1]}")

    # Output file details
    output_id = uuid.uuid4()
    output_format = file_formats[-1]  # Assuming output format is the same as the target's format
    output_path = os.path.join(predefined_path, f"{output_id}.{output_format}")

    # Complete the command with target and output paths
    run_command.extend([f"--target {target_path}", f"--output {output_path}"])
    
    print("RUNNING THE PROCESS AND CALLING FACEFUSION")
    
    # Execute the full command within the Conda environment
    subprocess.run(run_command, shell=False, check=True)

    return output_path

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

    await facefusion_utils.send_webhook_acknowledgment(user_id, job_id, 'in progress')

    try:
        predefined_path = '/workspace/files/'

        facefusion_utils.download_and_save_files(uris, file_ids, file_formats, predefined_path)

        output_path = run_facefusion(file_ids,
                                     file_formats,
                                     predefined_path)

        if output_path:
            s3_uri = facefusion_utils.upload_file_to_s3(output_path)

            await facefusion_utils.send_webhook_acknowledgment(user_id, job_id, 'completed', s3_uri)
        else:
            raise Exception("GENERATED NO VIDEO DEEPFAKES")
    except Exception as e:
        print(e)
        await facefusion_utils.send_webhook_acknowledgment(user_id, job_id, 'failed')

    facefusion_utils.remove_files(file_ids, file_formats, predefined_path)