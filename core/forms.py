# ARQUIVO: core/forms.py (VERSÃO CORRIGIDA FINAL PARA ATRIBUIÇÃO DE CONFERENTE E DELEGADO POR AGENTE)

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm, UserChangeForm
from .models import FolhaPonto, Usuario, Unidade, CodigoOcorrencia, Transferencia
from datetime import date
import re 

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
        if user and user.perfil == 'Agente de Pessoal':
            self.fields['servidor'].queryset = Usuario.objects.filter(
                lotacao__in=user.unidades_atuacao.all(), 
                ativo=True
            ).exclude(
                perfil__in=['Administrador Geral', 'Delegado de Polícia']
            ).order_by('nome')
        else: 
            self.fields['servidor'].queryset = Usuario.objects.filter(
                ativo=True
            ).exclude(
                perfil__in=['Administrador Geral', 'Delegado de Polícia']
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

class UsuarioCreationForm(forms.ModelForm): # Para Agente de Pessoal criar usuários comuns
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades para Conferência" # Label mais direto
    )

    class Meta:
        model = Usuario
        fields = ['id_funcional', 'nome', 'email', 'perfil', 'lotacao', 'unidades_atuacao']
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): 
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-control'
        
        if 'lotacao' in self.fields and request and request.user.is_authenticated:
            if request.user.perfil == 'Agente de Pessoal':
                sorted_unidades_lotacao = sorted(request.user.unidades_atuacao.filter(ativo=True), key=custom_sort_key)
                self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]
            else: # Admin Geral ou outros perfis
                sorted_unidades_lotacao = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
                self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]

        # MODIFICAÇÃO CHAVE: Incluir 'Delegado de Polícia' nas opções de perfil para o Agente de Pessoal
        if 'perfil' in self.fields:
            # O Agente só pode criar policiais (cargos) ou Delegados.
            # A atribuição de Conferente será feita via unidades_atuacao, não via perfil principal.
            self.fields['perfil'].choices = Usuario.POLICIA_CARGOS + [('Delegado de Polícia', 'Delegado de Polícia')]


    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.pk or not user.password: 
            user.set_password(user.id_funcional)
        user.username = user.id_funcional
        
        # O is_staff deve ser False para um novo servidor comum,
        # independentemente das unidades de atuação, a menos que seja delegado
        if user.perfil != 'Delegado de Polícia': # Delegados podem precisar de is_staff para o Admin Django
            user.is_staff = False

        if commit: 
            user.save()
            self.save_m2m() # Salva as relações ManyToMany, como 'unidades_atuacao'
        return user

class UsuarioChangeForm(forms.ModelForm): # Para Agente de Pessoal editar usuários comuns
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades para Conferência" # Label mais direto
    )
    class Meta:
        model = Usuario
        fields = ['nome', 'email', 'perfil', 'lotacao', 'status_servidor', 'unidades_atuacao']
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): 
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-control'
        
        if 'lotacao' in self.fields:
            if request and request.user.perfil == 'Agente de Pessoal':
                sorted_unidades_lotacao = sorted(request.user.unidades_atuacao.filter(ativo=True), key=custom_sort_key)
                self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]
            else:
                sorted_unidades_lotacao = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
                self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]

        # MODIFICAÇÃO CHAVE: Incluir 'Delegado de Polícia' nas opções de perfil para o Agente de Pessoal
        if 'perfil' in self.fields:
            self.fields['perfil'].choices = Usuario.POLICIA_CARGOS + [('Delegado de Polícia', 'Delegado de Polícia')]


class TransferenciaForm(forms.ModelForm):
    class Meta:
        model = Transferencia
        fields = ['unidade_destino', 'data_transferencia']
        widgets = {'data_transferencia': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidade_destino'].choices = [(u.pk, u.nome_unidade) for u in sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)]
        self.fields['unidade_destino'].widget.attrs.update({'class': 'form-control'})

class GerarPdfUnidadeForm(forms.Form):
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.all(), label="Unidade", widget=forms.Select(attrs={'class': 'form-control'}))
    ano = forms.IntegerField(initial=date.today().year, label="Ano", widget=forms.NumberInput(attrs={'class': 'form-control'}))
    trimestre = forms.TypedChoiceField(choices=FolhaPonto.TRIMESTRE_CHOICES, coerce=int, label="Trimestre", widget=forms.Select(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.perfil == 'Agente de Pessoal':
            sorted_unidades = sorted(user.unidades_atuacao.filter(ativo=True), key=custom_sort_key)
        elif user and user.perfil == 'Delegado de Polícia': 
            sorted_unidades = sorted(Unidade.objects.filter(pk=user.lotacao.pk), key=custom_sort_key) if user.lotacao else []
        else: 
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
        self.fields['unidade'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]


class UnidadeForm(forms.ModelForm):
    class Meta:
        model = Unidade
        fields = ['nome_unidade', 'codigo_ua', 'ativo']
        widgets = {
            'nome_unidade': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_ua': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 126000000000000'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

# --- FORMS PARA ADMIN GERAL ---
class AdminAgenteCreationForm(forms.ModelForm):
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades de Atuação (Gerência/Conferência)" # Revertido para o label original completo
    )
    class Meta:
        model = Usuario
        fields = ['id_funcional', 'nome', 'email', 'lotacao', 'unidades_atuacao']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple): 
                field.widget.attrs['class'] = 'form-control'
            
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
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades de Atuação (Gerência/Conferência)" # Revertido para o label original completo
    )
    class Meta:
        model = Usuario
        fields = ['nome', 'email', 'lotacao', 'unidades_atuacao', 'ativo', 'status_servidor']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple): 
                field.widget.attrs['class'] = 'form-control'
        
        if 'lotacao' in self.fields:
            sorted_unidades_lotacao = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]

