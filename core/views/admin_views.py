# F:\dev\sigaf-novo\core\views\admin_views.py (COMPLETO E MODIFICADO - REMOVENDO agente_historico_folhas_view)

import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from core.models import Usuario, Unidade, LogAuditoria, FolhaPonto
from core.forms import UnidadeForm, AdminAgenteCreationForm, AdminAgenteChangeForm, \
    UsuarioCreationForm, UsuarioChangeForm, AdminProfileForm, \
    AdminUsuarioCreationForm, AdminUsuarioChangeForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import date, timedelta
import json 
from django.db import transaction 
from core.utils import registrar_log

# Decorator para garantir que o usuário é Administrador Geral
def admin_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.perfil != 'Administrador Geral':
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Função de ordenação para as unidades
def custom_sort_key(unidade):
    match = re.match(r'^(\d+)', unidade.nome_unidade)
    if match:
        return (int(match.group(1)), unidade.nome_unidade)
    else:
        return (float('inf'), unidade.nome_unidade)

@admin_required
def admin_geral_dashboard_view(request):
    total_usuarios = Usuario.objects.filter(ativo=True).count()
    total_unidades = Unidade.objects.filter(ativo=True).count()
    total_agentes = Usuario.objects.filter(ativo=True, perfil='Agente de Pessoal').count()
    total_delegados = Usuario.objects.filter(ativo=True, perfil='Delegado de Polícia').count() # Adicionado contagem de delegados

    hoje = date.today()
    sete_dias_atras = hoje - timedelta(days=6)

    logins_recente = LogAuditoria.objects.filter(
        acao='LOGIN_SUCCESS',
        data_hora__date__range=[sete_dias_atras, hoje]
    ).order_by('data_hora__date')

    login_counts_por_dia = {}
    current_date = sete_dias_atras
    while current_date <= hoje:
        login_counts_por_dia[current_date.strftime('%d/%m')] = 0
        current_date += timedelta(days=1)

    for log in logins_recente:
        dia_formatado = log.data_hora.strftime('%d/%m')
        login_counts_por_dia[dia_formatado] += 1

    login_chart_labels = list(login_counts_por_dia.keys())
    login_chart_data = list(login_counts_por_dia.values())
    
    context = {
        'total_usuarios': total_usuarios,
        'total_unidades': total_unidades,
        'total_agentes': total_agentes,
        'total_delegados': total_delegados, # Passando para o contexto
        'total_logs': LogAuditoria.objects.count(),
        'login_chart_labels_json': json.dumps(login_chart_labels),
        'login_chart_data_json': json.dumps(login_chart_data),
    }
    return render(request, 'core/admin_geral_dashboard.html', context)


# --- Views de Unidade ---
@admin_required
def listar_unidades_view(request):
    unidades_ordenadas = sorted(Unidade.objects.all(), key=custom_sort_key)
    return render(request, 'core/admin_listar_unidades.html', {'unidades': unidades_ordenadas})

@admin_required
def adicionar_unidade_view(request):
    if request.method == 'POST':
        form = UnidadeForm(request.POST)
        if form.is_valid():
            nova_unidade = form.save()
            registrar_log(request, 'UNIDADE_CRIADA', { # Adicionado log
                'unidade_id': nova_unidade.id,
                'nome_unidade': nova_unidade.nome_unidade,
                'codigo_ua': nova_unidade.codigo_ua,
            })
            messages.success(request, 'Unidade adicionada com sucesso!')
            return redirect('core:listar_unidades')
        else:
            messages.error(request, 'Erro ao adicionar unidade. Por favor, corrija os erros no formulário.')
    else:
        form = UnidadeForm()
    return render(request, 'core/admin_form_unidade.html', {'form': form, 'titulo': 'Adicionar Nova Unidade'})

