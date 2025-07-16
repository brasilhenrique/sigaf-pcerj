# F:\dev\sigaf-novo\core\views\delegado_gerenciamento_views.py (COMPLETO E CORRIGIDO COM DEPURAÇÃO)

import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from core.models import Usuario, Unidade
from core.forms import AdminDelegadoCreationForm, AdminDelegadoChangeForm
from core.views.admin_views import admin_required 
from datetime import date 
from core.utils import registrar_log 

# Função de ordenação para as unidades (reutilizada de admin_views)
def custom_sort_key(unidade):
    match = re.match(r'^(\d+)', unidade.nome_unidade)
    if match:
        return (int(match.group(1)), unidade.nome_unidade)
    else:
        return (float('inf'), unidade.nome_unidade)


@admin_required
def listar_delegados_view(request):
    search_query = request.GET.get('q', '').strip()
    
    delegados_queryset = Usuario.objects.filter(perfil='Delegado de Polícia')

    if search_query:
        delegados_queryset = delegados_queryset.filter(
            Q(nome__icontains=search_query) |
            Q(id_funcional__icontains=search_query)
        )
    
    # Ordena por lotação primeiro, depois por nome
    delegados = sorted(delegados_queryset.all(), key=lambda u: (u.lotacao.nome_unidade if u.lotacao else '', u.nome))

    # Agrupa por lotação para exibição
    delegados_por_lotacao = {}
    for delegado in delegados:
        lotacao_nome = delegado.lotacao.nome_unidade if delegado.lotacao else 'Não Atribuída'
        if lotacao_nome not in delegados_por_lotacao:
            delegados_por_lotacao[lotacao_nome] = []
        delegados_por_lotacao[lotacao_nome].append(delegado)

    return render(request, 'core/admin_listar_delegados.html', {
        'delegados_por_lotacao': delegados_por_lotacao, 
        'search_query': search_query
    })

@admin_required
def adicionar_delegado_view(request):
    if request.method == 'POST':
        form = AdminDelegadoCreationForm(request.POST)
        if form.is_valid():
            # --- DEPURAÇÃO DENTRO DA VIEW ANTES DO FORM.SAVE() ---
            print("\n--- DEPURAÇÃO: adicionar_delegado_view antes do form.save() ---")
            print(f"request.POST: {request.POST}")
            print(f"form.cleaned_data: {form.cleaned_data}")
            # CORREÇÃO AQUI: Acessando 'unidades_atuacao'
            print(f"unidades_atuacao na cleaned_data (na view): {form.cleaned_data.get('unidades_atuacao')}") 
            # --- FIM DEPURAÇÃO ---

            novo_delegado = form.save() # Se o commit=True (padrão) for usado, ele já chama save_m2m()
            
            registrar_log(request, 'DELEGADO_CRIADO', {
                'delegado_id': novo_delegado.id,
                'delegado_nome': novo_delegado.nome,
                'delegado_id_funcional': novo_delegado.id_funcional,
                'lotacao': novo_delegado.lotacao.nome_unidade if novo_delegado.lotacao else 'N/A',
                # CORRIGIDO: usando unidades_atuacao para o log
                'unidades_atuacao_ids': list(novo_delegado.unidades_atuacao.all().values_list('id', flat=True)) 
            })
            messages.success(request, 'Delegado de Polícia criado com sucesso!')
            return redirect('core:listar_delegados')
        else:
            print("Erros do formulário:", form.errors) # Mostra erros do formulário
            print(f"Request POST data: {request.POST}")
            print(f"Form errors on invalid: {form.errors}")
            messages.error(request, 'Erro ao adicionar delegado. Por favor, corrija os erros no formulário.')
            return render(request, 'core/admin_form_delegado.html', {
                'form': form,
                'titulo': 'Adicionar Novo Delegado'
            })
    else:
        form = AdminDelegadoCreationForm()
        print("\n--- DEPURAÇÃO FORMULÁRIO DELEGADO (GET request) ---")
        print(f"Formulario inicializado: {form}")
        # CORREÇÃO AQUI: Acessando 'unidades_atuacao'
        print(f"Queryset de unidades_atuacao no GET: {form.fields['unidades_atuacao'].queryset.count()} unidades")
        # CORREÇÃO AQUI: Acessando 'unidades_atuacao'
        print(f"Primeiras 5 unidades: {list(form.fields['unidades_atuacao'].queryset[:5])}")
        print("--- FIM DA DEPURAÇÃO (GET request) ---\n")
    
    return render(request, 'core/admin_form_delegado.html', {
        'form': form,
        'titulo': 'Adicionar Novo Delegado'
    })

