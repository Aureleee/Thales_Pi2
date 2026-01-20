# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    utils.py                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: aurele <aurele@student.42.fr>              +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/01/14 15:43:02 by aurele            #+#    #+#              #
#    Updated: 2026/01/20 21:03:06 by aurele           ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

import json, urllib.request, urllib.parse, requests, os, websocket, io, random
from PIL import Image

"""
Ce fichier contient les fonctions utiles pour upload/download images/worflows a comfyUI
et pour avoir le queue prompt et le poll history.

source: https://github.com/Comfy-Org/ComfyUI/tree/master/script_examples

queue_prompt: 
    -> prend le wf, l'envoie a comfyUI et renvoie sa reponse: contient prompt_id 
upload_file:
    -> upload un file image a comfyUI (via l'API http)
        -> retourne le path "logique" que comfyUI attend ensuite (subfolder/name.png ou juste name.png)
"""
class ComfyUIClient:
    def __init__(self, server_address, client_id):
        self.server_address = server_address
        self.client_id = client_id
        
    # def queue_prompt(self, prompt):
    #     payload ={"prompt": prompt, "client_id": self.client_id} #attention ici le "prompt" represente le wf complet :D (c'est un dict ducoup)
    #     data = json.dumps(payload).encode("utf-8") #-> on prepare la data a send a comfyUI. (dict->json->bytes)
    #     url = f"http://{self.server_address}/prompt" # ATTENTION, en local sur mon mac comfyUI utilise http mais il peut utiliser https
    #     req = urllib.request.Request(url, data=data) # prepa de la request, POST
    #     resp = urllib.request.urlopen(req) #open TCP request-> connecte a l'adresse-> envoie la req http ..attend la reponse (status code, headers, body)
    #     body = resp.read() #on recup le body (bytes)
    #     resp.close() #ferme la connexion
    #     return json.loads(body)# permet de lire la reponse (bytes-> json-> dict)
    def queue_prompt(self, prompt):
        payload = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(payload).encode("utf-8")

        url = f"http://{self.server_address}/prompt"
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8"))

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print("\n=== COMFYUI 400 BODY ===")
            print(err_body)
            print("=== END BODY ===\n")
            raise
    
    def get_history(self, prompt_id):
        url = f"http://{self.server_address}/history/{prompt_id}"
        req = urllib.request.Request(url) #rq, ici pas de data -> request = GET
        resp = urllib.request.urlopen(req)
        body = resp.read()
        resp.close()
        return json.loads(body)
        #fonction super similaire, c'est des simples requetes http. 
        
    def get_image(self, file_name, subfolder, folder_type):
        data = {"filename":file_name, "subfolder":subfolder, "type":folder_type}
        url_values = urllib.parse.urlencode(data)
        url = f"http://{self.server_address}/view?{url_values}" #notre url est prête
        resp = urllib.request.urlopen(url)
        img = resp.read()
        resp.close()
        return img
    
    def get_images(self, ws, prompt, verbose = True):
        body_answer= self.queue_prompt(prompt) # envoie de la request -> comfyUI
        prompt_id = body_answer["prompt_id"] # dans sa reponse on recupère le prompt_id (qu'on utilise pour track l'avancement)
        if verbose: #True par default, permet de voir l'avancement
            print(f"queud promt_id={prompt_id}", flush = True)
        output_images = dict()
        last_node = None
        while True: #Tant que comfyUI travaille, regarde regulièrement ou il en est.
            out = ws.recv() # PENSER à établir au préalable une connection ws
            if isinstance(out, str): #en fonction des reponses de comfyUI, on donne l'avancement de la pass
                # soit il nous envoie le JSON text (str) ou alors les frames binaires pour les previews
                message= json.loads(out)
                #voir la docu comfyUI pour plus d'info
                msg_type = message.get("type")
                if verbose and msg_type == "progress": #afficher le progres, pas necesaire mais pratique
                    data = message.get("data", {}) # en fait systematiquement on decode
                    value = data.get("value")
                    maximum = data.get("max")
                    if value is not None and maximum is not None:
                        print(f"progress {value}/{maximum}", flush=True)
                if msg_type == "executing":
                    data = message.get("data",{})
                    if verbose:
                        node = data.get("node")
                        if node != last_node: #on update le node uniquement des qu'il passe au suivant
                            print(f"execute le node={node}", flush=True)
                            last_node = node 
                    if data.get("node") is None and data.get("prompt_id") == prompt_id:
                        #qunad confyUI a finit alors data["node"] = None.
                        break
            else: #dans ce cas la c'est les binary previews
            #typiquement: isinstance(out, bytes) == True -> wo -> Image.open...
            #mais c'est les "preview" uniquement"-> ducoup on dowload les images via l'API http via l'historique
                continue
        history = self.get_history(prompt_id)[prompt_id]
        #quand comfyUI a termine on refait une request http et on download les iamges
        for node_id, node_output in history.get("outputs", {}).items():
            #ici chaque node peut potentiellement avoir des images en output
            #pratique dans notre cas pour si on a depthmap + edge..etc 
            images = []
            if "images" in node_output:
                for image in node_output["images"]: #dans le cas ou un node a plusieurs output.
                    image_data = self.get_image(image["filename"], image.get("subfolder", ""), image.get("type", "output"),)
                    images.append(image_data)
            if images:
                output_images[node_id] = images
        return output_images
    
    def upload_file(self, file, subfolder, overwrite):
        path = "" #if its fails on return vide
        try:
            body = {"image": file}
            data = {} # params en plus (form data)-> overwrite / subfolder
            if overwrite:
                data["overwrite"] = "true" #ATTENTION: comfyUI attend un string ici
            if subfolder:
                data["subfolder"] = subfolder
            resp = requests.post(
                f"http://{self.server_address}/upload/image",
                files=body, #multipart/form-data (binaire) (pas du json)
                data=data,  # form fields (texte)
            )
            if resp.status_code == 200:
                j = resp.json() #on decode le json (-> dict python)
                path = j["name"] #name du fichier stocké par comfyUI
                if j.get("subfolder"):
                    path = f'{j["subfolder"]}/{path}' #on reconstruit le path final (subfolder/name)
            else:
                raise RuntimeError(f"{resp.status_code} - {resp.reason}") #error http
        except Exception as error:
            print(error) #quick debug
        return path
    
    def run_comfyui_img2img(
            self,
            image_path: str,
            workflow_json_path: str,
            output_dir: str,
            image_name: str,
            n_images: int,
            positive_prompt: str,
            denoise: float,
            cfg: float = 1.0,
            verbose=True,
        ):
            import io
            import random

            os.makedirs(output_dir, exist_ok=True)

            if verbose:
                print(f"client_id={self.client_id}", flush=True)

            # upload input image
            if verbose:
                print(f"Uploading image: {image_path}", flush=True)
            with open(image_path, "rb") as f:
                comfyui_path_image = self.upload_file(f, "", True)
            if verbose:
                print(f"Uploaded as: {comfyui_path_image}", flush=True)

            # load workflow
            if verbose:
                print(f"Loading workflow: {workflow_json_path}", flush=True)
            with open(workflow_json_path, "r", encoding="utf-8") as f:
                workflow = json.loads(f.read())

            # set params
            workflow["6"]["inputs"]["text"] = positive_prompt
            workflow["22"]["inputs"]["denoise"] = float(denoise)
            workflow["29"]["inputs"]["image"] = comfyui_path_image
            workflow["13"]["inputs"]["cfg"] = float(cfg)

            # connect once
            if verbose:
                print(f"Connecting ws://{self.server_address}/ws?clientId={self.client_id}", flush=True)
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))

            saved_files = []

            for i in range(int(n_images)):
                seed = random.randint(1, 1_000_000_000)
                workflow["13"]["inputs"]["noise_seed"] = seed

                if verbose:
                    print(f"\n[{i+1}/{n_images}] seed={seed} denoise={denoise}", flush=True)

                images = self.get_images(ws, workflow, verbose=verbose)

                for node_id in images:
                    for idx, image_data in enumerate(images[node_id]):
                        img = Image.open(io.BytesIO(image_data))
                        out_path = os.path.join(
                            output_dir,
                            f"{image_name}__node{node_id}__seed{seed}__{i}_{idx}.png",
                        )
                        img.save(out_path)
                        saved_files.append(out_path)

                        if verbose:
                            print(f"Saved: {out_path}", flush=True)

            ws.close()
            if verbose:
                print("Done.", flush=True)

            return saved_files

    
    def run_pipeline(
    self,
    input_dir,
    mask_path,  # NEW (chemin vers mask_test.png)
    output_dir,
    workflow_json_path,
    n_images,
    positive_prompt,
    denoise,
    cfg_list=(1.0,),
):
        os.makedirs(output_dir, exist_ok=True)

        for image_name in os.listdir(input_dir):
            if not image_name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            image_path = os.path.join(input_dir, image_name)
            base_name = os.path.splitext(image_name)[0]

            for cfg_value in cfg_list:
                output_dir_image = os.path.join(output_dir, f"output_{base_name}_cfg{cfg_value}")
                os.makedirs(output_dir_image, exist_ok=True)

                print("\n" + "=" * 60)
                print(f"Traitement de: {image_name} | CFG: {cfg_value}")
                print("=" * 60)

                self.run_comfyui_img2img(
                    image_path=image_path,
                    #mask_path=mask_path,  # NEW
                    workflow_json_path=workflow_json_path,
                    output_dir=output_dir_image,
                    image_name=base_name,
                    n_images=n_images,
                    positive_prompt=positive_prompt,
                    denoise=denoise,
                    cfg=cfg_value,
                    verbose=True,
                )


    
