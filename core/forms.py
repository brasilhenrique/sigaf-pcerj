# ARQUIVO: core/forms.py (VERSÃO CORRIGIDA FINAL - Adicionado queryset inicial)

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm, UserChangeForm
from .models import FolhaPonto, Usuario, Unidade, CodigoOcorrencia, Transferencia
from datetime import date
import re # Importar re para a função de ordenação

# Função de ordenação personalizada para unidades
def custom_sort_key(unidade):
    match = re.match(r'^(\d+)', unidade.nome_unidade)
    if match:
        return (int(match.group(1)), unidade.nome_unidade)
    else:
        return (float('inf'), unidade.nome_unidade)

# FORMULÁRIOS DE AUTENTICAÇÃO
class ChangePasswordForm(PasswordChangeForm):
    old_password = forms.CharField(label="Senha Antiga", strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'autofocus': True, 'class': 'form-control'}))
    new_password1 = forms.CharField(label="Nova Senha", strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}))
    new_password2 = forms.CharField(label="Confirmação da Nova Senha", strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}))

# FORMULÁRIOS DO MÓDULO AGENTE DE PESSOAL
class CriarFolhaManualForm(forms.ModelForm):
    ano = forms.IntegerField(initial=date.today().year, label="Ano", widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2025'}))
    class Meta:
        model = FolhaPonto
        fields = ['servidor', 'ano', 'trimestre']
        widgets = {'servidor': forms.Select(attrs={'class': 'form-control select2'}), 'trimestre': forms.Select(attrs={'class': 'form-control'})}
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # MANTEM A ORDENAÇÃO POR NOME PARA SERVIDORES (que não são unidades)
        if user and user.perfil == 'Agente de Pessoal':
            self.fields['servidor'].queryset = Usuario.objects.filter(
                lotacao__in=user.unidades_gerenciadas.all(), 
                ativo=True,
                perfil__in=['Servidor', 'Delegado', 'Agente de Pessoal']
            ).order_by('nome')
        else:
            self.fields['servidor'].queryset = Usuario.objects.filter(
                ativo=True,
                perfil__in=['Servidor', 'Delegado', 'Agente de Pessoal']
            ).order_by('nome')


    def clean(self):
        cleaned_data = super().clean()
        servidor = cleaned_data.get('servidor')
        ano = cleaned_data.get('ano')
        trimestre = cleaned_data.get('trimestre')

        if servidor and ano and trimestre:
            if FolhaPonto.objects.filter(servidor=servidor, ano=ano, trimestre=trimestre).exists():
                raise forms.ValidationError(f"Já existe uma folha de ponto para {servidor.nome} no {trimestre}º trimestre de {ano}.")
        return cleaned_data

class AplicarOcorrenciaLoteForm(forms.Form):
    codigo_lote = forms.ModelChoiceField(queryset=CodigoOcorrencia.objects.exclude(codigo__in=['Livre', 'SÁBADO', 'DOMINGO']), label="Ocorrência", empty_label="--- Selecione ---", widget=forms.Select(attrs={'class': 'form-control'}), required=True)
    data_inicio_lote = forms.DateField(label="Data de Início", widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=True)
    data_fim_lote = forms.DateField(label="Data de Fim", widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=True)

class UsuarioCreationForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['id_funcional', 'nome', 'email', 'perfil', 'lotacao']
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): 
            field.widget.attrs['class'] = 'form-control'
        
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA LOTAÇÃO USANDO CHOICES
        if 'lotacao' in self.fields:
            if request and request.user.perfil == 'Agente de Pessoal':
                sorted_unidades = sorted(request.user.unidades_gerenciadas.filter(ativo=True), key=custom_sort_key)
            else:
                sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            # Converte a lista de objetos Unidade em uma lista de tuplas (ID, Nome) para choices
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]


    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.pk or not user.password: 
            user.set_password(user.id_funcional)
        user.username = user.id_funcional
        if commit: 
            user.save()
        return user

class UsuarioChangeForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['nome', 'email', 'perfil', 'lotacao', 'status_servidor']
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): field.widget.attrs['class'] = 'form-control'
        
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA LOTAÇÃO USANDO CHOICES
        if 'lotacao' in self.fields:
            if request and request.user.perfil == 'Agente de Pessoal':
                sorted_unidades = sorted(request.user.unidades_gerenciadas.filter(ativo=True), key=custom_sort_key)
            else:
                sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]


