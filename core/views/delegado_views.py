# F:\dev\sigaf-novo\core\views\delegado_views.py
# (COMPLETO E CORRIGIDO - Corrigido o redirecionamento após conferência da própria folha)

from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from core.models import FolhaPonto, DiaPonto, LogAuditoria
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from datetime import date
import calendar 

from core.models import FolhaPonto, DiaPonto, Usuario, CodigoOcorrencia 
from core.utils import preparar_dados_para_web, registrar_log
from django.db.models import Q 


def delegado_required(view_func):
    """
    Decorator para garantir que o usuário logado tem o perfil de Delegado de Polícia ou
    é um "Servidor-Conferente" (ou seja, possui unidades de atuação atribuídas).
    """
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Permite Delegado de Polícia OU qualquer usuário com unidades_atuacao atribuídas
        # (desde que não seja um Admin Geral ou Agente de Pessoal, que têm dashboards próprios).
        is_delegado_or_servidor_conferente = \
            request.user.perfil == 'Delegado de Polícia' or \
            (request.user.unidades_atuacao.exists() and \
             not request.user.is_agente_pessoal and \
             not request.user.is_administrador_geral) 

        if not is_delegado_or_servidor_conferente:
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@delegado_required
def delegado_dashboard_view(request):
    """
    Dashboard do Delegado/Servidor-Conferente, mostrando folhas que precisam de sua conferência
    nas unidades que ele atua.
    Inclui folhas de Servidores, Agentes de Pessoal e do próprio usuário (se aplicável).
    """
    conferente_logado = request.user
    
    # Lista de IDs das unidades que o usuário logado (Delegado/Servidor-Conferente) atua
    unidades_para_conferencia_ids = list(conferente_logado.unidades_atuacao.all().values_list('id', flat=True))

    # Incluir a própria lotação do usuário logado se ele tiver uma lotação definida
    # e se essa lotação não for já uma unidade de atuação (para evitar duplicidade na filtragem)
    if conferente_logado.lotacao and conferente_logado.lotacao.id not in unidades_para_conferencia_ids:
        unidades_para_conferencia_ids.append(conferente_logado.lotacao.id)
    
    # Garante que não haja IDs duplicados
    unidades_para_conferencia_ids = list(set(unidades_para_conferencia_ids))

    if not unidades_para_conferencia_ids:
        messages.info(request, "Você não tem unidades atribuídas para conferência.")
        return render(request, 'core/delegado_dashboard.html', {'folhas_pendentes': []})

    # Encontra folhas de ponto de servidores lotados nas unidades que o usuário logado atua,
    # que tenham status 'Em Andamento' E dias que ainda não foram conferidos.
    
    base_query = FolhaPonto.objects.filter(
        servidor__lotacao__id__in=unidades_para_conferencia_ids,
        status='Em Andamento', 
        dias__delegado_conferiu=False # Dias que ainda não foram conferidos
    ).filter(
        # Dias que SÃO ou se tornam conferíveis:
        Q(dias__codigo__codigo__iexact='Livre', dias__servidor_assinou=True) | # Se for 'Livre' E assinado
        ~Q(dias__codigo__codigo__iexact='Livre') # OU se NÃO for 'Livre' (ou seja, é bloqueado por outra ocorrência)
    ).distinct()

    # Aplicamos a lógica de exclusão: SOMENTE Administradores Gerais (que não têm folha no sistema)
    folhas_pendentes = base_query.exclude(
        Q(servidor__perfil='Administrador Geral')
    ).select_related('servidor', 'servidor__lotacao').order_by('servidor__nome', '-ano', '-trimestre')

    # =================================================================
    # NOVA LÓGICA DO POWER BUTTON: PROCESSAMENTO PARA O MODAL
    # =================================================================
    total_pendentes = folhas_pendentes.count()
    total_limpas = 0
    total_sujas = 0
    lista_sujas = []

    # Iteramos sobre a queryset que você já montou perfeitamente
    for folha in folhas_pendentes:
        # Pega apenas os dias PENDENTES desta folha que não são Livre, Sábado ou Domingo
        dias_sujos = list(folha.dias.filter(
            delegado_conferiu=False
        ).exclude(
            codigo__isnull=True
        ).exclude(
            codigo__codigo__in=['LIVRE', 'Livre', 'SÁBADO', 'DOMINGO', 'SABADO']
        ).select_related('codigo').order_by('data_dia'))
        
        # Pendura uma propriedade "on-the-fly" na folha para as badges (verde/amarela) aparecerem no HTML
        folha.tem_ocorrencias = len(dias_sujos) > 0 
        
        if not folha.tem_ocorrencias:
            total_limpas += 1
        else:
            total_sujas += 1
            # Chama a função _agrupar_dias_ocorrencia (que adicionamos na etapa anterior)
            agrupamentos = _agrupar_dias_ocorrencia(dias_sujos)
            for texto_grupo in agrupamentos:
                lista_sujas.append(f"{folha.servidor.nome} - {texto_grupo}")
    # =================================================================

    context = {
        'folhas_pendentes': folhas_pendentes,
        'total_pendentes': total_pendentes,
        'total_limpas': total_limpas,
        'total_sujas': total_sujas,
        'lista_sujas': lista_sujas,
    }
    return render(request, 'core/delegado_dashboard.html', context)