class AdminUsuarioCreationForm(forms.ModelForm): # Para Admin Geral criar usuários comuns (cargos policiais)
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades de Atuação (para Conferente)"
    )
    class Meta:
        model = Usuario
        fields = ('id_funcional', 'nome', 'email', 'perfil', 'lotacao', 'unidades_atuacao')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): 
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-control'
        
        if 'lotacao' in self.fields:
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), 
            key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]
        
        # O Admin Geral pode criar qualquer perfil listado em POLICIA_CARGOS.
        # Adiciona a opção de criar um Delegado, e também um Agente de Pessoal,
        # mas não "Conferente" como perfil principal, pois é uma atribuição.
        if 'perfil' in self.fields:
            self.fields['perfil'].choices = Usuario.POLICIA_CARGOS + [
                ('Delegado de Polícia', 'Delegado de Polícia'),
                ('Agente de Pessoal', 'Agente de Pessoal'),
            ]


    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(user.id_funcional)
        user.username = user.id_funcional

        # Garante que is_staff seja False para perfis comuns, a menos que explicitamente marcado no Admin Django.
        # Apenas Administrador Geral e Delegado de Polícia devem ter is_staff = True por padrão.
        if user.perfil not in ['Administrador Geral', 'Delegado de Polícia']:
            user.is_staff = False

        if commit:
            user.save()
            self.save_m2m() # Salva as relações ManyToMany, como 'unidades_atuacao'
        return user

class AdminUsuarioChangeForm(UserChangeForm): # Para Admin Geral editar usuários comuns (cargos policiais)
    password = None 
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades de Atuação (para Conferente)"
    )

    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = ('nome', 'email', 'perfil', 'lotacao', 'ativo', 'status_servidor', 'unidades_atuacao')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): 
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-control'
      
        if 'lotacao' in self.fields:
            sorted_unidades = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades]
            
        # O Admin Geral pode editar qualquer perfil listado em POLICIA_CARGOS.
        # Adiciona a opção de editar para Delegado e Agente de Pessoal.
        if 'perfil' in self.fields:
            self.fields['perfil'].choices = Usuario.POLICIA_CARGOS + [
                ('Delegado de Polícia', 'Delegado de Polícia'),
                ('Agente de Pessoal', 'Agente de Pessoal'),
            ]


class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['nome', 'email']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items(): field.widget.attrs['class'] = 'form-control'

# --- NOVOS FORMS PARA ADMIN GERAL: GESTÃO DE DELEGADOS ---
class AdminDelegadoCreationForm(forms.ModelForm):
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades para Conferência"
    )
    class Meta:
        model = Usuario
        fields = ['id_funcional', 'nome', 'email', 'lotacao', 'unidades_atuacao']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-control'
            
        if 'lotacao' in self.fields:
            sorted_unidades_lotacao = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.pk or not user.password:
            user.set_password(user.id_funcional)
        user.perfil = 'Delegado de Polícia'
        user.username = user.id_funcional
        
        print("\n--- DEPURAÇÃO: AdminDelegadoCreationForm.save() ---")
        print(f"Commit é {commit}")
        print(f"User instance antes do save principal: {user}")
        print(f"User PK antes do save principal: {user.pk}")
        print(f"unidades_atuacao na cleaned_data (dentro do form.save): {self.cleaned_data.get('unidades_atuacao')}")
        # --- FIM DEPURAÇÃO ---

        if commit:
            user.save()
            print(f"User instance APÓS save principal: {user}")
            print(f"User PK APÓS save principal: {user.pk}")
            print(f"Chamando self.save_m2m() em {self.__class__.__name__}")
            self.save_m2m() # AQUI é onde o M2M é salvo
        return user

class AdminDelegadoChangeForm(forms.ModelForm):
    unidades_atuacao = forms.ModelMultipleChoiceField(
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), 
        required=False,
        label="Unidades para Conferência"
    )
    class Meta:
        model = Usuario
        fields = ['nome', 'email', 'lotacao', 'unidades_atuacao', 'ativo', 'status_servidor']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-control'
            
        if 'lotacao' in self.fields:
            sorted_unidades_lotacao = sorted(Unidade.objects.filter(ativo=True), key=custom_sort_key)
            self.fields['lotacao'].choices = [(u.pk, u.nome_unidade) for u in sorted_unidades_lotacao]

# NOVO FORMULÁRIO: AtribuirConferenteForm
# ATENÇÃO: Este formulário será usado APENAS para a tela de "Gestão de Conferentes" do Agente de Pessoal,
# onde ele pode adicionar/remover atribuições de conferência para usuários existentes.
# O perfil primário do usuário NÃO é alterado por este formulário.
class AtribuirConferenteForm(forms.ModelForm): 
    unidades_atuacao = forms.ModelMultipleChoiceField( 
        queryset=Unidade.objects.filter(ativo=True).order_by('nome_unidade'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Unidades para Conferência"
    )
    
    class Meta: 
        model = Usuario
        # Apenas o campo unidades_atuacao será editado por este formulário.
        # O perfil do usuário NÃO será definido aqui.
        fields = ['unidades_atuacao']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidades_atuacao'].queryset = Unidade.objects.filter(ativo=True).order_by('nome_unidade')