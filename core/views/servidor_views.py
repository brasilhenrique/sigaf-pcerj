# F:\dev\sigaf-novo\core\views\servidor_views.py (COMPLETO E MODIFICADO para redirecionamento de Servidor-Conferente)

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
    Dashboard principal. Exibe a folha de ponto pessoal para assinatura.
    Redireciona perfis funcionais para seus dashboards, exceto quando acessam explicitamente 'Minha Folha de Ponto'.
    """
    # Redireciona Administrador Geral para seu dashboard
    if request.user.perfil == 'Administrador Geral':
        return redirect('core:admin_geral_dashboard')
    
    # Se o usuário é Agente de Pessoal e NÃO está acessando a URL de 'Minha Folha de Ponto' explicitamente,
    # redireciona para o dashboard do agente. Caso contrário, ele prossegue para ver sua folha.
    if request.user.perfil == 'Agente de Pessoal' and request.resolver_match.url_name != 'agente_minha_folha':
        return redirect('core:agente_dashboard')

    # Redireciona Delegados e Servidores-Conferentes para o dashboard de conferência,
    # A MENOS que estejam acessando explicitamente a sua própria folha de ponto.
    # Lógica para "Servidor-Conferente": é um usuário que NÃO é Admin Geral ou Agente,
    # mas TEM unidades de atuação atribuídas (indicando responsabilidade de conferência)
    # e não é um Delegado (que já é tratado por sua própria propriedade).
    is_servidor_conferente = request.user.unidades_atuacao.exists() and \
                             not request.user.is_agente_pessoal and \
                             not request.user.is_administrador_geral and \
                             not request.user.is_delegado # Garantir que não seja delegado

    if (request.user.perfil == 'Delegado de Polícia' or is_servidor_conferente) and request.resolver_match.url_name != 'delegado_minha_folha':
        return redirect('core:delegado_dashboard') # Redireciona para o dashboard de pendências

    # Se chegou aqui, o usuário é um 'Servidor' (cargo policial sem atribuições extras),
    # ou um Agente de Pessoal/Delegado/Servidor-Conferente acessando **sua própria folha**
    # via o link "Minha Folha de Ponto" (que é a tela padrão do dashboard).

    hoje = date.today()
    trimestre_atual = (hoje.month - 1) // 3 + 1
    
    folhas_do_usuario_queryset = FolhaPonto.objects.filter(
        servidor=request.user,
        status__in=['Em Andamento', 'Concluída']
    ).order_by('-ano', '-trimestre')

    num_folhas_ativas = folhas_do_usuario_queryset.count()

    if num_folhas_ativas == 0:
        messages.info(request, "Nenhuma folha de ponto ativa encontrada para você no momento.")
        context = { 'folhas_com_dados': [] }
        return render(request, 'core/dashboard.html', context)
    
    folhas_com_dados = []
    for folha in folhas_do_usuario_queryset:
        meses_preparados_para_web = preparar_dados_para_web(folha)
        
        for mes_data in meses_preparados_para_web:
            mes_dias = mes_data['dias']
            
            mes_data['pode_assinar_mes'] = any(
                d.codigo.codigo.lower() == 'livre' and not d.servidor_assinou and not d.delegado_conferiu
                for d in mes_dias
            )
            mes_data['totalmente_assinado'] = all(
                (d.servidor_assinou or d.codigo.codigo.lower() != 'livre') and not d.delegado_conferiu
                for d in mes_dias
            )
            # Para a própria folha, a conferência do delegado não é um impedimento total
            # Mas podemos indicar se há dias já conferidos pelo próprio usuário
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

    messages.success(request, f"Dia {dia.data_dia.strftime('%d/%m')} assinado com sucesso.")
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

# NOVO: View para "Meu Histórico de Folhas"
@login_required
def meu_historico_folhas_view(request):
    """
    Exibe todas as folhas de ponto do usuário logado, independentemente do status.
    """
    usuario = request.user
    
    # Exclui o Administrador Geral desta view
    if usuario.perfil == 'Administrador Geral':
        messages.error(request, "Acesso negado. Administradores Gerais não possuem histórico de folhas nesta interface.")
        return redirect('core:admin_geral_dashboard')

    folhas = FolhaPonto.objects.filter(servidor=usuario).order_by('-ano', '-trimestre')

    context = {
        'servidor': usuario,
        'folhas': folhas,
    }
    return render(request, 'core/meu_historico_folhas.html', context)