@admin_required
def editar_unidade_view(request, unidade_id):
    unidade = get_object_or_404(Unidade, id=unidade_id)
    if request.method == 'POST':
        form = UnidadeForm(request.POST, instance=unidade)
        if form.is_valid():
            mudancas = {k: {'old': str(form.initial.get(k)), 'new': str(form.cleaned_data.get(k))}
                        for k, v in form.cleaned_data.items() if str(form.cleaned_data.get(k)) != str(form.initial.get(k))} # Comparação de strings
            
            form.save()
            if mudancas: # Registrar log apenas se houver mudanças reais
                registrar_log(request, 'UNIDADE_EDITADA', {
                    'unidade_id': unidade.id,
                    'nome_unidade': unidade.nome_unidade,
                    'mudancas': mudancas,
                })
            messages.success(request, 'Unidade atualizada com sucesso!')
            return redirect('core:listar_unidades')
        else:
            messages.error(request, 'Erro ao atualizar unidade. Por favor, corrija os erros no formulário.')
    else:
        form = UnidadeForm(instance=unidade)
    return render(request, 'core/admin_form_unidade.html', {'form': form, 'titulo': f'Editando Unidade: {unidade.nome_unidade}'})

@admin_required
def excluir_unidade_permanente_view(request, unidade_id):
    unidade = get_object_or_404(Unidade, id=unidade_id)
    if request.method == 'POST':
        usuarios_lotados = Usuario.objects.filter(lotacao=unidade)
        if usuarios_lotados.exists():
            messages.error(request, f"Não é possível excluir a unidade '{unidade.nome_unidade}' porque há usuários lotados nela. Por favor, transfira-os primeiro.")
            return redirect('core:listar_unidades')
        
        with transaction.atomic():
            unidade_nome = unidade.nome_unidade
            unidade_id_ = unidade.id
            unidade.delete()
            messages.success(request, f"Unidade '{unidade_nome}' excluída permanentemente.")
            registrar_log(request, 'DELETE_UNIDADE_PERMANENTE', {
                'unidade_nome_deletada': unidade_nome,
                'unidade_id_deletada': unidade_id_
            })
        return redirect('core:listar_unidades')
    return render(request, 'core/admin_excluir_unidade_permanente_confirm.html', {'unidade': unidade})

@admin_required
def inativar_unidade_view(request, unidade_id):
    unidade = get_object_or_404(Unidade, id=unidade_id)
    if request.method == 'POST':
        unidade.ativo = not unidade.ativo
        # Opcional: ajustar status_servidor se for inativado.
        if not unidade.ativo and unidade.status_servidor == 'Ativo':
            unidade.status_servidor = 'Demitido' 
            unidade.data_inativacao = date.today()
        elif unidade.ativo and unidade.status_servidor != 'Ativo':
            unidade.status_servidor = 'Ativo'
            unidade.data_inativacao = None

        unidade.save()
        log_acao = 'UNIDADE_ATIVADA' if unidade.ativo else 'UNIDADE_INATIVADA' # Adicionado log
        registrar_log(request, log_acao, {
            'unidade_id': unidade.id,
            'nome_unidade': unidade.nome_unidade,
            'status_novo': 'Ativo' if unidade.ativo else unidade.status_servidor
        })
        messages.success(request, f"Unidade '{unidade.nome_unidade}' foi {'ativado' if unidade.ativo else 'inativado'} com sucesso.")
        return redirect('core:listar_unidades')
    
    context = {
        'unidade': unidade,
        'acao': 'inativar' if unidade.ativo else 'ativar'
    }
    return render(request, 'core/admin_excluir_unidade_confirm.html', context)


# --- Views de Agente (Gerenciamento de Agentes pelo Admin Geral) ---
@admin_required
def listar_agentes_view(request):
    agentes_ordenados = sorted(Usuario.objects.filter(perfil='Agente de Pessoal'), key=lambda u: u.nome)
    return render(request, 'core/admin_listar_agentes.html', {'agentes': agentes_ordenados})

@admin_required
def adicionar_agente_view(request):
    if request.method == 'POST':
        form = AdminAgenteCreationForm(request.POST)
        if form.is_valid():
            novo_agente = form.save(commit=False) 
            novo_agente.perfil = 'Agente de Pessoal' 
            novo_agente.username = novo_agente.id_funcional 
            novo_agente.set_password(novo_agente.id_funcional) 
            novo_agente.save() 
            form.save_m2m() 
            
            registrar_log(request, 'AGENTE_CRIADO', { 
                'agente_id': novo_agente.id,
                'agente_nome': novo_agente.nome,
                'agente_id_funcional': novo_agente.id_funcional,
                'lotacao': novo_agente.lotacao.nome_unidade if novo_agente.lotacao else 'N/A',
                'unidades_atuacao_ids': list(novo_agente.unidades_atuacao.all().values_list('id', flat=True))
            })
            messages.success(request, 'Agente de Pessoal criado com sucesso!')
            return redirect('core:listar_agentes')
        else:
            print("Erros do formulário:", form.errors)
            messages.error(request, 'Erro ao adicionar agente. Por favor, corrija os erros no formulário.')
            return render(request, 'core/admin_form_agente.html', {
                'form': form,
                'titulo': 'Adicionar Novo Agente'
            })
    else:
        form = AdminAgenteCreationForm()
    
    return render(request, 'core/admin_form_agente.html', {
        'form': form,
        'titulo': 'Adicionar Novo Agente'
    })

