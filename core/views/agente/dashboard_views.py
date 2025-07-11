# ARQUIVO: core/views/agente/dashboard_views.py
# SIGAF Detection

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from core.models import Usuario, FolhaPonto
import json

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
    unidades_gerenciadas = agente.unidades_gerenciadas.all()
    
    servidores_gerenciados = Usuario.objects.filter(
        lotacao__in=unidades_gerenciadas, 
        ativo=True,
        perfil__in=['Servidor', 'Delegado', 'Agente de Pessoal']
    ).select_related('lotacao').order_by('lotacao__nome_unidade', 'nome')

    pendencias = FolhaPonto.objects.filter(
        servidor__in=servidores_gerenciados,
        status='Em Andamento'
    ).distinct().select_related('servidor').order_by('servidor__nome', '-ano', '-trimestre')

    folhas_concluidas = FolhaPonto.objects.filter(
        servidor__in=servidores_gerenciados,
        status='Concluída'
    ).select_related('servidor').order_by('servidor__nome', '-ano', '-trimestre')
    
    status_counts = FolhaPonto.objects.filter(
        servidor__lotacao__in=unidades_gerenciadas
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
        'servidores': servidores_gerenciados,
        'pendencias': pendencias,
        'folhas_concluidas': folhas_concluidas,
        'total_servidores_ativos': servidores_gerenciados.count(),
        'chart_data_json': chart_data_json,
    }
    return render(request, 'core/agente_dashboard.html', context)