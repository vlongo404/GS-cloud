#!/usr/bin/env python3
"""Gera docs/Documentacao-API-Tarefas.pdf.

Uso:
    pip install -r docs/requirements-docs.txt
    python docs/gerar_diagramas.py      # (opcional) refaz os diagramas
    python docs/gerar_pdf.py

- Dados do aluno, repositorio, IP e configuracao da Azure: docs/config.json
- Prints de evidencia: salve em docs/prints/ com o prefixo da lista de evidencias
  (ex.: 01-grupo-de-recursos.png, 02-vm-visao-geral.png). Cada print recebe a marca
  d'agua "Nome - Evidencia Original - data" automaticamente (os originais nao sao
  alterados). Prints ausentes aparecem como quadro "PENDENTE" no PDF.
"""
import datetime
import json
import os
import sys
import tempfile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

DOCS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DOCS)
PRINTS = os.path.join(DOCS, "prints")
DIAG = os.path.join(DOCS, "diagramas")
SAIDA = os.path.join(DOCS, "Documentacao-API-Tarefas.pdf")

AZUL = colors.HexColor("#1f4e79")
AZUL_CLARO = colors.HexColor("#dbe9f6")
CINZA = colors.HexColor("#555555")
CINZA_CLARO = colors.HexColor("#f2f2f2")
LARGURA = A4[0] - 4 * cm  # largura util

# --------------------------------------------------------------------------
# Configuracao
# --------------------------------------------------------------------------
PADRAO = {
    "aluno": "Aluno",
    "rm": "",
    "turma": "",
    "disciplina": "",
    "professor": "",
    "repo_url": "https://github.com/SEU_USUARIO/api-tarefas",
    "ip_publico": "IP_PUBLICO_DA_VM",
    "data": "",
    "azure": {
        "regiao": "Canada Central",
        "regiao_grupo": "Brazil South",
        "grupo_recursos": "rg-api-tarefas",
        "vm_nome": "vm-gs",
        "sku": "Standard_B2ats_v2",
        "vcpu": "2",
        "ram": "1 GiB",
        "imagem": "Ubuntu Server 22.04 LTS",
        "disco": "Premium SSD (Premium_LRS), 30 GiB",
    },
}

EVIDENCIAS = [
    ("01", "Grupo de recursos na Azure",
     "Portal Azure > Grupos de recursos > rg-api-tarefas, mostrando todos os recursos criados (VM, disco, IP, NSG, rede)."),
    ("02", "Visão geral da máquina virtual",
     "Página Visão geral da VM: região, tamanho (SKU Standard_B2ats_v2), sistema operacional, IP público e status Em execução."),
    ("03", "Regras de entrada do NSG",
     "VM > Rede (ou o NSG) > Regras de porta de entrada, mostrando a porta 22 (SSH) e a porta 80 (HTTP)."),
    ("04", "Disco do sistema operacional",
     "VM > Discos: tipo Premium SSD (LRS) e tamanho de 30 GiB."),
    ("05", "Configuração da VM via SSH",
     "Terminal executando deploy/setup-vm.sh dentro da VM, até a última linha com o retorno do /health."),
    ("06", "Serviço ativo no systemd",
     "Saída de: sudo systemctl status api-tarefas (active (running))."),
    ("07", "Teste da rota /health pela internet",
     "Navegador ou curl em http://IP_PUBLICO/health a partir da sua máquina (não de dentro da VM)."),
    ("08", "Criando uma tarefa (POST)",
     "curl -X POST http://IP_PUBLICO/tarefas ... com a resposta 201 e o JSON da tarefa."),
    ("09", "Listando e consultando tarefas (GET)",
     "curl em /tarefas e /tarefas/1 mostrando os dados gravados no SQLite."),
    ("10", "Atualizando e removendo (PUT e DELETE)",
     "curl -X PUT marcando concluida como true e curl -X DELETE (204), seguido de um GET que retorna 404."),
    ("11", "Repositório no GitHub",
     "Página do repositório público api-tarefas com a lista de arquivos e a URL visível na barra de endereço."),
]


