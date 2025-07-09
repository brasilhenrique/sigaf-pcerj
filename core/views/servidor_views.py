# F:\dev\sigaf-novo\core\views\servidor_views.py (COMPLETO E CORRIGIDO - REDIRECIONAMENTO DE FOLHA ÚNICA)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from datetime import date
import calendar 

from core.models import FolhaPonto, DiaPonto, CodigoOcorrencia 
from core.utils import preparar_dados_para_web, registrar_log


@login_required
def dashboard_view(request):
    """
    Dashboard principal para todos os perfis.
    Exibe a folha de ponto pessoal do usuário, a menos que seja Administrador Geral (sem folha).
    Se houver apenas UMA folha de ponto ativa, redireciona diretamente para ela.
    """
    # Redirecionamento para dashboards específicos de gestão (apenas Admin Geral)
    if request.user.perfil == 'Administrador Geral':
        return redirect('core:admin_geral_dashboard')
    
    # Para Servidor, Agente de Pessoal e Delegado, esta view exibirá a folha de ponto pessoal.
    hoje = date.today()
    trimestre_atual = (hoje.month - 1) // 3 + 1
    
    folhas_do_usuario_queryset = FolhaPonto.objects.filter(
        servidor=request.user,
        status__in=['Em Andamento', 'Concluída'] # Considera apenas folhas ativas (não arquivadas)
    ).order_by('-ano', '-trimestre')

    # NOVA LÓGICA: Contar as folhas e redirecionar se houver apenas uma
    num_folhas_ativas = folhas_do_usuario_queryset.count()

    if num_folhas_ativas == 0:
        messages.info(request, "Nenhuma folha de ponto ativa encontrada para você no momento.")
        # Renderiza o template com a mensagem de 'empty'
        context = { 'folhas_com_dados': [] } # Passa uma lista vazia para o template
        return render(request, 'core/dashboard.html', context)
    
    elif num_folhas_ativas == 1:
        # Se houver apenas uma folha, redireciona diretamente para a tela de gerenciamento/visualização
        folha_unica = folhas_do_usuario_queryset.first()
        
        # Redireciona para a tela de gerenciamento se o usuário for Agente
        # ou para a tela de conferência se for Delegado conferindo a própria
        # ou para a tela padrão de dashboard para Servidor.
        if request.user.perfil == 'Agente de Pessoal':
            # Um agente gerencia suas folhas, então redireciona para a tela de gerenciar_ponto
            return redirect('core:gerenciar_ponto', folha_id=folha_unica.id)
        elif request.user.perfil == 'Delegado':
            # Um delegado confere sua própria folha, então redireciona para delegado_minha_folha
            return redirect('core:delegado_minha_folha') # delegado_minha_folha já carrega a folha do request.user
            # Ou poderia ser redirect('core:delegado_ver_folha', folha_id=folha_unica.id) se essa fosse a tela padrão de visualização para delegados
        else: # Servidor
            # Servidor vê sua própria folha no dashboard padrão, então não precisa de redirecionamento extra aqui,
            # apenas continua o fluxo normal da view para renderizar.
            pass # Continua para a lógica abaixo que prepara os dados e renderiza 'core/dashboard.html'
    
    # Lógica para mais de uma folha OU para Servidor com uma única folha (continua o fluxo normal)
    folhas_com_dados = []
    for folha in folhas_do_usuario_queryset: # Usa o queryset já filtrado
        meses_preparados_para_web = preparar_dados_para_web(folha)
        
        for mes_data in meses_preparados_para_web:
            mes_dias = mes_data['dias']
            mes_num = mes_data['mes_num']
            
            pode_assinar_mes = any(
                d.codigo.codigo.lower() == 'livre' and not d.servidor_assinou and not d.delegado_conferiu
                for d in mes_dias
            )
            mes_data['pode_assinar_mes'] = pode_assinar_mes

            totalmente_assinado_no_mes = all(
                (d.servidor_assinou or d.codigo.codigo.lower() != 'livre') and not d.delegado_conferiu
                for d in mes_dias
            )
            mes_data['totalmente_assinado'] = totalmente_assinado_no_mes
            mes_data['totalmente_conferido'] = all(d.delegado_conferiu for d in mes_dias)
        
        folhas_com_dados.append({
            'folha_ponto': folha,
            'meses': meses_preparados_para_web
        })

    context = {
        'folhas_com_dados': folhas_com_dados
    }
    return render(request, 'core/dashboard.html', context)


