# ARQUIVO: core/views/agente/pdf_views.py

import io
import os
import pathlib
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from weasyprint import HTML

from core.models import FolhaPonto
from core.forms import GerarPdfUnidadeForm
from core.utils import preparar_dados_para_pdf, get_meses_trimestre, MESES_PT_BR

def agente_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.perfil != 'Agente de Pessoal':
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('core:agente_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@agente_required
def gerar_pdf_unidade_view(request):
    if request.method == 'POST':
        form = GerarPdfUnidadeForm(request.POST, user=request.user)
        if form.is_valid():
            unidade = form.cleaned_data['unidade']
            ano = form.cleaned_data['ano']
            trimestre = int(form.cleaned_data['trimestre'])
            
            folhas = FolhaPonto.objects.filter(
                servidor__lotacao=unidade, 
                servidor__ativo=True,
                servidor__lotacao__in=request.user.unidades_gerenciadas.all(),
                ano=ano, 
                trimestre=trimestre
            ).select_related('servidor', 'servidor__lotacao').order_by('servidor__nome')

            if not folhas.exists(): 
                messages.error(request, "Nenhuma folha de ponto encontrada para os filtros selecionados ou você não tem permissão para gerar o PDF desta unidade/período.")
                return redirect('core:gerar_pdf_unidade')

            dados_relatorio = []
            for folha in folhas:
                linhas_tabela = preparar_dados_para_pdf(folha)
                numeros_meses = get_meses_trimestre(folha.trimestre)
                nomes_meses = [MESES_PT_BR.get(m, '') for m in numeros_meses]

                dados_relatorio.append({
                    'folha': folha,
                    'linhas_tabela': linhas_tabela,
                    'meses': nomes_meses
                })
            
            imagem_uri = request.build_absolute_uri(settings.STATIC_URL + 'img/logo_pcerj.jpg')
            
            # ALTERAÇÃO AQUI: Passando o nome do trimestre para o contexto
            trimestre_display_name = dict(FolhaPonto.TRIMESTRE_CHOICES).get(trimestre)

            context = {
                'dados_relatorio': dados_relatorio,
                'unidade': unidade,
                'ano': ano,
                'trimestre_display': trimestre_display_name, # Variável adicionada
                'imagem_path': imagem_uri,
                'titulo_pdf': f"Relatório de Frequência - {unidade.nome_unidade}"
            }
            
            html_string = render_to_string('core/impressao_ponto_unidade.html', context)
            pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
            
            response = HttpResponse(pdf_file, content_type='application/pdf')
            filename = f"folhas_{unidade.nome_unidade}_{ano}_{trimestre}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    else: 
        form = GerarPdfUnidadeForm(user=request.user)
    return render(request, 'core/agente_gerar_pdf_unidade.html', {'form': form})

@login_required
def gerar_pdf_individual_view(request, folha_id):
    folha = get_object_or_404(FolhaPonto, id=folha_id)
    
    if request.user != folha.servidor and \
       not (request.user.perfil == 'Agente de Pessoal' and folha.servidor.lotacao in request.user.unidades_gerenciadas.all()):
        messages.error(request, "Você não tem permissão para gerar este PDF.")
        return redirect('core:dashboard')
    
    linhas_tabela = preparar_dados_para_pdf(folha)
    numeros_meses = get_meses_trimestre(folha.trimestre)
    nomes_meses = [MESES_PT_BR.get(m, '') for m in numeros_meses]
    
    imagem_uri = request.build_absolute_uri(settings.STATIC_URL + 'img/logo_pcerj.jpg')

    context = {
        'folha': folha,
        'linhas_tabela': linhas_tabela,
        'meses': nomes_meses,
        'imagem_path': imagem_uri,
        'titulo_pdf': f"Folha de Ponto - {folha.servidor.nome}"
    }
    
    html_string = render_to_string('core/impressao_ponto_individual.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"folha_ponto_{folha.servidor.id_funcional}_{folha.ano}_{folha.trimestre}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"' 
    return response