def carregar_config():
    cfg = json.loads(json.dumps(PADRAO))
    caminho = os.path.join(DOCS, "config.json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            usuario = json.load(f)
        for chave, valor in usuario.items():
            if isinstance(valor, dict) and isinstance(cfg.get(chave), dict):
                cfg[chave].update(valor)
            else:
                cfg[chave] = valor
    return cfg


CFG = carregar_config()
AZ = CFG["azure"]
HOJE = datetime.date.today().strftime("%d/%m/%Y")
DATA_DOC = CFG["data"] if CFG["data"] else HOJE
PENDENCIAS = []


def e(texto):
    return escape(str(texto))


# --------------------------------------------------------------------------
# Marca d'agua nos prints
# --------------------------------------------------------------------------
def carregar_fonte(tamanho):
    candidatos = [
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for caminho in candidatos:
        if os.path.exists(caminho):
            return ImageFont.truetype(caminho, tamanho)
    try:
        import matplotlib

        caminho = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
        return ImageFont.truetype(caminho, tamanho)
    except Exception:
        return ImageFont.load_default(size=tamanho)


def aplicar_marca_dagua(origem, destino, data_txt):
    texto = f"{CFG['aluno']} · Evidência Original · {data_txt}"
    img = Image.open(origem).convert("RGB")
    if img.width > 1800:
        nova_altura = int(img.height * 1800 / img.width)
        img = img.resize((1800, nova_altura), Image.LANCZOS)
    w, h = img.size
    base = img.convert("RGBA")

    # 1) texto diagonal repetido, discreto
    fonte = carregar_fonte(max(14, w // 40))
    lado = int((w ** 2 + h ** 2) ** 0.5) + 20
    camada = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    dr = ImageDraw.Draw(camada)
    larg_txt = dr.textlength(texto, font=fonte)
    passo_x = int(larg_txt * 1.3)
    passo_y = int(fonte.size * 5)
    for linha, y in enumerate(range(0, lado, passo_y)):
        desloc = passo_x // 2 if linha % 2 else 0
        for x in range(-passo_x, lado, passo_x):
            dr.text((x + desloc, y), texto, font=fonte, fill=(110, 110, 110, 85))
    camada = camada.rotate(28, resample=Image.BICUBIC)
    esq, topo = (lado - w) // 2, (lado - h) // 2
    camada = camada.crop((esq, topo, esq + w, topo + h))
    base = Image.alpha_composite(base, camada)

    # 2) faixa legivel no canto inferior direito
    fonte2 = carregar_fonte(max(13, w // 58))
    dr2 = ImageDraw.Draw(base, "RGBA")
    tw = dr2.textlength(texto, font=fonte2)
    pad = max(6, fonte2.size // 3)
    x1, y1 = w - tw - 2 * pad, h - fonte2.size - 2 * pad
    dr2.rectangle([x1, y1, w, h], fill=(0, 0, 0, 175))
    dr2.text((x1 + pad, y1 + pad - 1), texto, font=fonte2, fill=(255, 255, 255, 255))

    base.convert("RGB").save(destino, "JPEG", quality=88)


def achar_prints(prefixo):
    if not os.path.isdir(PRINTS):
        return []
    achados = []
    for nome in sorted(os.listdir(PRINTS)):
        base, ext = os.path.splitext(nome)
        if base.startswith(prefixo) and ext.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            achados.append(os.path.join(PRINTS, nome))
    return achados


# --------------------------------------------------------------------------
# Estilos
# --------------------------------------------------------------------------
S = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14.5,
                           spaceAfter=6, textColor=colors.HexColor("#222222")),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, leading=20,
                         textColor=AZUL, spaceBefore=14, spaceAfter=8, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=16,
                         textColor=AZUL, spaceBefore=10, spaceAfter=5, keepWithNext=1),
    "cap": ParagraphStyle("cap", fontName="Helvetica-Oblique", fontSize=8.8, leading=11,
                          textColor=CINZA, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=12),
    "cellh": ParagraphStyle("cellh", fontName="Helvetica-Bold", fontSize=9, leading=12,
                            textColor=colors.white),
    "bul": ParagraphStyle("bul", fontName="Helvetica", fontSize=10, leading=14,
                          leftIndent=14, bulletIndent=3, spaceAfter=3,
                          textColor=colors.HexColor("#222222")),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=7.6, leading=9.6),
    "capa_t": ParagraphStyle("capa_t", fontName="Helvetica-Bold", fontSize=26, leading=31,
                             textColor=colors.white),
    "capa_s": ParagraphStyle("capa_s", fontName="Helvetica", fontSize=13, leading=18,
                             textColor=colors.white),
    "pend": ParagraphStyle("pend", fontName="Helvetica", fontSize=9.5, leading=13,
                           textColor=colors.HexColor("#7f3f00"), alignment=TA_CENTER),
}

N_FIG = [0]


def P(texto, estilo="body"):
    return Paragraph(texto, S[estilo])


def bullets(itens):
    return [Paragraph(t, S["bul"], bulletText="•") for t in itens]


def tabela(linhas, larguras, cabecalho=True):
    dados = []
    for i, linha in enumerate(linhas):
        estilo = "cellh" if (cabecalho and i == 0) else "cell"
        dados.append([Paragraph(str(c), S[estilo]) for c in linha])
    t = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilos = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if cabecalho:
        estilos.append(("BACKGROUND", (0, 0), (-1, 0), AZUL))
        for i in range(1, len(dados)):
            if i % 2 == 0:
                estilos.append(("BACKGROUND", (0, i), (-1, i), CINZA_CLARO))
    t.setStyle(TableStyle(estilos))
    return [t, Spacer(1, 8)]


def codigo(texto, max_linhas=24):
    """Bloco de codigo com fundo cinza; quebra em varias linhas de tabela para poder
    atravessar paginas."""
    linhas = texto.rstrip("\n").split("\n")
    pedacos = ["\n".join(linhas[i:i + max_linhas]) for i in range(0, len(linhas), max_linhas)]
    dados = [[Preformatted(p, S["code"])] for p in pedacos]
    t = Table(dados, colWidths=[LARGURA])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [t, Spacer(1, 8)]


def figura_itens(caminho, legenda, larg_max=None, alt_max=11.5 * cm):
    N_FIG[0] += 1
    larg_max = larg_max or LARGURA
    with Image.open(caminho) as im:
        w, h = im.size
    escala = min(larg_max / w, alt_max / h)
    img = RLImage(caminho, width=w * escala, height=h * escala)
    return [img, P(f"Figura {N_FIG[0]} - {legenda}", "cap")]


def figura(caminho, legenda, larg_max=None, alt_max=11.5 * cm):
    return KeepTogether(figura_itens(caminho, legenda, larg_max, alt_max))


def quadro_pendente_itens(arquivo_sugerido, o_que_mostrar):
    N_FIG[0] += 1
    txt = (f"<b>PRINT PENDENTE</b><br/>Salve o print em <font name='Courier'>docs/prints/"
           f"{e(arquivo_sugerido)}</font> e gere o PDF de novo.<br/><i>{e(o_que_mostrar)}</i>")
    t = Table([[Paragraph(txt, S["pend"])]], colWidths=[LARGURA], rowHeights=[3.2 * cm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#c55a11")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff4e5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [t, P(f"Figura {N_FIG[0]} - (pendente)", "cap")]


# --------------------------------------------------------------------------
# Paginas
# --------------------------------------------------------------------------
def rodape(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cccccc"))
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.0 * cm, f"API de Tarefas · {CFG['aluno']}")
    canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"Página {doc.page}")
    canvas.restoreState()


def capa():
    itens = [
        ("Aluno", e(CFG["aluno"]) + (f" (RM {e(CFG['rm'])})" if CFG["rm"] else "")),
        ("Turma", e(CFG["turma"])),
        ("Disciplina", e(CFG["disciplina"])),
        ("Professor", e(CFG["professor"])),
        ("Data", e(DATA_DOC)),
        ("Repositório", e(CFG["repo_url"])),
        ("URL da API", e(f"http://{CFG['ip_publico']}")),
    ]
    itens = [i for i in itens if i[1].strip()]
    topo = Table(
        [[Paragraph("Documentação Técnica", S["capa_s"])],
         [Paragraph("API de Tarefas com Flask e SQLite hospedada em uma VM na Azure", S["capa_t"])]],
        colWidths=[LARGURA])
    topo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, 0), 22),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 26),
    ]))
    info = Table([[Paragraph(f"<b>{k}</b>", S["cell"]), Paragraph(v, S["cell"])] for k, v in itens],
                 colWidths=[3.2 * cm, LARGURA - 3.2 * cm])
    info.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [Spacer(1, 3 * cm), topo, Spacer(1, 1.2 * cm), info, PageBreak()]


