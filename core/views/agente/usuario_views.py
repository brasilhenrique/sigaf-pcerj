# F:\dev\sigaf-novo\core\views\agente\usuario_views.py (ATUALIZADO - Inativação com Motivo)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.db import transaction 
from datetime import date 

from core.models import Usuario, Transferencia, Unidade, FolhaPonto
from core.forms import UsuarioCreationForm, UsuarioChangeForm, TransferenciaForm, AtribuirConferenteForm, InativarUsuarioForm 
from core.utils import registrar_log

def agente_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.perfil != 'Agente de Pessoal':
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@agente_required
def adicionar_usuario_view(request):
    if request.method == 'POST':
        form = UsuarioCreationForm(request.POST, request=request) 
        if form.is_valid():
            novo_usuario = form.save()
            registrar_log(request, 'USER_CREATE_BY_AGENTE', {
                'novo_usuario_id': novo_usuario.id,
                'novo_usuario_nome': novo_usuario.nome,
                'novo_usuario_id_funcional': novo_usuario.id_funcional,
                'perfil': novo_usuario.perfil,
                'lotacao': novo_usuario.lotacao.nome_unidade if novo_usuario.lotacao else 'N/A',
                'unidades_atuacao_ids': list(novo_usuario.unidades_atuacao.all().values_list('id', flat=True)) 
            })
            messages.success(request, 'Usuário criado com sucesso!')
            return redirect('core:agente_dashboard')
    else:
        form = UsuarioCreationForm(request=request) 
    return render(request, 'core/agente_form_usuario.html', {'form': form, 'titulo': 'Adicionar Novo Usuário'})

@agente_required
def editar_usuario_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    # Permissão: Um agente só pode editar usuários lotados em suas unidades de atuação.
    # Ele pode editar a si mesmo (se for Agente de Pessoal).
    if not ((usuario.lotacao and usuario.lotacao in request.user.unidades_atuacao.all()) or usuario == request.user) or \
       usuario.perfil == 'Administrador Geral': 
        messages.error(request, 'Você não tem permissão para editar este usuário.')
        return redirect('core:agente_dashboard')

    # Se o usuário a ser editado é um Agente de Pessoal (mas não é o próprio agente logado)
    if usuario.perfil == 'Agente de Pessoal' and usuario != request.user:
        messages.error(request, 'Você não pode editar outros Agentes de Pessoal por esta interface. Utilize o painel de Administrador Geral.')
        return redirect('core:agente_dashboard')

    if request.method == 'POST':
        form = UsuarioChangeForm(request.POST, instance=usuario, request=request) 
        if form.is_valid():
            mudancas = {k: {'old': str(form.initial.get(k)), 'new': str(form.cleaned_data.get(k))} 
                        for k, v in form.cleaned_data.items() if str(form.cleaned_data.get(k)) != str(form.initial.get(k))}
            
            unidades_atuacao_antigas_ids = set(usuario.unidades_atuacao.all().values_list('id', flat=True)) 

            if 'status_servidor' in mudancas:
                if mudancas['status_servidor']['new'] in ['Aposentado', 'Demitido', 'Falecido', 'Exonerado', 'Licenciado'] and usuario.ativo:
                    usuario.ativo = False
                    usuario.data_inativacao = date.today()
                    messages.info(request, f"O usuário {usuario.nome} foi automaticamente inativado e a data de inativação registrada.")
                elif mudancas['status_servidor']['new'] == 'Ativo' and not usuario.ativo:
                    usuario.ativo = True
                    usuario.data_inativacao = None
                    messages.info(request, f"O usuário {usuario.nome} foi automaticamente reativado e a data de inativação removida.")

            if usuario.perfil in [cargo[0] for cargo in Usuario.POLICIA_CARGOS]:
                if usuario.is_staff: 
                    usuario.is_staff = False
                    usuario.save(update_fields=['is_staff'])

            usuario = form.save() 
            
            unidades_atuacao_novas_ids = set(usuario.unidades_atuacao.all().values_list('id', flat=True))

            mudancas_unidades_atuacao = {} 
            if unidades_atuacao_antigas_ids != unidades_atuacao_novas_ids:
                unidades_adicionadas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_novas_ids - unidades_atuacao_antigas_ids)]
                unidades_removidas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_atuacao_antigas_ids - unidades_atuacao_novas_ids)]
                mudancas_unidades_atuacao = {
                    'adicionadas': unidades_adicionadas,
                    'removidas': unidades_removidas 
                }
            
            if mudancas or mudancas_unidades_atuacao: 
                registrar_log(request, 'USER_EDIT_BY_AGENTE', {
                    'usuario_id': usuario.id,
                    'usuario_nome': usuario.nome,
                    'mudancas': mudancas,
                    'mudancas_unidades_atuacao': mudancas_unidades_atuacao
                })
            messages.success(request, 'Usuário atualizado com sucesso!')
            return redirect('core:agente_dashboard')
    else:
        form = UsuarioChangeForm(instance=usuario, request=request) 
    return render(request, 'core/agente_form_usuario.html', {'form': form, 'titulo': f'Editando: {usuario.nome}'})