@admin_required
def editar_delegado_view(request, delegado_id):
    delegado = get_object_or_404(Usuario, id=delegado_id, perfil='Delegado de Polícia')
    if request.method == 'POST':
        form = AdminDelegadoChangeForm(request.POST, instance=delegado)
        if form.is_valid():
            mudancas_perfil_status = {}
            if form.cleaned_data['status_servidor'] != form.initial.get('status_servidor'):
                mudancas_perfil_status['status_servidor'] = {
                    'old': form.initial.get('status_servidor'),
                    'new': form.cleaned_data['status_servidor']
                }

            if mudancas_perfil_status.get('status_servidor'):
                if mudancas_perfil_status['status_servidor']['new'] in ['Aposentado', 'Demitido', 'Falecido'] and delegado.ativo:
                    delegado.ativo = False
                    delegado.data_inativacao = date.today()
                    messages.info(request, f"O Delegado {delegado.nome} foi automaticamente inativado e a data de inativação registrada.")
                elif mudancas_perfil_status['status_servidor']['new'] == 'Ativo' and not delegado.ativo:
                    delegado.ativo = True
                    delegado.data_inativacao = None
                    messages.info(request, f"O Delegado {delegado.nome} foi automaticamente reativado e a data de inativação removida.")
            
            # Captura unidades de atuação antigas para o log ANTES de salvar o form
            # CORREÇÃO AQUI: Acessando 'unidades_atuacao'
            unidades_atuacao_antigas_ids = set(delegado.unidades_atuacao.all().values_list('id', flat=True)) 
            
            delegado = form.save() # O form.save() já chamará save_m2m() internamente
            
            # Captura unidades de atuação novas para o log DEPOIS de salvar
            # CORREÇÃO AQUI: Acessando 'unidades_atuacao'
            unidades_atuacao_novas_ids = set(delegado.unidades_atuacao.all().values_list('id', flat=True)) 

            mudancas_unidades_atuacao = {}
            if unidades_atuacao_antigas_ids != unidades_atuacao_novas_ids:
                unidades_adicionadas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_novas_ids - unidades_atuacao_antigas_ids)]
                unidades_removidas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_antigas_ids - unidades_atuacao_novas_ids)]
                mudancas_unidades_atuacao = {
                    'adicionadas': unidades_adicionadas,
                    'removidas': unidades_removidas
                }
            
            if mudancas_perfil_status or mudancas_unidades_atuacao:
                registrar_log(request, 'DELEGADO_EDITADO', {
                    'delegado_id': delegado.id,
                    'delegado_nome': delegado.nome,
                    'mudancas_perfil_status': mudancas_perfil_status,
                    'mudancas_unidades_atuacao': mudancas_unidades_atuacao
                })

            messages.success(request, 'Delegado de Polícia atualizado com sucesso!')
            return redirect('core:listar_delegados')
        else:
            print("Erros do formulário:", form.errors)
            messages.error(request, 'Erro ao atualizar delegado. Por favor, corrija os erros no formulário.')
            return render(request, 'core/admin_form_delegado.html', {
                'form': form,
                'titulo': f'Editando Delegado: {delegado.nome}',
                'delegado_a_editar': delegado
            })
    else:
        form = AdminDelegadoChangeForm(instance=delegado)
        print("\n--- DEPURAÇÃO FORMULÁRIO DELEGADO (EDIÇÃO GET request) ---")
        print(f"Formulario inicializado para edição: {form}")
        # CORREÇÃO AQUI: Acessando 'unidades_atuacao'
        print(f"Unidades selecionadas atualmente para {delegado.nome}: {list(delegado.unidades_atuacao.all())}") 
        # CORREÇÃO AQUI: Acessando 'unidades_atuacao'
        print(f"Unidades disponíveis no queryset do campo: {form.fields['unidades_atuacao'].queryset.count()}")
        print("--- FIM DA DEPURAÇÃO (EDIÇÃO GET request) ---\n")
    
    return render(request, 'core/admin_form_delegado.html', {
        'form': form,
        'titulo': f'Editando Delegado: {delegado.nome}',
        'delegado_a_editar': delegado
    })

@admin_required
def inativar_delegado_view(request, delegado_id):
    delegado = get_object_or_404(Usuario, id=delegado_id, perfil='Delegado de Polícia')
    if request.method == 'POST':
        delegado.ativo = not delegado.ativo
        if not delegado.ativo and delegado.status_servidor == 'Ativo':
            delegado.status_servidor = 'Demitido' 
            delegado.data_inativacao = date.today()
        elif delegado.ativo and delegado.status_servidor != 'Ativo':
            delegado.status_servidor = 'Ativo'
            delegado.data_inativacao = None

        delegado.save()
        log_acao = 'DELEGADO_ATIVADO' if delegado.ativo else 'DELEGADO_INATIVADO'
        registrar_log(request, log_acao, {
            'delegado_id': delegado.id,
            'delegado_nome': delegado.nome,
            'status_novo': 'Ativo' if delegado.ativo else delegado.status_servidor
        })
        messages.success(request, f"Delegado '{delegado.nome}' foi {'ativado' if delegado.ativo else 'inativado'} com sucesso.")
        return redirect('core:listar_delegados')
    return render(request, 'core/admin_inativar_delegado_confirm.html', {'delegado': delegado})