@delegado_required
def delegado_ver_folha_view(request, folha_id):
    """
    Exibe uma folha de ponto para o delegado/servidor-conferente conferir.
    Permite que qualquer conferente acesse qualquer folha, uma vez autenticado e autorizado pelo decorator.
    """
    folha = get_object_or_404(FolhaPonto, id=folha_id)
    
    conferente_logado = request.user

    # Permite acesso à folha de qualquer servidor do sistema.
    if not (folha.servidor == conferente_logado or conferente_logado.perfil == 'Delegado de Polícia' or conferente_logado.is_conferente):
        messages.error(request, "Você não tem permissão para visualizar a folha de ponto deste servidor.")
        return redirect('core:delegado_dashboard')

    meses_dados = preparar_dados_para_web(folha)

    # Adiciona informações para botões de conferir/desfazer mês
    for mes_data in meses_dados:
        mes_dias = mes_data['dias']
        
        # Pode conferir se há pelo menos um dia que atenda aos critérios de conferência
        # E que ainda não tenha sido conferido.
        # Condições para ser conferível: (NÃO é Livre) OU (é Livre E assinado).
        mes_data['pode_conferir_mes'] = any(
            not d.delegado_conferiu and 
            (d.codigo.codigo.lower() != 'livre' or d.servidor_assinou)
            for d in mes_dias
        ) and folha.status != 'Arquivada'

        # Pode desfazer conferência se há pelo menos um dia conferido PELO USUÁRIO LOGADO
        # E se a folha não está arquivada
        mes_data['pode_desfazer_conferencia_mes'] = any(
            d.delegado_conferiu and d.delegado == request.user
            for d in mes_dias
        ) and folha.status != 'Arquivada'

    context = {
        'folha': folha,
        'meses': meses_dados,
        'hoje': date.today()
    }
    return render(request, 'core/delegado_conferencia_folha.html', context)

@require_POST
@delegado_required 
def delegado_conferir_dia_view(request, dia_id):
    dia = get_object_or_404(DiaPonto, pk=dia_id)
    folha = dia.folha # Pega a folha associada ao dia
    conferente_logado = request.user

    # Permissão: O usuário logado deve ser um Delegado ou um Servidor-Conferente.
    if not (conferente_logado.perfil == 'Delegado de Polícia' or conferente_logado.is_conferente):
        messages.error(request, "Você não tem permissão para conferir este dia.")
        return redirect('core:delegado_ver_folha', folha_id=folha.id)
  
    # Impede a conferência se a folha estiver arquivada.
    if folha.status == 'Arquivada':
        messages.error(request, "Não é possível conferir dias de uma folha arquivada.")
        return redirect('core:delegado_ver_folha', folha_id=folha.id)
    
    # Por isso (como deve ser):
    if dia.data_dia > date.today():
        messages.error(request, "Não é possível conferir um dia futuro.")
        if folha.servidor == request.user:
            return redirect('core:delegado_minha_folha')
        return redirect('core:delegado_ver_folha', folha_id=folha.id)

    # Impede a conferência se o dia já foi conferido.
    if dia.delegado_conferiu:
        messages.warning(request, "Este dia já foi conferido.")
        if folha.servidor == request.user:
            return redirect('core:delegado_minha_folha')
        return redirect('core:delegado_ver_folha', folha_id=folha.id)

    # Lógica de validação da regra de negócio para a conferência de um dia "Livre"
    if dia.codigo.codigo.lower() == 'livre' and not dia.servidor_assinou:
        messages.error(request, "Não é possível conferir um dia 'Livre' que não foi assinado pelo servidor. Peça ao servidor para assinar primeiro.")
        if folha.servidor == request.user:
            return redirect('core:delegado_minha_folha')
        return redirect('core:delegado_ver_folha', folha_id=folha.id)

    dia.delegado_conferiu = True
    dia.delegado = request.user
    dia.data_conferencia = date.today() 
    dia.save()

    folha.update_status() # Atualiza o status da folha após a conferência do dia

    messages.success(request, f"Dia {dia.data_dia.strftime('%d/%m')} conferido com sucesso.")
    
    # CORREÇÃO AQUI: Se for a própria folha, volta para a Minha Folha
    if folha.servidor == request.user:
        return redirect('core:delegado_minha_folha')
    
    return redirect('core:delegado_ver_folha', folha_id=folha.id)


