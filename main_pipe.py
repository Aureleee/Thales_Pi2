# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    main_pipe.py                                       :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: aurele <aurele@student.42.fr>              +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/01/20 17:50:45 by aurele            #+#    #+#              #
#    Updated: 2026/01/20 20:52:04 by aurele           ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

from utils import ComfyUIClient
import uuid

client_id = str(uuid.uuid4())
server_address = "127.0.0.1:8188" # faire attention sur Runpod address

def main():
    client = ComfyUIClient(
        server_address=server_address,
        client_id=client_id
    )
    client.run_pipeline(
        input_dir="inputs_test",
        mask_path="mask_test.png",
        output_dir="final_outputs",
        workflow_json_path="sdx_turbo_input_images.json",
        n_images=4,
        positive_prompt="forest",
        denoise=0.8,
        cfg_list=[1.0],
    )



if __name__ == "__main__":
    main()