# ATENÇÃO: @require_POST removido para permitir GET da página de confirmação
@agente_required
def inativar_usuario_view(request, usuario_id): 
    usuario = get_object_or_404(Usuario, id=usuario_id)

    # Permissão
    if (usuario == request.user) or \
       usuario.perfil in ['Agente de Pessoal', 'Administrador Geral', 'Delegado de Polícia'] or \
       (usuario.lotacao and usuario.lotacao not in request.user.unidades_atuacao.all()):
        messages.error(request, 'Você não tem permissão para inativar este usuário.')
        return redirect('core:agente_dashboard')

    if request.method == 'POST':
        form = InativarUsuarioForm(request.POST)
        if form.is_valid():
            if usuario.ativo: 
                novo_status = form.cleaned_data['motivo']
                usuario.ativo = False
                usuario.status_servidor = novo_status
                usuario.data_inativacao = date.today()
                usuario.save()
                registrar_log(request, 'USER_INACTIVATE_BY_AGENTE', {
                    'usuario_id': usuario.id,
                    'usuario_nome': usuario.nome,
                    'motivo_status': usuario.status_servidor,
                    'data_inativacao': str(usuario.data_inativacao)
                })
                messages.success(request, f'Usuário "{usuario.nome}" inativado com sucesso. Status definido como "{usuario.status_servidor}".')
            else:
                messages.info(request, f'O usuário "{usuario.nome}" já está inativo.')
            return redirect('core:agente_dashboard')
    else:
        form = InativarUsuarioForm()
        
    return render(request, 'core/agente_deletar_usuario_confirm.html', {'usuario': usuario, 'form': form}) 

