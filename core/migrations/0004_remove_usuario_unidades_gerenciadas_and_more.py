# Generated by Django 5.2.3 on 2025-07-15 12:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_folhaponto_observacoes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='usuario',
            name='unidades_gerenciadas',
        ),
        migrations.AddField(
            model_name='usuario',
            name='unidades_atuacao',
            field=models.ManyToManyField(blank=True, help_text='Selecione as unidades pelas quais este usuário pode ser responsável por gerência (Agente de Pessoal) ou conferência de folhas (Delegado de Polícia/Conferente).', to='core.unidade', verbose_name='Unidades de Atuação (Gerência/Conferência)'),
        ),
        migrations.AlterField(
            model_name='usuario',
            name='perfil',
            field=models.CharField(choices=[('Assistente I', 'Assistente I'), ('Assistente II', 'Assistente II'), ('Auxiliar Policial de Necropsia', 'Auxiliar Policial de Necropsia'), ('Comissário de Polícia', 'Comissário de Polícia'), ('Inspetor de Polícia', 'Inspetor de Polícia'), ('Investigador Policial', 'Investigador Policial'), ('Oficial de Cartório Policial', 'Oficial de Cartório Policial'), ('Perito Criminal', 'Perito Criminal'), ('Perito Legista', 'Perito Legista'), ('Perito Papiloscopista', 'Perito Papiloscopista'), ('Piloto Policial', 'Piloto Policial'), ('Técnico Policial de Necropsia', 'Técnico Policial de Necropsia'), ('Delegado de Polícia', 'Delegado de Polícia'), ('Agente de Pessoal', 'Agente de Pessoal'), ('Administrador Geral', 'Administrador Geral'), ('Conferente', 'Conferente')], default='Investigador Policial', max_length=50),
        ),
    ]