@require_POST
@login_required
def assinar_dia_view(request):
    dia_id = request.POST.get('dia_id')
    next_url = request.POST.get('next', 'core:dashboard') 
    dia = get_object_or_404(DiaPonto, id=dia_id)

    if dia.folha.servidor != request.user:
        messages.error(request, "Você não tem permissão para assinar este dia.")
        return redirect(next_url)
    
    if dia.codigo.codigo.lower() != 'livre':
        messages.error(request, f"Não é possível assinar o dia {dia.data_dia.strftime('%d/%m')} pois ele está com ocorrência: {dia.codigo.denominacao}.")
        return redirect(next_url)

    if dia.servidor_assinou:
        messages.warning(request, f"O dia {dia.data_dia.strftime('%d/%m')} já está assinado.")
        return redirect(next_url)

    if dia.delegado_conferiu:
        messages.error(request, f"O dia {dia.data_dia.strftime('%d/%m')} já foi conferido e não pode ser alterado.")
        return redirect(next_url)
        
    dia.servidor_assinou = True
    dia.data_assinatura_servidor = date.today()
    dia.save()

    dia.folha.update_status()

    # registrar_log(request, 'ASSINATURA_DIA', {'dia_id': dia.id, 'data': str(dia.data_dia)})
    messages.success(request, f"Dia {dia.data_dia.strftime('%d/%m')} assinado com sucesso!")
    return redirect(next_url)


@require_POST
@login_required
def desfazer_assinatura_view(request):
    dia_id = request.POST.get('dia_id')
    next_url = request.POST.get('next', 'core:dashboard') 
    dia = get_object_or_404(DiaPonto, id=dia_id)

    if dia.folha.servidor != request.user:
        messages.error(request, "Você não tem permissão para alterar esta assinatura.")
        return redirect(next_url)
    
    if dia.delegado_conferiu:
        messages.error(request, "Não é possível desfazer a assinatura de um dia já conferido.")
        return redirect(next_url)
        
    dia.servidor_assinou = False
    dia.data_assinatura_servidor = None
    dia.save()

    dia.folha.update_status()
    
    messages.success(request, f"Assinatura do dia {dia.data_dia.strftime('%d/%m')} desfeita com sucesso.")
    return redirect(next_url)


@require_POST 
@login_required
def assinar_mes_inteiro_view(request, folha_id, mes_num):
    folha = get_object_or_404(FolhaPonto, id=folha_id, servidor=request.user)
    next_url = request.POST.get('next', 'core:dashboard') 
    
    num_dias_no_mes = calendar.monthrange(folha.ano, mes_num)[1]
    
    dias_assinados_count = 0
    for dia_num in range(1, num_dias_no_mes + 1):
        data_dia_completa = date(folha.ano, mes_num, dia_num)
        try:
            dia = DiaPonto.objects.get(folha=folha, data_dia=data_dia_completa)
            if dia.codigo.codigo.lower() == 'livre' and not dia.servidor_assinou and not dia.delegado_conferiu:
                dia.servidor_assinou = True
                dia.data_assinatura_servidor = date.today()
                dia.save()
                dias_assinados_count += 1
        except DiaPonto.DoesNotExist:
            pass
    
    folha.update_status()

    if dias_assinados_count > 0:
        messages.success(request, f"{dias_assinados_count} dia(s) do mês foram assinados com sucesso!")
    else:
        messages.info(request, "Nenhum dia 'Livre' pendente encontrado para assinar neste mês ou todos já foram conferidos.")

    return redirect(next_url)


@require_POST 
@login_required
def desfazer_mes_inteiro_view(request, folha_id, mes_num):
    folha = get_object_or_404(FolhaPonto, id=folha_id, servidor=request.user)
    next_url = request.POST.get('next', 'core:dashboard') 

    dias_desfeitos_count = 0
    for dia in folha.dias.filter(data_dia__month=mes_num, servidor_assinou=True, delegado_conferiu=False):
        dia.servidor_assinou = False
        dia.data_assinatura_servidor = None
        dia.save()
        dias_desfeitos_count += 1
    
    folha.update_status()

    if dias_desfeitos_count > 0:
        messages.success(request, f"Assinatura de {dias_desfeitos_count} dia(s) do mês foram desfeitas.")
    else:
        messages.info(request, "Nenhuma assinatura para desfazer neste mês (dias já conferidos não podem ser desfeitos).")

    return redirect(next_url)