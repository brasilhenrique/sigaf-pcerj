# ARQUIVO: core/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Usuario, FolhaPonto
from datetime import date
from .utils import popular_dias_folha

@receiver(post_save, sender=Usuario)
def criar_folha_ponto_para_novo_usuario(sender, instance, created, **kwargs):
    """
    Cria uma FolhaPonto para o trimestre atual sempre que um novo usuário
    (que não seja Admin Geral) é criado e está ativo.
    """
    # A folha será criada para QUALQUER usuário ATIVO, EXCETO Administrador Geral.
    if created and instance.ativo and instance.perfil != 'Administrador Geral':
        hoje = date.today()
        trimestre_atual = (hoje.month - 1) // 3 + 1
        
        # Cria a folha e já faz o Snapshot do cargo atual
        folha, folha_criada = FolhaPonto.objects.get_or_create(
            servidor=instance, 
            ano=hoje.year, 
            trimestre=trimestre_atual,
            defaults={
                'unidade_id_geracao': instance.lotacao,
                'cargo_servidor_na_folha': instance.perfil # Garante o snapshot na criação
            }
        )

        if folha_criada:
            popular_dias_folha(folha) # Preenche os dias com "Livre", "Sábado", "Domingo"