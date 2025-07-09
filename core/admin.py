# core/admin.py (CORRIGIDO)

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import Unidade, Usuario, CodigoOcorrencia, FolhaPonto, DiaPonto, Transferencia

class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ('id_funcional', 'nome', 'email', 'perfil', 'lotacao', 'unidades_gerenciadas')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["id_funcional"])
        user.username = self.cleaned_data["id_funcional"] # Garante que o campo username (herdado) seja o id_funcional
        if commit:
            user.save()
            self.save_m2m()
        return user

class UsuarioAdmin(UserAdmin):
    add_form = CustomUserCreationForm

    list_display = ('id_funcional', 'nome', 'perfil', 'lotacao', 'unidades_gerenciadas_display', 'ativo', 'is_staff')
    list_filter = ('perfil', 'lotacao', 'ativo')
    search_fields = ('nome', 'id_funcional')
    ordering = ('nome',)
    actions = ['reset_password_to_id']
    
    fieldsets = (
        (None, {'fields': ('id_funcional', 'password')}),
        ('Informações Pessoais', {'fields': ('nome', 'email')}),
        ('Status e Lotação', {'fields': ('perfil', 'lotacao', 'unidades_gerenciadas', 'ativo', 'status_servidor', 'primeiro_login', 'data_inativacao')}),
        ('Permissões Django', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions'), 'classes': ('collapse',)}),
        ('Datas Importantes', {'fields': ('date_joined', 'last_login'), 'classes': ('collapse',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('id_funcional', 'nome', 'email', 'perfil', 'lotacao', 'unidades_gerenciadas'),
        }),
    )

    filter_horizontal = ('unidades_gerenciadas',) # Permite gerenciar M2M para unidades gerenciadas no admin

    def unidades_gerenciadas_display(self, obj):
        return ", ".join([unidade.nome_unidade for unidade in obj.unidades_gerenciadas.all()])
    unidades_gerenciadas_display.short_description = 'Unidades Gerenciadas'
    
    @admin.action(description="Redefinir senha para ID Funcional")
    def reset_password_to_id(self, request, queryset):
        for user in queryset:
            user.set_password(user.id_funcional)
            user.primeiro_login = True # Define como primeiro login para forçar a troca na próxima vez
            user.save()
        self.message_user(request, "A senha dos usuários selecionados foi redefinida com sucesso. Eles serão forçados a alterar a senha no próximo login.", messages.SUCCESS)

admin.site.register(Unidade)
admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(CodigoOcorrencia)
admin.site.register(FolhaPonto)
admin.site.register(DiaPonto)
admin.site.register(Transferencia)