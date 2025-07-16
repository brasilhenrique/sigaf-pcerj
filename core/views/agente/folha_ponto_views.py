# ARQUIVO: core/views/agente/folha_ponto_views.py (COMPLETO E MODIFICADO)

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
from django.db import transaction


def agente_required(view_func):
    """
    Decorator para garantir que o usuário logado tem o perfil de Agente de Pessoal.
    """
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.perfil != 'Agente de Pessoal':
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@agente_required 
def gerenciar_ponto_view(request, folha_id):
    """
    Permite ao Agente de Pessoal (ou Admin Geral) gerenciar os dias de uma folha de ponto.
    """
    folha_ponto = get_object_or_404(FolhaPonto, id=folha_id)
    servidor = folha_ponto.servidor

    # Lógica de permissão para gerenciar a folha:
    # 1. Se o usuário logado é Administrador Geral, ele pode gerenciar qualquer folha.
    # 2. Se o usuário logado é Agente de Pessoal:
    #    a. Ele pode gerenciar a própria folha.
    #    b. Ele pode gerenciar a folha de um servidor cuja lotação esteja entre suas unidades de atuação.
    if request.user.perfil == 'Administrador Geral':
        pass # Admin Geral tem acesso total
    elif request.user.perfil == 'Agente de Pessoal':
        if not (servidor.pk == request.user.pk or \
                (servidor.lotacao and servidor.lotacao in request.user.unidades_atuacao.all())):
            messages.error(request, "Acesso negado. Esta folha não pertence a uma de suas unidades de atuação ou não é sua própria folha.")
            return redirect('core:agente_dashboard')
    else: # Qualquer outro perfil não tem permissão de gerenciamento
        messages.error(request, "Você não tem permissão para gerenciar folhas de ponto de outros servidores.")
        return redirect('core:dashboard')


    if folha_ponto.status == 'Arquivada':
        messages.warning(request, "Esta folha de ponto está arquivada e não pode ser editada.")
        
    # Garante que os dias sejam populados se não existirem, ou sejam recuperados.
    if not folha_ponto.dias.exists():
        dias_criados = popular_dias_folha(folha_ponto)
        if dias_criados:
            messages.info(request, f"A folha de ponto de {servidor.nome} foi populada automaticamente com {len(dias_criados)} dias.")
        else:
            messages.error(request, f"Erro ao popular dias para a folha de {servidor.nome}. Nenhuma ocorrência padrão (Livre, SÁBADO, DOMINGO) encontrada?")
        
    meses_preparados = preparar_dados_para_web(folha_ponto) # Sempre chama para pegar os dados atualizados


    # Ordena por código para a exibição no dropdown
    codigos_ocorrencia = CodigoOcorrencia.objects.all().order_by('codigo') 
    context = {
        'servidor': servidor, 
        'folha_ponto': folha_ponto,
        'meses': meses_preparados, 
        'ano': folha_ponto.ano,
        'codigos_ocorrencia': codigos_ocorrencia,
        'pode_editar': folha_ponto.status != 'Arquivada' 
    }
    return render(request, 'core/gerenciar_ponto.html', context)


@agente_required 
def agente_minha_folha_view(request):
    """
    View dedicada para "Minha Folha de Ponto" do Agente de Pessoal.
    Redireciona para o dashboard principal onde a própria folha é exibida.
    """
    return redirect('core:dashboard') # Redireciona para a tela de assinatura para a própria folha do agente.

