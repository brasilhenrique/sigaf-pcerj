#!/usr/bin/env bash
# exit on error
set -o errexit

# Instala as dependências listadas no requirements.txt
pip install -r requirements.txt

# Executa o comando para coletar todos os arquivos estáticos
python manage.py collectstatic --no-input

# Executa as migrações do banco de dados
python manage.py migrate