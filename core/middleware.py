from django.shortcuts import redirect
from django.urls import reverse

class ForcarTrocaSenhaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Rotas permitidas para não causar loop infinito
            rotas_permitidas = [
                reverse('core:change_password'), # Rota correta para trocar a senha
                reverse('core:logout'),          # Rota para sair do sistema
            ]
            
            # Se a bandeira estiver ligada e ele tentar acessar outra página
            if getattr(request.user, 'precisa_trocar_senha', False) and request.path not in rotas_permitidas:
                # Ignora arquivos estáticos e painel admin
                if not request.path.startswith('/static/') and not request.path.startswith('/admin/'):
                    return redirect('core:change_password')

        response = self.get_response(request)
        return response