@admin_required
def editar_agente_view(request, agente_id):
    agente = get_object_or_404(Usuario, id=agente_id, perfil='Agente de Pessoal')
    if request.method == 'POST':
        form = AdminAgenteChangeForm(request.POST, instance=agente)
        if form.is_valid():
            mudancas_status = {} # Renomeado para maior clareza
            if form.cleaned_data['status_servidor'] != form.initial.get('status_servidor'):
                mudancas_status['status_servidor'] = {
                    'old': form.initial.get('status_servidor'),
                    'new': form.cleaned_data['status_servidor']
                }
            
            # Lógica para inativar/reativar baseado no status_servidor
            if mudancas_status.get('status_servidor'): # Usa o dicionário
                if mudancas_status['status_servidor']['new'] in ['Aposentado', 'Demitido', 'Falecido'] and agente.ativo:
                    agente.ativo = False
                    agente.data_inativacao = date.today()
                    messages.info(request, f"O Agente {agente.nome} foi automaticamente inativado e a data de inativação registrada.")
                elif mudancas_status['status_servidor']['new'] == 'Ativo' and not agente.ativo:
                    agente.ativo = True
                    agente.data_inativacao = None
                    messages.info(request, f"O Agente {agente.nome} foi automaticamente reativado e a data de inativação removida.")

            # Captura unidades de atuação antigas para o log ANTES de salvar o form
            unidades_atuacao_antigas_ids = set(agente.unidades_atuacao.all().values_list('id', flat=True)) 
            
            agente = form.save() # Salva o objeto principal
            form.save_m2m() # Salva as relações ManyToMany (unidades_atuacao)
            
            # Captura unidades de atuação novas para o log DEPOIS de salvar
            unidades_atuacao_novas_ids = set(agente.unidades_atuacao.all().values_list('id', flat=True)) 

            mudancas_unidades_atuacao = {}
            if unidades_atuacao_antigas_ids != unidades_atuacao_novas_ids:
                unidades_adicionadas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_novas_ids - unidades_atuacao_antigas_ids)]
                unidades_removidas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_antigas_ids - unidades_atuacao_novas_ids)]
                mudancas_unidades_atuacao = {
                    'adicionadas': unidades_adicionadas,
                    'removidas': unidades_removidas
                }
            
            if mudancas_status or mudancas_unidades_atuacao: 
                registrar_log(request, 'AGENTE_EDITADO', { # Adicionado log
                    'agente_id': agente.id,
                    'agente_nome': agente.nome,
                    'mudancas_status': mudancas_status, # Mudado nome da chave
                    'mudancas_unidades_atuacao': mudancas_unidades_atuacao
                })

            messages.success(request, 'Agente de Pessoal atualizado com sucesso!')
            return redirect('core:listar_agentes')
        else:
            print("Erros do formulário:", form.errors)
            messages.error(request, 'Erro ao atualizar agente. Por favor, corrija os erros no formulário.')
            return render(request, 'core/admin_form_agente.html', {
                'form': form,
                'titulo': f'Editando Agente: {agente.nome}'
            })
    else:
        form = AdminAgenteChangeForm(instance=agente)
    
    return render(request, 'core/admin_form_agente.html', {
        'form': form,
        'titulo': f'Editando Agente: {agente.nome}'
    })

