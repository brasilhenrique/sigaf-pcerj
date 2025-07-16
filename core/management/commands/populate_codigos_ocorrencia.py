# core/management/commands/populate_codigos_ocorrencia.py

from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import CodigoOcorrencia

# Data extraída do manual e incluindo os códigos padrão do sistema.
# O 'codigo' será sempre em maiúsculas para consistência com o uso de .iexact.
# A 'denominacao' será o nome principal.
# A 'descricao_completa' será a definição.

CODIGOS_OCORRENCIA_DATA = [
    # Códigos internos padrão do sistema (cruciais para o funcionamento)
    {"codigo": "LIVRE", "denominacao": "Livre", "descricao_completa": "Dia de trabalho normal, sem ocorrências de afastamento."},
    {"codigo": "SÁBADO", "denominacao": "Sábado", "descricao_completa": "Dia de Sábado. Não se aplica para dias de trabalho com marcação de ponto."},
    {"codigo": "DOMINGO", "denominacao": "Domingo", "descricao_completa": "Dia de Domingo. Não se aplica para dias de trabalho com marcação de ponto."},

    # Códigos do Manual (já com os 012 e 013 incluídos)
    {"codigo": "002", "denominacao": "AFASTAMENTO POR LUTO", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de falecimento do cônjuge, companheiro (a), pais, filhos ou irmãos."},
    {"codigo": "003", "denominacao": "AFASTAMENTO POR CASAMENTO", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de casamento."},
    {"codigo": "004", "denominacao": "AFASTAMENTO POR LEGISLAÇÃO SANITÁRIA", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença que deva ser informada às autoridades de saúde pública."},
    {"codigo": "005", "denominacao": "AFASTAMENTO OBRIGATÓRIO POR LEI", "descricao_completa": "O servidor ficará afastado de suas funções quando for convocado para participar de algum serviço obrigatório por Lei, pelo tempo que durar a convocação."},
    {"codigo": "006", "denominacao": "AFASTAMENTO PARA JURI", "descricao_completa": "O servidor ficará afastado de suas funções quando for convocado para participar de júri, pelo tempo que durar a convocação."},
    {"codigo": "007", "denominacao": "AFASTAMENTO PARA SERVIÇO ELEITORAL", "descricao_completa": "O servidor ficará afastado de suas funções quando for convocado para participar de serviço eleitoral, pelo tempo que durar a convocação."},
    {"codigo": "008", "denominacao": "AFASTAMENTO PARA CAMPANHA ELEITORAL", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de candidatura a cargo eletivo."},
    {"codigo": "009", "denominacao": "AFASTAMENTO PARA DEPOIMENTO EM COMISSÃO DE INQUÉRITO", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de convocação para prestação de depoimento em Comissão de Inquérito Administrativo."},
    {"codigo": "010", "denominacao": "DISPENSA DE PONTO", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de participação em congressos, seminários, jornadas ou quaisquer outras formas de reunião de profissionais técnicos, especialistas, religiosos, quando considerado de interesse público."},
    {"codigo": "011", "denominacao": "FALTA ABONADA POR DOENÇA", "descricao_completa": "As faltas do servidor que ficar afastado de suas funções por motivo de doença, inclusive em pessoa da família, até o máximo até 3 (três) dias durante o mês, serão abonadas mediante apresentação de atestado ou laudo expedido pelo órgão estadual oficial competente."},
    {"codigo": "012", "denominacao": "FÉRIAS DO EXERCÍCIO", "descricao_completa": "Férias referentes ao exercício atual."},
    {"codigo": "013", "denominacao": "FÉRIAS EXERCÍCIO ANTERIOR", "descricao_completa": "Férias referentes a exercícios anteriores."},
    {"codigo": "015", "denominacao": "LICENÇA PATERNIDADE", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de nascimento de filho(a) ou adoção. Em caso de nascimento prematuro, a licença paternidade será contada a partir da alta da Unidade de Tratamento Intensivo (UTI), mesmo em caso de perda gestacional."},
    {"codigo": "016", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - INSS", "descricao_completa": "A partir do 16º dia de afastamento do servidor de suas funções, o pagamento será feito pela Previdência Social através do Auxílio Doença Previdenciário, benefício concedido ao servidor impedido de trabalhar por motivo de doença ou acidente, por período superior a 15 dias consecutivos ou intercalados dentro de 60 dias, com o mesmo CID ou CIDs relacionados."},
    {"codigo": "017", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - INICIAL SEM ALTA", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença sem previsão de alta."},
    {"codigo": "018", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - INICIAL COM ALTA", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença com previsão de alta. A licença com alta especifica o período em que o servidor estará licenciado, tendo que apresentar-se ao seu local de trabalho no dia seguinte ao término para retomar suas atividades."},
    {"codigo": "019", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - PRORROGAÇÃO SEM ALTA", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença quando ainda persistirem os motivos de seu afastamento, sem previsão de alta."},
    {"codigo": "020", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - PRORROGAÇÃO COM ALTA", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença quando ainda persistirem os motivos de seu afastamento, com previsão de alta. A licença com alta especifica o período em que o servidor estará licenciado, tendo que apresentar-se ao seu local de trabalho no dia seguinte ao término para retomar suas atividades."},
    {"codigo": "021", "denominacao": "LICENÇA ACIDENTE EM SERVIÇO", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de acidente em serviço, aquele que ocorre pelo exercício das atribuições do cargo, provocando, direta ou indiretamente, lesão corporal, perturbação funcional ou doença que determine a morte; a perda total ou parcial, permanente ou temporária, da capacidade física ou mental para o trabalho."},
    {"codigo": "022", "denominacao": "LICENÇA DOENÇA PESSOA DA FAMÍLIA", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença de pessoa da família, ascendente, descendente, colateral consanguíneo ou afim, até o 2º grau civil, cônjuge ou dependente que conste do respectivo assentamento individual, desde que prove ser indispensável sua assistência pessoal e esta não possa ser prestada simultaneamente com o exercício do cargo."},
    {"codigo": "023", "denominacao": "LICENÇA GESTANTE", "descricao_completa": "A servidora ficará afastada de suas funções por motivo de gestação ou adoção."},
    {"codigo": "025", "denominacao": "LICENÇA ALEITAMENTO", "descricao_completa": "A servidora ficará afastada de suas funções por motivo de aleitamento materno, mediante a apresentação de laudo médico emitido pelo serviço de perícia médica oficial do Estado."},
    {"codigo": "026", "denominacao": "SUSPENSÃO PREVENTIVA", "descricao_completa": "O funcionário que responder por malversação, alcance de dinheiro público ou infração de que possa resultar a pena de demissão, poderá permanecer suspenso preventivamente, a critério da autoridade que determinar a abertura do respectivo inquérito, até decisão final do processo administrativo."},
    {"codigo": "029", "denominacao": "IMPONTUALIDADE", "descricao_completa": "Se o servidor comparecer ao serviço dentro dos 60 (sessenta) minutos seguintes à hora inicial do expediente ou retirar-se sem autorização, dentro dos 60 (sessenta) minutos finais, ou, ainda, ausentar-se sem autorização por período inferior a 60 (sessenta) minutos."},
    {"codigo": "030", "denominacao": "FALTA", "descricao_completa": "Quando o servidor não comparece ao serviço injustificadamente."},
    {"codigo": "031", "denominacao": "ATRASO", "descricao_completa": "Não serão descontadas nem computadas como jornada extraordinária as variações de horário no registro de ponto não excedentes a cinco minutos, observado o limite máximo de dez minutos diários."},
    {"codigo": "035", "denominacao": "AFASTAMENTO PARA ESTUDOS", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de estudo, no exterior ou em qualquer parte do território nacional, desde que de interesse para a Administração e não ultrapasse o prazo de 12 (doze) meses."},
    {"codigo": "036", "denominacao": "AFASTAMENTO PARA MISSÃO OFICIAL", "descricao_completa": "O servidor ficará afastado de suas funções por motivo missão oficial."},
    {"codigo": "038", "denominacao": "LICENÇA MANDATO LEGIS / EXEC C VENC", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de exercício de mandato legislativo ou executivo, federal ou estadual."},
    {"codigo": "050", "denominacao": "PRISÃO 1/3", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de prisão por ordem judicial não decorrente de condenação definitiva."},
    {"codigo": "051", "denominacao": "PRISÃO 2/3", "descricao_completa": "O servidor ficará afastado de suas funções durante o cumprimento, sem perda do cargo, de pena privativa de liberdade."},
    {"codigo": "052", "denominacao": "SUSPENSÃO CONVERTIDA EM MULTA", "descricao_completa": "Quando houver conveniência para o serviço, a pena de suspensão poderá ser convertida em multa, na base de 50% por dia de vencimento ou remuneração."},
    {"codigo": "054", "denominacao": "FALTA ABONADA PARA PROVA OU EXAME EM CONCURSO PÚBLICO", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de realização de exame/concurso público, e terá a falta abonada."},
    {"codigo": "056", "denominacao": "AFASTAMENTO PARA ESTÁGIO EXPERIMENTAL", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de estágio experimental."},
    {"codigo": "057", "denominacao": "SERVIDOR EM DISPONIBILIDADE", "descricao_completa": "O servidor será colocado em disponibilidade caso extinto o cargo, ou declarada sua desnecessidade."},
    {"codigo": "061", "denominacao": "FALTA POR GREVE", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de greve nos termos e nos limites definidos em Lei específica."},
    {"codigo": "062", "denominacao": "SUSPENSÃO A296 D2479/A105 LC15/A146 LC6", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de suspensão, que será aplicada nos casos de falta grave; desrespeito a proibições que, pela sua natureza, não ensejarem pena de demissão; reincidência em falta já punida com repreensão."},
    {"codigo": "065", "denominacao": "AFASTAMENTO POR ABANDONO DE CARGO", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de abandono de cargo."},
    {"codigo": "066", "denominacao": "LICENÇA MANDATO LEGIS / EXEC S VENC", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de desempenho de mandato eletivo, federal ou estadual."},
    {"codigo": "067", "denominacao": "LICENÇA PARA SERVIÇO MILITAR", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de convocado para serviço militar ou outro encargo da segurança nacional."},
    {"codigo": "069", "denominacao": "LICENÇA PARA ACOMPANHAR CÔNJUGE", "descricao_completa": "O servidor ficará afastado de suas funções para acompanhar o cônjuge quando este for exercer mandato eletivo ou, sendo militar ou servidor for mandado servir, 'ex-officio', em outro ponto do território estadual, nacional ou no exterior."},
    {"codigo": "070", "denominacao": "LICENÇA PARA TRATAR DE INTERESSE PARTICULAR", "descricao_completa": "O servidor ficará afastado de suas funções para tratar de interesses particulares."},
    {"codigo": "074", "denominacao": "BLOQUEIO PAGAMENTO - ACUMULAÇÃO ILÍCITA", "descricao_completa": "Caso declarada a ilicitude da acumulação e o servidor não optar entre os cargos e respectiva remuneração, o órgão de origem deve suspender o pagamento do vínculo mais recente."},
    {"codigo": "075", "denominacao": "PEDIDO DE EXONERAÇÃO FORA DO EXERCÍCIO", "descricao_completa": "Pedido de exoneração solicitado pelo servidor."},
    {"codigo": "094", "denominacao": "BLOQUEIO PAGAMENTO-ATENDER EXIGÊNCIA (ART 360 DEC2479)", "descricao_completa": "O servidor poderá ter suspenso seu pagamento caso não cumpra exigência de prazo determinado pela legislação."},
    {"codigo": "100", "denominacao": "LICENÇA DOENÇA PROFISSIONAL", "descricao_completa": "O servidor ficará afastado de suas funções pelo motivo de doença profissional, que se atribui às condições inerentes ao serviço ou fatos nele ocorridos."},
    {"codigo": "101", "denominacao": "AFASTAMENTO PARA DOAÇÃO DE SANGUE", "descricao_completa": "O servidor ficará afastado de suas funções pelo motivo de doação de sangue."},
    {"codigo": "102", "denominacao": "AFASTAMENTO PARA PROVA EM VESTIBULAR", "descricao_completa": "O servidor ficará afastado de suas funções pelo motivo de prova de vestibular."},
    {"codigo": "103", "denominacao": "FALTA ABONADA PARA FINS DISCIPLINARES", "descricao_completa": "Justificativa para períodos de abandono das funções quando o servidor pede reassunção do cargo."},
    {"codigo": "104", "denominacao": "AFAST CURSO FORMAÇÃO ETAPA CONCURSO COM VENC", "descricao_completa": "Solicitação de afastamento das funções pelo servidor com objetivo de participar de curso de formação que integre etapa de concurso público para provimento de cargos."},
    {"codigo": "105", "denominacao": "AFAST CURSO FORMAÇÃO ETAPA CONCURSO SEM VENC", "descricao_completa": "Solicitação de afastamento das funções pelo servidor com objetivo de participar de curso de formação que integre etapa de concurso público para provimento de cargos."},
    {"codigo": "106", "denominacao": "LICENÇA ADOÇÃO", "descricao_completa": "A servidora ficará afastada de suas funções pelo motivo de adoção."},
    {"codigo": "107", "denominacao": "LICENÇA ADOÇÃO- PAI", "descricao_completa": "O prazo concedido ao servidor estadual que adotar filhos será de 30 (trinta) dias."},
    {"codigo": "108", "denominacao": "AFASTAMENTO PARA EXAME PREVENTIVO", "descricao_completa": "A servidora ficará afastada de suas funções pelo motivo exame médico preventivo. Todas as servidoras públicas, inclusive as celetistas e as contratadas através de quaisquer formas de mediação e que prestem serviços em órgãos públicos farão, uma vez por ano, o exame preventivo de câncer de mama e do colo do útero."},
    {"codigo": "109", "denominacao": "AFASTAMENTO POR DETERMINAÇÃO JUDICIAL COM VENCIMENTO", "descricao_completa": "O servidor ficará afastado de suas funções por determinação judicial."},
    {"codigo": "110", "denominacao": "AFASTAMENTO POR DETERMINAÇÃO JUDICIAL SEM VENCIMENTO", "descricao_completa": "O servidor ficará afastado de suas funções por determinação judicial."},
    {"codigo": "111", "denominacao": "FALTA ABONADA CONTRATO TEMPORARIO", "descricao_completa": "Faltas ao trabalho abonadas, mediante justificativa."},
    {"codigo": "117", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE INICIAL - CLT", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença."},
    {"codigo": "118", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE INICIAL - CONTR TEMP", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de doença. A partir do 16º dia de afastamento do servidor de suas funções, o pagamento será feito pela Previdência Social através do Auxílio Doença Previdenciário."},
    {"codigo": "120", "denominacao": "LICENÇA ACIDENTE TRABALHO INICIAL - INSS", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de acidente de trabalho. A partir do 16º dia de afastamento do servidor de suas funções, o pagamento será feito pela Previdência Social através do Auxílio Doença Previdenciário."},
    {"codigo": "121", "denominacao": "LICENÇA ACIDENTE TRABALHO - RGPS", "descricao_completa": "O servidor ficará afastado de suas funções por motivo de acidente de trabalho. A partir do 16º dia de afastamento do servidor de suas funções, o pagamento será feito pela Previdência Social através do Auxílio Doença Previdenciário."},
    {"codigo": "124", "denominacao": "LICENÇA GESTANTE PRÉ-TERMO §8 ART19 DL220", "descricao_completa": "A Licença concedida à gestante com recém-nascido pré-termo. Será acrescida do número de semanas equivalente à diferença entre o nascimento a termo – 37 semanas de idade gestacional - e a idade gestacional do recém-nascido, devidamente comprovada."},
    {"codigo": "150", "denominacao": "PRISÃO - ABSOLVIÇÃO AFINAL", "descricao_completa": "Servidor recolhido à prisão, absolvido afinal."},
    {"codigo": "153", "denominacao": "LICENÇA GESTANTE COMPLEMENTO LEI 128/09", "descricao_completa": "A servidora ficará afastada de suas funções por motivo de gestação."},
    {"codigo": "156", "denominacao": "AFASTAMENTO PARA ESTÁGIO PROBATÓRIO", "descricao_completa": "O servidor ficará afastado de suas funções para exercício de estágio probatório em outro ente."},
    {"codigo": "161", "denominacao": "FALTA POR GREVE ABONADA", "descricao_completa": "O servidor terá os dias de faltas por motivo de greve abonadas."},
    {"codigo": "162", "denominacao": "FALTA POR GREVE ABONADA COM REPOSIÇÃO", "descricao_completa": "O servidor terá os dias de faltas por motivo de greve abonadas, desde que haja a reposição dos dias faltosos."},
    {"codigo": "165", "denominacao": "ABANDONO SERVIÇO CONTRATO TEMPORARIO", "descricao_completa": "O servidor terá seu contrato extinto, sem direito a indenizações se faltar ao trabalho por três dias consecutivos ou cinco intercalados em um período de 12 meses, ressalvadas as faltas abonadas por motivo de doença do contratado, cônjuge, ascendentes ou descentes diretos, desde que devidamente comprovada;"},
    {"codigo": "200", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE", "descricao_completa": "O servidor Militar ficará afastado de suas funções para tratamento de saúde."},
    {"codigo": "201", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - ATO SERVIÇO", "descricao_completa": "O servidor Militar ficará afastado de suas funções para tratamento de saúde acometida no ato de serviço."},
    {"codigo": "202", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE – MOLÉSTIA INFECTO CONTAGIOSA", "descricao_completa": "A licença para tratamento de saúde por doença infecto contagiosa é um dos motivos de afastamento do servidor com vencimentos e vantagens integrais em regra. Pode ainda ocorrer de, em razão da natureza da enfermidade, o servidor ser considerado irrecuperável, com indicação imediata de aposentadoria."},
    {"codigo": "203", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - DECLARADO INCAPAZ", "descricao_completa": "O servidor Militar ficará afastado de suas funções para tratamento de saúde quando declarado incapaz."},
    {"codigo": "204", "denominacao": "LICENÇA TRATAMENTO DE SAÚDE - DECL INCAPAZ - ATO SERVIÇO", "descricao_completa": "Acidente em serviço."},
    {"codigo": "208", "denominacao": "TRÂNSITO", "descricao_completa": "O servidor Militar ficará afastado de suas funções quando estiver em trânsito para exercício em nova sede/unidade."},
    {"codigo": "209", "denominacao": "INSTALAÇÃO", "descricao_completa": "O servidor Militar ficará afastado de suas funções quando estiver se instalando e se organizando em nova sede."},
    {"codigo": "210", "denominacao": "DISPENSA DE SERVIÇO", "descricao_completa": "O servidor Militar ficará afastado de suas funções quando receber dispensa de serviço, uma forma de recompensas constituem ,reconhecimento dos bons serviços prestados. As recompensas serão concedidas de acordo com as normas estabelecidas nos regulamentos da Corporação."},
    {"codigo": "211", "denominacao": "CONDENAÇÃO / PRISÃO", "descricao_completa": "O servidor Militar ficará afastado de suas funções quando condenado à pena restritiva de liberdade superior a 6 (seis) meses, em sentença transitada em julgado, enquanto durar a execução, excluído o período de sua suspensão condicional, se concedida esta, ou até ser declarado indigno de pertencer à corporação ou com ele incompatível."},
    {"codigo": "212", "denominacao": "À DISPOSIÇÃO DA JUSTIÇA COMUM", "descricao_completa": "O servidor Militar ficará afastado de suas funções quando se ver processar, após ficar exclusivamente à disposição da Justiça Comum."},
    {"codigo": "213", "denominacao": "AUSENTE", "descricao_completa": "O servidor Militar será considerado “Ausente” nas situações tipificadas nos Estatutos do Bombeiro Militar e Polícia Militar, conforme legislação específica."},
    {"codigo": "214", "denominacao": "DESAPARECIDO", "descricao_completa": "O servidor Militar será considerado “Desaparecido” nas situações tipificadas nos Estatutos do Bombeiro Militar e Polícia Militar, conforme legislação específica."},
    {"codigo": "215", "denominacao": "AGREGADO POR DESERÇÃO", "descricao_completa": "Significa o afastamento unilateral do servidor militar pela administração militar conforme, tipificado no Código Penal Militar"},
    {"codigo": "216", "denominacao": "AGREGADO POR EXTRAVIO", "descricao_completa": "O servidor Militar será agregado quando ter sido considerado oficialmente extraviado;"},
    {"codigo": "217", "denominacao": "EM PROCESSO DE EXONERAÇÃO EX OFFICIO", "descricao_completa": "O servidor militar ao ser colocado à dispensa do serviço público à critério da administração, terá seus vencimentos suspensos enquanto da investigação, podendo, ao final da mesma, ser reintegrado ou excluído da corporação."},
    {"codigo": "218", "denominacao": "LICENÇA PARA TRATAMENTO DE SAÚDE DETERMINAÇÃO JUDICIAL", "descricao_completa": "Afastamento de servidor para cumprimento de decisão judicial orientada pela Procuradoria Geral do Estado – PGE, encaminhada pelas Assessorias Jurídicas dos respectivos órgãos."},
    {"codigo": "300", "denominacao": "PRESENÇA", "descricao_completa": "O servidor é convocado para serviço quando haja feriado, ponto facultativo ou finais de semana."},
    {"codigo": "315", "denominacao": "LICENÇA MATERNIDADE DETERMINAÇÃO JUDICIAL", "descricao_completa": "Afastamento de servidor para cumprimento de decisão judicial orientada pela Procuradoria Geral do Estado – PGE, encaminhada pelas Assessorias Jurídicas dos respectivos órgãos."},
    {"codigo": "361", "denominacao": "ABONO FALTAS GREVE DET JUD", "descricao_completa": "Cumprimento de decisão judicial."},
]

class Command(BaseCommand):
    help = 'Popula o banco de dados com os códigos de ocorrência de afastamento da Polícia Civil, incluindo os padrões do sistema.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("Iniciando a população/atualização dos códigos de ocorrência..."))
        
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for item in CODIGOS_OCORRENCIA_DATA:
                codigo = item["codigo"].upper() # Garante que o código é maiúsculo
                denominacao = item["denominacao"]
                descricao_completa = item["descricao_completa"]

                try:
                    # Tenta obter o objeto se já existir pelo código (case-insensitive)
                    ocorrencia, created = CodigoOcorrencia.objects.get_or_create(
                        codigo__iexact=codigo, # Busca case-insensitive
                        defaults={
                            'codigo': codigo, # Salva o código em maiúsculo
                            'denominacao': denominacao,
                            'descricao_completa': descricao_completa
                        }
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f"  Criado: {codigo} - {denominacao}"))
                    else:
                        # Se não foi criado, significa que já existia.
                        # Agora verifica se precisa ser atualizado (se denominação ou descrição mudaram).
                        needs_update = False
                        if ocorrencia.denominacao != denominacao:
                            ocorrencia.denominacao = denominacao
                            needs_update = True
                        if ocorrencia.descricao_completa != descricao_completa:
                            ocorrencia.descricao_completa = descricao_completa
                            needs_update = True
                        
                        if needs_update:
                            ocorrencia.save()
                            updated_count += 1
                            self.stdout.write(self.style.WARNING(f"  Atualizado: {codigo} - {denominacao}"))
                        else:
                            self.stdout.write(self.style.NOTICE(f"  Existente e sem alterações: {codigo} - {denominacao}"))

                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"  Erro ao processar código {codigo} - {denominacao}: {e}"))
        
        self.stdout.write(self.style.HTTP_INFO("\n--- Resumo da Operação ---"))
        self.stdout.write(self.style.SUCCESS(f"Total de códigos criados: {created_count}"))
        self.stdout.write(self.style.WARNING(f"Total de códigos atualizados: {updated_count}"))
        self.stdout.write(self.style.HTTP_INFO("População/atualização de códigos de ocorrência concluída."))