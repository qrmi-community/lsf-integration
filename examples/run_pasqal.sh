#!/bin/bash
set -e
source /home/lsfuser/pyenv/bin/activate
exec python3 /home/lsfuser/examples/pasqal.py "$@"