@admin_required
def inativar_agente_view(request, agente_id):
    agente = get_object_or_404(Usuario, id=agente_id, perfil='Agente de Pessoal')
    if request.method == 'POST':
        agente.ativo = not agente.ativo
        # Opcional: ajustar status_servidor se for inativado.
        if not agente.ativo and agente.status_servidor == 'Ativo':
            agente.status_servidor = 'Demitido' 
            agente.data_inativacao = date.today()
        elif agente.ativo and agente.status_servidor != 'Ativo':
            agente.status_servidor = 'Ativo'
            agente.data_inativacao = None

        agente.save()
        log_acao = 'AGENTE_ATIVADO' if agente.ativo else 'AGENTE_INATIVADO' # Adicionado log
        registrar_log(request, log_acao, {
            'agente_id': agente.id,
            'agente_nome': agente.nome,
            'status_novo': 'Ativo' if agente.ativo else agente.status_servidor
        })
        messages.success(request, f"Agente '{agente.nome}' foi {'ativado' if agente.ativo else 'inativado'} com sucesso.")
        return redirect('core:listar_agentes')
    return render(request, 'core/admin_inativar_agente_confirm.html', {'agente': agente})


# --- Views de Usuário (Gerenciamento de Usuários pelo Admin Geral) ---
@admin_required
def listar_usuarios_view(request):
    search_query = request.GET.get('q', '')
    # Para listar TODOS os usuários ativos (incluindo Admin Geral, Agentes, Delegados, Servidores-Conferentes e Servidores comuns)
    usuarios_queryset = Usuario.objects.filter(ativo=True)

    # --- INÍCIO DA SEÇÃO DE DEPURAÇÃO ---
    print("\n--- DEPURAÇÃO LISTAR USUÁRIOS ADMIN ---")
    print(f"Queryset para listar usuários (raw): {usuarios_queryset}")
    print(f"Usuários encontrados na queryset: {list(usuarios_queryset)}")
    print("--- FIM DA SEÇÃO DE DEPURAÇÃO ---\n")
    # --- FIM DA SEÇÃO DE DEPURAÇÃO ---

    if search_query:
        usuarios_queryset = usuarios_queryset.filter(
            Q(nome__icontains=search_query) |
            Q(id_funcional__icontains=search_query)
        )
    
    # A ordenação e agrupamento por lotação (e 'Não Atribuída') já está configurada
    usuarios = sorted(usuarios_queryset.all(), key=lambda u: (u.lotacao.nome_unidade if u.lotacao else 'Não Atribuída', u.nome))

    usuarios_por_lotacao = {}
    for usuario in usuarios:
        lotacao_nome = usuario.lotacao.nome_unidade if usuario.lotacao else 'Não Atribuída'
        if lotacao_nome not in usuarios_por_lotacao:
            usuarios_por_lotacao[lotacao_nome] = []
        usuarios_por_lotacao[lotacao_nome].append(usuario)

    return render(request, 'core/admin_listar_usuarios.html', {
        'usuarios_por_lotacao': usuarios_por_lotacao,
        'search_query': search_query
    })

@admin_required
def adicionar_usuario_admin_view(request):
    if request.method == 'POST':
        form = AdminUsuarioCreationForm(request.POST) # Não precisa passar `request` para Admin forms
        if form.is_valid():
            novo_usuario = form.save()
            registrar_log(request, 'USER_CREATE_BY_ADMIN', { # Adicionado log
                'novo_usuario_id': novo_usuario.id,
                'novo_usuario_nome': novo_usuario.nome,
                'novo_usuario_id_funcional': novo_usuario.id_funcional,
                'perfil': novo_usuario.perfil,
                'lotacao': novo_usuario.lotacao.nome_unidade if novo_usuario.lotacao else 'N/A',
                'unidades_atuacao_ids': list(novo_usuario.unidades_atuacao.all().values_list('id', flat=True)) # Logando unidades_atuacao
            })
            messages.success(request, 'Usuário criado com sucesso!')
            return redirect('core:listar_usuarios')
        else:
            print("Erros do formulário:", form.errors)
            messages.error(request, 'Erro ao criar usuário. Por favor, corrija os erros no formulário.')
            return render(request, 'core/admin_form_usuario.html', {'form': form, 'titulo': 'Adicionar Novo Usuário'})
    else:
        form = AdminUsuarioCreationForm()
    return render(request, 'core/admin_form_usuario.html', {'form': form, 'titulo': 'Adicionar Novo Usuário'})

