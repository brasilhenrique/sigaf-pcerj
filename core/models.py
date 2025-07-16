# ARQUIVO: core/models.py

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser, BaseUserManager

class Unidade(models.Model):
    nome_unidade = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    codigo_ua = models.CharField(max_length=15, unique=True, null=True, blank=True, verbose_name="Código UA")

    def __str__(self):
        return self.nome_unidade

    class Meta:
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"

class UsuarioManager(BaseUserManager):
    def create_user(self, id_funcional, password=None, **extra_fields):
        if not id_funcional:
            raise ValueError('O ID Funcional é obrigatório')
        user = self.model(id_funcional=id_funcional, **extra_fields)
        user.set_password(password or id_funcional)
        user.username = id_funcional # Garante que o username (campo herdado) seja o id_funcional
        user.save(using=self._db)
        return user

    def create_superuser(self, id_funcional, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('perfil', 'Administrador Geral')
        extra_fields.setdefault('nome', 'Administrador do Sistema')
        
        return self.create_user(id_funcional, password, **extra_fields)

class Usuario(AbstractUser):
    # NOVOS CARGOS E PERFIS
    # POLICIA_CARGOS devem ser usados para perfis de 'Servidor' com cargos específicos
    POLICIA_CARGOS = [
        ('Assistente I', 'Assistente I'),
        ('Assistente II', 'Assistente II'),
        ('Auxiliar Policial de Necropsia', 'Auxiliar Policial de Necropsia'),
        ('Comissário de Polícia', 'Comissário de Polícia'),
        ('Inspetor de Polícia', 'Inspetor de Polícia'),
        ('Investigador Policial', 'Investigador Policial'),
        ('Oficial de Cartório Policial', 'Oficial de Cartório Policial'),
        ('Perito Criminal', 'Perito Criminal'),
        ('Perito Legista', 'Perito Legista'),
        ('Perito Papiloscopista', 'Perito Papiloscopista'),
        ('Piloto Policial', 'Piloto Policial'),
        ('Técnico Policial de Necropsia', 'Técnico Policial de Necropsia'),
    ]

    # NOVA PROPRIEDADE ESTÁTICA para ter a lista de nomes de cargos
    POLICIA_CARGOS_NAMES = [cargo[0] for cargo in POLICIA_CARGOS]

    # PERFIS_FUNCIONAL são os perfis com funções administrativas no sistema
    PERFIS_FUNCIONAL = [
        ('Delegado de Polícia', 'Delegado de Polícia'), # Delegado agora é um cargo específico, mas também um perfil funcional
        ('Agente de Pessoal', 'Agente de Pessoal'),
        ('Administrador Geral', 'Administrador Geral'),
        # REMOVIDO: 'Conferente' não é mais um perfil primário aqui.
        # Ele será uma atribuição adicional para servidores com POLICIA_CARGOS.
    ]

    # Combina todos os tipos de perfis/cargos para o campo choices
    # REMOVIDO: A inclusão direta de 'Conferente' aqui.
    # A lógica de "ser conferente" será baseada na posse de unidades_atuacao
    PERFIL_CHOICES = POLICIA_CARGOS + PERFIS_FUNCIONAL 
    
    STATUS_CHOICES = [
        ('Ativo', 'Ativo'),
        ('Aposentado', 'Aposentado'),
        ('Demitido', 'Demitido'),
        ('Falecido', 'Falecido'),
    ]

    id_funcional = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    perfil = models.CharField(max_length=50, choices=PERFIL_CHOICES, default='Investigador Policial')
    lotacao = models.ForeignKey(Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name='servidores')
    ativo = models.BooleanField(default=True)
    status_servidor = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Ativo')
    primeiro_login = models.BooleanField(default=True)
    data_inativacao = models.DateField(null=True, blank=True)
    
    # CAMPO RENOMEADO E GENERALIZADO
    unidades_atuacao = models.ManyToManyField(
        Unidade,
        blank=True,
        verbose_name="Unidades de Atuação (Gerência/Conferência)",
        help_text="Selecione as unidades pelas quais este usuário pode ser responsável por gerência (Agente de Pessoal) ou conferência de folhas (Delegado de Polícia/Servidor-Conferente)." # Help text atualizado
    )

    USERNAME_FIELD = 'id_funcional'
    REQUIRED_FIELDS = ['nome', 'email']
    objects = UsuarioManager()

    def get_full_name(self):
        return self.nome

    def get_short_name(self):
        parts = self.nome.split()
        return parts[0]

    def get_display_name(self):
        parts = self.nome.split()
        if len(parts) > 1:
            return f"{parts[0]} {parts[-1]}"
        return self.nome

    def get_full_display(self):
        return f"{self.nome} - ID nº {self.id_funcional}"

    def __str__(self):
        return f"{self.nome} ({self.id_funcional})"

    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        self.username = self.id_funcional
        super(Usuario, self).save(*args, **kwargs)

    # Propriedades de conveniência para os grupos de perfis
    @property
    def is_policia_cargo(self):
        # Um usuário com perfil de policial NÃO PODE ser um Agente de Pessoal, Delegado ou Admin Geral.
        # Esta propriedade não define a capacidade de conferência, apenas o tipo de cargo base.
        return self.perfil in self.POLICIA_CARGOS_NAMES

    @property
    def is_delegado(self):
        return self.perfil == 'Delegado de Polícia'

    @property
    def is_agente_pessoal(self):
        return self.perfil == 'Agente de Pessoal'
    
    @property
    def is_conferente(self): # PROPRIEDADE REVISADA: Agora baseada em unidades_atuacao
        # Um usuário é considerado 'Conferente' se não é Admin Geral, não é Agente de Pessoal,
        # e possui unidades de atuação atribuídas (indicando responsabilidade de conferência)
        # e não é um Delegado (que já é tratado por sua própria propriedade).
        # A exclusão de `is_delegado` aqui garante que a lógica de permissão de delegado não se sobreponha a este.
        return (not self.is_administrador_geral and 
                not self.is_agente_pessoal and
                not self.is_delegado and
                self.unidades_atuacao.exists())

    @property
    def is_administrador_geral(self):
        return self.perfil == 'Administrador Geral'

class CodigoOcorrencia(models.Model):
    codigo = models.CharField(max_length=10, unique=True) 
    denominacao = models.CharField(max_length=255)
    descricao_completa = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.codigo} - {self.denominacao}"

