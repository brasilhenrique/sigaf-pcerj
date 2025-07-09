# ARQUIVO: core/views/agente/folha_ponto_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from datetime import date
import calendar 

from core.models import Usuario, FolhaPonto, DiaPonto, CodigoOcorrencia
from core.forms import CriarFolhaManualForm, AplicarOcorrenciaLoteForm 
from core.utils import registrar_log, popular_dias_folha, preparar_dados_para_web
from django.db.models import Q

def agente_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.perfil != 'Agente de Pessoal':
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required 
def gerenciar_ponto_view(request, folha_id):
    folha_ponto = get_object_or_404(FolhaPonto, id=folha_id)
    servidor = folha_ponto.servidor

    # Lógica de permissão
    if request.user.perfil == 'Agente de Pessoal':
        if servidor.lotacao not in request.user.unidades_gerenciadas.all():
            messages.error(request, "Acesso negado. Esta folha não pertence a uma de suas unidades gerenciadas.")
            return redirect('core:agente_dashboard')
    elif request.user.perfil == 'Administrador Geral':
        pass
    else:
        messages.error(request, "Você não tem permissão para gerenciar folhas de ponto.")
        return redirect('core:dashboard')


    if folha_ponto.status == 'Arquivada':
        messages.warning(request, "Esta folha de ponto está arquivada e não pode ser editada.")
        
    if not folha_ponto.dias.exists():
        dias_novos = popular_dias_folha(folha_ponto)
        messages.info(request, f"A folha de ponto de {servidor.nome} foi populada automaticamente.")
        meses_preparados = preparar_dados_para_web(folha_ponto, dias_da_folha=dias_novos)
    else:
        meses_preparados = preparar_dados_para_web(folha_ponto)
    
    codigos_ocorrencia = CodigoOcorrencia.objects.all().order_by('denominacao')
    context = {
        'servidor': servidor, 
        'folha_ponto': folha_ponto,
        'meses': meses_preparados, 
        'ano': folha_ponto.ano,
        'codigos_ocorrencia': codigos_ocorrencia,
        'pode_editar': folha_ponto.status != 'Arquivada' 
    }
    return render(request, 'core/gerenciar_ponto.html', context)


@login_required 
def agente_historico_folhas_view(request, usuario_id):
    usuario_alvo = get_object_or_404(Usuario, id=usuario_id)
    
    # Lógica de permissão
    if request.user.perfil == 'Agente de Pessoal':
        if usuario_alvo.lotacao not in request.user.unidades_gerenciadas.all():
            messages.error(request, "Você não tem permissão para ver o histórico de folhas deste usuário.")
            return redirect('core:agente_dashboard') 
    elif request.user.perfil == 'Administrador Geral':
        pass
    else:
        messages.error(request, "Você não tem permissão para acessar esta página.")
        return redirect('core:dashboard')


    folhas_do_usuario = FolhaPonto.objects.filter(servidor=usuario_alvo).order_by('-ano', '-trimestre') 

    context = {
        'servidor': usuario_alvo, 
        'folhas': folhas_do_usuario, 
    }
    return render(request, 'core/admin_historico_folhas.html', context) 


@agente_required
def folhas_arquivadas_view(request):
    agente = request.user
    unidades_gerenciadas = agente.unidades_gerenciadas.all()
    
    folhas_arquivadas_queryset = FolhaPonto.objects.filter(
        servidor__lotacao__in=unidades_gerenciadas, 
        status='Arquivada'
    ).select_related('servidor', 'servidor__lotacao').order_by('-ano', '-trimestre', 'servidor__nome')

    folhas_por_ano = {}
    for folha in folhas_arquivadas_queryset:
        if folha.ano not in folhas_por_ano:
            folhas_por_ano[folha.ano] = {}
        trimestre_display = folha.get_trimestre_display()
        if trimestre_display not in folhas_por_ano[folha.ano]:
            folhas_por_ano[folha.ano][trimestre_display] = []
        folhas_por_ano[folha.ano][trimestre_display].append(folha)

    context = {'folhas_por_ano': folhas_por_ano}
    return render(request, 'core/folhas_arquivadas.html', context)

