import calendar
from datetime import date
from .models import DiaPonto, CodigoOcorrencia, LogAuditoria, FolhaPonto

MESES_PT_BR = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

def get_meses_trimestre(trimestre):
    trimestres = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}
    return trimestres.get(trimestre, tuple())

def preparar_dados_para_web(folha, dias_da_folha=None):
    dados_formatados = []
    numeros_meses = get_meses_trimestre(folha.trimestre)
    if dias_da_folha is None:
        dias_da_folha = DiaPonto.objects.filter(folha=folha).order_by('data_dia').select_related('codigo', 'delegado')
    
    dias_por_mes_map = {mes_num: [d for d in dias_da_folha if d.data_dia.month == mes_num] for mes_num in numeros_meses}

    for mes_num in numeros_meses:
        dias_do_mes = dias_por_mes_map.get(mes_num, [])
        dados_mes = {
            'nome_mes': MESES_PT_BR.get(mes_num, ''), 
            'mes_num': mes_num,
            'dias': dias_do_mes
        }
        dados_formatados.append(dados_mes)
    return dados_formatados

def preparar_dados_para_pdf(folha):
    dados_por_dia = {mes_num: {i: None for i in range(1, 32)} for mes_num in get_meses_trimestre(folha.trimestre)}
    meses_do_trimestre = get_meses_trimestre(folha.trimestre)
    dias_da_folha = DiaPonto.objects.filter(folha=folha).select_related('codigo', 'delegado').order_by('data_dia')

    for dia_obj in dias_da_folha:
        mes, dia = dia_obj.data_dia.month, dia_obj.data_dia.day
        if mes in dados_por_dia and dia <= calendar.monthrange(folha.ano, mes)[1]:
             dados_por_dia[mes][dia] = dia_obj
    
    linhas_tabela = []
    for dia_num in range(1, 32):
        linha_atual = {'dia': str(dia_num).zfill(2), 'meses': []}
        
        algum_dia_existe_nesta_linha = False

        for mes_num in meses_do_trimestre:
            if dia_num > calendar.monthrange(folha.ano, mes_num)[1]:
                linha_atual['meses'].append(None)
            else:
                dia_obj = dados_por_dia[mes_num].get(dia_num)
                linha_atual['meses'].append(dia_obj)
                if dia_obj is not None:
                    algum_dia_existe_nesta_linha = True
        
        if algum_dia_existe_nesta_linha:
            linhas_tabela.append(linha_atual)

    return linhas_tabela

def popular_dias_folha(folha_ponto_instance):
    try:
        cod_livre = CodigoOcorrencia.objects.get(codigo__iexact='Livre')
        cod_sabado = CodigoOcorrencia.objects.get(codigo__iexact='SÁBADO')
        cod_domingo = CodigoOcorrencia.objects.get(codigo__iexact='DOMINGO')
    except CodigoOcorrencia.DoesNotExist:
        print("Erro: Códigos de ocorrência padrão (Livre, SÁBADO, DOMINGO) não encontrados.")
        return []
        
    meses_do_trimestre = get_meses_trimestre(folha_ponto_instance.trimestre)
    ano = folha_ponto_instance.ano
    dias_a_criar = []
    for mes in meses_do_trimestre:
        num_dias_no_mes = calendar.monthrange(ano, mes)[1]
        for dia in range(1, num_dias_no_mes + 1):
            data_atual = date(ano, mes, dia)
            dia_da_semana = data_atual.weekday()
            
            codigo_padrao = cod_livre
            if dia_da_semana == 5:
                codigo_padrao = cod_sabado
            elif dia_da_semana == 6:
                codigo_padrao = cod_domingo
            
            dias_a_criar.append(DiaPonto(folha=folha_ponto_instance, data_dia=data_atual, codigo=codigo_padrao))
    
    if dias_a_criar:
        DiaPonto.objects.bulk_create(dias_a_criar)
    return dias_a_criar

# LISTA RESTRITIVA DE AÇÕES DE AUDITORIA ESSENCIAIS (FOCO EM IRREVERSÍVEL)
ACOES_DE_AUDITORIA_ESSENCIAIS = [
    'DELETE_USUARIO_PERMANENTE',      # Exclusão PERMANENTE de usuário
    'DELETE_FOLHA_PERMANENTE',        # Exclusão PERMANENTE de folha
    'DELETE_UNIDADE_PERMANENTE',      # Exclusão PERMANENTE de unidade
    'USER_TRANSFER',                  # Transferência de usuário
    'DELETAR_FOLHA',                  # Exclusão (não permanente) de folha por agente
    'PASSWORD_CHANGE_SUCCESS',        # Troca de senha
    'CRIAR_FOLHA_MANUAL',             # Criação manual de folha por agente
    # As ações abaixo foram removidas para tornar o log mais restritivo
    # 'LOGIN_FAILURE',
    # 'FIRST_LOGIN_REDIRECT',
    # 'USER_CREATE_BY_AGENTE',
    # 'USER_CREATE_BY_ADMIN',
    # 'USER_EDIT_BY_AGENTE',
    # 'USER_EDIT_BY_ADMIN',
    # 'USER_INACTIVATE_BY_AGENTE',
    # 'USER_REACTIVATE_BY_AGENTE',
    # 'BLOQUEIO_DIA',
    # 'BLOQUEIO_LOTE',
    # 'ARQUIVAR_FOLHA',
    # 'DESARQUIVAR_FOLHA',
    # 'ARQUIVAR_FOLHA_LOTE',
    # 'LOGOUT',
    # 'LOGIN_SUCCESS',
    # 'UNIDADE_ATIVADA',
    # 'UNIDADE_INATIVADA',
    # 'AGENTE_ATIVADO',
    # 'AGENTE_INATIVADO',
    # 'USUARIO_ATIVADO',
    # 'USUARIO_INATIVADO',
    # 'UNIDADE_CRIADA', # Nova adição para registro de criação de unidade
    # 'UNIDADE_EDITADA', # Nova adição para registro de edição de unidade
    # 'AGENTE_CRIADO', # Nova adição para registro de criação de agente
    # 'AGENTE_EDITADO', # Nova adição para registro de edição de agente
    # 'USER_EDIT_BY_ADMIN', # Nova adição para registro de edição de usuario por admin
    # 'USER_CREATE_BY_ADMIN', # Nova adição para registro de criação de usuario por admin
]

def registrar_log(request, acao, detalhes=None, ip_address=None):
    if acao not in ACOES_DE_AUDITORIA_ESSENCIAIS:
        return

    usuario_logado = request.user if request.user.is_authenticated else None
    
    if not ip_address and request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
    
    print(f"--- DEBUG: registrar_log ---") # DEBUG
    print(f"Ação: {acao}") # DEBUG
    print(f"Usuário Logado: {usuario_logado.id_funcional if usuario_logado else 'Sistema'}") # DEBUG
    print(f"Detalhes recebidos: {detalhes}") # DEBUG
    print(f"Tipo dos Detalhes: {type(detalhes)}") # DEBUG

    LogAuditoria.objects.create(usuario=usuario_logado, acao=acao, detalhes=detalhes if detalhes is not None else {}, ip_address=ip_address)
    print(f"Log de Auditoria criado com sucesso para ação '{acao}'.") # DEBUG
    print(f"----------------------------") # DEBUG