@admin_required
def editar_usuario_admin_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == 'POST':
        form = AdminUsuarioChangeForm(request.POST, instance=usuario)
        if form.is_valid():
            mudancas = {k: {'old': str(form.initial.get(k)), 'new': str(form.cleaned_data.get(k))}
                        for k, v in form.cleaned_data.items() if str(form.cleaned_data.get(k)) != str(form.initial.get(k))} # Comparação de strings
            
            # Captura unidades de atuação antigas para o log ANTES de salvar o form
            unidades_atuacao_antigas_ids = set(usuario.unidades_atuacao.all().values_list('id', flat=True)) 

            # Lógica para inativar/reativar baseado no status_servidor (mantida)
            if 'status_servidor' in mudancas:
                if mudancas['status_servidor']['new'] in ['Aposentado', 'Demitido', 'Falecido'] and usuario.ativo:
                    usuario.ativo = False
                    usuario.data_inativacao = date.today()
                    messages.info(request, f"O usuário {usuario.nome} foi automaticamente inativado e a data de inativação registrada.")
                elif mudancas['status_servidor']['new'] == 'Ativo' and not usuario.ativo:
                    usuario.ativo = True
                    usuario.data_inativacao = None
                    messages.info(request, f"O usuário {usuario.nome} foi automaticamente reativado e a data de inativação removida.")
            
            # Garante que `is_staff` seja False para perfis comuns, a menos que explicitamente marcado no Admin Django.
            # Um servidor comum (mesmo que conferente) não deve ter acesso ao admin.
            if usuario.perfil in [cargo[0] for cargo in Usuario.POLICIA_CARGOS]:
                if usuario.is_staff:
                    usuario.is_staff = False
                    usuario.save(update_fields=['is_staff'])

            form.save()
            form.save_m2m() # Salva as relações ManyToMany, como 'unidades_atuacao'
            
            # Captura unidades de atuação novas para o log DEPOIS de salvar
            unidades_atuacao_novas_ids = set(usuario.unidades_atuacao.all().values_list('id', flat=True))

            mudancas_unidades_atuacao = {}
            if unidades_atuacao_antigas_ids != unidades_atuacao_novas_ids:
                unidades_adicionadas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_novas_ids - unidades_atuacao_antigas_ids)]
                unidades_removidas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_antigas_ids - unidades_atuacao_novas_ids)]
                mudancas_unidades_atuacao = {
                    'adicionadas': unidades_adicionadas,
                    'removidas': mudancas_removidas
                }

            if mudancas or mudancas_unidades_atuacao:
                registrar_log(request, 'USER_EDIT_BY_ADMIN', { # Adicionado log
                    'usuario_id': usuario.id,
                    'usuario_nome': usuario.nome,
                    'mudancas': mudancas,
                    'mudancas_unidades_atuacao': mudancas_unidades_atuacao
                })

            messages.success(request, 'Usuário atualizado com sucesso!')
            return redirect('core:listar_usuarios')
        else:
            messages.error(request, 'Erro ao atualizar usuário. Por favor, corrija os erros no formulário.')
        return render(request, 'core/admin_form_usuario.html', {'form': form, 'titulo': f'Editando Usuário: {usuario.nome}', 'usuario_a_editar': usuario})
    else:
        form = AdminUsuarioChangeForm(instance=usuario)
    return render(request, 'core/admin_form_usuario.html', {'form': form, 'titulo': f'Editando Usuário: {usuario.nome}', 'usuario_a_editar': usuario})

@admin_required
def inativar_usuario_admin_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    if usuario.perfil == 'Administrador Geral' and request.user == usuario:
        messages.error(request, "Você não pode inativar a si mesmo por esta interface. Peça a outro administrador ou use o painel Django admin se necessário.")
        return redirect('core:listar_usuarios')

    if request.method == 'POST':
        usuario.ativo = not usuario.ativo
        # Ajusta status_servidor quando o usuário é inativado por esta função
        if not usuario.ativo and usuario.status_servidor == 'Ativo':
            usuario.status_servidor = 'Demitido'
            usuario.data_inativacao = date.today()
        # Ajusta status_servidor quando o usuário é reativado por esta função
        elif usuario.ativo and usuario.status_servidor != 'Ativo':
            usuario.status_servidor = 'Ativo'
            usuario.data_inativacao = None
        
        usuario.save()
        log_acao = 'USUARIO_ATIVADO' if usuario.ativo else 'USUARIO_INATIVADO' # Adicionado log
        registrar_log(request, log_acao, {
            'usuario_id': usuario.id,
            'usuario_nome': usuario.nome,
            'status_novo': 'Ativo' if usuario.ativo else usuario.status_servidor
        })
        messages.success(request, f"Usuário '{usuario.nome}' foi {'ativado' if usuario.ativo else 'inativado'} com sucesso.")
        return redirect('core:listar_usuarios')
    return render(request, 'core/admin_inativar_usuario_confirm.html', {'usuario': usuario})