@require_POST
@agente_required
def bloquear_dia_view(request):
    dia_id = request.POST.get('dia_id')
    codigo_id = request.POST.get('codigo')
    folha_id = request.POST.get('folha_id') 
    
    dia = get_object_or_404(DiaPonto, id=dia_id)
    codigo = get_object_or_404(CodigoOcorrencia, id=codigo_id)

    if dia.folha.servidor.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, "Você não tem permissão para alterar esta folha de ponto.")
        return redirect('core:agente_dashboard') 
    
    if dia.folha.status == 'Arquivada':
        messages.error(request, "Não é possível alterar dias em uma folha arquivada.")
        return redirect('core:gerenciar_ponto', folha_id=dia.folha.id)

    if codigo.codigo.lower() != 'livre':
        if dia.servidor_assinou or dia.delegado_conferiu:
            dia.servidor_assinou = False
            dia.data_assinatura_servidor = None
            dia.delegado_conferiu = False
            dia.delegado = None
            dia.data_conferencia = None
            messages.info(request, f"Assinatura e/ou conferência do dia {dia.data_dia.strftime('%d/%m/%Y')} foram removidas devido ao bloqueio.")
    
    dia.codigo = codigo
    dia.save()
    
    dia.folha.update_status()

    registrar_log(request, 'BLOQUEIO_DIA', {
        'dia_id': dia.id, 
        'data': str(dia.data_dia), 
        'codigo_novo': codigo.codigo,
        'servidor_id': dia.folha.servidor.id_funcional
    })
    
    messages.success(request, f"Ocorrência do dia {dia.data_dia.strftime('%d/%m/%Y')} alterada para '{codigo.denominacao}'.")
    return redirect('core:gerenciar_ponto', folha_id=folha_id) 
    
@require_POST
@agente_required
def bloquear_dias_em_lote_view(request, folha_id):
    folha = get_object_or_404(FolhaPonto, pk=folha_id)

    if folha.servidor.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, "Você não tem permissão para alterar esta folha de ponto.")
        return redirect('core:agente_dashboard')
    
    if folha.status == 'Arquivada':
        messages.error(request, "Não é possível alterar dias em uma folha arquivada.")
        return redirect('core:gerenciar_ponto', folha_id=folha.id)

    form = AplicarOcorrenciaLoteForm(request.POST)

    if form.is_valid():
        codigo_novo = form.cleaned_data['codigo_lote']
        data_inicio = form.cleaned_data['data_inicio_lote']
        data_fim = form.cleaned_data['data_fim_lote']
        
        dias_afetados_query = DiaPonto.objects.filter(
            folha=folha, 
            data_dia__range=[data_inicio, data_fim]
        )

        dias_removidos_count = 0
        if codigo_novo.codigo.lower() != 'livre':
            dias_com_assinatura_ou_conferencia = dias_afetados_query.filter(
                Q(servidor_assinou=True) | Q(delegado_conferiu=True)
            )

            for dia in dias_com_assinatura_ou_conferencia:
                dia.servidor_assinou = False
                dia.data_assinatura_servidor = None
                dia.delegado_conferiu = False
                dia.delegado = None
                dia.data_conferencia = None
                dia.save() 
                dias_removidos_count += 1
        
        num_dias_alterados = dias_afetados_query.update(codigo=codigo_novo)

        folha.update_status()

        registrar_log(request, 'BLOQUEIO_LOTE', {
            'folha_id': folha.id,
            'servidor_id': folha.servidor.id_funcional,
            'data_inicio': str(data_inicio),
            'data_fim': str(data_fim),
            'codigo_novo': codigo_novo.codigo,
            'dias_alterados': num_dias_alterados,
            'assinaturas_removidas': dias_removidos_count
        })

        if dias_removidos_count > 0:
            messages.warning(request, f"Assinaturas/conferências de {dias_removidos_count} dia(s) foram removidas devido ao bloqueio em lote.")
        messages.success(request, f"{num_dias_alterados} dia(s) alterado(s) para '{codigo_novo.denominacao}' no período selecionado.")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Erro no campo '{form.fields[field].label}': {error}")

    return redirect('core:gerenciar_ponto', folha_id=folha.id)