def conteudo():
    st = []
    az = {k: e(v) for k, v in AZ.items()}

    # 1 ---------------------------------------------------------------
    st.append(P("1. Objetivo e checklist da atividade", "h1"))
    st.append(P(
        "A atividade consiste em desenvolver uma API básica com banco de dados SQLite, "
        "hospedá-la de ponta a ponta na nuvem, compartilhar o código no GitHub e entregar a "
        "documentação completa, com esquemas visuais, em Word ou PDF. O professor pediu quatro "
        "itens; a tabela indica onde cada um está neste documento."))
    st += tabela([
        ["Item exigido", "Onde está neste documento"],
        ["1. Prints de tela", "Seção 8 (Evidências), com marca d'água de autoria"],
        ["2. Explicação detalhada", "Seções 2 a 7, 9 e 10, mais os anexos com o código completo"],
        ["3. Link do repositório no Git", f"Capa e seção 11: {e(CFG['repo_url'])}"],
        ["4. Elementos de nuvem: armazenamento, VM (SKU) e linguagem de programação",
         "Seção 5 (e seção 3 para a linguagem)"],
    ], [6.5 * cm, LARGURA - 6.5 * cm])

    # 2 ---------------------------------------------------------------
    st.append(P("2. Visão geral e arquitetura", "h1"))
    st.append(P(
        "A solução é uma API REST de tarefas (cadastro, consulta, atualização e remoção) escrita em "
        "Python com Flask. Os dados ficam em um arquivo SQLite dentro de uma máquina virtual Linux na "
        f"Azure ({az['regiao']}). O gunicorn serve a aplicação na porta 80, o systemd mantém o serviço "
        "no ar, e uma regra no grupo de segurança de rede (NSG) libera o acesso HTTP pela internet."))
    st.append(figura(os.path.join(DIAG, "01-arquitetura.png"), "Arquitetura da solução na Azure.", alt_max=10.5 * cm))
    st.append(P("Caminho de uma requisição:"))
    st += bullets([
        "O cliente (curl ou navegador) envia a requisição HTTP para o IP público da VM, porta 80.",
        "O NSG avalia as regras de entrada e permite o tráfego da porta 80.",
        "O gunicorn recebe a conexão e entrega a requisição a um dos 2 workers, que executam o Flask.",
        "O Flask valida os dados, consulta ou grava no SQLite usando consultas parametrizadas e "
        "devolve a resposta em JSON.",
    ])
    st.append(figura(os.path.join(DIAG, "02-fluxo-requisicao.png"),
                     "Fluxo de uma requisição POST /tarefas, do cliente até o banco.", alt_max=9.5 * cm))

    # 3 ---------------------------------------------------------------
    st.append(P("3. Linguagem de programação e tecnologias", "h1"))
    st.append(P(
        "A linguagem usada é <b>Python 3</b>, com o micro-framework <b>Flask</b>. Na VM, o Ubuntu 22.04 "
        "traz o Python 3.10; os testes locais foram executados em Python 3.13. A escolha prioriza código "
        "curto, fácil de explicar e sem dependências além do necessário."))
    st += tabela([
        ["Tecnologia", "Função no projeto", "Por que foi escolhida"],
        ["Python 3", "Linguagem da API", "Sintaxe simples e módulo sqlite3 na biblioteca padrão."],
        ["Flask", "Framework web (rotas, JSON, erros)", "Mínimo e direto: uma rota é uma função com um decorador."],
        ["SQLite (módulo sqlite3)", "Banco de dados relacional em arquivo único",
         "Sem servidor de banco para instalar ou administrar; exigido pela atividade."],
        ["gunicorn", "Servidor WSGI de produção", "O servidor embutido do Flask é só para desenvolvimento."],
        ["systemd", "Gerenciador de serviços do Linux",
         "Inicia a API no boot e reinicia automaticamente se o processo cair."],
        ["Ubuntu Server 22.04 LTS", "Sistema operacional da VM", "Imagem oficial, suporte de longo prazo, apt para pacotes."],
        ["Git e GitHub", "Versionamento e entrega do código", "A VM clona o repositório para publicar a versão."],
        ["Azure CLI", "Criação da infraestrutura por comandos", "Processo repetível e documentado (infraestrutura como script)."],
    ], [3.6 * cm, 5.2 * cm, LARGURA - 8.8 * cm])

    # 4 ---------------------------------------------------------------
    st.append(P("4. A API", "h1"))
    st.append(P("4.1 Rotas", "h2"))
    st += tabela([
        ["Método", "Rota", "Descrição", "Resposta"],
        ["GET", "/", "Informações e lista de rotas", "200"],
        ["GET", "/health", "Verifica a API e o acesso ao banco", "200"],
        ["GET", "/tarefas", "Lista as tarefas (filtro opcional ?concluida=0 ou 1)", "200"],
        ["GET", "/tarefas/&lt;id&gt;", "Busca uma tarefa pelo id", "200 ou 404"],
        ["POST", "/tarefas", "Cria uma tarefa (campo titulo obrigatório)", "201 ou 400"],
        ["PUT", "/tarefas/&lt;id&gt;", "Atualiza titulo, descricao e/ou concluida", "200, 400 ou 404"],
        ["DELETE", "/tarefas/&lt;id&gt;", "Remove a tarefa", "204 ou 404"],
    ], [2.0 * cm, 3.6 * cm, LARGURA - 8.6 * cm, 3.0 * cm])

    st.append(P("4.2 Exemplos de uso", "h2"))
    st.append(P("Os comandos abaixo foram executados em teste local com o gunicorn. Na VM, troque "
                "<font name='Courier'>127.0.0.1:5000</font> pelo IP público (porta 80)."))
    st += codigo(
        "$ curl -X POST http://127.0.0.1:5000/tarefas -H 'Content-Type: application/json' \\\n"
        "       -d '{\"titulo\":\"Estudar Azure\",\"descricao\":\"VM e storage\"}'\n"
        "HTTP 201\n"
        "{\n"
        "  \"atualizada_em\": \"2026-11-02T16:58:09+00:00\",\n"
        "  \"concluida\": false,\n"
        "  \"criada_em\": \"2026-11-02T16:58:09+00:00\",\n"
        "  \"descricao\": \"VM e storage\",\n"
        "  \"id\": 1,\n"
        "  \"titulo\": \"Estudar Azure\"\n"
        "}\n"
        "\n"
        "$ curl -X PUT http://127.0.0.1:5000/tarefas/1 -H 'Content-Type: application/json' \\\n"
        "       -d '{\"concluida\":true}'\n"
        "HTTP 200   (mesma tarefa, com \"concluida\": true)\n"
        "\n"
        "$ curl -X DELETE http://127.0.0.1:5000/tarefas/1\n"
        "HTTP 204   (sem corpo)\n"
        "\n"
        "$ curl http://127.0.0.1:5000/tarefas/1\n"
        "HTTP 404\n"
        "{\"erro\": \"tarefa nao encontrada\"}\n")

    st.append(P("4.3 Validação e erros", "h2"))
    st += tabela([
        ["Situação", "Resposta"],
        ["Corpo ausente, que não seja JSON ou que não seja um objeto", "400 com {\"erro\": \"...\"}"],
        ["titulo ausente (POST), vazio ou com mais de 120 caracteres", "400"],
        ["concluida diferente de true ou false; descricao que não seja texto", "400"],
        ["Id inexistente em GET, PUT ou DELETE", "404"],
        ["Rota inexistente ou método não permitido", "404 ou 405, também em JSON"],
    ], [LARGURA - 5.5 * cm, 5.5 * cm])

    st.append(P("4.4 Cuidados de segurança no código", "h2"))
    st += bullets([
        "<b>Consultas parametrizadas</b>: os valores sempre vão como parâmetros (?), nunca concatenados "
        "no SQL. Um teste automatizado grava um título com tentativa de SQL injection e confirma que a "
        "tabela continua intacta.",
        "<b>Validação de entrada</b> antes de tocar no banco (tipo, tamanho e campos aceitos).",
        "<b>Nomes de coluna no UPDATE</b> vêm do dicionário já validado, nunca direto do cliente.",
        "<b>Modo debug desligado</b>: erros internos não expõem código nem variáveis ao cliente.",
        "<b>Serviço sem root</b>: o gunicorn roda como usuário comum, com permissão apenas para ouvir na porta 80.",
    ])

    # 5 ---------------------------------------------------------------
    st.append(P("5. Elementos de nuvem utilizados", "h1"))
    st.append(P("5.1 Resumo dos recursos", "h2"))
    st += tabela([
        ["Recurso Azure", "Configuração usada", "Função"],
        ["Grupo de recursos", f"{az['grupo_recursos']} (metadados em {az['regiao_grupo']}; recursos em {az['regiao']})", "Agrupa todos os recursos; apagar o grupo remove tudo."],
        ["Máquina virtual", f"{az['vm_nome']} · SKU {az['sku']} · {az['vcpu']} vCPU · {az['ram']} de RAM · {az['imagem']}",
         "Executa o gunicorn, o Flask e o SQLite."],
        ["Armazenamento (disco gerenciado do SO)", az["disco"], "Guarda o sistema, o código, o ambiente Python e o arquivo do banco."],
        ["IP público", "SKU Standard (endereço estático)", "Endereço de acesso à API pela internet."],
        ["NSG (grupo de segurança de rede)", "Entrada liberada: 22/TCP (SSH) e 80/TCP (HTTP)", "Firewall da interface de rede da VM."],
        ["Rede virtual, sub-rede e NIC", "Criadas automaticamente junto com a VM", "Conectividade da VM."],
    ], [4.0 * cm, 6.8 * cm, LARGURA - 10.8 * cm])

    st.append(P("5.2 Máquina virtual e SKU", "h2"))
    st.append(P(
        f"<b>SKU</b> é o código do produto que define o tamanho da máquina. Aqui foi usado "
        f"<b>{az['sku']}</b>, que se lê assim: <i>Standard</i> (categoria padrão), <i>B</i> (série "
        "burstable, de desempenho com picos), <i>2</i> (dois vCPUs), <i>a</i> (processador AMD), "
        "<i>t</i> (tiny memory: a menor proporção de memória por vCPU), <i>s</i> (aceita discos Premium SSD) "
        f"e <i>v2</i> (segunda geração da série). Esse tamanho oferece {az['vcpu']} vCPUs e {az['ram']} de memória."))
    st.append(P(
        "O tamanho inicialmente planejado era o Standard_B1s em Brazil South, mas a assinatura usada "
        "retornou o erro SkuNotAvailable (restrição de capacidade) para ele nessa região. Por isso a VM "
        f"foi criada em <b>{az['regiao']}</b>, com o {az['sku']}. O grupo de recursos continua com os "
        f"metadados em {az['regiao_grupo']}, o que não afeta o funcionamento."))
    st.append(P(
        "A série B acumula créditos de CPU enquanto a VM trabalha abaixo do seu desempenho base e pode "
        "usar até 100% da vCPU em momentos de pico. Isso combina com uma API de poucas requisições, que "
        "fica ociosa na maior parte do tempo, e é a opção de menor custo para a atividade."))
    st.append(P(
        "Segundo a página de serviços gratuitos da Microsoft, contas novas da Azure recebem 750 horas "
        "por mês de cada um dos tamanhos B1s, B2pts v2 e B2ats v2, por 12 meses (oferta para contas "
        "elegíveis). O tamanho usado aqui, B2ats v2, está nessa lista."))

    st.append(P("5.3 Armazenamento", "h2"))
    st += bullets([
        f"<b>Disco do sistema operacional</b>: disco gerenciado {az['disco']}. O tipo Premium SSD foi o padrão sugerido pelo portal para este tamanho "
        "(a letra <i>s</i> do SKU indica suporte a discos Premium). A redundância é local (LRS), com três "
        "cópias dentro do mesmo datacenter. Para reduzir custo seria possível trocar para Standard SSD, que "
        "também atenderia a uma carga leve como esta.",
        "<b>Onde fica o banco</b>: o arquivo <font name='Courier'>/var/lib/api-tarefas/tarefas.db</font> "
        "está nesse disco persistente. A VM também costuma ter um disco temporário local, que "
        "<b>não</b> é persistente e por isso não é usado para o banco.",
        "<b>Por que não usar Storage Account ou Azure SQL</b>: o SQLite é um arquivo local e precisa de "
        "acesso rápido a disco; ele não funciona como serviço de banco remoto. A atividade pede SQLite, "
        "então o armazenamento adequado é o disco da própria VM.",
        "<b>Cópia de segurança (melhoria)</b>: tirar um snapshot do disco ou copiar o arquivo .db para um "
        "contêiner de Blob Storage com agendamento.",
    ])

    st.append(P("5.4 Rede e segurança", "h2"))
    st += tabela([
        ["Porta", "Protocolo", "Origem", "Como foi criada", "Motivo"],
        ["22", "TCP (SSH)", "Qualquer", "Marcada na criação da VM", "Administração remota da VM por SSH."],
        ["80", "TCP (HTTP)", "Qualquer", "Marcada na criação da VM", "Acesso público à API."],
        ["Demais", "-", "-", "Regras padrão do NSG", "Entrada negada."],
    ], [1.6 * cm, 2.4 * cm, 2.0 * cm, 5.2 * cm, LARGURA - 11.2 * cm])
    st.append(P(
        "Em produção, a porta 22 deveria aceitar apenas o IP do administrador, e o tráfego HTTP "
        "deveria passar por HTTPS (seção 10)."))

    st.append(P("5.5 Custos e limpeza", "h2"))
    st.append(P(
        "Uma VM desalocada deixa de cobrar computação, mas o disco e o IP público continuam sendo "
        "cobrados. Para encerrar tudo após a avaliação, o comando abaixo remove o grupo de recursos "
        "inteiro:"))
    st += codigo(f"az group delete --name {AZ['grupo_recursos']} --yes --no-wait")

    # 6 ---------------------------------------------------------------
    st.append(P("6. Banco de dados SQLite", "h1"))
    st.append(P(
        "O SQLite é um banco relacional embutido: todo o banco é um único arquivo, acessado pelo módulo "
        "sqlite3 do Python, sem processo de servidor. A tabela é criada automaticamente na "
        "primeira execução da aplicação (CREATE TABLE IF NOT EXISTS)."))
    st.append(figura(os.path.join(DIAG, "03-modelo-dados.png"), "Modelo de dados: tabela tarefas.", alt_max=8 * cm))
    st += codigo(
        "CREATE TABLE IF NOT EXISTS tarefas (\n"
        "    id            INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    titulo        TEXT    NOT NULL,\n"
        "    descricao     TEXT    NOT NULL DEFAULT '',\n"
        "    concluida     INTEGER NOT NULL DEFAULT 0,\n"
        "    criada_em     TEXT    NOT NULL,\n"
        "    atualizada_em TEXT    NOT NULL\n"
        ");")
    st += bullets([
        "<b>Modo WAL</b> (PRAGMA journal_mode=WAL): permite que leituras continuem enquanto ocorre uma "
        "gravação, o que ajuda com os 2 workers do gunicorn.",
        "<b>Limitação conhecida</b>: o SQLite aceita uma gravação por vez. Para a carga desta atividade é "
        "suficiente; para muitos acessos simultâneos seria necessário migrar para PostgreSQL ou Azure SQL.",
        "<b>Datas</b> em texto ISO 8601, em UTC.",
    ])

    # 7 ---------------------------------------------------------------
    st.append(P("7. Deploy passo a passo", "h1"))
    st.append(figura(os.path.join(DIAG, "04-deploy.png"), "Sequência do deploy, da criação da VM ao serviço no ar.", alt_max=8.5 * cm))
    st.append(P("7.1 Criação da VM no portal da Azure", "h2"))
    st += tabela([
        ["Campo", "Valor usado"],
        ["Grupo de recursos", az["grupo_recursos"]],
        ["Nome da máquina virtual", az["vm_nome"]],
        ["Região", az["regiao"]],
        ["Imagem", az["imagem"]],
        ["Tamanho (SKU)", f"{az['sku']} ({az['vcpu']} vCPUs, {az['ram']})"],
        ["Usuário administrador", "azureuser (mesmo usuário definido no serviço systemd)"],
        ["Autenticação SSH", "Senha"],
        ["Portas de entrada públicas", "SSH (22) e HTTP (80)"],
        ["Disco do sistema operacional", az["disco"]],
    ], [5.2 * cm, LARGURA - 5.2 * cm])
    st.append(P("7.1.1 Equivalente por linha de comando (deploy/azure-cli.sh)", "h2"))
    st += codigo(
        f"az group create --name {AZ['grupo_recursos']} --location {AZ['regiao'].lower().replace(' ', '')}\n"
        f"az vm create --resource-group {AZ['grupo_recursos']} --name {AZ['vm_nome']} \\\n"
        f"   --image Ubuntu2204 --size {AZ['sku']} --admin-username azureuser --generate-ssh-keys \\\n"
        "   --storage-sku Premium_LRS --os-disk-size-gb 30 --public-ip-sku Standard\n"
        f"az vm open-port --resource-group {AZ['grupo_recursos']} --name {AZ['vm_nome']} --port 80 --priority 900\n"
        f"az vm show -d --resource-group {AZ['grupo_recursos']} --name {AZ['vm_nome']} --query publicIps -o tsv")
    st.append(P("7.2 Configuração da VM (deploy/setup-vm.sh)", "h2"))
    st.append(P(
        "Depois de conectar com <font name='Courier'>ssh azureuser@IP_PUBLICO</font>, o script instala "
        "python3-venv e git, clona o repositório em /opt/api-tarefas, cria o ambiente virtual, instala "
        "as dependências do requirements.txt, registra o serviço no systemd e testa o /health."))
    st += codigo(f"./setup-vm.sh {CFG['repo_url']}.git")
    st.append(P("7.3 Serviço systemd (deploy/api-tarefas.service)", "h2"))
    st += tabela([
        ["Diretiva", "Efeito"],
        ["User=azureuser", "O processo roda sem privilégios de root."],
        ["StateDirectory=api-tarefas", "O systemd cria /var/lib/api-tarefas, pertencente ao usuário, para o arquivo .db."],
        ["Environment=DB_PATH=...", "Informa à aplicação onde está o banco."],
        ["ExecStart=... gunicorn --workers 2 --bind 0.0.0.0:80 app:app", "Sobe 2 workers e ouve na porta 80."],
        ["AmbientCapabilities=CAP_NET_BIND_SERVICE", "Permite ouvir em porta menor que 1024 sem ser root."],
        ["NoNewPrivileges=true, PrivateTmp=true", "Reduzem a superfície de ataque do processo."],
        ["Restart=always", "Reinicia o serviço automaticamente em caso de falha."],
        ["WantedBy=multi-user.target (+ enable)", "Inicia o serviço no boot da VM."],
    ], [8.4 * cm, LARGURA - 8.4 * cm])
    st.append(P("7.4 Atualizar a versão publicada", "h2"))
    st += codigo(
        "cd /opt/api-tarefas && git pull\n"
        ".venv/bin/pip install -r requirements.txt\n"
        "sudo systemctl restart api-tarefas")
    return st


