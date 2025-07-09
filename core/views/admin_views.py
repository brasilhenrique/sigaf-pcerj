# F:\dev\sigaf-novo\core\views\admin_views.py (VERSÃO ESTÁVEL - SEM DEBUG DE LOGS)

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
import json # Mantido porque é usado para o gráfico do dashboard
from django.db import transaction # Mantido porque é usado para exclusões atômicas

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

    # Lógica para o gráfico de logins na última semana
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
        'total_logs': LogAuditoria.objects.count(),
        'login_chart_labels_json': json.dumps(login_chart_labels),
        'login_chart_data_json': json.dumps(login_chart_data),
    }
    return render(request, 'core/admin_geral_dashboard.html', context)


# --- Views de Unidade ---
@admin_required
def listar_unidades_view(request):
    return render(request, 'core/admin_listar_unidades.html', {'unidades': Unidade.objects.all().order_by('nome_unidade')})

@admin_required
def adicionar_unidade_view(request):
    if request.method == 'POST':
        form = UnidadeForm(request.POST)
        if form.is_valid():
            form.save()
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
            form.save()
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
            unidade.delete()
            messages.success(request, f"Unidade '{unidade.nome_unidade}' excluída permanentemente.")
            from core.utils import registrar_log
            registrar_log(request, 'DELETE_UNIDADE_PERMANENTE', {
                'unidade_nome': unidade.nome_unidade,
                'unidade_id': unidade.id
            })
        return redirect('core:listar_unidades')
    return render(request, 'core/admin_excluir_unidade_permanente_confirm.html', {'unidade': unidade})

@admin_required
def inativar_unidade_view(request, unidade_id):
    unidade = get_object_or_404(Unidade, id=unidade_id)
    if request.method == 'POST':
        unidade.ativo = not unidade.ativo
        unidade.save()
        status_mensagem = "ativada" if unidade.ativo else "inativada"
        messages.success(request, f"Unidade '{unidade.nome_unidade}' foi {status_mensagem} com sucesso.")
        from core.utils import registrar_log
        registrar_log(request, f'UNIDADE_{status_mensagem.upper()}', {
            'unidade_nome': unidade.nome_unidade,
            'unidade_id': unidade.id
        })
        return redirect('core:listar_unidades')
    
    context = {
        'unidade': unidade,
        'acao': 'inativar' if unidade.ativo else 'ativar'
    }
    return render(request, 'core/admin_excluir_unidade_confirm.html', context)


# --- Views de Agente ---
@admin_required
def listar_agentes_view(request):
    return render(request, 'core/admin_listar_agentes.html', {'agentes': Usuario.objects.filter(perfil='Agente de Pessoal').order_by('nome')})

@admin_required
def adicionar_agente_view(request):
    if request.method == 'POST':
        form = AdminAgenteCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Agente de Pessoal criado com sucesso!')
            return redirect('core:listar_agentes')
        else:
            messages.error(request, 'Erro ao adicionar agente. Por favor, corrija os erros no formulário.')
            form.fields['unidades_gerenciadas'].queryset = Unidade.objects.filter(ativo=True)
            unidades_ordenadas = sorted(list(form.fields['unidades_gerenciadas'].queryset), key=custom_sort_key)
            return render(request, 'core/admin_form_agente.html', {
                'form': form,
                'unidades_ordenadas': unidades_ordenadas,
                'titulo': 'Adicionar Novo Agente'
            })
    else:
        form = AdminAgenteCreationForm()
    
    form.fields['unidades_gerenciadas'].queryset = Unidade.objects.filter(ativo=True)
    unidades_ordenadas = sorted(list(form.fields['unidades_gerenciadas'].queryset), key=custom_sort_key)
    
    return render(request, 'core/admin_form_agente.html', {
        'form': form,
        'unidades_ordenadas': unidades_ordenadas,
        'titulo': 'Adicionar Novo Agente'
    })