class FolhaPonto(models.Model):
    TRIMESTRE_CHOICES = [
        (1, '1º Trimestre (Jan-Fev-Mar)'),
        (2, '2º Trimestre (Abr-Mai-Jun)'),
        (3, '3º Trimestre (Jul-Ago-Set)'),
        (4, '4º Trimestre (Out-Nov-Dez)'),
    ]
    
    STATUS_CHOICES = [
        ('Em Andamento', 'Em Andamento'),
        ('Concluída', 'Concluída'),
        ('Arquivada', 'Arquivada'),
    ]
    servidor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='folhas_ponto')
    trimestre = models.IntegerField(choices=TRIMESTRE_CHOICES)
    ano = models.IntegerField()
    unidade_id_geracao = models.ForeignKey(Unidade, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Em Andamento')
    data_geracao = models.DateTimeField(auto_now_add=True)
    ativa = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    def __str__(self):
        return f"Folha de {self.servidor.nome} - {self.get_trimestre_display()} de {self.ano}"

    def update_status(self):
        # Se a folha está arquivada, não muda o status automaticamente
        if self.status == 'Arquivada':
            return

        # Verifica se há dias com ocorrência 'Livre' e não assinados pelo servidor
        # Assumindo que 'LIVRE' é o código para dias que precisam de assinatura
        pendencia_assinatura = self.dias.filter(
            codigo__codigo__iexact='Livre', 
            servidor_assinou=False
        ).exists()

        # Verifica se há dias não conferidos pelo delegado
        # (Não importa se assinado ou não para a conferência do delegado, conforme nova regra)
        pendencia_conferencia = self.dias.filter(
            delegado_conferiu=False
        ).exists()


        # Se não há pendências de assinatura E não há pendências de conferência, a folha está concluída
        if not pendencia_assinatura and not pendencia_conferencia:
            if self.status != 'Concluída':
                self.status = 'Concluída'
                self.save(update_fields=['status'])
        else:
            # Se há qualquer pendência, e o status era 'Concluída', volta para 'Em Andamento'
            if self.status == 'Concluída': # Só altera se estiver "Concluída" para evitar loops com "Em Andamento"
                self.status = 'Em Andamento'
                self.save(update_fields=['status'])


class DiaPonto(models.Model):
    folha = models.ForeignKey(FolhaPonto, on_delete=models.CASCADE, related_name='dias')
    data_dia = models.DateField()
    codigo = models.ForeignKey(CodigoOcorrencia, on_delete=models.SET_NULL, null=True)
    servidor_assinou = models.BooleanField(default=False)
    data_assinatura_servidor = models.DateField(null=True, blank=True)
    delegado_conferiu = models.BooleanField(default=False)
    delegado = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='dias_conferidos')
    data_conferencia = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Dia {self.data_dia} para {self.folha.servidor.nome}"

class Transferencia(models.Model):
    servidor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='transferencias')
    unidade_origem = models.ForeignKey(Unidade, on_delete=models.SET_NULL, null=True, related_name='transferencias_saida')
    unidade_destino = models.ForeignKey(Unidade, on_delete=models.SET_NULL, null=True, related_name='transferencias_entrada')
    data_transferencia = models.DateField()
    agente_responsavel = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='transferencias_realizadas')
    data_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transferência de {self.servidor.nome} para {self.unidade_destino.nome_unidade} em {self.data_transferencia}"

class LogAuditoria(models.Model):
    acao = models.CharField(max_length=100, db_index=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_de_auditoria')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    detalhes = models.JSONField(default=dict)
    data_hora = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        # Verifica se o usuário é nulo (pode ocorrer para ações do sistema)
        nome_usuario = self.usuario.nome if self.usuario else "Sistema"
        return f"{self.data_hora.strftime('%d/%m/%Y %H:%M')} - {nome_usuario} - {self.acao}"

    class Meta:
        ordering = ['-data_hora']
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"