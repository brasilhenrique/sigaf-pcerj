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
        user.username = id_funcional 
        user.save(using=self._db)
        return user

    def create_superuser(self, id_funcional, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('perfil', 'Administrador Geral')
        extra_fields.setdefault('nome', 'Administrador do Sistema')
        
        return self.create_user(id_funcional, password, **extra_fields)

class Usuario(AbstractUser):
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

    POLICIA_CARGOS_NAMES = [cargo[0] for cargo in POLICIA_CARGOS]

    PERFIS_FUNCIONAL = [
        ('Delegado de Polícia', 'Delegado de Polícia'), 
        ('Agente de Pessoal', 'Agente de Pessoal'),
        ('Administrador Geral', 'Administrador Geral'),
    ]

    PERFIL_CHOICES = POLICIA_CARGOS + PERFIS_FUNCIONAL 
    
    STATUS_CHOICES = [
        ('Ativo', 'Ativo'),
        ('Aposentado', 'Aposentado'),
        ('Demitido', 'Demitido'),
        ('Exonerado', 'Exonerado'),
        ('Licenciado', 'Licenciado'),
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
    
    unidades_atuacao = models.ManyToManyField(
        Unidade,
        blank=True,
        verbose_name="Unidades de Atuação (Gerência/Conferência)",
        help_text="Selecione as unidades pelas quais este usuário pode ser responsável por gerência (Agente de Pessoal) ou conferência de folhas (Delegado de Polícia/Servidor-Conferente)."
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

    @property
    def is_policia_cargo(self):
        return self.perfil in self.POLICIA_CARGOS_NAMES

    @property
    def is_delegado(self):
        return self.perfil == 'Delegado de Polícia'

    @property
    def is_agente_pessoal(self):
        return self.perfil == 'Agente de Pessoal'
    
    @property
    def is_conferente(self): 
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
    
    # NOVO CAMPO: Snapshot do cargo para histórico
    cargo_servidor_na_folha = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cargo na Época")

    def __str__(self):
        return f"Folha de {self.servidor.nome} - {self.get_trimestre_display()} de {self.ano}"

    def save(self, *args, **kwargs):
        # Se o campo estiver vazio e o servidor existir, preenche com o perfil atual
        if not self.cargo_servidor_na_folha and self.servidor:
            self.cargo_servidor_na_folha = self.servidor.perfil
        super().save(*args, **kwargs)

    def update_status(self):
        if self.status == 'Arquivada':
            return

        pendencia_assinatura = self.dias.filter(
            codigo__codigo__iexact='Livre', 
            servidor_assinou=False
        ).exists()

        pendencia_conferencia = self.dias.filter(
            delegado_conferiu=False
        ).exists()


        if not pendencia_assinatura and not pendencia_conferencia:
            if self.status != 'Concluída':
                self.status = 'Concluída'
                self.save(update_fields=['status'])
        else:
            if self.status == 'Concluída': 
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
        nome_usuario = self.usuario.nome if self.usuario else "Sistema"
        return f"{self.data_hora.strftime('%d/%m/%Y %H:%M')} - {nome_usuario} - {self.acao}"

    class Meta:
        ordering = ['-data_hora']
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"