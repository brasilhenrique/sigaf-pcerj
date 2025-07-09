# core/signals.py (CORRIGIDO)

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Usuario, FolhaPonto
from datetime import date
from .utils import popular_dias_folha # Importa a função de utils

@receiver(post_save, sender=Usuario)
def criar_folha_ponto_para_novo_usuario(sender, instance, created, **kwargs):
    """
    Cria uma FolhaPonto para o trimestre atual sempre que um novo usuário
    (que não seja Admin Geral) é criado e está ativo.
    """
    if created and instance.perfil != 'Administrador Geral' and instance.ativo:
        hoje = date.today()
        trimestre_atual = (hoje.month - 1) // 3 + 1
        
        # get_or_create para segurança, caso a folha já exista (evita duplicatas)
        # e para garantir que a unidade de geração seja a lotação atual do servidor
        folha, folha_criada = FolhaPonto.objects.get_or_create(
            servidor=instance, 
            ano=hoje.year, 
            trimestre=trimestre_atual,
            defaults={'unidade_id_geracao': instance.lotacao} # Define a unidade de geração
        )

        if folha_criada:
            popular_dias_folha(folha) # Popula a folha recém-criada
            # Opcional: Você pode querer registrar um log aqui para a criação automática da folha
            # from .utils import registrar_log
            # registrar_log(None, 'FOLHA_AUTO_CREATE', {
            #     'servidor_id': instance.id_funcional,
            #     'trimestre': trimestre_atual,
            #     'ano': hoje.year,
            #     'motivo': 'Novo Usuário'
            # })