@agente_required
def transferir_usuario_view(request, usuario_id):
    usuario_a_transferir = get_object_or_404(Usuario, id=usuario_id)
    unidade_origem = usuario_a_transferir.lotacao

    # Permissão
    if not (unidade_origem and unidade_origem in request.user.unidades_atuacao.all()) or \
       usuario_a_transferir.perfil in ['Agente de Pessoal', 'Administrador Geral', 'Delegado de Polícia']:
        messages.error(request, "Você não tem permissão para transferir este usuário.")
        return redirect('core:agente_dashboard')
    
    if not usuario_a_transferir.ativo:
        messages.error(request, f"Não é possível transferir um usuário inativo ({usuario_a_transferir.nome}). Por favor, reative-o primeiro se desejar transferir.")
        return redirect('core:agente_historico_folhas', usuario_id=usuario_id) 

    if request.method == 'POST':
        form = TransferenciaForm(request.POST, instance=usuario_a_transferir)
        if form.is_valid():
            nova_unidade = form.cleaned_data['unidade_destino']
            data_transferencia = form.cleaned_data['data_transferencia']

            if nova_unidade == unidade_origem:
                messages.warning(request, "A unidade de destino é a mesma que a unidade de origem. Nenhuma transferência realizada.")
                return redirect('core:agente_dashboard')

            with transaction.atomic(): 
                usuario_a_transferir.lotacao = nova_unidade
                usuario_a_transferir.save()

                Transferencia.objects.create(
                    servidor=usuario_a_transferir,
                    unidade_origem=unidade_origem,
                    unidade_destino=nova_unidade,
                    data_transferencia=data_transferencia,
                    agente_responsavel=request.user
                )

                hoje = date.today()
                trimestre_atual = (hoje.month - 1) // 3 + 1
                FolhaPonto.objects.filter(
                    servidor=usuario_a_transferir,
                    ano=hoje.year,
                    trimestre=trimestre_atual
                ).update(unidade_id_geracao=nova_unidade) 

                registrar_log(request, 'USER_TRANSFER', {
                    'servidor_id': usuario_a_transferir.id,
                    'servidor_nome': usuario_a_transferir.nome,
                    'unidade_origem': unidade_origem.nome_unidade if unidade_origem else 'N/A',
                    'unidade_destino': nova_unidade.nome_unidade,
                    'data_transferencia': str(data_transferencia)
                })
                messages.success(request, f"Usuário {usuario_a_transferir.nome} transferido para {nova_unidade.nome_unidade} com sucesso.")
            return redirect('core:agente_dashboard')
    else:
        form = TransferenciaForm(instance=usuario_a_transferir) 
        form.fields['unidade_destino'].label = "Nova Unidade de Lotação" 

    context = {
        'form': form,
        'usuario_a_transferir': usuario_a_transferir,
        'unidade_origem': unidade_origem 
    }
    return render(request, 'core/transferir_usuario.html', context)
    
@agente_required
def listar_inativos_view(request):
    unidades_atuacao = request.user.unidades_atuacao.all() 
    search_query = request.GET.get('q', '').strip()

    # Filtra usuários inativos que não são Agentes de Pessoal, Administradores Gerais ou Delegados
    servidores_inativos_queryset = Usuario.objects.filter(
        lotacao__in=unidades_atuacao, 
        ativo=False
    ).exclude(
        perfil__in=['Agente de Pessoal', 'Administrador Geral', 'Delegado de Polícia']
    )
    
    if search_query:
        servidores_inativos_queryset = servidores_inativos_queryset.filter(
            Q(nome__icontains=search_query) |
            Q(id_funcional__icontains=search_query)
        )
    
    inativos_por_lotacao = {}
    for unidade in unidades_atuacao.order_by('nome_unidade'): 
        servidores_na_unidade = servidores_inativos_queryset.filter(lotacao=unidade).order_by('nome')
        if servidores_na_unidade.exists():
            inativos_por_lotacao[unidade.nome_unidade] = list(servidores_na_unidade)

    context = {
        'inativos_por_lotacao': inativos_por_lotacao,
        'search_query': search_query,
    }
    return render(request, 'core/agente_listar_inativos.html', context)

@require_POST
@agente_required
def reativar_usuario_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id, ativo=False)
    
    # Permissão
    if (usuario.lotacao and usuario.lotacao not in request.user.unidades_atuacao.all()) or \
       usuario.perfil in ['Agente de Pessoal', 'Administrador Geral', 'Delegado de Polícia']:
        messages.error(request, "Você não tem permissão para reativar este usuário.")
        return redirect('core:listar_inativos')
        
    usuario.ativo = True
    usuario.status_servidor = 'Ativo' 
    usuario.data_inativacao = None 
    usuario.save()

    registrar_log(request, 'USER_REACTIVATE_BY_AGENTE', {
        'usuario_id': usuario.id,
        'usuario_nome': usuario.nome,
        'status_novo': usuario.status_servidor
    })
    
    messages.success(request, f"O usuário {usuario.nome} foi reativado com sucesso. Status definido como '{usuario.status_servidor}'.")
    return redirect('core:listar_inativos')

