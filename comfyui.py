import websocket
import uuid
import json
import os
import urllib.request
import urllib.parse

import comfyui_utils

from fastapi import Request, APIRouter

router = APIRouter(prefix="/image-generation")

client_id = str(uuid.uuid4())
server_address = "127.0.0.1:8188"

def queue_prompt(prompt):
    print("QUEUEING PROMPT")
    p = {"prompt": prompt, "client_id": client_id}
    print(f"GOT THE PRMOPT {prompt}")
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    print(f"SENT A REQUEST TO COMFY: {req}")
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    print(f"GETTING IMAGE --filename: {filename} --subfolder: {subfolder} --folder_type: {folder_type}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    print(f"URL VALUES: {url_values}")
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        print("READING RESPONSE")
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        # Read response content
        response_content = response.read()
        print(f"GOT HISTORY FOR PROMPT ID {prompt_id}: {response_content}")
        # Decode the JSON content
        return json.loads(response_content)

def get_images(ws, prompt):
    print("QUEUEING PROMPT")
    prompt_id = queue_prompt(prompt)['prompt_id']
    raw_images_output = []
    while True:
        out = ws.recv()
        if isinstance(out, str):
            print("IS AN INSTANCE - GETTING THE OUTPUT")
            message = json.loads(out)
            print(f"OUTPUT MESSAGE: {message}")
            if message['type'] == 'executing':
                print("MESSAGE TYPE IS EXECUTING")
                data = message['data']
                print(f"GOT MESSAGE DATA {data}")
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    print("EXECUTION IS DONE")
                    break #Execution is done
        else:
            print("IS NOT AN INSTANCE - CONTINUING POLLING")
            continue #previews are binary data
    
    try:
        print("GETTING THE HISTORY FOR THE REQUESTED PROMPT")
        history = get_history(prompt_id)[prompt_id]

        status = history['status']['status_str']
        print(f"GENERATION STATUS: {status}")

        completed = history['status']['completed']
        print(f"GENERATION COMPLETED: {completed}")

        if status == "success" and completed:
            for o in history['outputs']:
                print(f"GOT OUTPUT: {o}")
                node_output = history['outputs'][o]
                print(f"NODE OUTPUT {node_output}")
                if 'images' in node_output:
                    print("IMAGES FOUND IN NODE OUTPUT")
                    for image in node_output['images']:
                        print(f"GOT AN IMAGE {image}")
                        image_data = get_image(image['filename'], image['subfolder'], image['type'])

                        raw_images_output.append(image_data)
                else:
                    print("IMAGES NOT FOUND IN NODE OUTPUT")

            return raw_images_output
        else:
            print(f"COULDN'T GENERATE IMAGES FOR PROMPT ID: {prompt_id}")
    except json.JSONDecodeError as e:
        print(f"JSON DECODE ERROR: {e}")
    except Exception as e:
        print(f"WHILE READING EXECUTION HISTORY EXCEPTION OCCURED: {e}")


@router.post("/")
async def generate(request: Request):
    payload = await request.json() 
    workflow = payload.get('workflow', {})
    uploadcare_uris = payload.get('uploadcare_uris', {})
    image_ids = payload.get('image_ids', {})
    image_formats = payload.get('image_formats', {})
    message_id = payload.get('message_id', {})
    user_id = payload.get('user_id', {})

    webhook_url = f"{os.getenv('COMFYUI_BACKEND_URL')}/image-generation/webhook"

    print(image_formats)

    await comfyui_utils.send_webhook_acknowledgment(user_id, 
                                                    message_id, 
                                                    'in progress', 
                                                    webhook_url)

    try:
        predefined_path = '/workspace/images/'

        comfyui_utils.download_and_save_images(uploadcare_uris, 
                                               image_ids, 
                                               image_formats, 
                                               predefined_path)

        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
        images = get_images(ws, workflow)
        
        if images:
            # if len(images) >= 2:
            #     images = images[len(images)//2:] if images else []
            s3_uris = comfyui_utils.upload_images_to_s3(images)

            await comfyui_utils.send_webhook_acknowledgment(user_id, message_id, 'completed', webhook_url, s3_uris)
        else:
            raise Exception("GENERATED NO IMAGES")
    except Exception as e:
        print(f"ERROR: {e}")
        await comfyui_utils.send_webhook_acknowledgment(user_id, message_id, 'failed', webhook_url)

    comfyui_utils.remove_images(image_ids, image_formats, predefined_path)