@login_required # Mantém este login_required pois é acessada por Admin Geral também.
def agente_historico_folhas_view(request, usuario_id):
    """
    Exibe todas as folhas de ponto de um usuário específico.
    Acessível por Admin Geral (qualquer usuário) e Agente de Pessoal (usuários em suas unidades de atuação).
    """
    servidor = get_object_or_404(Usuario, id=usuario_id)

    # Lógica de permissão:
    # 1. Se o usuário logado é o próprio servidor, pode ver.
    # 2. Se o usuário logado é Agente de Pessoal e o servidor está em uma de suas unidades de atuação.
    # 3. Se o usuário logado é Administrador Geral.
    # 4. Outros perfis não têm permissão para ver histórico de outros usuários.
    if not (request.user.pk == servidor.pk or \
            (request.user.perfil == 'Agente de Pessoal' and servidor.lotacao and servidor.lotacao in request.user.unidades_atuacao.all()) or \
            request.user.perfil == 'Administrador Geral'):
        messages.error(request, "Você não tem permissão para acessar o histórico de folhas deste servidor.")
        return redirect('core:dashboard') # Redireciona para o dashboard padrão

    # Filtra as folhas de ponto ativas e arquivadas
    folhas = FolhaPonto.objects.filter(servidor=servidor).order_by('-ano', '-trimestre')

    context = {
        'servidor': servidor,
        'folhas': folhas,
    }
    return render(request, 'core/agente_historico_folhas.html', context)


@require_POST
@agente_required
def bloquear_dia_view(request):
    """
    Permite ao Agente de Pessoal (ou Admin Geral) aplicar uma ocorrência a um dia específico da folha.
    """
    dia_id = request.POST.get('dia_id')
    folha_id = request.POST.get('folha_id')
    codigo_id = request.POST.get('codigo')

    dia = get_object_or_404(DiaPonto, id=dia_id)
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    # Permissão para o agente (e admin geral)
    # Se a folha.servidor.lotacao estiver dentro das unidades de atuação do agente
    if not (request.user.perfil == 'Administrador Geral' or 
            (request.user.perfil == 'Agente de Pessoal' and folha.servidor.lotacao and folha.servidor.lotacao in request.user.unidades_atuacao.all())):
        messages.error(request, "Você não tem permissão para alterar este dia de ponto.")
        return redirect('core:gerenciar_ponto', folha_id=folha_id)

    # Se a folha estiver arquivada, não permite edição.
    if folha.status == 'Arquivada':
        messages.error(request, "Esta folha de ponto está arquivada e não pode ser editada.")
        return redirect('core:gerenciar_ponto', folha_id=folha_id)

    novo_codigo = get_object_or_404(CodigoOcorrencia, id=codigo_id)

    # Lógica de registro para auditoria
    old_codigo_denominacao = dia.codigo.denominacao
    old_servidor_assinou = dia.servidor_assinou
    old_delegado_conferiu = dia.delegado_conferiu
    
    dia.codigo = novo_codigo
    # Ao alterar a ocorrência, a assinatura do servidor e a conferência do delegado são removidas.
    dia.servidor_assinou = False
    dia.data_assinatura_servidor = None
    dia.delegado_conferiu = False
    dia.delegado = None
    dia.data_conferencia = None
    dia.save()

    folha.update_status()

    # Registrar log de auditoria
    detalhes_log = {
        'folha_id': folha.id,
        'servidor_id_funcional': folha.servidor.id_funcional,
        'data_dia': str(dia.data_dia),
        'antiga_ocorrencia': old_codigo_denominacao,
        'nova_ocorrencia': novo_codigo.denominacao,
        'assinatura_removida': old_servidor_assinou,
        'conferencia_removida': old_delegado_conferiu,
    }
    registrar_log(request, 'BLOQUEIO_DIA', detalhes_log)

    messages.success(request, f"Ocorrência do dia {dia.data_dia.strftime('%d/%m')} alterada para '{novo_codigo.denominacao}' com sucesso.")
    return redirect('core:gerenciar_ponto', folha_id=folha_id)


