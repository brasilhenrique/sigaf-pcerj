# F:\dev\sigaf-novo\core\views\auth_views.py (CORRIGIDO)

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from core.forms import ChangePasswordForm
from core.utils import registrar_log

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def login_view(request):
    # Se o usuário já estiver logado, redireciona para o dashboard
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        # Pega os dados diretamente do formulário HTML
        id_funcional = request.POST.get('id_funcional')
        password = request.POST.get('password')

        # O `authenticate` do Django já sabe que precisa usar 'id_funcional' 
        # como username por causa da configuração no seu models.py
        user = authenticate(request, username=id_funcional, password=password)
        
        if user is not None:
            # Lógica de primeiro login e força troca de senha (Fase 2 - Produção)
            if user.primeiro_login:
                messages.info(request, "Este é seu primeiro login ou sua senha foi redefinida. Por favor, crie uma nova senha segura.")
                login(request, user) # Loga o usuário temporariamente para a troca de senha
                registrar_log(request, 'FIRST_LOGIN_REDIRECT', {'id_funcional': id_funcional}, ip_address=get_client_ip(request))
                return redirect('core:change_password')

            login(request, user)
            registrar_log(request, 'LOGIN_SUCCESS', {'id_funcional': id_funcional}, ip_address=get_client_ip(request))
            
            # Redirecionamento por perfil
            if user.perfil == 'Administrador Geral':
                return redirect('core:admin_geral_dashboard')
            elif user.perfil == 'Agente de Pessoal':
                return redirect('core:agente_dashboard')
            elif user.perfil == 'Delegado':
                return redirect('core:delegado_dashboard')
            else: # Perfil Servidor (ou qualquer outro não especificado)
                return redirect('core:dashboard')
        else:
            # Se a autenticação falhar, exibe a mensagem de erro
            registrar_log(request, 'LOGIN_FAILURE', {'id_funcional_attempt': id_funcional}, ip_address=get_client_ip(request))
            messages.error(request, 'ID Funcional ou senha inválidos.')
            return render(request, 'core/login.html', {'id_funcional': id_funcional}) # Mantém o ID funcional preenchido
            # return redirect('core:login') # Alternativa, mas perderia o id_funcional preenchido

    # Se a requisição for GET, apenas renderiza a página de login
    return render(request, 'core/login.html')


def logout_view(request):
    # Registra o log ANTES de fazer o logout para ainda ter acesso ao usuário
    registrar_log(request, 'LOGOUT', ip_address=get_client_ip(request))
    logout(request)
    messages.info(request, 'Você saiu do sistema.')
    return redirect('core:login')


def change_password_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "Você precisa estar logado para alterar sua senha.")
        return redirect('core:login')
    
    # Se o usuário for um administrador geral, não deve ter a flag primeiro_login
    # e não deve ser forçado a trocar a senha inicial.
    # Esta verificação pode ser útil para o setup inicial.
    if request.user.perfil == 'Administrador Geral':
        # Você pode adicionar uma mensagem aqui ou simplesmente permitir que ele altere
        # a senha normalmente sem forçar.
        pass # Não faz nada de especial para o Admin Geral aqui.
        
    if request.method == 'POST':
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Mantém o usuário logado
            
            # Se a senha foi alterada via o fluxo de "primeiro login", reseta a flag.
            if user.primeiro_login:
                user.primeiro_login = False
                user.save(update_fields=['primeiro_login'])

            registrar_log(request, 'PASSWORD_CHANGE_SUCCESS', {'user_id': user.id_funcional}, ip_address=get_client_ip(request))
            messages.success(request, 'Sua senha foi alterada com sucesso!')
            # Redireciona para o dashboard correto após a troca de senha
            if user.perfil == 'Administrador Geral':
                return redirect('core:admin_geral_dashboard')
            elif user.perfil == 'Agente de Pessoal':
                return redirect('core:agente_dashboard')
            elif user.perfil == 'Delegado':
                return redirect('core:delegado_dashboard')
            else: # Perfil Servidor (ou qualquer outro não especificado)
                return redirect('core:dashboard')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = ChangePasswordForm(request.user)
        
    return render(request, 'core/change_password.html', {'form': form})