@require_POST 
@delegado_required 
def delegado_desfazer_conferencia_view(request, dia_id):
    dia = get_object_or_404(DiaPonto, pk=dia_id)
    folha = dia.folha # Pega a folha associada ao dia
    
    # Verifica se o usuário logado (Delegado/Servidor-Conferente) é quem realizou a conferência
    if dia.delegado != request.user:
        messages.error(request, "Você só pode desfazer suas próprias conferências.")
        if folha.servidor == request.user:
            return redirect('core:delegado_minha_folha')
        return redirect('core:delegado_ver_folha', folha_id=folha.id)

    # Verifica se o dia pertence a uma folha ativa (não arquivada)
    if folha.status == 'Arquivada':
        messages.error(request, "Não é possível desfazer conferência em folhas arquivadas.")
        if folha.servidor == request.user:
            return redirect('core:delegado_minha_folha')
        return redirect('core:delegado_ver_folha', folha_id=folha.id)

    dia.delegado_conferiu = False
    dia.delegado = None
    dia.data_conferencia = None
    dia.save()
    
    folha.update_status() # Atualiza o status da folha

    messages.success(request, f"Conferência do dia {dia.data_dia.strftime('%d/%m')} desfeita.")
    
    # CORREÇÃO AQUI: Se for a própria folha, volta para a Minha Folha
    if folha.servidor == request.user:
        return redirect('core:delegado_minha_folha')
        
    return redirect('core:delegado_ver_folha', folha_id=folha.id)

@require_POST 
@delegado_required 
def delegado_conferir_mes_view(request, folha_id, mes_num):
    folha = get_object_or_404(FolhaPonto, id=folha_id)
    conferente_logado = request.user

    # Permite a conferência em lote de qualquer folha, desde que o usuário seja um conferente.
    if not (conferente_logado.perfil == 'Delegado de Polícia' or conferente_logado.is_conferente):
        messages.error(request, "Você não tem permissão para conferir esta folha de ponto em lote.")
        return redirect('core:delegado_dashboard')
        
    # Se a folha estiver arquivada, não permite conferir.
    if folha.status == 'Arquivada':
        messages.error(request, "Esta folha de ponto está arquivada e não pode ser conferida em lote.")
        if folha.servidor == request.user:
            return redirect('core:delegado_minha_folha')
        return redirect('core:delegado_ver_folha', folha_id=folha.id)

    num_dias_no_mes = calendar.monthrange(folha.ano, mes_num)[1]
    dias_conferidos_count = 0

    for dia_num in range(1, num_dias_no_mes + 1):
        data_dia_completa = date(folha.ano, mes_num, dia_num)
        try:
            dia = DiaPonto.objects.get(folha=folha, data_dia=data_dia_completa)
        
            # Confere apenas se o dia NÃO foi conferido ainda E se atende à nova regra de negócio:
            # - É um dia "Livre" E assinado pelo servidor, OU
            # - Não é um dia "Livre" (ou seja, é bloqueado por outra ocorrência)
            if dia.data_dia <= date.today() and not dia.delegado_conferiu and (dia.codigo.codigo.lower() != 'livre' or dia.servidor_assinou):
                dia.delegado_conferiu = True
                dia.delegado = request.user
                dia.data_conferencia = date.today()
                dia.save()
                dias_conferidos_count += 1
        except DiaPonto.DoesNotExist:
            pass 
  
    folha.update_status()

    if dias_conferidos_count > 0:
        messages.success(request, f"{dias_conferidos_count} dia(s) do mês foram conferidos com sucesso.")
    else:
        messages.info(request, "Nenhum dia que atenda aos critérios de conferência (bloqueado ou livre e assinado) foi encontrado para este mês.")

    # CORREÇÃO AQUI: Se for a própria folha, volta para a Minha Folha
    if folha.servidor == request.user:
        return redirect('core:delegado_minha_folha')

    return redirect('core:delegado_ver_folha', folha_id=folha.id)