@agente_required
@require_POST
def bloquear_dias_em_lote_view(request, folha_id):
    """
    Permite ao Agente de Pessoal (ou Admin Geral) aplicar uma ocorrência em lote a vários dias da folha.
    """
    folha = get_object_or_404(FolhaPonto, id=folha_id)
    
    # Permissão para o agente (e admin geral)
    # Se a folha.servidor.lotacao estiver dentro das unidades de atuação do agente
    if not (request.user.perfil == 'Administrador Geral' or 
            (request.user.perfil == 'Agente de Pessoal' and folha.servidor.lotacao and folha.servidor.lotacao in request.user.unidades_atuacao.all())):
        messages.error(request, "Você não tem permissão para alterar esta folha de ponto em lote.")
        return redirect('core:gerenciar_ponto', folha_id=folha_id)
    
    # Se a folha estiver arquivada, não permite edição.
    if folha.status == 'Arquivada':
        messages.error(request, "Esta folha de ponto está arquivada e não pode ser editada em lote.")
        return redirect('core:gerenciar_ponto', folha_id=folha_id)

    form = AplicarOcorrenciaLoteForm(request.POST)
    if form.is_valid():
        codigo_lote = form.cleaned_data['codigo_lote']
        data_inicio_lote = form.cleaned_data['data_inicio_lote']
        data_fim_lote = form.cleaned_data['data_fim_lote']

        dias_afetados_count = 0
        alteracoes_detalhes = []

        dias_para_alterar = DiaPonto.objects.filter(
            folha=folha,
            data_dia__gte=data_inicio_lote,
            data_dia__lte=data_fim_lote
        ).exclude(codigo=codigo_lote) # Evita alterar dias que já têm o mesmo código

        with transaction.atomic():
            for dia in dias_para_alterar:
                # Armazena o estado antigo para o log
                old_codigo_denominacao = dia.codigo.denominacao
                old_servidor_assinou = dia.servidor_assinou
                old_delegado_conferiu = dia.delegado_conferiu

                dia.codigo = codigo_lote
                dia.servidor_assinou = False
                dia.data_assinatura_servidor = None
                dia.delegado_conferiu = False
                dia.delegado = None
                dia.data_conferencia = None
                dia.save()
                dias_afetados_count += 1
                
                alteracoes_detalhes.append({
                    'data_dia': str(dia.data_dia),
                    'antiga_ocorrencia': old_codigo_denominacao,
                    'nova_ocorrencia': codigo_lote.denominacao,
                    'assinatura_removida': old_servidor_assinou,
                    'conferencia_removida': old_delegado_conferiu,
                })

            folha.update_status()

        if dias_afetados_count > 0:
            messages.success(request, f"{dias_afetados_count} dia(s) atualizado(s) em lote com a ocorrência '{codigo_lote.denominacao}'.")
            registrar_log(request, 'BLOQUEIO_LOTE', {
                'folha_id': folha.id,
                'servidor_id_funcional': folha.servidor.id_funcional,
                'data_inicio_lote': str(data_inicio_lote),
                'data_fim_lote': str(data_fim_lote),
                'nova_ocorrencia_lote': codigo_lote.denominacao,
                'dias_afetados_count': dias_afetados_count,
                'detalhes_dias_alterados': alteracoes_detalhes,
            })
        else:
            messages.info(request, "Nenhum dia foi alterado. Verifique se a ocorrência já está aplicada ou se o período está correto.")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Erro no campo '{field}': {error}")

    return redirect('core:gerenciar_ponto', folha_id=folha_id)


@agente_required
def agente_criar_folha_view(request):
    """
    Permite ao Agente de Pessoal criar uma nova folha de ponto manualmente para um servidor.
    """
    # Pré-selecionar o servidor se um usuario_id for passado na URL (útil ao clicar de um histórico)
    initial_servidor = request.GET.get('usuario_id')
    initial_data = {}
    if initial_servidor:
        try:
            # Garante que o usuário que está sendo preenchido pertença à unidade gerenciada pelo agente
            servidor_obj = Usuario.objects.get(id=initial_servidor, lotacao__in=request.user.unidades_atuacao.all())
            initial_data['servidor'] = servidor_obj
        except Usuario.DoesNotExist:
            messages.warning(request, "Servidor pré-selecionado não encontrado ou não pertence às suas unidades de atuação.")

    if request.method == 'POST':
        form = CriarFolhaManualForm(request.POST, user=request.user)
        if form.is_valid():
            folha = form.save(commit=False)
            folha.unidade_id_geracao = folha.servidor.lotacao # Atribui a unidade de lotação atual do servidor

            try:
                with transaction.atomic():
                    folha.save()
                    popular_dias_folha(folha) # Popula os dias automaticamente
                    messages.success(request, f"Folha de ponto para {folha.servidor.nome} no {folha.trimestre}º trimestre de {folha.ano} criada com sucesso!")
                    
                    # Registrar log
                    registrar_log(request, 'CRIAR_FOLHA_MANUAL', {
                        'servidor_id_funcional': folha.servidor.id_funcional,
                        'trimestre': folha.trimestre,
                        'ano': folha.ano,
                        'unidade_geracao': folha.unidade_id_geracao.nome_unidade,
                        'motivo': 'Criação Manual por Agente'
                    })
                    return redirect('core:gerenciar_ponto', folha_id=folha.id)
            except Exception as e:
                messages.error(request, f"Erro ao criar folha de ponto: {e}")
                
        else:
            messages.error(request, "Erro ao criar folha de ponto. Verifique os dados informados.")
    else:
        form = CriarFolhaManualForm(initial=initial_data, user=request.user)
    
    return render(request, 'core/agente_criar_folha.html', {'form': form})


