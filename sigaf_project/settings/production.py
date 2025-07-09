# ARQUIVO: sigaf_project/settings/production.py

from .base import *
import os
import dj_database_url # Usado para configurar o DB a partir da URL do Render

# Configurações para o ambiente de PRODUÇÃO
DEBUG = False

# A SECRET_KEY será lida de uma variável de ambiente no servidor do Render
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

# O Render define o hostname automaticamente
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [RENDER_EXTERNAL_HOSTNAME]
else:
    ALLOWED_HOSTS = []

# Configuração do banco de dados PostgreSQL do Render
DATABASES = {
    'default': dj_database_url.config(
        # Render fornece a URL completa do banco de dados em uma variável de ambiente
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600
    )
}

# Configuração para arquivos estáticos em produção
STATIC_ROOT = BASE_DIR / 'staticfiles'