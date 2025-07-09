# F:\dev\sigaf-novo\core\views\agente\usuario_views.py (CORRIGIDO)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.db import transaction # Importar para garantir atomicidade
from datetime import date # Importar para data_inativacao

from core.models import Usuario, Transferencia, Unidade, FolhaPonto
from core.forms import UsuarioCreationForm, UsuarioChangeForm, TransferenciaForm
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
        form = UsuarioCreationForm(request.POST, request=request) # Passa o request
        if form.is_valid():
            novo_usuario = form.save()
            registrar_log(request, 'USER_CREATE_BY_AGENTE', {
                'novo_usuario_id': novo_usuario.id,
                'novo_usuario_nome': novo_usuario.nome,
                'novo_usuario_id_funcional': novo_usuario.id_funcional,
                'perfil': novo_usuario.perfil,
                'lotacao': novo_usuario.lotacao.nome_unidade if novo_usuario.lotacao else 'N/A'
            })
            messages.success(request, 'Usuário criado com sucesso!')
            return redirect('core:agente_dashboard')
    else:
        form = UsuarioCreationForm(request=request) # Passa o request
    return render(request, 'core/agente_form_usuario.html', {'form': form, 'titulo': 'Adicionar Novo Usuário'})

@agente_required
def editar_usuario_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    # Permissão: Um agente só pode editar usuários lotados em suas unidades gerenciadas.
    if usuario.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, 'Você não tem permissão para editar este usuário.')
        return redirect('core:agente_dashboard')

    if request.method == 'POST':
        form = UsuarioChangeForm(request.POST, instance=usuario, request=request) # Passa o request
        if form.is_valid():
            mudancas = {k: {'old': form.initial.get(k), 'new': form.cleaned_data.get(k)} 
                        for k, v in form.cleaned_data.items() if form.cleaned_data.get(k) != form.initial.get(k)}
            
            # Ajusta o status ativo se o status_servidor for alterado para inativo
            if 'status_servidor' in mudancas:
                if mudancas['status_servidor']['new'] in ['Aposentado', 'Demitido', 'Falecido'] and usuario.ativo:
                    usuario.ativo = False
                    usuario.data_inativacao = date.today()
                    messages.info(request, f"O usuário {usuario.nome} foi automaticamente inativado e a data de inativação registrada.")
                elif mudancas['status_servidor']['new'] == 'Ativo' and not usuario.ativo:
                    usuario.ativo = True
                    usuario.data_inativacao = None
                    messages.info(request, f"O usuário {usuario.nome} foi automaticamente reativado e a data de inativação removida.")

            usuario = form.save() # Salva as mudanças do formulário

            # Log apenas se houver mudanças reais (além do status_servidor ajustado acima)
            if mudancas: # Verificamos se há mudanças para registrar log
                 registrar_log(request, 'USER_EDIT_BY_AGENTE', {
                    'usuario_id': usuario.id,
                    'usuario_nome': usuario.nome,
                    'mudancas': mudancas
                })
            messages.success(request, 'Usuário atualizado com sucesso!')
            return redirect('core:agente_dashboard')
    else:
        form = UsuarioChangeForm(instance=usuario, request=request) # Passa o request
    return render(request, 'core/agente_form_usuario.html', {'form': form, 'titulo': f'Editando: {usuario.nome}'})

@agente_required
@require_POST # Assegura que a ação só pode ser acessada via POST
def inativar_usuario_view(request, usuario_id): # Renomeada de 'deletar_usuario_view' para clareza
    usuario = get_object_or_404(Usuario, id=usuario_id)

    # Permissão: Um agente só pode inativar usuários lotados em suas unidades gerenciadas.
    if usuario.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, 'Você não tem permissão para inativar este usuário.')
        return redirect('core:agente_dashboard')

    if request.method == 'POST': # Confirmação via POST
        if usuario.ativo: # Verifica se já não está inativo
            usuario.ativo = False
            usuario.status_servidor = 'Demitido' # Define um status padrão para inativação
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
        
    # Se for um GET para a view de inativação (apenas para exibição da confirmação)
    # Reutiliza o template de confirmação que você já tem
    return render(request, 'core/agente_deletar_usuario_confirm.html', {'usuario': usuario}) # Renomeado para inativar