@admin_required
def editar_agente_view(request, agente_id):
    agente = get_object_or_404(Usuario, id=agente_id, perfil='Agente de Pessoal')
    if request.method == 'POST':
        form = AdminAgenteChangeForm(request.POST, instance=agente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Agente de Pessoal atualizado com sucesso!')
            return redirect('core:listar_agentes')
        else:
            messages.error(request, 'Erro ao atualizar agente. Por favor, corrija os erros no formulário.')
            form.fields['unidades_gerenciadas'].queryset = Unidade.objects.filter(ativo=True)
            unidades_ordenadas = sorted(list(form.fields['unidades_gerenciadas'].queryset), key=custom_sort_key)
            return render(request, 'core/admin_form_agente.html', {
                'form': form,
                'unidades_ordenadas': unidades_ordenadas,
                'titulo': f'Editando Agente: {agente.nome}'
            })
    else:
        form = AdminAgenteChangeForm(instance=agente)
    
    form.fields['unidades_gerenciadas'].queryset = Unidade.objects.filter(ativo=True)
    unidades_ordenadas = sorted(list(form.fields['unidades_gerenciadas'].queryset), key=custom_sort_key)

    return render(request, 'core/admin_form_agente.html', {
        'form': form,
        'unidades_ordenadas': unidades_ordenadas,
        'titulo': f'Editando Agente: {agente.nome}'
    })

@admin_required
def inativar_agente_view(request, agente_id):
    agente = get_object_or_404(Usuario, id=agente_id, perfil='Agente de Pessoal')
    if request.method == 'POST':
        agente.ativo = not agente.ativo
        agente.save()
        messages.success(request, f"Agente '{agente.nome}' foi {'ativado' if agente.ativo else 'inativado'} com sucesso.")
        from core.utils import registrar_log
        registrar_log(request, f'AGENTE_{"ATIVADO" if agente.ativo else "INATIVADO"}', {
            'agente_nome': agente.nome,
            'agente_id': agente.id_funcional
        })
        return redirect('core:listar_agentes')
    return render(request, 'core/admin_inativar_agente_confirm.html', {'agente': agente})


# --- Views de Usuário (pelo Admin) ---
@admin_required
def listar_usuarios_view(request):
    search_query = request.GET.get('q', '')
    if search_query:
        usuarios = Usuario.objects.filter(
            Q(nome__icontains=search_query) |
            Q(id_funcional__icontains=search_query)
        ).order_by('nome')
    else:
        usuarios = Usuario.objects.all().order_by('nome')
    return render(request, 'core/admin_listar_usuarios.html', {'usuarios': usuarios, 'search_query': search_query})

@admin_required
def adicionar_usuario_admin_view(request):
    if request.method == 'POST':
        form = AdminUsuarioCreationForm(request.POST)
        if form.is_valid():
            form.save()
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
            form.save()
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
    if request.method == 'POST':
        usuario.ativo = not usuario.ativo
        usuario.save()
        messages.success(request, f"Usuário '{usuario.nome}' foi {'ativado' if usuario.ativo else 'inativado'} com sucesso.")
        from core.utils import registrar_log
        registrar_log(request, f'USUARIO_{"ATIVADO" if usuario.ativo else "INATIVADO"}', {
            'usuario_nome': usuario.nome,
            'usuario_id': usuario.id_funcional
        })
        return redirect('core:listar_usuarios')
    return render(request, 'core/admin_inativar_usuario_confirm.html', {'usuario': usuario})

@admin_required
def deletar_usuario_permanente_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    if request.method == 'POST':
        with transaction.atomic():
            usuario_nome = usuario.nome
            usuario_id_funcional = usuario.id_funcional
            usuario.delete()
            messages.success(request, f"Usuário '{usuario_nome}' (ID: {usuario_id_funcional}) e todos os seus dados foram excluídos permanentemente.")
            from core.utils import registrar_log
            registrar_log(request, 'DELETE_USUARIO_PERMANENTE', {
                'usuario_nome_deletado': usuario_nome,
                'usuario_id_funcional_deletado': usuario_id_funcional
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
            folha.delete()
            messages.success(request, f"Folha de ponto de '{servidor_nome}' para o período '{periodo}' excluída permanentemente.")
            from core.utils import registrar_log
            registrar_log(request, 'DELETE_FOLHA_PERMANENTE', {
                'servidor_nome': servidor_nome,
                'folha_periodo': periodo,
                'folha_id': folha_id
            })
        return redirect('core:listar_usuarios')
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
            log_obj.detalhes_json_str = json.dumps(log_obj.detalhes, ensure_ascii=False) 
        else:
            log_obj.detalhes_json_str = "{}" 
        logs_para_template.append(log_obj)

    try:
        logs_page_obj = paginator.page(page)
        # Filtra os logs serializados para obter apenas os que estão na página atual
        logs_page_obj.object_list = [l for l in logs_para_template if l.pk in [obj.pk for obj in logs_page_obj.object_list]]
        logs = logs_page_obj
    except PageNotAnInteger: # Correção: o nome da exceção é PageNotAnInteger
        logs = paginator.page(1)
        logs.object_list = [l for l in logs_serializados if l.pk in [obj.pk for obj in logs.object_list]]
    except EmptyPage:
        logs = paginator.page(paginator.num_pages)
        logs.object_list = [l for l in logs_serializados if l.pk in [obj.pk for obj in logs.object_list]]
    
    # Dados para os filtros do template
    usuarios_para_filtro = Usuario.objects.all().order_by('nome')
    acoes_disponiveis = LogAuditoria.objects.values_list('acao', flat=True).distinct().order_by('acao')

    context = {
        'page_obj': logs,
        'usuarios_para_filtro': usuarios_para_filtro,
        'acoes_disponiveis': acoes_disponiveis,
        'filtro_aplicado': {
            'usuario': int(usuario_id) if usuario_id else '',
            'acao': acao if acao else '',
            'data_inicio': data_inicio if data_inicio else '',
            'data_fim': data_fim if data_fim else '',
        }
    }
    return render(request, 'core/admin_auditoria.html', context)