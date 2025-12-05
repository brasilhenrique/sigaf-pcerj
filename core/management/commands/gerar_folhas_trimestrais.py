# core/management/commands/gerar_folhas_trimestrais.py

import sys
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Usuario, FolhaPonto
from core.utils import popular_dias_folha

class Command(BaseCommand):
    help = 'Verifica e gera as folhas de ponto para o trimestre atual para todos os usuários ativos que ainda não as possuem.'

    def handle(self, *args, **options):
        hoje = date.today()
        # Define os dias de início do trimestre para verificação
        dias_de_geracao = [date(hoje.year, 1, 1), date(hoje.year, 4, 1), date(hoje.year, 7, 1), date(hoje.year, 10, 1)]

        # Executa somente se hoje for um dos dias de geração
        if hoje not in dias_de_geracao:
            self.stdout.write(self.style.WARNING(f"Hoje ({hoje.strftime('%d/%m/%Y')}) não é um dia de geração de folha trimestral. Nenhuma ação será executada."))
            sys.exit(0)

        trimestre_atual = (hoje.month - 1) // 3 + 1
        ano_atual = hoje.year
        
        self.stdout.write(f"Iniciando verificação para o {trimestre_atual}º trimestre de {ano_atual}.")

        # Gera folhas para QUALQUER usuário ATIVO, EXCETO Administrador Geral.
        usuarios_ativos = Usuario.objects.filter(ativo=True).exclude(perfil='Administrador Geral')
        
        folhas_criadas_count = 0
        usuarios_processados_count = 0

        with transaction.atomic():
            for usuario in usuarios_ativos:
                usuarios_processados_count += 1
                # Verifica se o usuário já tem uma folha para o trimestre/ano atual
                folha_existente = FolhaPonto.objects.filter(
                    servidor=usuario,
                    ano=ano_atual,
                    trimestre=trimestre_atual
                ).exists()

                if not folha_existente:
                    try:
                        nova_folha = FolhaPonto.objects.create(
                            servidor=usuario,
                            ano=ano_atual,
                            trimestre=trimestre_atual,
                            unidade_id_geracao=usuario.lotacao,
                            status='Em Andamento',
                            cargo_servidor_na_folha=usuario.perfil # Salva o cargo atual na folha
                        )
                        # Popula os dias da folha recém-criada
                        popular_dias_folha(nova_folha)
                        folhas_criadas_count += 1
                        self.stdout.write(f"  [SUCESSO] Folha criada para {usuario.nome} ({usuario.id_funcional}).")
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f"  [ERRO] Falha ao criar folha para {usuario.nome}: {e}"))
                else:
                    self.stdout.write(f"  [INFO] Folha já existente para {usuario.nome}. Nenhuma ação necessária.")

        self.stdout.write(self.style.SUCCESS(f"\nOperação concluída. {usuarios_processados_count} usuários verificados. {folhas_criadas_count} novas folhas de ponto foram geradas."))