@agente_required
def transferir_usuario_view(request, usuario_id):
    usuario_a_transferir = get_object_or_404(Usuario, id=usuario_id)
    unidade_origem = usuario_a_transferir.lotacao

    # Permissão: O agente só pode transferir usuários de suas próprias unidades gerenciadas.
    if unidade_origem not in request.user.unidades_gerenciadas.all():
        messages.error(request, "Você não tem permissão para transferir este usuário, pois ele não está em uma de suas unidades gerenciadas.")
        return redirect('core:agente_dashboard')
    
    # Se o usuário está inativo, não deve ser transferido
    if not usuario_a_transferir.ativo:
        messages.error(request, f"Não é possível transferir um usuário inativo ({usuario_a_transferir.nome}). Por favor, reative-o primeiro se desejar transferir.")
        return redirect('core:agente_historico_folhas', usuario_id=usuario_id) # Ou outra página apropriada

    if request.method == 'POST':
        form = TransferenciaForm(request.POST, instance=usuario_a_transferir)
        if form.is_valid():
            nova_unidade = form.cleaned_data['unidade_destino']
            data_transferencia = form.cleaned_data['data_transferencia']

            # Verifica se a unidade de destino é diferente da origem
            if nova_unidade == unidade_origem:
                messages.warning(request, "A unidade de destino é a mesma que a unidade de origem. Nenhuma transferência realizada.")
                return redirect('core:agente_dashboard')

            with transaction.atomic(): # Garante que todas as operações sejam atômicas
                # 1. Atualiza a lotação do usuário
                usuario_a_transferir.lotacao = nova_unidade
                usuario_a_transferir.save()

                # 2. Registra a transferência na tabela de Transferencias
                Transferencia.objects.create(
                    servidor=usuario_a_transferir,
                    unidade_origem=unidade_origem,
                    unidade_destino=nova_unidade,
                    data_transferencia=data_transferencia,
                    agente_responsavel=request.user
                )

                # 3. Move as folhas de ponto do trimestre atual para a nova unidade (se existirem)
                hoje = date.today()
                trimestre_atual = (hoje.month - 1) // 3 + 1
                FolhaPonto.objects.filter(
                    servidor=usuario_a_transferir,
                    ano=hoje.year,
                    trimestre=trimestre_atual
                ).update(unidade_id_geracao=nova_unidade) # Atualiza a unidade_id_geracao

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
        form = TransferenciaForm(instance=usuario_a_transferir) # Passa a instância para pré-popular
        form.fields['unidade_destino'].label = "Nova Unidade de Lotação" # Ajusta o label para clareza
        # O queryset já é filtrado no forms.py para unidades ativas.

    context = {
        'form': form,
        'usuario_a_transferir': usuario_a_transferir,
        'unidade_origem': unidade_origem # Passa a unidade de origem para o template
    }
    return render(request, 'core/transferir_usuario.html', context)
    
@agente_required
def listar_inativos_view(request):
    unidades_gerenciadas = request.user.unidades_gerenciadas.all()
    search_query = request.GET.get('q', '').strip()

    servidores_inativos_queryset = Usuario.objects.filter(
        lotacao__in=unidades_gerenciadas, 
        ativo=False
    )
    
    if search_query:
        servidores_inativos_queryset = servidores_inativos_queryset.filter(
            Q(nome__icontains=search_query) |
            Q(id_funcional__icontains=search_query)
        )
    
    # Agrupar por lotação para exibição organizada
    inativos_por_lotacao = {}
    for unidade in unidades_gerenciadas.order_by('nome_unidade'):
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
    
    # Permissão: Um agente só pode reativar usuários lotados em suas unidades gerenciadas.
    if usuario.lotacao not in request.user.unidades_gerenciadas.all():
        messages.error(request, "Você não tem permissão para reativar este usuário.")
        return redirect('core:listar_inativos')
        
    usuario.ativo = True
    usuario.status_servidor = 'Ativo' # Define o status de volta para Ativo
    usuario.data_inativacao = None # Remove a data de inativação
    usuario.save()

    registrar_log(request, 'USER_REACTIVATE_BY_AGENTE', {
        'usuario_id': usuario.id,
        'usuario_nome': usuario.nome,
        'status_novo': usuario.status_servidor
    })
    
    messages.success(request, f"O usuário {usuario.nome} foi reativado com sucesso. Status definido como '{usuario.status_servidor}'.")
    return redirect('core:listar_inativos')