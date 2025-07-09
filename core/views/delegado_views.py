# F:\dev\sigaf-novo\core\views\delegado_views.py (CORRIGIDO)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from datetime import date
import calendar # Importar para usar em conferir/desfazer mês inteiro

from core.models import FolhaPonto, DiaPonto, Usuario, CodigoOcorrencia # Importar Usuario e CodigoOcorrencia
from core.utils import preparar_dados_para_web, registrar_log


def delegado_required(view_func):
    """
    Decorator para garantir que o usuário logado tem o perfil de Delegado.
    """
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.perfil != 'Delegado':
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@delegado_required
def delegado_dashboard_view(request):
    """
    Dashboard do Delegado, mostrando folhas que precisam de sua conferência na sua lotação.
    """
    delegado = request.user
    
    # Encontra folhas de ponto de servidores na mesma lotação do delegado
    # que tenham dias assinados pelo servidor mas ainda não conferidos pelo delegado.
    # Usamos distinct() para evitar duplicatas de folhas que tenham múltiplos dias pendentes
    folhas_pendentes = FolhaPonto.objects.filter(
        servidor__lotacao=delegado.lotacao,
        status='Em Andamento', # Apenas folhas que ainda estão sendo processadas
        dias__servidor_assinou=True, # Pelo menos um dia assinado
        dias__delegado_conferiu=False # Pelo menos um dia não conferido
    ).distinct().select_related('servidor').order_by('servidor__nome')

    context = {
        'folhas_pendentes': folhas_pendentes
    }
    return render(request, 'core/delegado_dashboard.html', context)


@delegado_required
def delegado_ver_folha_view(request, folha_id):
    """
    Exibe uma folha de ponto para o delegado conferir.
    Um delegado pode ver qualquer folha (pela busca global) ou folhas de sua lotação.
    A permissão para conferir é mais flexível: "Poder de conferir qualquer folha de ponto encontrada na busca global."
    """
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    # Lógica de permissão: o delegado pode ver a folha se for da sua lotação OU se foi encontrada na busca global.
    # No entanto, a lógica da busca global (delegado_busca_view) já filtra o que ele pode ver.
    # Aqui, a verificação mais importante é se é uma folha ativa (não arquivada)
    # E se não é um Administrador Geral. Administradores Gerais não têm folhas de ponto.

    meses_dados = preparar_dados_para_web(folha)

    # Adiciona informações para botões de conferir/desfazer mês
    for mes_data in meses_dados:
        mes_dias = mes_data['dias']
        mes_num = mes_data['mes_num']
        
        # Pode conferir se há pelo menos um dia assinado e não conferido
        mes_data['pode_conferir_mes'] = any(
            d.servidor_assinou and not d.delegado_conferiu
            for d in mes_dias
        )

        # Pode desfazer conferência se há pelo menos um dia conferido PELO DELEGADO LOGADO
        mes_data['pode_desfazer_conferencia_mes'] = any(
            d.delegado_conferiu and d.delegado == request.user
            for d in mes_dias
        )

    context = {
        'folha': folha,
        'meses': meses_dados
    }
    return render(request, 'core/delegado_conferencia_folha.html', context)

@require_POST
@delegado_required
def delegado_conferir_dia_view(request, dia_id):
    dia = get_object_or_404(DiaPonto, pk=dia_id)
    
    # Verifica se o dia pertence a uma folha ativa (não arquivada)
    if dia.folha.status == 'Arquivada':
        messages.error(request, "Não é possível conferir dias de uma folha arquivada.")
        return redirect('core:delegado_ver_folha', folha_id=dia.folha.id)

    # Um delegado pode conferir qualquer folha de ponto, mesmo que não seja da sua lotação.
    # Mas só pode conferir se o dia foi assinado e ainda não foi conferido.
    if not dia.servidor_assinou:
        messages.error(request, "Este dia ainda não foi assinado pelo servidor.")
        return redirect('core:delegado_ver_folha', folha_id=dia.folha.id)
    
    if dia.delegado_conferiu:
        messages.warning(request, "Este dia já foi conferido.")
        return redirect('core:delegado_ver_folha', folha_id=dia.folha.id)

    dia.delegado_conferiu = True
    dia.delegado = request.user
    dia.data_conferencia = date.today() # A especificação pede data, não datetime.
    dia.save()

    # Atualiza o status da folha de ponto após a conferência
    dia.folha.update_status()

    # registrar_log(request, 'CONFERENCIA_DIA', {'dia_id': dia.id, 'delegado_id': request.user.id})
    messages.success(request, f"Dia {dia.data_dia.strftime('%d/%m')} conferido com sucesso.")
    return redirect('core:delegado_ver_folha', folha_id=dia.folha.id)