@agente_required
def agente_criar_folha_view(request):
    hoje = date.today()
    initial_data = {'ano': hoje.year, 'trimestre': (hoje.month - 1) // 3 + 1}
    usuario_id = request.GET.get('usuario_id')
    if usuario_id:
        initial_data['servidor'] = usuario_id 
    
    if request.method == 'POST':
        form = CriarFolhaManualForm(request.POST, user=request.user) 
        if form.is_valid():
            nova_folha = form.save(commit=False)
            nova_folha.unidade_id_geracao = nova_folha.servidor.lotacao 
            nova_folha.save()
            
            popular_dias_folha(nova_folha)
            messages.success(request, f"Folha de ponto para {nova_folha.servidor.nome} ({nova_folha.get_trimestre_display()} de {nova_folha.ano}) criada com sucesso!")
            registrar_log(request, 'CRIAR_FOLHA_MANUAL', {
                'folha_id': nova_folha.id,
                'servidor_id': nova_folha.servidor.id_funcional,
                'trimestre': nova_folha.trimestre,
                'ano': nova_folha.ano
            })
            return redirect('core:agente_historico_folhas', usuario_id=nova_folha.servidor.id)
    else:
        form = CriarFolhaManualForm(user=request.user, initial=initial_data)
    
    context = {'form': form}
    return render(request, 'core/agente_criar_folha.html', context)


@agente_required
def agente_deletar_folha_view(request, folha_id):
    folha = get_object_or_404(FolhaPonto, id=folha_id)
    servidor_id = folha.servidor.id

    if folha.servidor.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, "Você não tem permissão para excluir esta folha de ponto.")
        return redirect('core:agente_dashboard')
    
    if request.method == 'POST':
        folha.delete()
        registrar_log(request, 'DELETAR_FOLHA', {
            'folha_periodo': f"{folha.get_trimestre_display()} de {folha.ano}",
            'servidor_id': folha.servidor.id_funcional
        })
        messages.success(request, "A folha de ponto foi excluída permanentemente.")
        return redirect('core:agente_historico_folhas', usuario_id=servidor_id)

    context = {'folha': folha}
    return render(request, 'core/agente_deletar_folha_confirm.html', context)

@require_POST
@agente_required
def arquivar_folha_view(request, folha_id):
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    if folha.servidor.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, "Você não tem permissão para arquivar esta folha de ponto.")
        return redirect('core:agente_dashboard')

    if folha.status != 'Concluída':
        messages.error(request, f"A folha de ponto de {folha.servidor.nome} não pode ser arquivada, pois o status atual é '{folha.status}'.")
        return redirect(request.META.get('HTTP_REFERER', 'core:agente_dashboard'))

    folha.status = 'Arquivada'
    folha.save()
    registrar_log(request, 'ARQUIVAR_FOLHA', {
        'folha_id': folha.id, 
        'servidor_id': folha.servidor.id_funcional,
        'trimestre': folha.trimestre,
        'ano': folha.ano
    })
    messages.success(request, f"Folha de ponto de {folha.servidor.nome} ({folha.get_trimestre_display()} de {folha.ano}) arquivada com sucesso.")
    return redirect(request.META.get('HTTP_REFERER', 'core:agente_dashboard'))

@require_POST
@agente_required
def desarquivar_folha_view(request, folha_id):
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    if folha.servidor.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, "Você não tem permissão para desarquivar esta folha de ponto.")
        return redirect('core:agente_dashboard')

    folha.status = 'Em Andamento' 
    folha.save()
    folha.update_status() 
    registrar_log(request, 'DESARQUIVAR_FOLHA', {
        'folha_id': folha.id, 
        'servidor_id': folha.servidor.id_funcional,
        'trimestre': folha.trimestre,
        'ano': folha.ano
    })
    messages.success(request, f"Folha de ponto de {folha.servidor.nome} ({folha.get_trimestre_display()} de {folha.ano}) desarquivada com sucesso.")
    return redirect('core:folhas_arquivadas')

@require_POST
@agente_required
def arquivar_lote_view(request):
    agente = request.user
    unidades_gerenciadas = agente.unidades_gerenciadas.all()

    folhas_para_arquivar = FolhaPonto.objects.filter(
        servidor__lotacao__in=unidades_gerenciadas,
        status='Concluída'
    )
    
    count_arquivadas = 0
    for folha in folhas_para_arquivar:
        folha.status = 'Arquivada'
        folha.save()
        registrar_log(request, 'ARQUIVAR_FOLHA_LOTE', {
            'folha_id': folha.id, 
            'servidor_id': folha.servidor.id_funcional,
            'trimestre': folha.trimestre,
            'ano': folha.ano
        })
        count_arquivadas += 1

    if count_arquivadas > 0:
        messages.success(request, f"{count_arquivadas} folha(s) de ponto concluída(s) foram arquivadas com sucesso.")
    else:
        messages.info(request, "Nenhuma folha de ponto concluída para arquivar em lote no momento.")
        
    return redirect('core:agente_dashboard')