@admin_required
def deletar_usuario_permanente_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    if usuario.perfil == 'Administrador Geral' and request.user == usuario:
        messages.error(request, "Você não pode deletar a si mesmo por esta interface. Peça a outro administrador ou use o painel Django admin se necessário.")
        return redirect('core:listar_usuarios')

    if request.method == 'POST':
        with transaction.atomic():
            usuario_nome = usuario.nome
            usuario_id_funcional = usuario.id_funcional
            usuario.delete()
            messages.success(request, f"Usuário '{usuario_nome}' (ID: {usuario_id_funcional}) e todos os seus dados foram excluídos permanentemente.")
        registrar_log(request, 'DELETE_USUARIO_PERMANENTE', {
            'usuario_nome_deletado': usuario_nome,
            'usuario_id_deletado': usuario_id_funcional
        })
        return redirect('core:listar_usuarios')
    return render(request, 'core/admin_deletar_usuario_permanente_confirm.html', {'usuario_a_deletar': usuario})

@admin_required
def deletar_folha_permanente_view(request, folha_id):
    folha = get_object_or_404(FolhaPonto, id=folha_id)
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
        return redirect('core:admin_historico_folhas', usuario_id=folha.servidor.id) 
    return render(request, 'core/admin_deletar_folha_permanente_confirm.html', {'folha': folha})


@admin_required
def admin_auditoria_view(request):
    logs_list = LogAuditoria.objects.all()

    # Filtros
    usuario_id = request.GET.get('usuario')
    acao = request.GET.get('acao')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if usuario_id:
        logs_list = logs_list.filter(usuario_id=usuario_id)
    if acao:
        logs_list = logs_list.filter(acao__icontains=acao)
    if data_inicio:
        logs_list = logs_list.filter(data_hora__date__gte=data_inicio)
    if data_fim:
        logs_list = logs_list.filter(data_hora__date__lte=data_fim)

    logs_list = logs_list.order_by('-data_hora')

    # Paginação
    page = request.GET.get('page', 1)
    paginator = Paginator(logs_list, 50) 

    # Mapeamento dos logs para adicionar o atributo 'detalhes_json_str'
    logs_para_template = []
    for log_obj in logs_list:
        if log_obj.detalhes:
            log_obj.detalhes_json_str = json.dumps(log_obj.detalhes, ensure_ascii=False) # Correção: usar log_obj.detalhes_json_str
        else:
            log_obj.detalhes_json_str = "{}"
        logs_para_template.append(log_obj)

    try:
        logs_page_obj = paginator.page(page)
        # Ajuste para garantir que object_list tenha o atributo 'detalhes_json_str'
        # Isso é importante porque o paginator.page(page) retorna um novo queryset slice
        logs_page_obj.object_list = [l for l in logs_para_template if l.pk in [obj.pk for obj in logs_page_obj.object_list]]
        logs = logs_page_obj
    except PageNotAnInteger:
        logs = paginator.page(1)
        logs.object_list = [l for l in logs_para_template if l.pk in [obj.pk for obj in logs.object_list]]
    except EmptyPage:
        logs = paginator.page(paginator.num_pages)
        logs.object_list = [l for l in logs_para_template if l.pk in [obj.pk for obj in logs.object_list]]
    
    # Dados para os filtros do template
    usuarios_para_filtro = Usuario.objects.all().order_by('nome')
    acoes_disponiveis = LogAuditoria.objects.values_list('acao', flat=True).distinct().order_by('acao')

    context = {
        'page_obj': logs,
        'usuarios_para_filtro': usuarios_para_filtro,
        'acoes_disponiveis': acoes_disponiveis,
        'filtro_aplicado': {
            'usuario': int(usuario_id) if usuario_id and usuario_id.isdigit() else '',
            'acao': acao if acao else '',
            'data_inicio': data_inicio if data_inicio else '',
            'data_fim': data_fim if data_fim else '',
        }
    }
    return render(request, 'core/admin_auditoria.html', context)