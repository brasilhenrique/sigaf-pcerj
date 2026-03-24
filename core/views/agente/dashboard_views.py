# ARQUIVO: core/views/agente/dashboard_views.py (COMPLETO E MODIFICADO - USANDO unidades_atuacao)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from core.models import Usuario, FolhaPonto, Unidade, Cargo
from core.forms import CargoForm
import json
from datetime import date 
from django.views.decorators.http import require_POST

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
        folha_atual_desse_servidor = FolhaPonto.objects.filter(
            servidor=servidor,
            ano=hoje.year,
            trimestre=trimestre_atual
        ).first()
        
        if folha_atual_desse_servidor:
            servidor.id_current_folha = folha_atual_desse_servidor.id
        else:
            servidor.id_current_folha = None

        servidores_for_template.append(servidor)
 
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

@require_POST
@agente_required
def configurar_unidades_view(request):
    from core.models import FolhaPonto, DiaPonto, CodigoOcorrencia
    
    unidades_gerenciadas = request.user.unidades_atuacao.all()
    unidades_plantao_ids = request.POST.getlist('unidades_plantao')
    unidades_plantao_ids = [int(i) for i in unidades_plantao_ids if i.isdigit()]
    
    try:
        cod_livre = CodigoOcorrencia.objects.get(codigo__iexact='LIVRE')
        cod_sabado = CodigoOcorrencia.objects.get(codigo__iexact='SÁBADO')
        cod_domingo = CodigoOcorrencia.objects.get(codigo__iexact='DOMINGO')
    except CodigoOcorrencia.DoesNotExist:
        messages.error(request, "Erro fatal: Códigos padrão não encontrados no banco.")
        return redirect('core:agente_dashboard')

    folhas_alteradas_count = 0

    for unidade in unidades_gerenciadas:
        novo_status = unidade.id in unidades_plantao_ids
        
        if unidade.regime_plantao != novo_status:
            unidade.regime_plantao = novo_status
            unidade.save(update_fields=['regime_plantao'])
            
            folhas_em_andamento = FolhaPonto.objects.filter(unidade_id_geracao=unidade, status='Em Andamento')
            
            for folha in folhas_em_andamento:
                # LÓGICA DE FOLHA VIRGEM 
                tem_assinatura = folha.dias.filter(servidor_assinou=True).exists()
                tem_conferencia = folha.dias.filter(delegado_conferiu=True).exists()
                # CORREÇÃO AQUI: 'LIVRE' em maiúsculo para bater com o banco de dados
                tem_ocorrencia_diferente = folha.dias.exclude(codigo__codigo__in=['LIVRE', 'SÁBADO', 'DOMINGO']).exists()
                
                # Se a folha for 100% virgem, aplicamos a retroatividade
                if not tem_assinatura and not tem_conferencia and not tem_ocorrencia_diferente:
                    
                    if novo_status: # Virou Plantão (Tudo Livre)
                        folha.dias.filter(codigo__in=[cod_sabado, cod_domingo]).update(codigo=cod_livre)
                        
                    else: # Virou Expediente (Bloqueia Fim de Semana)
                        dias_livres = folha.dias.filter(codigo=cod_livre)
                        for dia in dias_livres:
                            dia_semana = dia.data_dia.weekday()
                            if dia_semana == 5: # Sábado
                                dia.codigo = cod_sabado
                                dia.save(update_fields=['codigo'])
                            elif dia_semana == 6: # Domingo
                                dia.codigo = cod_domingo
                                dia.save(update_fields=['codigo'])
                                
                    folhas_alteradas_count += 1

    messages.success(request, f"Regime atualizado com sucesso! O sistema ajustou automaticamente {folhas_alteradas_count} folha(s) que ainda estavam sem apontamentos.")
    return redirect('core:agente_dashboard')

@login_required
def listar_cargos_view(request):
    if request.user.perfil != 'Administrador Geral':
        messages.error(request, "Acesso negado.")
        return redirect('core:dashboard')
        
    cargos = Cargo.objects.all().order_by('nome')
    return render(request, 'core/admin_geral_cargos.html', {'cargos': cargos})

@login_required
def adicionar_cargo_view(request):
    if request.user.perfil != 'Administrador Geral':
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = CargoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cargo adicionado com sucesso!")
            return redirect('core:admin_geral_cargos')
    else:
        form = CargoForm()
        
    context = {'form': form, 'acao': 'Adicionar'}
    return render(request, 'core/admin_geral_cargo_form.html', context)

@login_required
def editar_cargo_view(request, cargo_id):
    if request.user.perfil != 'Administrador Geral':
        return redirect('core:dashboard')

    cargo = get_object_or_404(Cargo, id=cargo_id)
    
    if request.method == 'POST':
        form = CargoForm(request.POST, instance=cargo)
        if form.is_valid():
            form.save()
            messages.success(request, "Cargo atualizado com sucesso!")
            return redirect('core:admin_geral_cargos')
    else:
        form = CargoForm(instance=cargo)
        
    context = {'form': form, 'acao': 'Editar', 'cargo': cargo}
    return render(request, 'core/admin_geral_cargo_form.html', context)

@require_POST
@login_required
def alternar_status_cargo_view(request, cargo_id):
    if request.user.perfil != 'Administrador Geral':
        return redirect('core:dashboard')

    cargo = get_object_or_404(Cargo, id=cargo_id)
    cargo.ativo = not cargo.ativo
    cargo.save()
    
    status = "ativado" if cargo.ativo else "inativado"
    messages.success(request, f"Cargo '{cargo.nome}' {status} com sucesso!")
    return redirect('core:admin_geral_cargos')