@agente_required
@require_POST
def agente_deletar_folha_view(request, folha_id):
    """
    Permite ao Agente de Pessoal (ou Admin Geral) excluir permanentemente uma folha de ponto.
    Esta é uma ação irreversível.
    """
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    # Permissão: Somente Agentes de Pessoal que gerenciam a unidade do servidor
    # ou Administradores Gerais
    if not (request.user.perfil == 'Administrador Geral' or 
            (request.user.perfil == 'Agente de Pessoal' and folha.servidor.lotacao and folha.servidor.lotacao in request.user.unidades_atuacao.all())):
        messages.error(request, "Você não tem permissão para realizar esta ação.")
        return redirect('core:agente_historico_folhas', usuario_id=folha.servidor.id)

    # Confirmação de exclusão permanente
    if request.method == 'POST':
        with transaction.atomic():
            servidor_nome = folha.servidor.nome
            periodo = f"{folha.get_trimestre_display()} de {folha.ano}"
            folha_id_log = folha.id # Pega o ID antes de deletar
            
            folha.delete()
            messages.success(request, f"Folha de ponto de '{servidor_nome}' para o período '{periodo}' excluída permanentemente.")
            
            registrar_log(request, 'DELETE_FOLHA_PERMANENTE', {
                'servidor_nome': servidor_nome,
                'folha_periodo': periodo,
                'folha_id': folha_id_log,
                'acao_por': 'Agente (Exclusão Permanente)'
            })
            return redirect('core:agente_historico_folhas', usuario_id=folha.servidor.id)
            
    # Para o GET request (exibir a página de confirmação)
    context = {
        'folha': folha,
    }
    return render(request, 'core/agente_deletar_folha_confirm.html', context)


@agente_required
@require_POST
def arquivar_folha_view(request, folha_id):
    """
    Permite ao Agente de Pessoal (ou Admin Geral) arquivar uma folha de ponto.
    Uma folha arquivada não pode ser editada até ser desarquivada.
    """
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    # Permissão: Somente Agentes de Pessoal que gerenciam a unidade do servidor
    # ou Administradores Gerais
    if not (request.user.perfil == 'Administrador Geral' or 
            (request.user.perfil == 'Agente de Pessoal' and folha.servidor.lotacao and folha.servidor.lotacao in request.user.unidades_atuacao.all())):
        messages.error(request, "Você não tem permissão para arquivar esta folha.")
        next_url = request.POST.get('next', 'core:agente_dashboard')
        return redirect(next_url)

    if folha.status == 'Arquivada':
        messages.info(request, f"A folha de {folha.servidor.nome} - {folha.get_trimestre_display()} de {folha.ano} já está arquivada.")
    elif folha.status != 'Concluída':
        messages.warning(request, f"A folha de {folha.servidor.nome} - {folha.get_trimestre_display()} de {folha.ano} não pode ser arquivada porque não está com status 'Concluída'.")
    else:
        folha.status = 'Arquivada'
        folha.ativa = False # Torna a folha inativa para não aparecer nos dashboards normais
        folha.save()
        messages.success(request, f"Folha de {folha.servidor.nome} - {folha.get_trimestre_display()} de {folha.ano} arquivada com sucesso!")
        registrar_log(request, 'ARQUIVAR_FOLHA', {
            'folha_id': folha.id,
            'servidor_id_funcional': folha.servidor.id_funcional,
            'periodo': f"{folha.get_trimestre_display()} de {folha.ano}"
        })
    
    next_url = request.POST.get('next', 'core:agente_dashboard') # Redireciona para onde veio
    return redirect(next_url)

