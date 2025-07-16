# ARQUIVO: core/views/agente/dashboard_views.py (COMPLETO E MODIFICADO - USANDO unidades_atuacao)

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from core.models import Usuario, FolhaPonto, Unidade # Importado Unidade para usar em .filter()
import json
from datetime import date 

def agente_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.perfil != 'Agente de Pessoal':
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@agente_required
def agente_dashboard_view(request):
    agente = request.user
    
    # Alterado de unidades_gerenciadas_ids para unidades_atuacao_ids
    unidades_atuacao_ids = list(agente.unidades_atuacao.all().values_list('id', flat=True))

    base_servidores_queryset = Usuario.objects.filter(
        lotacao__id__in=unidades_atuacao_ids, # Alterado aqui
        ativo=True,
    ).exclude(
        perfil='Administrador Geral'
    ).select_related('lotacao').order_by('lotacao__nome_unidade', 'nome')

    servidores_for_template = []
    hoje = date.today()
    trimestre_atual = (hoje.month - 1) // 3 + 1

    for servidor in base_servidores_queryset:
        servidor_dict = {
            'id': servidor.id,
            'nome': servidor.nome,
            'id_funcional': servidor.id_funcional,
            'perfil': servidor.perfil,
            'lotacao': servidor.lotacao,
            'ativo': servidor.ativo,
            # 'id_current_folha' será adicionado apenas se encontrado para o próprio agente
        }
        
        # Popula 'id_current_folha' apenas se for o próprio agente e a folha existir
        if servidor.pk == agente.pk: 
            folha_atual_desse_servidor = FolhaPonto.objects.filter(
                servidor=servidor,
                ano=hoje.year,
                trimestre=trimestre_atual
            ).first()
            if folha_atual_desse_servidor:
                servidor_dict['id_current_folha'] = folha_atual_desse_servidor.id
            # Se não for encontrada, a chave não será adicionada, o que é tratado no template.

        servidores_for_template.append(servidor_dict)

    pendencias = FolhaPonto.objects.filter(
        servidor__in=base_servidores_queryset,
        status='Em Andamento'
    ).distinct().select_related('servidor', 'servidor__lotacao').order_by('servidor__nome', '-ano', '-trimestre')

    folhas_concluidas = FolhaPonto.objects.filter(
        servidor__in=base_servidores_queryset,
        status='Concluída'
    ).distinct().select_related('servidor', 'servidor__lotacao').order_by('servidor__nome', '-ano', '-trimestre')
    
    total_servidores_ativos = base_servidores_queryset.count()

    status_counts = FolhaPonto.objects.filter(
        servidor__lotacao__id__in=unidades_atuacao_ids # Alterado aqui
    ).values('status').annotate(total=Count('status')).order_by('status')

    status_colors = {
        'Em Andamento': '#f39c12',
        'Concluída': '#00a65a',
        'Arquivada': '#6c757d',
    }

    chart_labels = []
    chart_data = []
    chart_background_colors = []
    all_possible_statuses = ['Em Andamento', 'Concluída', 'Arquivada']
    status_map = {item['status']: item['total'] for item in status_counts}

    for status in all_possible_statuses:
        chart_labels.append(status)
        chart_data.append(status_map.get(status, 0))
        chart_background_colors.append(status_colors.get(status, '#cccccc'))

    chart_data_json = json.dumps({
        "labels": chart_labels,
        "data": chart_data,
        "backgroundColor": chart_background_colors
    })

    context = {
        'servidores': servidores_for_template,
        'pendencias': pendencias,
        'folhas_concluidas': folhas_concluidas,
        'total_servidores_ativos': total_servidores_ativos,
        'chart_data_json': chart_data_json,
    }
    return render(request, 'core/agente_dashboard.html', context)