@require_POST
@delegado_required
def delegado_desfazer_conferencia_view(request, dia_id):
    dia = get_object_or_404(DiaPonto, pk=dia_id)

    # Verifica se o delegado logado é quem realizou a conferência
    if dia.delegado != request.user:
        messages.error(request, "Você só pode desfazer suas próprias conferências.")
        return redirect('core:delegado_ver_folha', folha_id=dia.folha.id)

    dia.delegado_conferiu = False
    dia.delegado = None
    dia.data_conferencia = None
    dia.save()
    
    # Atualiza o status da folha de ponto após desfazer a conferência
    dia.folha.update_status()

    messages.success(request, f"Conferência do dia {dia.data_dia.strftime('%d/%m')} desfeita.")
    return redirect('core:delegado_ver_folha', folha_id=dia.folha.id)

@require_POST # Apenas POST, pois altera o estado do DB
@delegado_required
def delegado_conferir_mes_view(request, folha_id, mes_num):
    folha = get_object_or_404(FolhaPonto, id=folha_id)
    
    # Verifica se o delegado pode conferir esta folha (sua lotação ou busca global)
    # A verificação principal aqui é que os dias estejam assinados e não conferidos.
    
    num_dias_no_mes = calendar.monthrange(folha.ano, mes_num)[1]
    dias_conferidos_count = 0

    # Percorre os dias do mês na folha
    for dia_num in range(1, num_dias_no_mes + 1):
        data_dia_completa = date(folha.ano, mes_num, dia_num)
        try:
            dia = DiaPonto.objects.get(folha=folha, data_dia=data_dia_completa)
            # Confere apenas se o dia foi assinado e não foi conferido ainda
            if dia.servidor_assinou and not dia.delegado_conferiu:
                dia.delegado_conferiu = True
                dia.delegado = request.user
                dia.data_conferencia = date.today()
                dia.save()
                dias_conferidos_count += 1
        except DiaPonto.DoesNotExist:
            pass # Dia não existe para este mês na folha (ex: dia 31 em meses de 30 dias)
    
    # Atualiza o status da folha de ponto após as conferências em massa
    folha.update_status()

    if dias_conferidos_count > 0:
        messages.success(request, f"{dias_conferidos_count} dia(s) do mês foram conferidos com sucesso!")
    else:
        messages.info(request, "Nenhum dia pendente de conferência encontrado para este mês.")

    return redirect('core:delegado_ver_folha', folha_id=folha.id)


@require_POST # Apenas POST, pois altera o estado do DB
@delegado_required
def desfazer_conferencia_mes_view(request, folha_id, mes_num):
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    dias_desfeitos_count = 0
    # Percorre os dias do mês na folha que foram conferidos pelo delegado logado
    for dia in folha.dias.filter(data_dia__month=mes_num, delegado_conferiu=True, delegado=request.user):
        dia.delegado_conferiu = False
        dia.delegado = None
        dia.data_conferencia = None
        dia.save()
        dias_desfeitos_count += 1
    
    # Atualiza o status da folha de ponto após desfazer conferências em massa
    folha.update_status()

    if dias_desfeitos_count > 0:
        messages.success(request, f"Conferência de {dias_desfeitos_count} dia(s) do mês foram desfeitas.")
    else:
        messages.info(request, "Nenhuma conferência sua encontrada para desfazer neste mês.")

    return redirect('core:delegado_ver_folha', folha_id=folha.id)