@require_POST 
@delegado_required 
def desfazer_conferencia_mes_view(request, folha_id, mes_num):
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    # Se a folha estiver arquivada, não permite desfazer conferência.
    if folha.status == 'Arquivada':
        messages.error(request, "Esta folha de ponto está arquivada e a conferência não pode ser desfeita em lote.")
        if folha.servidor == request.user:
            return redirect('core:delegado_minha_folha')
        return redirect('core:delegado_ver_folha', folha_id=folha.id)

    dias_desfeitos_count = 0
    # Percorre os dias do mês na folha que foram conferidos PELO USUÁRIO LOGADO
    for dia in folha.dias.filter(data_dia__month=mes_num, delegado_conferiu=True, delegado=request.user):
        dia.delegado_conferiu = False
        dia.delegado = None
        dia.data_conferencia = None
        dia.save()
        dias_desfeitos_count += 1
    
    folha.update_status()

    if dias_desfeitos_count > 0:
        messages.success(request, f"Conferência de {dias_desfeitos_count} dia(s) do mês foram desfeitas.")
    else:
        messages.info(request, "Nenhuma conferência sua encontrada para desfazer neste mês.")

    # CORREÇÃO AQUI: Se for a própria folha, volta para a Minha Folha
    if folha.servidor == request.user:
        return redirect('core:delegado_minha_folha')

    return redirect('core:delegado_ver_folha', folha_id=folha.id)


@delegado_required 
def delegado_busca_view(request):
    """
    Ferramenta de busca global para Delegados/Servidores-Conferentes.
    Permite buscar a folha de ponto de qualquer servidor (ativo ou inativo) pelo ID Funcional.
    Agora permite acesso irrestrito a todas as folhas do sistema.
    """
    search_query = request.GET.get('q', '').strip()
    servidor_encontrado = None
    folhas_do_servidor = []
    search_performed = False

    conferente_logado = request.user

    if search_query:
        search_performed = True
        try:
            # Busca o usuário pelo ID Funcional
            servidor_encontrado = Usuario.objects.get(id_funcional__iexact=search_query)
            
            # Checa a permissão para visualizar o usuário encontrado:
            # Se o usuário logado é um conferente (Delegado ou Servidor-Conferente),
            # ele tem permissão para visualizar qualquer folha de qualquer servidor.
            # A única restrição é que o próprio Delegado não pode ser um Admin Geral (que não tem folha).
            if not (servidor_encontrado == conferente_logado or \
                    conferente_logado.perfil == 'Delegado de Polícia' or \
                    conferente_logado.is_conferente):
                messages.error(request, f"Você não tem permissão para visualizar a folha de '{servidor_encontrado.nome}'.")
                servidor_encontrado = None # Nula o servidor para não exibir dados
            else:
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