@agente_required
@require_POST
def desarquivar_folha_view(request, folha_id):
    """
    Permite ao Agente de Pessoal (ou Admin Geral) desarquivar uma folha de ponto.
    """
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    # Permissão: Somente Agentes de Pessoal que gerenciam a unidade do servidor
    # ou Administradores Gerais
    if not (request.user.perfil == 'Administrador Geral' or 
            (request.user.perfil == 'Agente de Pessoal' and folha.servidor.lotacao and folha.servidor.lotacao in request.user.unidades_atuacao.all())):
        messages.error(request, "Você não tem permissão para desarquivar esta folha.")
        return redirect('core:folhas_arquivadas')

    if folha.status != 'Arquivada':
        messages.info(request, f"A folha de {folha.servidor.nome} - {folha.get_trimestre_display()} de {folha.ano} não está arquivada.")
    else:
        # Ao desarquivar, volta para 'Em Andamento' (ou 'Concluída' se todos os dias estiverem ok)
        # O safest é 'Em Andamento' para permitir re-conferência ou ajustes.
        folha.status = 'Em Andamento'
        folha.ativa = True
        folha.save()
        messages.success(request, f"Folha de {folha.servidor.nome} - {folha.get_trimestre_display()} de {folha.ano} desarquivada com sucesso e voltou para 'Em Andamento'!")
        registrar_log(request, 'DESARQUIVAR_FOLHA', {
            'folha_id': folha.id,
            'servidor_id_funcional': folha.servidor.id_funcional,
            'periodo': f"{folha.get_trimestre_display()} de {folha.ano}"
        })
    
    return redirect('core:folhas_arquivadas')


@agente_required
@require_POST
def arquivar_lote_view(request):
    """
    Permite ao Agente de Pessoal arquivar todas as folhas 'Concluídas' nas suas unidades de atuação.
    """
    agente = request.user
    
    # Busca todas as folhas CONCLUÍDAS nas unidades de atuação do agente
    # Exclui folhas de Delegados e Administradores Gerais
    folhas_concluidas = FolhaPonto.objects.filter(
        servidor__lotacao__in=agente.unidades_atuacao.all(),
        status='Concluída'
    ).exclude(
        Q(servidor__perfil='Delegado de Polícia') | Q(servidor__perfil='Administrador Geral')
    ).distinct()

    if not folhas_concluidas.exists():
        messages.info(request, "Nenhuma folha concluída para arquivar em lote nas suas unidades de atuação.")
        return redirect('core:agente_dashboard')

    count_arquivadas = 0
    folhas_arquivadas_detalhes = []

    with transaction.atomic():
        for folha in folhas_concluidas:
            if folha.status == 'Concluída': # Garante que só concluídas sejam arquivadas
                folha.status = 'Arquivada'
                folha.ativa = False
                folha.save()
                count_arquivadas += 1
                folhas_arquivadas_detalhes.append({
                    'folha_id': folha.id,
                    'servidor_id_funcional': folha.servidor.id_funcional,
                    'periodo': f"{folha.get_trimestre_display()} de {folha.ano}"
                })
    
    if count_arquivadas > 0:
        messages.success(request, f"{count_arquivadas} folha(s) concluída(s) arquivada(s) em lote com sucesso!")
        registrar_log(request, 'ARQUIVAR_FOLHA_LOTE', {
            'agente_id_funcional': agente.id_funcional,
            'count_arquivadas': count_arquivadas,
            'folhas_arquivadas': folhas_arquivadas_detalhes,
        })
    else:
        messages.info(request, "Nenhuma folha nova foi arquivada em lote. Verifique se há folhas concluídas disponíveis.")

    return redirect('core:agente_dashboard')