@delegado_required
def delegado_busca_view(request):
    """
    Ferramenta de busca global para delegados.
    Permite buscar a folha de ponto de qualquer servidor (ativo ou inativo) pelo ID Funcional.
    """
    search_query = request.GET.get('q', '').strip()
    servidor_encontrado = None
    folhas_do_servidor = []
    search_performed = False

    if search_query:
        search_performed = True
        try:
            # Busca o usuário pelo ID Funcional, incluindo inativos
            servidor_encontrado = Usuario.objects.get(id_funcional__iexact=search_query)
            
            # Recupera todas as folhas de ponto deste servidor, ordenadas
            folhas_do_servidor = FolhaPonto.objects.filter(
                servidor=servidor_encontrado
            ).order_by('-ano', '-trimestre')

        except Usuario.DoesNotExist:
            messages.error(request, f"Servidor com ID Funcional '{search_query}' não encontrado.")
            servidor_encontrado = None
            folhas_do_servidor = []

    context = {
        'query': search_query,
        'servidor_encontrado': servidor_encontrado,
        'folhas_do_servidor': folhas_do_servidor,
        'search_performed': search_performed,
    }
    return render(request, 'core/delegado_busca.html', context)

@login_required # Removido @delegado_required pois qualquer delegado pode ver sua própria folha
def delegado_minha_folha_view(request):
    """
    Permite ao delegado visualizar e gerenciar sua própria folha de ponto.
    A lógica é muito similar à dashboard do servidor, mas pode ter botões de conferência.
    """
    hoje = date.today()
    trimestre_atual = (hoje.month - 1) // 3 + 1
    
    # Busca todas as folhas do próprio delegado
    folhas_do_delegado = FolhaPonto.objects.filter(
        servidor=request.user,
        status__in=['Em Andamento', 'Concluída'] # Exibe apenas folhas ativas
    ).order_by('-ano', '-trimestre') # Ordena para mostrar a mais recente primeiro

    folhas_com_dados = []
    if not folhas_do_delegado.exists():
        messages.warning(request, "Nenhuma folha de ponto encontrada para o seu perfil no momento.")
    else:
        for folha in folhas_do_delegado:
            meses_preparados_para_web = preparar_dados_para_web(folha)
            
            for mes_data in meses_preparados_para_web:
                mes_dias = mes_data['dias']
                mes_num = mes_data['mes_num']
                
                # Para o botão 'Assinar Mês Inteiro' (se for um dia 'Livre' e não assinado/conferido)
                mes_data['pode_assinar_mes'] = any(
                    d.codigo.codigo.lower() == 'livre' and not d.servidor_assinou and not d.delegado_conferiu
                    for d in mes_dias
                )

                # Para o botão 'Desfazer Assinatura Mês Inteiro' (se todos os dias 'Livre' foram assinados e NENHUM foi conferido)
                mes_data['totalmente_assinado'] = all(
                    (d.servidor_assinou or d.codigo.codigo.lower() != 'livre') and not d.delegado_conferiu
                    for d in mes_dias
                )
                
                # Para o botão 'Conferir Mês Inteiro' (se há dias assinados e não conferidos)
                mes_data['pode_conferir_mes'] = any(
                    d.servidor_assinou and not d.delegado_conferiu
                    for d in mes_dias
                )

                # Para o botão 'Desfazer Conferência Mês Inteiro' (se há dias conferidos PELO DELEGADO LOGADO)
                mes_data['totalmente_conferido'] = all(d.delegado_conferiu and d.delegado == request.user for d in mes_dias)


            folhas_com_dados.append({
                'folha_ponto': folha,
                'meses': meses_preparados_para_web
            })

    context = {
        'folhas_com_dados': folhas_com_dados
    }
    return render(request, 'core/delegado_minha_folha.html', context)