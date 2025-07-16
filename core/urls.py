# ARQUIVO: core/urls.py (MODIFICADO - Importações explícitas e claras e novas rotas de Conferente)

from django.contrib import admin
# 1. Adicionamos 'include' na linha de importação
from django.urls import path, include

# Importações de Views
from .views import auth_views
from .views import servidor_views
from .views import delegado_views
from .views import admin_views
from .views import delegado_gerenciamento_views

# Importações de Views do Agente
from .views.agente import dashboard_views as agente_dashboard_views
from .views.agente import usuario_views as agente_usuario_views
from .views.agente import folha_ponto_views as agente_folha_ponto_views
from .views.agente import pdf_views as agente_pdf_views

app_name = 'core'

urlpatterns = [
    # Rota raiz do site, aponta para a página de login
    path('', auth_views.login_view, name='login_root'),

    # Autenticação
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('change_password/', auth_views.change_password_view, name='change_password'),

    # Dashboards e Folha de Ponto Pessoal (Redireciona para perfis específicos)
    path('dashboard/', servidor_views.dashboard_view, name='dashboard'), 

    # Ações do Servidor
    path('assinar_dia/', servidor_views.assinar_dia_view, name='assinar_dia'),
    path('desfazer_assinatura/', servidor_views.desfazer_assinatura_view, name='desfazer_assinatura'),
    path('assinar_mes_inteiro/<int:folha_id>/<int:mes_num>/', servidor_views.assinar_mes_inteiro_view, name='assinar_mes_inteiro'),
    path('desfazer_mes_inteiro/<int:folha_id>/<int:mes_num>/', servidor_views.desfazer_mes_inteiro_view, name='desfazer_mes_inteiro'),
    path('gerar_pdf_individual/<int:folha_id>/', agente_pdf_views.gerar_pdf_individual_view, name='gerar_pdf_individual'),

    # Rotas do Administrador Geral
    path('admin_geral/dashboard/', admin_views.admin_geral_dashboard_view, name='admin_geral_dashboard'),
    path('admin_geral/unidades/', admin_views.listar_unidades_view, name='listar_unidades'),
    path('admin_geral/unidades/adicionar/', admin_views.adicionar_unidade_view, name='adicionar_unidade'),
    path('admin_geral/unidades/editar/<int:unidade_id>/', admin_views.editar_unidade_view, name='editar_unidade'),
    path('admin_geral/unidades/inativar/<int:unidade_id>/', admin_views.inativar_unidade_view, name='inativar_unidade'),
    path('admin_geral/unidades/excluir_permanente/<int:unidade_id>/', admin_views.excluir_unidade_permanente_view, name='excluir_unidade_permanente'),
    
    # Gerenciamento de Agentes pelo Admin Geral
    path('admin_geral/agentes/', admin_views.listar_agentes_view, name='listar_agentes'),
    path('admin_geral/agentes/adicionar/', admin_views.adicionar_agente_view, name='adicionar_agente'),
    path('admin_geral/agentes/editar/<int:agente_id>/', admin_views.editar_agente_view, name='editar_agente'),
    path('admin_geral/agentes/inativar/<int:agente_id>/', admin_views.inativar_agente_view, name='inativar_agente'),
    
    # Gerenciamento de Usuários (Servidores comuns) pelo Admin Geral
    path('admin_geral/usuarios/', admin_views.listar_usuarios_view, name='listar_usuarios'),
    path('admin_geral/usuarios/adicionar/', admin_views.adicionar_usuario_admin_view, name='adicionar_usuario_admin'),
    path('admin_geral/usuarios/editar/<int:usuario_id>/', admin_views.editar_usuario_admin_view, name='editar_usuario_admin'),
    path('admin_geral/usuarios/inativar/<int:usuario_id>/', admin_views.inativar_usuario_admin_view, name='inativar_usuario_admin'),
    path('admin_geral/usuarios/historico_folhas/<int:usuario_id>/', agente_folha_ponto_views.agente_historico_folhas_view, name='admin_historico_folhas'),
    path('admin_geral/auditoria/', admin_views.admin_auditoria_view, name='admin_auditoria'),
    path('admin_geral/usuarios/deletar_permanente/<int:usuario_id>/', admin_views.deletar_usuario_permanente_view, name='deletar_usuario_permanente'),
    
    # Gerenciamento de Delegados pelo Admin Geral
    path('admin_geral/delegados/', delegado_gerenciamento_views.listar_delegados_view, name='listar_delegados'),
    path('admin_geral/delegados/adicionar/', delegado_gerenciamento_views.adicionar_delegado_view, name='adicionar_delegado'),
    path('admin_geral/delegados/editar/<int:delegado_id>/', delegado_gerenciamento_views.editar_delegado_view, name='editar_delegado'),
    path('admin_geral/delegados/inativar/<int:delegado_id>/', delegado_gerenciamento_views.inativar_delegado_view, name='inativar_delegado'),

    # Rotas do Agente de Pessoal
    path('agente/dashboard/', agente_dashboard_views.agente_dashboard_view, name='agente_dashboard'),
    path('agente/usuarios/adicionar/', agente_usuario_views.adicionar_usuario_view, name='adicionar_usuario'),
    path('agente/usuarios/editar/<int:usuario_id>/', agente_usuario_views.editar_usuario_view, name='editar_usuario'),
    path('agente/usuarios/inativar/<int:usuario_id>/', agente_usuario_views.inativar_usuario_view, name='inativar_usuario'),
    path('agente/usuarios/transferir/<int:usuario_id>/', agente_usuario_views.transferir_usuario_view, name='transferir_usuario'),
    path('agente/usuarios/inativos/', agente_usuario_views.listar_inativos_view, name='listar_inativos'),
    path('agente/usuarios/reativar/<int:usuario_id>/', agente_usuario_views.reativar_usuario_view, name='reativar_usuario'),
    path('agente/folhas/gerenciar/<int:folha_id>/', agente_folha_ponto_views.gerenciar_ponto_view, name='gerenciar_ponto'),
    path('agente/folhas/salvar_observacoes/<int:folha_id>/', agente_folha_ponto_views.salvar_observacoes_folha_view, name='salvar_observacoes_folha'),
    path('agente/folhas/historico/<int:usuario_id>/', agente_folha_ponto_views.agente_historico_folhas_view, name='agente_historico_folhas'),
    path('agente/folhas/bloquear_dia/', agente_folha_ponto_views.bloquear_dia_view, name='bloquear_dia'),
    path('agente/folhas/bloquear_lote/<int:folha_id>/', agente_folha_ponto_views.bloquear_dias_em_lote_view, name='bloquear_dias_em_lote'),
    path('agente/folhas/criar_manual/', agente_folha_ponto_views.agente_criar_folha_view, name='agente_criar_folha'),
    path('agente/folhas/deletar/<int:folha_id>/', agente_folha_ponto_views.agente_deletar_folha_view, name='agente_deletar_folha'),
    path('agente/folhas/arquivar/<int:folha_id>/', agente_folha_ponto_views.arquivar_folha_view, name='arquivar_folha'),
    path('agente/folhas/desarquivar/<int:folha_id>/', agente_folha_ponto_views.desarquivar_folha_view, name='desarquivar_folha'),
    path('agente/folhas/arquivar_lote/', agente_folha_ponto_views.arquivar_lote_view, name='arquivar_lote'),
    path('agente/pdf/unidade/', agente_pdf_views.gerar_pdf_unidade_view, name='gerar_pdf_unidade'),
    path('agente/folhas/arquivadas/', agente_folha_ponto_views.folhas_arquivadas_view, name='folhas_arquivadas'),

    # Rotas de Gestão de Conferentes pelo Agente de Pessoal
    path('agente/conferentes/', agente_usuario_views.listar_conferentes_view, name='listar_conferentes'), # NOVO
    path('agente/conferentes/atribuir/<int:usuario_id>/', agente_usuario_views.atribuir_conferente_view, name='atribuir_conferente'), # NOVO
    path('agente/conferentes/remover/<int:usuario_id>/', agente_usuario_views.remover_conferente_view, name='remover_conferente'), # NOVO

    # Minha Folha de Ponto (agora sempre aponta para a assinatura, para todos os perfis aptos)
    path('agente/minha_folha/', servidor_views.dashboard_view, name='agente_minha_folha'),
    path('delegado/minha_folha/', delegado_views.delegado_minha_folha_view, name='delegado_minha_folha'), # Já existia, mantido.

    # Rotas do Delegado
    path('delegado/dashboard/', delegado_views.delegado_dashboard_view, name='delegado_dashboard'),
    path('delegado/folhas/ver/<int:folha_id>/', delegado_views.delegado_ver_folha_view, name='delegado_ver_folha'),
    path('delegado/folhas/conferir_dia/<int:dia_id>/', delegado_views.delegado_conferir_dia_view, name='delegado_conferir_dia'),
    path('delegado/folhas/desfazer_conferencia/<int:dia_id>/', delegado_views.delegado_desfazer_conferencia_view, name='delegado_desfazer_conferencia'),
    path('delegado/folhas/conferir_mes/<int:folha_id>/<int:mes_num>/', delegado_views.delegado_conferir_mes_view, name='delegado_conferir_mes'),
    path('delegado/folhas/desfazer_mes/<int:folha_id>/<int:mes_num>/', delegado_views.desfazer_conferencia_mes_view, name='desfazer_conferencia_mes'),
    path('delegado/busca/', delegado_views.delegado_busca_view, name='delegado_busca'),

    # NOVO: Rota para Meu Histórico de Folhas
    path('meu_historico/', servidor_views.meu_historico_folhas_view, name='meu_historico_folhas'), # Nova rota aqui
]