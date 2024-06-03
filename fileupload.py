import os
import boto3
import botocore
import boto3.s3.transfer as s3transfer
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fast_upload(session, 
                bucketname, 
                file_path,
                filename, 
                progress_func, 
                workers=40):
    try:
        botocore_config = botocore.config.Config(max_pool_connections=workers)
        s3client = session.client('s3', config=botocore_config)
        transfer_config = s3transfer.TransferConfig(
            use_threads=True,
            max_concurrency=workers,
            multipart_threshold=5 * 1024 * 1024,  # 5MB threshold for multipart uploads
            multipart_chunksize=5 * 1024 * 1024,  # 5MB chunksize
        )
        s3t = s3transfer.create_transfer_manager(s3client, transfer_config)

        logger.info(f"FILENAME: {filename}")
        logger.info(f"PATH TO THE FILE: {file_path}")
        
        # Check if file exists
        if not os.path.isfile(file_path):
            logger.error(f"The file {file_path} does not exist.")
            return

        future = s3t.upload(
            file_path, bucketname, filename,
            subscribers=[
                s3transfer.ProgressCallbackInvoker(progress_func),
            ],
        )
        
        future.result()  # wait for the upload to complete
        
        s3t.shutdown()  # wait for all the upload tasks to finish
        logger.info("Upload completed successfully.")
    except botocore.exceptions.ClientError as error:
        logger.error(f"An error occurred: {error}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

predefined_path = '/Users/jakubsiekiera/runpod_server/'
output_filename = 'output.mp4'

bucketname = 'magicalcurie'
file_path = os.path.join(predefined_path, output_filename)

try:
    totalsize = os.stat(file_path).st_size
except FileNotFoundError:
    logger.error(f"The file {file_path} does not exist.")
    totalsize = 0

if totalsize > 0:
    with tqdm(desc='upload', ncols=60, total=totalsize, unit='B', unit_scale=True) as pbar:
        # Create a session with explicit credentials (for testing)
        session = boto3.Session(
            aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            region_name='us-east-1'
        )
        fast_upload(session, bucketname, file_path, output_filename, pbar.update)
else:
    logger.error(f"Upload aborted due to file size being 0 or file not found.")