@agente_required
def listar_conferentes_view(request):
    agente = request.user
    
    conferentes_queryset = Usuario.objects.filter(
        Q(perfil='Delegado de Polícia') | 
        Q(unidades_atuacao__isnull=False) 
    ).exclude(
        Q(perfil='Administrador Geral') | Q(perfil='Agente de Pessoal')
    ).filter(
        Q(lotacao__in=agente.unidades_atuacao.all()) | Q(unidades_atuacao__in=agente.unidades_atuacao.all())
    ).distinct().order_by('nome')


    usuarios_candidatos_conferente = Usuario.objects.filter(
        lotacao__in=agente.unidades_atuacao.all(),
        ativo=True
    ).exclude(
        Q(perfil='Administrador Geral') | Q(perfil='Agente de Pessoal') | Q(perfil='Delegado de Polícia') | Q(unidades_atuacao__isnull=False) 
    ).order_by('nome')


    context = {
        'conferentes_existentes': conferentes_queryset,
        'usuarios_candidatos_conferente': usuarios_candidatos_conferente,
    }
    return render(request, 'core/agente_listar_conferentes.html', context)


@agente_required
def atribuir_conferente_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    agente = request.user

    if not (usuario.lotacao and usuario.lotacao in agente.unidades_atuacao.all()) or \
       usuario.perfil in ['Administrador Geral', 'Agente de Pessoal', 'Delegado de Polícia']:
        messages.error(request, "Você não tem permissão para atribuir conferência a este usuário.")
        return redirect('core:listar_conferentes')

    if request.method == 'POST':
        form = AtribuirConferenteForm(request.POST, instance=usuario) 
        if form.is_valid():
            unidades_antigas_ids = set(usuario.unidades_atuacao.all().values_list('id', flat=True))
            
            form.save() 
            
            unidades_novas_ids = set(usuario.unidades_atuacao.all().values_list('id', flat=True))

            mudancas_unidades = {}
            if unidades_antigas_ids != unidades_novas_ids:
                unidades_adicionadas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_novas_ids - unidades_antigas_ids)]
                unidades_removidas = [str(Unidade.objects.get(id=uid).nome_unidade) for uid in (unidades_antigas_ids - unidades_novas_ids)]
                mudancas_unidades = {
                    'adicionadas': unidades_adicionadas,
                    'removidas': unidades_removidas
                }
            
            registrar_log(request, 'CONFERENTE_ATRIBUIDO', {
                'usuario_conferente_id': usuario.id,
                'usuario_conferente_nome': usuario.nome,
                'unidades_atuacao_mudancas': mudancas_unidades,
                'atribuido_por_agente': request.user.id_funcional
            })
            messages.success(request, f"Servidor '{usuario.nome}' atribuído como Conferente para as unidades selecionadas.")
            return redirect('core:listar_conferentes')
        else:
            messages.error(request, "Erro ao atribuir Conferente. Verifique o formulário.")
    else:
        form = AtribuirConferenteForm(instance=usuario)
        
    context = {
        'form': form,
        'usuario_alvo': usuario,
        'titulo': f"Atribuir Unidades de Conferência para: {usuario.nome}",
    }
    return render(request, 'core/agente_atribuir_conferente.html', context)


@agente_required
@require_POST
def remover_conferente_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    agente = request.user

    if not (usuario.lotacao and usuario.lotacao in agente.unidades_atuacao.all()) or \
        usuario.perfil in ['Administrador Geral', 'Agente de Pessoal', 'Delegado de Polícia']: 
        messages.error(request, "Você não tem permissão para remover o status de Conferente deste usuário.")
        return redirect('core:listar_conferentes')

    if usuario.unidades_atuacao.exists():
        usuario_nome = usuario.nome 
        unidades_atuacao_removidas = list(usuario.unidades_atuacao.all().values_list('nome_unidade', flat=True))

        usuario.unidades_atuacao.clear() 
        usuario.save()

        registrar_log(request, 'CONFERENTE_REMOVIDO', {
            'usuario_conferente_id': usuario.id,
            'usuario_conferente_nome': usuario.nome,
            'unidades_atuacao_removidas': unidades_atuacao_removidas,
            'removido_por_agente': agente.id_funcional
        })
        messages.success(request, f"As atribuições de conferência para '{usuario_nome}' foram removidas.")
    else:
        messages.info(request, f"Servidor '{usuario.nome}' não possui atribuições de conferência para remover.")

    return redirect('core:listar_conferentes')