def segunda_parte():
    st = []
    az = {k: e(v) for k, v in AZ.items()}
    st.append(P("9. Testes", "h1"))
    st.append(P("9.1 Testes automatizados", "h2"))
    st.append(P(
        "O arquivo tests/test_api.py usa unittest e o cliente de testes do Flask, com banco temporário. "
        "Os 5 testes passaram na execução local (python -m unittest discover -s tests -v)."))
    st += tabela([
        ["Teste", "O que verifica"],
        ["test_health", "A rota /health responde 200 e acessa o banco."],
        ["test_crud_completo", "Fluxo POST, GET, PUT (concluida), filtro ?concluida=1, DELETE e GET final com 404."],
        ["test_validacao", "400 para corpo vazio, título em branco, título com 121 caracteres e corpo que não é JSON."],
        ["test_sql_injection_nao_funciona", "Um título com SQL malicioso é gravado como texto e a tabela continua existindo."],
        ["test_404", "Rota inexistente e PUT em id inexistente retornam 404."],
    ], [5.2 * cm, LARGURA - 5.2 * cm])
    st.append(P("9.2 Teste na nuvem", "h2"))
    st.append(P(
        "Depois do deploy, os testes manuais são feitos de fora da VM, apontando para o IP público "
        f"(<font name='Courier'>http://{e(CFG['ip_publico'])}</font>). Os resultados estão nas "
        "evidências 7 a 10 da seção 8."))

    st.append(P("10. Segurança, limitações e melhorias", "h1"))
    st += tabela([
        ["Ponto", "Situação atual", "Melhoria sugerida"],
        ["Tráfego HTTP", "Sem criptografia (porta 80)", "Colocar nginx como proxy reverso com certificado Let's Encrypt (HTTPS)."],
        ["Acesso SSH", "Porta 22 aberta para a internet, com login do usuário azureuser", "Restringir a origem ao IP do administrador no NSG, usar chave SSH em vez de senha ou usar o Azure Bastion."],
        ["Autenticação da API", "Rotas públicas, sem login", "Chave de API ou token (JWT) nas rotas de escrita."],
        ["Banco SQLite", "Uma gravação por vez; arquivo em um único disco", "Backup por snapshot ou cópia para Blob; migrar para PostgreSQL/Azure SQL se crescer."],
        ["Disponibilidade", "Uma única VM", "Zonas de disponibilidade e balanceador, o que exigiria banco em serviço gerenciado."],
        ["Entrega do código", "Deploy manual com git pull", "Pipeline de CI/CD (GitHub Actions) com testes automáticos antes de publicar."],
    ], [3.4 * cm, 5.4 * cm, LARGURA - 8.8 * cm])

    st.append(P("11. Repositório e referências", "h1"))
    st.append(P(f"Repositório no GitHub: <b>{e(CFG['repo_url'])}</b>"))
    st += codigo(
        "GS-cloud/\n"
        "  app.py                  API Flask + SQLite\n"
        "  requirements.txt        Flask e gunicorn\n"
        "  README.md               Resumo, rotas e como rodar\n"
        "  tests/test_api.py       Testes automatizados\n"
        "  deploy/\n"
        "    azure-cli.sh          Cria a infraestrutura na Azure\n"
        "    setup-vm.sh           Configura a VM (rodar dentro dela)\n"
        "    api-tarefas.service   Unidade systemd\n"
        "  docs/\n"
        "    gerar_diagramas.py    Gera os diagramas\n"
        "    gerar_pdf.py          Gera este PDF\n"
        "    config.json           Dados do aluno, repositório e configuração da Azure\n"
        "    diagramas/            Imagens dos esquemas visuais\n"
        "    prints/               Prints de evidência (originais)")
    st.append(P("Referências", "h2"))
    st += bullets([
        "Microsoft Learn - Série Bv1 de VMs: https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/bv1-series",
        "Microsoft Azure - Serviços gratuitos de máquinas virtuais: https://azure.microsoft.com/free/virtual-machines/",
        "Flask: https://flask.palletsprojects.com/",
        "gunicorn: https://gunicorn.org/",
        "SQLite: https://www.sqlite.org/",
    ])

    st.append(PageBreak())
    st.append(P("Anexo A - Código-fonte completo: app.py", "h1"))
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as f:
        st += codigo(f.read())
    st.append(PageBreak())
    st.append(P("Anexo B - Arquivos de deploy", "h1"))
    for nome in ("azure-cli.sh", "setup-vm.sh", "api-tarefas.service"):
        st.append(P(f"deploy/{nome}", "h2"))
        with open(os.path.join(ROOT, "deploy", nome), encoding="utf-8") as f:
            st += codigo(f.read())
    return st


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------
def main():
    doc = BaseDocTemplate(
        SAIDA, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2.2 * cm,
        title="Documentação - API de Tarefas (Flask + SQLite na Azure)",
        author=CFG["aluno"],
    )
    quadro = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=[quadro]),
        PageTemplate(id="miolo", frames=[quadro], onPage=rodape),
    ])

    # Evidencias precisam ser desenhadas com os JPEGs temporarios ainda presentes:
    # por isso o PDF inteiro e construido dentro do bloco do diretorio temporario.
    from reportlab.platypus import NextPageTemplate

    with tempfile.TemporaryDirectory() as tmp:
        st_cap = capa()
        st_cap.insert(-1, NextPageTemplate("miolo"))
        story = st_cap + conteudo()

        story.append(P("8. Evidências (prints de tela)", "h1"))
        story.append(P(
            "Cada print abaixo recebe, automaticamente, a marca d'água com o nome do aluno, a expressão "
            "\"Evidência Original\" e a data. Os arquivos originais ficam intactos em docs/prints."))
        encontrados = 0
        for ident, titulo, o_que in EVIDENCIAS:
            bloco = [P(f"8.{int(ident)} {e(titulo)}", "h2")]
            arquivos = achar_prints(ident)
            if not arquivos:
                bloco += quadro_pendente_itens(f"{ident}-nome-do-print.png", o_que)
                PENDENCIAS.append(f"print {ident} - {titulo}")
            else:
                for i, arq in enumerate(arquivos):
                    encontrados += 1
                    data_txt = CFG["data"] or datetime.date.fromtimestamp(
                        os.path.getmtime(arq)).strftime("%d/%m/%Y")
                    destino = os.path.join(tmp, f"{ident}-{i}.jpg")
                    aplicar_marca_dagua(arq, destino, data_txt)
                    bloco += figura_itens(destino, e(titulo) + ".", alt_max=8.6 * cm)
            story.append(KeepTogether(bloco))

        story += segunda_parte()
        doc.build(story)

    for chave, valor in (("repo_url", CFG["repo_url"]), ("ip_publico", CFG["ip_publico"])):
        if "SEU_USUARIO" in valor or "IP_PUBLICO_DA_VM" in valor:
            PENDENCIAS.append(f"config.json: preencher '{chave}'")
    print(f"PDF gerado: {SAIDA}")
    print(f"Prints encontrados: {encontrados} de {len(EVIDENCIAS)} itens")
    if PENDENCIAS:
        print("Pendências:")
        for p in PENDENCIAS:
            print("  -", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