@login_required 
def delegado_minha_folha_view(request):
    """
    Permite ao Delegado/Servidor-Conferente visualizar e assinar sua própria folha de ponto.
    A lógica é muito similar à dashboard do servidor, e pode ter botões de conferência para si mesmo.
    """
    conferente_ou_delegado = request.user
    
    # Busca todas as folhas do próprio usuário (Delegado/Servidor-Conferente)
    folhas_do_usuario = FolhaPonto.objects.filter(
        servidor=conferente_ou_delegado,
        status__in=['Em Andamento', 'Concluída'] 
    ).order_by('-ano', '-trimestre') 

    folhas_com_dados = []
    if not folhas_do_usuario.exists():
        messages.warning(request, "Nenhuma folha de ponto encontrada para o seu perfil no momento.")
    else:
        for folha in folhas_do_usuario:
            meses_preparados_for_web = preparar_dados_para_web(folha)
            
            for mes_data in meses_preparados_for_web:
                mes_dias = mes_data['dias']
                
                # Para o botão 'Assinar Mês Inteiro' (se for um dia 'Livre' e não assinado/conferido)
                mes_data['pode_assinar_mes'] = any(
                    d.codigo.codigo.lower() == 'livre' and not d.servidor_assinou and not d.delegado_conferiu
                    for d in mes_dias
                )

                # Para o botão 'Desfazer Assinatura Mês Inteiro' (se há dias assinados e não conferidos pelo próprio usuário)
                mes_data['pode_desfazer_assinatura_mes'] = any(
                    d.servidor_assinou and not d.delegado_conferiu
                    for d in mes_dias
                )

                # Para o botão 'Conferir Mês Inteiro' (se há dias que atendem a nova lógica de conferência E a folha não está arquivada)
                mes_data['pode_conferir_mes'] = any(
                    not d.delegado_conferiu and (d.codigo.codigo.lower() != 'livre' or d.servidor_assinou)
                    for d in mes_dias
                ) and folha.status != 'Arquivada'

                # Para o botão 'Desfazer Conferência Mês Inteiro' (se há dias conferidos PELO USUÁRIO LOGADO E a folha não está arquivada)
                mes_data['pode_desfazer_conferencia_mes'] = any(d.delegado_conferiu and d.delegado == request.user for d in mes_dias) and folha.status != 'Arquivada'


            folhas_com_dados.append({
                'folha_ponto': folha,
                'meses': meses_preparados_for_web
            })

    context = {
        'folhas_com_dados': folhas_com_dados,
        'hoje': date.today()
    }
    return render(request, 'core/delegado_minha_folha.html', context)

# ==========================================
# FUNÇÕES DE CONFERÊNCIA EM LOTE E RÁPIDA
# ==========================================

def _agrupar_dias_ocorrencia(dias_sujos):
    """
    Função auxiliar que recebe uma lista de DiaPonto (com ocorrências) 
    e retorna strings formatadas agrupando datas consecutivas.
    Ex: "Férias do Exercício (Cód. 012) - 01/03/2026 a 10/03/2026"
    """
    if not dias_sujos:
        return []

    # Ordena os dias cronologicamente para garantir o agrupamento
    dias_ordenados = sorted(dias_sujos, key=lambda d: d.data_dia)
    
    agrupamentos = []
    dia_atual = dias_ordenados[0]
    inicio_grupo = dia_atual.data_dia
    fim_grupo = dia_atual.data_dia
    codigo_atual = dia_atual.codigo

    for i in range(1, len(dias_ordenados)):
        dia_iteracao = dias_ordenados[i]
        
        # Se for o dia imediatamente seguinte E tiver o mesmo código de ocorrência
        if dia_iteracao.data_dia == fim_grupo + timedelta(days=1) and dia_iteracao.codigo == codigo_atual:
            fim_grupo = dia_iteracao.data_dia
        else:
            # Fechou um grupo. Monta a string.
            if inicio_grupo == fim_grupo:
                data_str = inicio_grupo.strftime('%d/%m/%Y')
            else:
                data_str = f"{inicio_grupo.strftime('%d/%m/%Y')} a {fim_grupo.strftime('%d/%m/%Y')}"
            
            nome_codigo = f"{codigo_atual.denominacao} (Cód. {codigo_atual.codigo})" if codigo_atual else "Código Desconhecido"
            agrupamentos.append(f"{nome_codigo} - {data_str}")
            
            # Inicia novo grupo
            inicio_grupo = dia_iteracao.data_dia
            fim_grupo = dia_iteracao.data_dia
            codigo_atual = dia_iteracao.codigo

    # Adiciona o último grupo que ficou pendente no loop
    if inicio_grupo == fim_grupo:
        data_str = inicio_grupo.strftime('%d/%m/%Y')
    else:
        data_str = f"{inicio_grupo.strftime('%d/%m/%Y')} a {fim_grupo.strftime('%d/%m/%Y')}"
        
    nome_codigo = f"{codigo_atual.denominacao} (Cód. {codigo_atual.codigo})" if codigo_atual else "Código Desconhecido"
    agrupamentos.append(f"{nome_codigo} - {data_str}")

    return agrupamentos


