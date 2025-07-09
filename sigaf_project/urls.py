# Arquivo: sigaf_project/urls.py (VERSÃO NOVA E COMPLETA - CORRIGIDO)

from django.contrib import admin
# 1. Adicionamos 'include' na linha de importação
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # 2. Adicionamos esta nova linha
    # Ela diz: "Para qualquer URL que não seja 'admin/', inclua as URLs de 'core.urls'"
    path('', include('core.urls')),
]