class TransferenciaForm(forms.ModelForm):
    class Meta:
        model = Transferencia
        fields = ['unidade_destino', 'data_transferencia']
        widgets = {'data_transferencia': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA UNIDADE_DESTINO USANDO CHOICES
        self.fields['unidade_destino'].choices = [(u.pk, u.nome_unidade) for u in sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)]
        self.fields['unidade_destino'].widget.attrs.update({'class': 'form-control'})

class GerarPdfUnidadeForm(forms.Form):
    # ADICIONADO: queryset inicial para ModelChoiceField
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.all(), label="Unidade", widget=forms.Select(attrs={'class': 'form-control'}))
    ano = forms.IntegerField(initial=date.today().year, label="Ano", widget=forms.NumberInput(attrs={'class': 'form-control'}))
    trimestre = forms.TypedChoiceField(choices=FolhaPonto.TRIMESTRE_CHOICES, coerce=int, label="Trimestre", widget=forms.Select(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA UNIDADE USANDO CHOICES
        if user and user.perfil == 'Agente de Pessoal':
            sorted_unidades = sorted(user.unidades_gerenciadas.all(), key=custom_sort_key)
        else: # Para Admin Geral
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
        self.fields['unidade'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]


class UnidadeForm(forms.ModelForm):
    class Meta:
        model = Unidade
        fields = ['nome_unidade', 'ativo']
        widgets = {'nome_unidade': forms.TextInput(attrs={'class': 'form-control'}), 'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'})}

class AdminAgenteCreationForm(forms.ModelForm):
    # ADICIONADO: queryset inicial para ModelMultipleChoiceField
    unidades_gerenciadas = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.all(), # Queryset inicial
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Unidades Gerenciadas"
    )
    class Meta:
        model = Usuario
        fields = ['id_funcional', 'nome', 'email', 'lotacao', 'unidades_gerenciadas']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple): 
                field.widget.attrs['class'] = 'form-control'
        
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA AMBOS OS CAMPOS USANDO CHOICES
        if 'unidades_gerenciadas' in self.fields:
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['unidades_gerenciadas'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]
            
        if 'lotacao' in self.fields:
            sorted_unidades_lotacao = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]


    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.pk or not user.password: 
            user.set_password(user.id_funcional)
        user.perfil = 'Agente de Pessoal' 
        user.username = user.id_funcional
        if commit: 
            user.save()
            self.save_m2m()
        return user

class AdminAgenteChangeForm(forms.ModelForm):
    # ADICIONADO: queryset inicial para ModelMultipleChoiceField
    unidades_gerenciadas = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.all(), # Queryset inicial
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Unidades Gerenciadas"
    )
    class Meta:
        model = Usuario
        fields = ['nome', 'email', 'lotacao', 'unidades_gerenciadas', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple): 
                field.widget.attrs['class'] = 'form-control'
        
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA AMBOS OS CAMPOS USANDO CHOICES
        if 'unidades_gerenciadas' in self.fields:
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['unidades_gerenciadas'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]
        
        if 'lotacao' in self.fields:
            sorted_unidades_lotacao = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]

class AdminUsuarioCreationForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ('id_funcional', 'nome', 'email', 'perfil', 'lotacao')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): 
            field.widget.attrs['class'] = 'form-control'
        
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA LOTAÇÃO USANDO CHOICES
        if 'lotacao' in self.fields:
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]
        
        # *** CORREÇÃO AQUI ***
        # Filtra as opções do campo 'perfil'
        perfil_field = self.fields.get('perfil')
        if perfil_field:
            # Obtém todas as escolhas, mas remove as que não queremos
            all_choices = dict(Usuario.PERFIL_CHOICES)
            allowed_choices = {k: v for k, v in all_choices.items() if k in ['Servidor', 'Delegado']}
            perfil_field.choices = list(allowed_choices.items())

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(user.id_funcional)
        user.username = user.id_funcional
        if commit:
            user.save()
        return user

class AdminUsuarioChangeForm(UserChangeForm):
    password = None 
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = ('nome', 'email', 'perfil', 'lotacao', 'ativo', 'status_servidor')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): field.widget.attrs['class'] = 'form-control'
        
        # APLICA A ORDENAÇÃO PERSONALIZADA PARA LOTAÇÃO USANDO CHOICES
        if 'lotacao' in self.fields:
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]

class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['nome', 'email']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): field.widget.attrs['class'] = 'form-control'