@login_required
@require_POST
def conferir_folha_rapido_view(request, folha_id):
    """
    Botão Verde da Tabela: Confere uma única folha por inteiro sem precisar abrir a página de detalhes.
    """
    if not request.user.is_conferente and not request.user.is_delegado and not request.user.is_administrador_geral:
        messages.error(request, 'Acesso negado.')
        return redirect('core:dashboard')

    folha = get_object_or_404(FolhaPonto, id=folha_id)
    
    # Validação de Segurança Básica
    if not request.user.is_administrador_geral and folha.servidor.lotacao not in request.user.unidades_atuacao.all():
        messages.error(request, 'Você não tem permissão para conferir folhas desta unidade.')
        return redirect('core:delegado_dashboard')

    dias_pendentes = folha.dias.filter(delegado_conferiu=False)
    total_dias = dias_pendentes.count()

    if total_dias > 0:
        with transaction.atomic():
            dias_pendentes.update(
                delegado_conferiu=True,
                delegado=request.user,
                data_conferencia=timezone.now()
            )
            folha.update_status()
            
            LogAuditoria.objects.create(
                usuario=request.user,
                acao="Conferência Rápida de Folha",
                detalhes={"folha_id": folha.id, "servidor": folha.servidor.nome, "dias_conferidos": total_dias}
            )
            
        messages.success(request, f'Folha de {folha.servidor.nome} conferida com sucesso ({total_dias} dias).')
    else:
        messages.warning(request, 'Esta folha não possui dias pendentes de conferência.')

    return redirect('core:delegado_dashboard')


@login_required
@require_POST
def conferir_lote_view(request):
    """
    O Fucking Power Button: Confere múltiplas folhas de uma vez baseando-se na escolha do modal.
    """
    if not request.user.is_conferente and not request.user.is_delegado and not request.user.is_administrador_geral:
        messages.error(request, 'Acesso negado.')
        return redirect('core:dashboard')

    acao = request.POST.get('acao')
    
    # Pega as folhas pendentes da lotação do Delegado
    if request.user.is_administrador_geral:
        folhas_pendentes = FolhaPonto.objects.filter(dias__delegado_conferiu=False).distinct()
    else:
        folhas_pendentes = FolhaPonto.objects.filter(
            servidor__lotacao__in=request.user.unidades_atuacao.all(),
            dias__delegado_conferiu=False
        ).distinct()

    folhas_limpas = []
    todas_folhas = []

    for folha in folhas_pendentes:
        todas_folhas.append(folha)
        # Se a folha não tem nenhum dia com código diferente de Livre ou Finais de Semana
        tem_ocorrencia = folha.dias.exclude(codigo__isnull=True).exclude(codigo__codigo__in=['LIVRE', 'Livre', 'SÁBADO', 'DOMINGO', 'SABADO']).exists()
        if not tem_ocorrencia:
            folhas_limpas.append(folha)

    folhas_para_conferir = folhas_limpas if acao == 'somente_limpas' else todas_folhas
    total_conferido = 0
    
    if not folhas_para_conferir:
        messages.warning(request, "Nenhuma folha atende a este critério para conferência.")
        return redirect('core:delegado_dashboard')

    with transaction.atomic():
        for folha in folhas_para_conferir:
            dias_pendentes = folha.dias.filter(delegado_conferiu=False)
            dias_pendentes.update(
                delegado_conferiu=True,
                delegado=request.user,
                data_conferencia=timezone.now()
            )
            folha.update_status()
            total_conferido += 1
            
        LogAuditoria.objects.create(
            usuario=request.user,
            acao="Conferência de Folhas em Lote",
            detalhes={"tipo": acao, "total_folhas_conferidas": total_conferido}
        )

    tipo_str = "limpas" if acao == 'somente_limpas' else "incluindo ocorrências"
    messages.success(request, f'Sucesso! {total_conferido} folhas conferidas em lote ({tipo_str}).')
    return redirect('core:delegado_dashboard')