#!/bin/bash

ENV_NAME="venv_thales"
if [ ! -d "$ENV_NAME" ]; then 
    python3 -m venv $ENV_NAME
fi
source $ENV_NAME/bin/activate
pip3 install --upgrade pip
pip install -r requirements.txt
chmod 755 setup.sh #rwx->u and rx->g/o