@agente_required
def folhas_arquivadas_view(request):
    """
    Exibe todas as folhas de ponto arquivadas para as unidades de atuação do Agente de Pessoal.
    """
    agente = request.user

    # Filtra as folhas arquivadas dos servidores que estão lotados nas unidades de atuação do agente.
    folhas_arquivadas_queryset = FolhaPonto.objects.filter(
        servidor__lotacao__in=agente.unidades_atuacao.all(), # Filtra pelas unidades de atuação do agente
        status='Arquivada'
    ).select_related('servidor', 'unidade_id_geracao').order_by('-ano', '-trimestre', 'servidor__nome')

    # Agrupa as folhas por ano e trimestre para exibição
    folhas_por_ano = {}
    for folha in folhas_arquivadas_queryset:
        if folha.ano not in folhas_por_ano:
            folhas_por_ano[folha.ano] = {}
        
        trimestre_display = folha.get_trimestre_display()
        if trimestre_display not in folhas_por_ano[folha.ano]:
            folhas_por_ano[folha.ano][trimestre_display] = []
        
        folhas_por_ano[folha.ano][trimestre_display].append(folha)

    # Ordena os anos em ordem decrescente
    folhas_por_ano_ordenado = sorted(folhas_por_ano.items(), key=lambda item: item[0], reverse=True)

    context = {
        'folhas_por_ano_ordenado': folhas_por_ano_ordenado # Passa a lista ordenada para o template
    }
    return render(request, 'core/folhas_arquivadas.html', context)

@require_POST
@agente_required # Ou admin_required, se admin geral também puder salvar
def salvar_observacoes_folha_view(request, folha_id):
    """
    Permite ao Agente de Pessoal (ou Admin Geral) salvar observações em uma folha de ponto.
    """
    folha = get_object_or_404(FolhaPonto, id=folha_id)

    # Permissão:
    # 1. Se o usuário logado é Administrador Geral.
    # 2. Se o usuário logado é Agente de Pessoal e a lotação do servidor da folha está entre as unidades de atuação do agente.
    # 3. Se o usuário logado é o próprio servidor da folha e não é Delegado de Polícia nem Administrador Geral (outros podem ver, mas não editar).
    if not (request.user.perfil == 'Administrador Geral' or
            (request.user.perfil == 'Agente de Pessoal' and folha.servidor.lotacao and folha.servidor.lotacao in request.user.unidades_atuacao.all()) or
            (request.user.pk == folha.servidor.pk and request.user.perfil not in ['Delegado de Polícia', 'Administrador Geral'])
            ):
        messages.error(request, "Você não tem permissão para salvar observações nesta folha.")
        return redirect('core:gerenciar_ponto', folha_id=folha_id)
        
    if folha.status == 'Arquivada':
        messages.error(request, "Esta folha de ponto está arquivada e as observações não podem ser editadas.")
        return redirect('core:gerenciar_ponto', folha_id=folha_id)

    observacoes_novas = request.POST.get('observacoes', '').strip()
    
    # Armazena o valor antigo para o log de auditoria
    observacoes_antigas = folha.observacoes if folha.observacoes else ""

    if observacoes_novas != observacoes_antigas:
        folha.observacoes = observacoes_novas
        folha.save(update_fields=['observacoes'])
        messages.success(request, "Observações salvas com sucesso!")

        # Registrar log de auditoria se houver mudança
        detalhes_log = {
            'folha_id': folha.id,
            'servidor_id_funcional': folha.servidor.id_funcional,
            'periodo': f"{folha.get_trimestre_display()} de {folha.ano}",
            'observacoes_antigas': observacoes_antigas,
            'observacoes_novas': observacoes_novas,
        }
        registrar_log(request, 'SALVAR_OBSERVACOES_FOLHA', detalhes_log)
    else:
        messages.info(request, "Nenhuma alteração nas observações para salvar.")

    return redirect('core:gerenciar_ponto', folha_id=folha_id)