#!/usr/bin/env python3
"""Gera docs/Documentacao-API-Tarefas.pdf.

Uso:
    pip install -r docs/requirements-docs.txt
    python docs/gerar_diagramas.py      # (opcional) refaz os diagramas
    python docs/gerar_pdf.py

- Dados do aluno, repositorio, IP e configuracao da Azure: docs/config.json
- Prints de evidencia: salve em docs/prints/ com o prefixo da lista de evidencias
  (ex.: 01-grupo-de-recursos.png). Cada print recebe a marca d'agua
  "Nome - Evidencia Original" automaticamente (os originais nao sao alterados).
  Prints ausentes aparecem como quadro "pendente" no PDF.
- Fontes: docs/fonts (Inter, licenca OFL) e DejaVu Sans Mono (vem com o matplotlib).
"""
import datetime
import json
import os
import re
import sys
import tempfile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import BashLexer, IniLexer, PythonLexer
from pygments.token import Token
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents

DOCS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DOCS)
PRINTS = os.path.join(DOCS, "prints")
DIAG = os.path.join(DOCS, "diagramas")
FONTS = os.path.join(DOCS, "fonts")
SAIDA = os.path.join(DOCS, "Documentacao-API-Tarefas.pdf")

# --------------------------------------------------------------------------
# Identidade visual
# --------------------------------------------------------------------------
INDIGO = colors.HexColor("#2A38D6")
INDIGO_ESCURO = colors.HexColor("#1A2390")
TINTA = colors.HexColor("#1E2433")
MUTED = colors.HexColor("#6B7385")
FIO = colors.HexColor("#DDE0EA")
FUNDO_SUAVE = colors.HexColor("#F3F4FA")
VERDE = colors.HexColor("#0E9F6E")
AMBAR = colors.HexColor("#C77700")
VERMELHO = colors.HexColor("#CF3A4E")
TINTA_HEX = "#1E2433"
INDIGO_HEX = "#2A38D6"
MUTED_HEX = "#6B7385"

CODE_BG = colors.HexColor("#161B30")
CODE_BARRA = colors.HexColor("#202744")
CODE_TXT = "#DCE1F7"

MARGEM_E = 2.1 * cm
MARGEM_D = 2.1 * cm
LARGURA = A4[0] - MARGEM_E - MARGEM_D  # largura util
RECUO_TEXTO = 2.6 * cm  # limita a linha de texto corrido (< 80 caracteres)

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

# (id, titulo, o que a evidencia comprova)
EVIDENCIAS = [
    ("01", "Grupo de recursos na Azure",
     "Todos os recursos da solução estão no grupo rg-api-tarefas: VM, disco, IP público, NSG, "
     "interface e rede virtual."),
    ("02", "Visão geral da máquina virtual",
     "A VM vm-gs está em execução em Canada Central, tamanho Standard_B2ats_v2, Ubuntu 22.04, "
     "com o IP público 20.104.255.148."),
    ("03", "Regras de entrada do NSG",
     "O firewall libera a entrada nas portas 80 (HTTP) e 22 (SSH). Todo o resto segue a regra "
     "padrão de negar."),
    ("04", "Disco do sistema operacional",
     "O disco do SO é Premium SSD (LRS) de 30 GiB. Nele ficam o sistema, o código e o arquivo do banco."),
    ("05", "Configuração da VM via SSH",
     "O script setup-vm.sh instalou a aplicação dentro da VM e o /health respondeu "
     "{\"banco\":\"sqlite\",\"status\":\"ok\"}."),
    ("06", "Serviço ativo no systemd",
     "O api-tarefas.service está active (running), com o gunicorn e seus 2 workers."),
    ("07", "Teste da rota /health pela internet",
     "A API responde fora da VM: o /health abriu no navegador do aluno, pelo IP público."),
    ("08", "Criando uma tarefa (POST)",
     "POST /tarefas devolve 201 Created com o JSON da tarefa gravada no SQLite (id 1)."),
    ("09", "Listando tarefas (GET)",
     "GET /tarefas devolve a tarefa recém-gravada, o que confirma a persistência no banco."),
    ("10", "Atualizando e removendo (PUT e DELETE)",
     "O PUT altera concluida para true, o DELETE responde 204 e a consulta seguinte retorna 404."),
    ("11", "Banco SQLite na VM",
     "O arquivo tarefas.db existe em /var/lib/api-tarefas e a tabela tarefas guarda a tarefa criada pela API "
     "(consulta direta com sqlite3)."),
    ("12", "Repositório no GitHub",
     "O código está em um repositório público do GitHub, com as pastas deploy, docs e tests."),
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
# Fontes
# --------------------------------------------------------------------------
def registrar_fontes():
    import matplotlib

    mpl = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    inter = {
        "Inter": "Inter-Regular.ttf",
        "Inter-Italic": "Inter-Italic.ttf",
        "Inter-Medium": "Inter-Medium.ttf",
        "Inter-SemiBold": "Inter-SemiBold.ttf",
        "Inter-Bold": "Inter-Bold.ttf",
        "Inter-BoldItalic": "Inter-BoldItalic.ttf",
        "Inter-ExtraBold": "Inter-ExtraBold.ttf",
        "Inter-Display": "InterDisplay-ExtraBold.ttf",
    }
    dejavu = {
        "Inter": "DejaVuSans.ttf",
        "Inter-Italic": "DejaVuSans-Oblique.ttf",
        "Inter-Medium": "DejaVuSans.ttf",
        "Inter-SemiBold": "DejaVuSans-Bold.ttf",
        "Inter-Bold": "DejaVuSans-Bold.ttf",
        "Inter-BoldItalic": "DejaVuSans-BoldOblique.ttf",
        "Inter-ExtraBold": "DejaVuSans-Bold.ttf",
        "Inter-Display": "DejaVuSans-Bold.ttf",
    }
    usar_inter = all(os.path.exists(os.path.join(FONTS, f)) for f in inter.values())
    origem, pasta = (inter, FONTS) if usar_inter else (dejavu, mpl)
    if not usar_inter:
        print("Aviso: docs/fonts nao encontrada; usando DejaVu Sans no lugar da Inter.")
    for nome, arq in origem.items():
        pdfmetrics.registerFont(TTFont(nome, os.path.join(pasta, arq)))
    pdfmetrics.registerFontFamily(
        "Inter", normal="Inter", bold="Inter-Bold", italic="Inter-Italic", boldItalic="Inter-BoldItalic")
    mono = {
        "Mono": "DejaVuSansMono.ttf",
        "Mono-Bold": "DejaVuSansMono-Bold.ttf",
        "Mono-Oblique": "DejaVuSansMono-Oblique.ttf",
        "Mono-BoldOblique": "DejaVuSansMono-BoldOblique.ttf",
    }
    for nome, arq in mono.items():
        pdfmetrics.registerFont(TTFont(nome, os.path.join(mpl, arq)))
    pdfmetrics.registerFontFamily(
        "Mono", normal="Mono", bold="Mono-Bold", italic="Mono-Oblique", boldItalic="Mono-BoldOblique")


registrar_fontes()


# --------------------------------------------------------------------------
# Marca d'agua nos prints
# --------------------------------------------------------------------------
def carregar_fonte(tamanho):
    candidatos = [
        os.path.join(FONTS, "Inter-Medium.ttf"),
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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


def aplicar_marca_dagua(origem, destino):
    texto = f"{CFG['aluno']} · Evidência Original"
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
    "body": ParagraphStyle("body", fontName="Inter", fontSize=9.4, leading=14.6, spaceAfter=7,
                           textColor=TINTA, rightIndent=RECUO_TEXTO),
    "body_k": ParagraphStyle("body_k", fontName="Inter", fontSize=9.4, leading=14.6, spaceAfter=7,
                             textColor=TINTA, rightIndent=RECUO_TEXTO, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Inter-SemiBold", fontSize=11.8, leading=15, textColor=TINTA,
                         spaceBefore=15, spaceAfter=6, keepWithNext=1),
    "cap": ParagraphStyle("cap", fontName="Inter", fontSize=8, leading=11, textColor=MUTED,
                          spaceBefore=5, spaceAfter=14),
    "cell": ParagraphStyle("cell", fontName="Inter", fontSize=8.5, leading=11.8, textColor=TINTA),
    "cellf": ParagraphStyle("cellf", fontName="Inter-SemiBold", fontSize=8.5, leading=11.8, textColor=TINTA),
    "cellh": ParagraphStyle("cellh", fontName="Inter-SemiBold", fontSize=8, leading=10.5, textColor=INDIGO),
    "bul": ParagraphStyle("bul", fontName="Inter", fontSize=9.4, leading=14.2, leftIndent=13,
                          bulletIndent=1, spaceAfter=4.5, textColor=TINTA, rightIndent=RECUO_TEXTO),
    "call_t": ParagraphStyle("call_t", fontName="Inter-SemiBold", fontSize=8.8, leading=11.5, spaceAfter=2),
    "call_b": ParagraphStyle("call_b", fontName="Inter", fontSize=8.8, leading=13, textColor=TINTA),
    "ficha_l": ParagraphStyle("ficha_l", fontName="Inter", fontSize=7.6, leading=10, textColor=MUTED),
    "ficha_v": ParagraphStyle("ficha_v", fontName="Inter-SemiBold", fontSize=9.4, leading=13, textColor=TINTA),
    "evid": ParagraphStyle("evid", fontName="Inter", fontSize=8.3, leading=11.6, textColor=MUTED),
}

N_FIG = [0]
COD_ST = ParagraphStyle("cod", fontName="Mono", fontSize=7.3, leading=9.7, textColor=colors.HexColor(CODE_TXT))
NUM_ST = ParagraphStyle("num", fontName="Mono", fontSize=7.3, leading=9.7, textColor=colors.HexColor("#5D668C"),
                        alignment=2)


def _mono_inline(texto):
    """Troca o Courier dos trechos inline pelo mono do documento, com cor discreta."""
    return re.sub(r"<font name=['\"]Courier['\"]>",
                  f"<font name='Mono' size='8.2' color='{INDIGO_ESCURO.hexval().replace('0x', '#')}'>", texto)


def P(texto, estilo="body"):
    if estilo == "h1":
        m = re.match(r"^(\d+)\.\s+(.*)$", texto)
        if m:
            return SecaoH1(m.group(1), m.group(2))
        m = re.match(r"^Anexo ([A-Z]) - (.*)$", texto)
        if m:
            return SecaoH1(m.group(1), m.group(2))
        return SecaoH1("", texto)
    if estilo == "h2":
        m = re.match(r"^(\d+(?:\.\d+)+)\s+(.*)$", texto)
        if m:
            texto = (f"<font name='Inter-SemiBold' color='{INDIGO_HEX}'>{m.group(1)}</font>"
                     f"&nbsp;&nbsp;&nbsp;{m.group(2)}")
    return Paragraph(_mono_inline(texto), S[estilo])


def bullets(itens):
    marca = f"<bullet><font name='Inter-Bold' color='{INDIGO_HEX}' size='7'>&#9632;</font></bullet>"
    return [Paragraph(marca + _mono_inline(t), S["bul"]) for t in itens]


# --------------------------------------------------------------------------
# Componentes
# --------------------------------------------------------------------------
class SecaoH1(Flowable):
    """Titulo de secao: numero grande em indigo, titulo ao lado, fio no topo."""

    ALTURA = 50
    COLUNA = 50

    def __init__(self, numero, titulo, entrada=True):
        super().__init__()
        self.numero = numero
        self.titulo = titulo
        self.entrada = entrada and bool(numero)
        self.keepWithNext = True
        self.spaceBefore = 26
        self.spaceAfter = 10

    def wrap(self, aw, ah):
        self.largura = aw
        return aw, self.ALTURA

    def draw(self):
        c = self.canv
        self.y_abs = c.absolutePosition(0, 0)[1]
        c.setStrokeColor(FIO)
        c.setLineWidth(0.7)
        c.line(0, self.ALTURA, self.largura, self.ALTURA)
        x_titulo = 0
        if self.numero:
            c.setFillColor(INDIGO)
            c.setFont("Inter-Display", 31)
            c.drawString(0, 11, self.numero)
            x_titulo = self.COLUNA
        c.setFillColor(TINTA)
        c.setFont("Inter-Bold", 18)
        c.drawString(x_titulo, 13, self.titulo)

    def texto_toc(self):
        larg = pdfmetrics.stringWidth(self.numero, "Inter-SemiBold", 10)
        razao = pdfmetrics.stringWidth(" ", "Inter", 1) or 0.28
        falta = max(2.0, 24 - larg)
        n = int(falta // (razao * 10))
        resto = falta - n * razao * 10
        folga = "&nbsp;" * n + (f"<font size='{max(1.0, resto / razao):.2f}'>&nbsp;</font>" if resto > 0.3 else "")
        return (f"<font name='Inter-SemiBold' color='{INDIGO_HEX}'>{e(self.numero)}</font>"
                f"{folga}{e(self.titulo)}")


def tabela(linhas, larguras, cabecalho=True, forte=True, estilos_extra=None, dividir=False):
    dados = []
    for i, linha in enumerate(linhas):
        linha_p = []
        for j, c in enumerate(linha):
            if cabecalho and i == 0:
                est = "cellh"
            elif forte and j == 0:
                est = "cellf"
            else:
                est = "cell"
            linha_p.append(Paragraph(_mono_inline(str(c)), S[est]))
        dados.append(linha_p)
    t = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilos = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.45, FIO),
    ]
    if cabecalho:
        estilos += [("LINEBELOW", (0, 0), (-1, 0), 1.2, INDIGO),
                    ("TOPPADDING", (0, 0), (-1, 0), 3), ("BOTTOMPADDING", (0, 0), (-1, 0), 6)]
    if len(dados) <= 10 and not dividir:
        estilos.append(("NOSPLIT", (0, 0), (-1, -1)))
    if estilos_extra:
        estilos += estilos_extra
    t.setStyle(TableStyle(estilos))
    return [t, Spacer(1, 12)]


def ficha(itens):
    """Faixa de resumo: valor em destaque e legenda pequena, separadas por fios."""
    n = len(itens)
    larg = LARGURA / n
    linha = [[Paragraph(e(r), S["ficha_l"]), Paragraph(e(v), S["ficha_v"])] for r, v in itens]
    dados = [[Table([[a], [b]], colWidths=[larg - 14], style=TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])) for a, b in linha]]
    t = Table(dados, colWidths=[larg] * n)
    est = [
        ("LINEABOVE", (0, 0), (-1, 0), 2.2, INDIGO),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for i in range(1, n):
        est.append(("LINEBEFORE", (i, 0), (i, 0), 0.6, FIO))
    t.setStyle(TableStyle(est))
    return [t, Spacer(1, 14)]


def callout(titulo, texto, tom="info"):
    cor = {"info": INDIGO, "aviso": AMBAR}[tom]
    fundo = {"info": colors.HexColor("#EEF0FD"), "aviso": colors.HexColor("#FFF4DC")}[tom]
    titulo_st = ParagraphStyle("ct", parent=S["call_t"], textColor=cor)
    conteudo = [Paragraph(e(titulo), titulo_st), Paragraph(_mono_inline(texto), S["call_b"])]
    t = Table([["", conteudo]], colWidths=[3, LARGURA - 3 - 2.6 * cm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), cor),
        ("BACKGROUND", (1, 0), (1, 0), fundo),
        ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 12), ("RIGHTPADDING", (1, 0), (1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [t, Spacer(1, 12)]


# ---- codigo com realce de sintaxe ----------------------------------------
_COR_TOKEN = [
    (Token.Comment, ("#7C86A8", "i")),
    (Token.Keyword, ("#A5B4FF", "")),
    (Token.Operator.Word, ("#A5B4FF", "")),
    (Token.Name.Builtin, ("#A5B4FF", "")),
    (Token.Name.Decorator, ("#FFC98B", "")),
    (Token.Name.Function, ("#FFFFFF", "b")),
    (Token.Name.Class, ("#FFFFFF", "b")),
    (Token.Name.Tag, ("#A5B4FF", "")),
    (Token.Name.Attribute, ("#FFC98B", "")),
    (Token.Name.Variable, ("#FFC98B", "")),
    (Token.Literal.String, ("#8FE3BC", "")),
    (Token.Literal.Number, ("#FFC98B", "")),
    (Token.Keyword.Constant, ("#FFC98B", "")),
]


def _estilo_token(tok):
    escolhido = None
    for base, estilo in _COR_TOKEN:
        if tok in base:
            escolhido = estilo
    return escolhido


def _linhas_realce(texto, lang):
    """Devolve uma lista de linhas ja marcadas (cada linha fecha as suas tags)."""
    linhas = _linhas_realce_bruto(texto, lang)
    # linhas vazias precisam de um caractere, senao o XPreformatted as engole
    return [ln if re.sub(r"<[^>]+>", "", ln).strip() else "&nbsp;" for ln in linhas]


def _linhas_realce_bruto(texto, lang):
    linhas = texto.rstrip("\n").split("\n")
    if lang == "term":
        saida = []
        anterior_continua = False
        for ln in linhas:
            if ln.startswith("$"):
                saida.append(f"<font color='#37D399'>$</font> <font color='#FFFFFF'>{e(ln[2:])}</font>")
                anterior_continua = ln.rstrip().endswith("\\")
            elif anterior_continua:
                saida.append(f"<font color='#FFFFFF'>{e(ln)}</font>")
                anterior_continua = ln.rstrip().endswith("\\")
            elif ln.startswith("HTTP"):
                m = re.match(r"HTTP (\d+)", ln)
                cor = "#37D399" if m and m.group(1).startswith("2") else "#FFC98B"
                saida.append(f"<font color='{cor}'><b>{e(ln)}</b></font>")
            else:
                saida.append(f"<font color='#AAB4DD'>{e(ln)}</font>")
        return saida
    lexer = {"py": PythonLexer(), "sh": BashLexer(), "ini": IniLexer()}.get(lang)
    if lexer is None:
        return [f"<font color='{CODE_TXT}'>{e(ln)}</font>" if ln else "" for ln in linhas]
    saida, atual = [], ""
    for tok, val in lex(texto.rstrip("\n") + "\n", lexer):
        estilo = _estilo_token(tok)
        partes = val.split("\n")
        for i, parte in enumerate(partes):
            if i > 0:
                saida.append(atual)
                atual = ""
            if not parte:
                continue
            txt = e(parte)
            if estilo:
                cor, fmt = estilo
                if "b" in fmt:
                    txt = f"<b>{txt}</b>"
                if "i" in fmt:
                    txt = f"<i>{txt}</i>"
                txt = f"<font color='{cor}'>{txt}</font>"
            atual += txt
    if atual:
        saida.append(atual)
    while saida and not saida[-1].strip():
        saida.pop()
    return saida


def codigo(texto, lang="txt", titulo=None, numeros=False, max_linhas=14):
    """Painel de codigo escuro, com barra de titulo opcional; atravessa paginas em blocos."""
    linhas = _linhas_realce(texto, lang)
    n_gut = 26 if numeros else 0
    dados, estilos = [], []
    r = 0
    if titulo:
        dados.append([Paragraph(f"<font name='Mono' size='7.2' color='#AAB4DD'>{e(titulo)}</font>",
                                ParagraphStyle("ctit", fontName="Mono", fontSize=7.2, leading=9)), ""])
        estilos += [("BACKGROUND", (0, 0), (-1, 0), CODE_BARRA),
                    ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("SPAN", (0, 0), (-1, 0))]
        r = 1
    for ini in range(0, len(linhas), max_linhas):
        bloco = linhas[ini:ini + max_linhas]
        cod = XPreformatted("\n".join(bloco), COD_ST)
        if numeros:
            gut = XPreformatted("\n".join(str(ini + i + 1) for i in range(len(bloco))), NUM_ST)
            dados.append([gut, cod])
        else:
            dados.append([cod, ""])
    cols = [n_gut, LARGURA - n_gut] if numeros else [LARGURA, 0]
    if not numeros:
        cols = [LARGURA, 0.01]
    t = Table(dados, colWidths=cols if numeros else [LARGURA - 0.01, 0.01])
    estilos += [
        ("BACKGROUND", (0, r), (-1, -1), CODE_BG),
        ("LEFTPADDING", (0, r), (-1, -1), 12), ("RIGHTPADDING", (0, r), (-1, -1), 12),
        ("TOPPADDING", (0, r), (-1, -1), 2), ("BOTTOMPADDING", (0, r), (-1, -1), 2),
        ("TOPPADDING", (0, r), (-1, r), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if titulo:
        estilos += [("LEFTPADDING", (0, 0), (-1, 0), 12), ("NOSPLIT", (0, 0), (-1, min(1, len(dados) - 1)))]
    if numeros:
        estilos += [("LEFTPADDING", (0, r), (0, -1), 4), ("RIGHTPADDING", (0, r), (0, -1), 4),
                    ("LEFTPADDING", (1, r), (1, -1), 8), ("RIGHTPADDING", (1, r), (1, -1), 12)]
    t.setStyle(TableStyle(estilos))
    return [t, Spacer(1, 12)]


def figura(caminho, legenda, alt_max=10 * cm, larg_max=None):
    N_FIG[0] += 1
    larg_max = larg_max or LARGURA
    with Image.open(caminho) as im:
        w, h = im.size
    escala = min(larg_max / w, alt_max / h)
    cap = Paragraph(f"<font name='Inter-SemiBold' color='{TINTA_HEX}'>Figura {N_FIG[0]}</font>"
                    f"&nbsp;&nbsp;{legenda}", S["cap"])
    return Figura(caminho, w * escala, h * escala, cap)


class Figura(Flowable):
    """Imagem com legenda, tratada como um bloco unico (nao quebra entre paginas)."""

    def __init__(self, caminho, w, h, legenda):
        super().__init__()
        self.caminho, self.w, self.h, self.legenda = caminho, w, h, legenda

    def wrap(self, aw, ah):
        _, hc = self.legenda.wrap(aw, ah)
        self.hc = hc + self.legenda.style.spaceBefore + self.legenda.style.spaceAfter
        return aw, self.h + self.hc

    def draw(self):
        self.canv.drawImage(self.caminho, 0, self.hc, self.w, self.h, mask="auto")
        self.legenda.drawOn(self.canv, 0, self.legenda.style.spaceAfter)


class SkuDecoder(Flowable):
    """Mostra como ler o nome do tamanho da VM, parte por parte."""

    def __init__(self, partes, altura=70):
        super().__init__()
        self.partes, self.altura = partes, altura

    def wrap(self, aw, ah):
        self.largura = aw
        return aw, self.altura

    def draw(self):
        c = self.canv
        n = len(self.partes)
        col = self.largura / n
        for i, (codigo_, legenda) in enumerate(self.partes):
            x0 = i * col
            larg_chip = max(34, pdfmetrics.stringWidth(codigo_, "Inter-Bold", 15) + 20)
            cx = x0 + col / 2
            c.setFillColor(colors.HexColor("#EEF0FD"))
            c.setStrokeColor(INDIGO)
            c.setLineWidth(0.8)
            c.roundRect(cx - larg_chip / 2, self.altura - 34, larg_chip, 30, 5, stroke=1, fill=1)
            c.setFillColor(INDIGO)
            c.setFont("Inter-Bold", 15)
            c.drawCentredString(cx, self.altura - 25, codigo_)
            c.setStrokeColor(FIO)
            c.setLineWidth(0.7)
            c.line(cx, self.altura - 34, cx, self.altura - 42)
            p = Paragraph(legenda, ParagraphStyle("sk", fontName="Inter", fontSize=7.6, leading=9.6,
                                                  textColor=MUTED, alignment=1))
            _, h = p.wrap(col - 8, 40)
            p.drawOn(c, x0 + 4, self.altura - 44 - h)


class CartaoEvidencia(Flowable):
    """Cartao de evidencia: numero, titulo, print(s) e o que ele comprova."""

    CAB = 30
    PAD = 10

    def __init__(self, ident, titulo, comprova, imagens, alt_max=8.4 * cm, pendente_txt=None):
        super().__init__()
        self.ident, self.titulo, self.comprova = ident, titulo, comprova
        self.imagens = imagens
        self.alt_max = alt_max
        self.pendente_txt = pendente_txt
        self.keepWithNext = False
        self.spaceAfter = 16

    def _dimensoes(self):
        interna = self.largura - 2 * self.PAD
        dims = []
        for caminho in self.imagens:
            with Image.open(caminho) as im:
                w, h = im.size
            esc = min(interna / w, self.alt_max / h)
            dims.append((w * esc, h * esc))
        return dims

    def wrap(self, aw, ah):
        self.largura = aw
        self.dims = self._dimensoes()
        self.p_comp = Paragraph(
            f"<font name='Inter-SemiBold' color='{TINTA_HEX}'>O que comprova.</font> {e(self.comprova)}",
            S["evid"])
        _, self.h_comp = self.p_comp.wrap(aw - 2 * self.PAD - 2, 100)
        corpo = sum(h for _, h in self.dims) + 8 * max(0, len(self.dims) - 1) if self.dims else 64
        self.altura = self.CAB + self.PAD + corpo + self.PAD + self.h_comp + self.PAD + 2
        return aw, self.altura

    def draw(self):
        c = self.canv
        w, h = self.largura, self.altura
        c.setStrokeColor(FIO)
        c.setLineWidth(0.8)
        c.setFillColor(colors.white)
        c.roundRect(0, 0, w, h, 5, stroke=1, fill=1)
        # cabecalho
        c.setFillColor(FUNDO_SUAVE)
        c.saveState()
        p = c.beginPath()
        p.roundRect(0, h - self.CAB, w, self.CAB, 5)
        c.clipPath(p, stroke=0, fill=0)
        c.rect(0, h - self.CAB, w, self.CAB, stroke=0, fill=1)
        c.restoreState()
        c.setFillColor(FUNDO_SUAVE)
        c.rect(0, h - self.CAB, w, self.CAB - 6, stroke=0, fill=1)
        c.setStrokeColor(FIO)
        c.line(0, h - self.CAB, w, h - self.CAB)
        c.setFillColor(INDIGO)
        c.roundRect(self.PAD, h - self.CAB + 7, 26, 16, 3.5, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Inter-Bold", 8.6)
        c.drawCentredString(self.PAD + 13, h - self.CAB + 12, self.ident)
        c.setFillColor(TINTA)
        c.setFont("Inter-SemiBold", 9.6)
        c.drawString(self.PAD + 36, h - self.CAB + 11.5, self.titulo)
        # prints
        y = h - self.CAB - self.PAD
        if not self.dims:
            c.setStrokeColor(AMBAR)
            c.setDash(3, 3)
            c.setFillColor(colors.HexColor("#FFF9EC"))
            c.roundRect(self.PAD, y - 64, w - 2 * self.PAD, 64, 4, stroke=1, fill=1)
            c.setDash()
            c.setFillColor(AMBAR)
            c.setFont("Inter-SemiBold", 9)
            c.drawCentredString(w / 2, y - 28, "Print pendente")
            c.setFont("Inter", 8)
            c.drawCentredString(w / 2, y - 42, self.pendente_txt or "")
            y -= 64
        for (iw, ih), caminho in zip(self.dims, self.imagens):
            x = (w - iw) / 2
            c.drawImage(caminho, x, y - ih, iw, ih)
            c.setStrokeColor(FIO)
            c.setLineWidth(0.6)
            c.rect(x, y - ih, iw, ih, stroke=1, fill=0)
            y -= ih + 8
        y += 8
        self.p_comp.drawOn(c, self.PAD + 1, y - self.PAD - self.h_comp)


# --------------------------------------------------------------------------
# Paginas
# --------------------------------------------------------------------------
def _texto(c, x, y, s, fonte, tam, cor=colors.white, alpha=1.0, ancora="l", espaco=0):
    c.saveState()
    c.setFillColor(cor)
    c.setFillAlpha(alpha)
    t = c.beginText()
    t.setTextOrigin(x, y)
    t.setFont(fonte, tam)
    t.setCharSpace(espaco)
    if ancora == "r":
        t.setTextOrigin(x - pdfmetrics.stringWidth(s, fonte, tam) - espaco * len(s), y)
    elif ancora == "c":
        t.setTextOrigin(x - pdfmetrics.stringWidth(s, fonte, tam) / 2, y)
    t.textOut(s)
    c.drawText(t)
    c.restoreState()


def desenhar_capa(c, doc):
    W, H = A4
    c.saveState()
    c.setFillColor(INDIGO)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    ml = 2.1 * cm

    # topo
    _texto(c, ml, H - 52, CFG["disciplina"], "Inter-SemiBold", 10.5)
    _texto(c, ml, H - 67, CFG["professor"], "Inter", 9.5, alpha=0.7)
    larg_turma = pdfmetrics.stringWidth(CFG["turma"], "Inter-SemiBold", 9.5) + 22
    c.setStrokeColor(colors.white)
    c.setStrokeAlpha(0.6)
    c.setLineWidth(0.8)
    c.roundRect(W - ml - larg_turma, H - 66, larg_turma, 20, 10, stroke=1, fill=0)
    _texto(c, W - ml - larg_turma / 2, H - 59.5, CFG["turma"], "Inter-SemiBold", 9.5, ancora="c")

    # titulo
    _texto(c, ml - 3, H - 190, "API de", "Inter-Display", 80, espaco=-2.2)
    _texto(c, ml - 3, H - 262, "Tarefas", "Inter-Display", 80, espaco=-2.2)
    sub = "API REST com Flask e banco SQLite, publicada de ponta a ponta em uma máquina virtual na Azure."
    from reportlab.lib.utils import simpleSplit
    y = H - 300
    for ln in simpleSplit(sub, "Inter", 13.5, 360):
        _texto(c, ml, y, ln, "Inter", 13.5, alpha=0.9)
        y -= 18.5

    # camadas: do cliente ate o dado
    topo, alt_b = H - 372, 82
    camadas = [
        ("Cliente", "curl ou navegador", "HTTP"),
        ("Rede", f"IP público {CFG['ip_publico']} e NSG", "portas 80 e 22"),
        ("Máquina virtual", f"{AZ['vm_nome']}, Ubuntu 22.04, gunicorn e Flask", AZ["sku"]),
        ("Dados", "SQLite no disco Premium SSD da VM", "/var/lib/api-tarefas/tarefas.db"),
    ]
    for i, (nome, desc, dir_) in enumerate(camadas):
        y_top = topo - i * alt_b
        c.saveState()
        c.setFillColor(colors.black)
        c.setFillAlpha(0.07 + 0.085 * i)
        c.rect(0, y_top - alt_b, W, alt_b, stroke=0, fill=1)
        c.restoreState()
        c.setStrokeColor(colors.white)
        c.setStrokeAlpha(0.22)
        c.setLineWidth(0.6)
        c.line(0, y_top, W, y_top)
        _texto(c, ml, y_top - 38, nome, "Inter-Bold", 16)
        _texto(c, ml, y_top - 55, desc, "Inter", 8.8, alpha=0.75)
        fonte = "Mono" if dir_.startswith("/") else "Inter-Medium"
        _texto(c, W - ml, y_top - 46, dir_, fonte, 8.4 if fonte == "Mono" else 10.5, alpha=0.9, ancora="r")
    c.setStrokeColor(colors.white)
    c.setStrokeAlpha(0.22)
    c.line(0, topo - 4 * alt_b, W, topo - 4 * alt_b)

    # trilha da requisicao atravessando as camadas
    xl = 318
    c.setStrokeColor(colors.white)
    c.setStrokeAlpha(0.95)
    c.setLineWidth(1.3)
    c.line(xl, topo + 12, xl, topo - 4 * alt_b + 14)
    for i in range(4):
        cy = topo - i * alt_b - 42
        c.setFillColor(colors.white)
        c.circle(xl, cy, 5.2, stroke=0, fill=1)
        c.setFillColor(INDIGO)
        c.circle(xl, cy, 2.1, stroke=0, fill=1)
    # rotulo da requisicao
    rot = "POST /tarefas"
    lw = pdfmetrics.stringWidth(rot, "Mono-Bold", 8.4) + 18
    c.setFillColor(colors.white)
    c.setFillAlpha(1)
    c.roundRect(xl - lw / 2, topo + 14, lw, 18, 9, stroke=0, fill=1)
    _texto(c, xl, topo + 19.6, rot, "Mono-Bold", 8.4, cor=INDIGO_ESCURO, ancora="c")

    # rodape da capa
    base = 148
    campos = [
        [("Aluno", CFG["aluno"]), ("RM", CFG["rm"])],
        [("Data", DATA_DOC), ("API", f"http://{CFG['ip_publico']}")],
        [("Repositório", CFG["repo_url"].replace("https://", ""))],
    ]
    xs = [ml, ml + 210, ml + 210 + 150]
    for x, grupo in zip(xs, campos):
        yy = base - 90 + 56
        for rotulo, valor in grupo:
            if not valor:
                continue
            _texto(c, x, yy, rotulo, "Inter", 7.8, alpha=0.6)
            _texto(c, x, yy - 13, valor, "Inter-Medium", 9.6)
            yy -= 36
    c.restoreState()


def desenhar_miolo(c, doc):
    W, H = A4
    c.saveState()
    # cabecalho
    c.setFillColor(INDIGO)
    c.rect(MARGEM_E, H - 1.45 * cm, 5, 5, stroke=0, fill=1)
    c.setFillColor(TINTA)
    c.setFont("Inter-SemiBold", 7.8)
    c.drawString(MARGEM_E + 11, H - 1.45 * cm - 0.5, "API de Tarefas")
    sec = doc.secao_da_pagina(doc.page)
    if sec:
        c.setFillColor(MUTED)
        c.setFont("Inter", 7.8)
        c.drawRightString(W - MARGEM_D, H - 1.45 * cm - 0.5, sec)
    # rodape
    c.setStrokeColor(FIO)
    c.setLineWidth(0.6)
    c.line(MARGEM_E, 1.7 * cm, W - MARGEM_D, 1.7 * cm)
    c.setFillColor(MUTED)
    c.setFont("Inter", 7.8)
    rm = f", RM {CFG['rm']}" if CFG["rm"] else ""
    c.drawString(MARGEM_E, 1.2 * cm, f"{CFG['aluno']}{rm}")
    c.setFillColor(TINTA)
    c.setFont("Inter-SemiBold", 8.4)
    c.drawRightString(W - MARGEM_D, 1.2 * cm, str(doc.page))
    c.restoreState()


class Doc(BaseDocTemplate):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._ant = {"topo": {}, "fim": {}}
        self._novo = {"topo": {}, "fim": {}}
        self._cont = {}
        self._n = 0

    def beforePage(self):
        if self.page == 1:
            self._ant, self._novo = self._novo, {"topo": {}, "fim": {}}
            self._n = 0
        self._cont[self.page] = 0

    def afterFlowable(self, f):
        if isinstance(f, (Spacer, CondPageBreak, PageBreak, NextPageTemplate)):
            return
        self._cont[self.page] = self._cont.get(self.page, 0) + 1
        if isinstance(f, SecaoH1) and f.numero:
            rotulo = f"{f.numero}  {f.titulo}" if f.numero.isdigit() else f"Anexo {f.numero}  {f.titulo}"
            if getattr(f, "y_abs", 0) + f.ALTURA >= A4[1] - self.topMargin - 36:
                self._novo["topo"][self.page] = rotulo
            self._novo["fim"][self.page] = rotulo
        if isinstance(f, SecaoH1) and f.entrada:
            self._n += 1
            chave = f"sec{self._n}"
            self.canv.bookmarkPage(chave)
            self.canv.addOutlineEntry(f"{f.numero}. {f.titulo}", chave, 0, 0)
            txt = f.texto_toc()
            if not f.numero.isdigit():
                txt = (f"<font name='Inter-SemiBold' color='{INDIGO_HEX}'>Anexo {e(f.numero)}</font>"
                       f"&nbsp;&nbsp;{e(f.titulo)}")
            self.notify("TOCEntry", (0, txt, self.page, chave))

    def secao_da_pagina(self, pagina):
        d = self._ant
        if pagina in d["topo"]:
            return d["topo"][pagina]
        for p in range(pagina - 1, 0, -1):
            if p in d["fim"]:
                return d["fim"][p]
        return ""


def sumario():
    toc = TableOfContents()
    toc.rightColumnWidth = 30
    toc.dotsMinLevel = -1
    toc.levelStyles = [ParagraphStyle("toc0", fontName="Inter-Medium", fontSize=10, leading=14,
                                      textColor=TINTA, rightIndent=0)]
    toc.tableStyle = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.45, FIO),
    ])
    return toc


# --------------------------------------------------------------------------
# Conteudo
# --------------------------------------------------------------------------
def conteudo():
    st = []
    az = {k: e(v) for k, v in AZ.items()}

    # 1 ---------------------------------------------------------------
    st.append(P("1. Objetivo e itens da atividade", "h1"))
    st.append(P(
        "A atividade consiste em desenvolver uma API básica com banco de dados SQLite, "
        "hospedá-la de ponta a ponta na nuvem, compartilhar o código no GitHub e entregar a "
        "documentação completa, com esquemas visuais, em PDF. O professor pediu quatro "
        "itens; a tabela indica onde cada um está neste documento."))
    st += ficha([
        ("Linguagem", "Python 3 e Flask"),
        ("Banco de dados", "SQLite"),
        ("Máquina virtual", f"{AZ['sku']}"),
        ("Armazenamento", "Premium SSD 30 GiB"),
    ])
    st += tabela([
        ["Item exigido", "Onde está neste documento"],
        ["1. Prints de tela", "Seção 8 (Evidências), com marca d'água de autoria"],
        ["2. Explicação detalhada", "Seções 2 a 7, 9 e 10, mais os anexos com o código completo"],
        ["3. Link do repositório no Git", f"Capa e seção 11: {e(CFG['repo_url'])}"],
        ["4. Elementos de nuvem: armazenamento, VM (SKU) e linguagem de programação",
         "Seção 5 (e seção 3 para a linguagem)"],
    ], [7.0 * cm, LARGURA - 7.0 * cm])

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
    ], [3.7 * cm, 5.3 * cm, LARGURA - 9.0 * cm], dividir=True)

    # 4 ---------------------------------------------------------------
    st.append(P("4. A API", "h1"))
    st.append(P("4.1 Rotas", "h2"))

    def metodo(m):
        cor = {"GET": VERDE, "POST": INDIGO, "PUT": AMBAR, "DELETE": VERMELHO}[m].hexval().replace("0x", "#")
        return f"<font name='Mono-Bold' size='8' color='{cor}'>{m}</font>"

    def rota(r):
        return f"<font name='Mono' size='8'>{r}</font>"

    st += tabela([
        ["Método", "Rota", "Descrição", "Resposta"],
        [metodo("GET"), rota("/"), "Informações e lista de rotas", "200"],
        [metodo("GET"), rota("/health"), "Verifica a API e o acesso ao banco", "200"],
        [metodo("GET"), rota("/tarefas"), "Lista as tarefas (filtro opcional ?concluida=0 ou 1)", "200"],
        [metodo("GET"), rota("/tarefas/&lt;id&gt;"), "Busca uma tarefa pelo id", "200 ou 404"],
        [metodo("POST"), rota("/tarefas"), "Cria uma tarefa (campo titulo obrigatório)", "201 ou 400"],
        [metodo("PUT"), rota("/tarefas/&lt;id&gt;"), "Atualiza titulo, descricao e/ou concluida", "200, 400 ou 404"],
        [metodo("DELETE"), rota("/tarefas/&lt;id&gt;"), "Remove a tarefa", "204 ou 404"],
    ], [2.2 * cm, 3.7 * cm, LARGURA - 8.9 * cm, 3.0 * cm], forte=False)

    st.append(P("4.2 Exemplos de uso", "h2"))
    st.append(P("Os comandos abaixo foram executados em teste local com o gunicorn. Na VM, troque "
                "<font name='Courier'>127.0.0.1:5000</font> pelo IP público (porta 80).", "body_k"))
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
        "{\"erro\": \"tarefa nao encontrada\"}\n", lang="term", titulo="terminal")

    st.append(P("4.3 Validação e erros", "h2"))
    st += tabela([
        ["Situação", "Resposta"],
        ["Corpo ausente, que não seja JSON ou que não seja um objeto", "400 com {\"erro\": \"...\"}"],
        ["titulo ausente (POST), vazio ou com mais de 120 caracteres", "400"],
        ["concluida diferente de true ou false; descricao que não seja texto", "400"],
        ["Id inexistente em GET, PUT ou DELETE", "404"],
        ["Rota inexistente ou método não permitido", "404 ou 405, também em JSON"],
    ], [LARGURA - 5.5 * cm, 5.5 * cm], forte=False)

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
        ["Máquina virtual", f"{az['vm_nome']}, SKU {az['sku']}, {az['vcpu']} vCPU, {az['ram']} de RAM, {az['imagem']}",
         "Executa o gunicorn, o Flask e o SQLite."],
        ["Armazenamento (disco gerenciado do SO)", az["disco"], "Guarda o sistema, o código, o ambiente Python e o arquivo do banco."],
        ["IP público", "SKU Standard (endereço estático)", "Endereço de acesso à API pela internet."],
        ["NSG (grupo de segurança de rede)", "Entrada liberada: 22/TCP (SSH) e 80/TCP (HTTP)", "Firewall da interface de rede da VM."],
        ["Rede virtual, sub-rede e NIC", "Criadas automaticamente junto com a VM", "Conectividade da VM."],
    ], [4.0 * cm, 6.8 * cm, LARGURA - 10.8 * cm])

    st.append(P("5.2 Máquina virtual e SKU", "h2"))
    st.append(P(
        f"<b>SKU</b> é o código do produto que define o tamanho da máquina. O usado aqui, "
        f"<b>{az['sku']}</b>, se lê assim:"))
    st.append(SkuDecoder([
        ("Standard", "categoria padrão"),
        ("B", "série burstable, com picos de desempenho"),
        ("2", "dois vCPUs"),
        ("a", "processador AMD"),
        ("t", "tiny memory, pouca memória por vCPU"),
        ("s", "aceita discos Premium SSD"),
        ("v2", "segunda geração da série"),
    ]))
    st.append(Spacer(1, 6))
    st.append(P(f"Esse tamanho oferece {az['vcpu']} vCPUs e {az['ram']} de memória."))
    st += callout(
        "Por que Canada Central e não Brazil South",
        "O plano inicial era o Standard_B1s em Brazil South, mas a assinatura usada retornou o erro "
        "SkuNotAvailable (restrição de capacidade) para ele nessa região. Por isso a VM foi criada em "
        f"<b>{az['regiao']}</b>, com o {az['sku']}. O grupo de recursos continua com os metadados em "
        f"{az['regiao_grupo']}, o que não afeta o funcionamento.", tom="aviso")
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
        f"<b>Disco do sistema operacional</b>: disco gerenciado {az['disco']}. O tipo Premium SSD foi o "
        "padrão sugerido pelo portal para este tamanho (a letra <i>s</i> do SKU indica suporte a discos "
        "Premium). A redundância é local (LRS), com três cópias dentro do mesmo datacenter. Para reduzir "
        "custo seria possível trocar para Standard SSD, que também atenderia a uma carga leve como esta.",
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
    st += callout(
        "Apague tudo depois da avaliação",
        "Uma VM desalocada deixa de cobrar computação, mas o disco e o IP público continuam sendo "
        "cobrados. Para encerrar tudo, o comando abaixo remove o grupo de recursos inteiro.", tom="aviso")
    st += codigo(f"az group delete --name {AZ['grupo_recursos']} --yes --no-wait", lang="sh", titulo="Azure CLI")

    # 6 ---------------------------------------------------------------
    st.append(P("6. Banco de dados SQLite", "h1"))
    st.append(P(
        "O SQLite é um banco relacional embutido: todo o banco é um único arquivo, acessado pelo módulo "
        "sqlite3 do Python, sem processo de servidor. A tabela é criada automaticamente na "
        "primeira execução da aplicação (CREATE TABLE IF NOT EXISTS). A evidência 11 mostra o arquivo "
        "do banco na VM e a tarefa gravada nele."))
    st.append(figura(os.path.join(DIAG, "03-modelo-dados.png"), "Modelo de dados: tabela tarefas.", alt_max=7 * cm))
    st += codigo(
        "CREATE TABLE IF NOT EXISTS tarefas (\n"
        "    id            INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    titulo        TEXT    NOT NULL,\n"
        "    descricao     TEXT    NOT NULL DEFAULT '',\n"
        "    concluida     INTEGER NOT NULL DEFAULT 0,\n"
        "    criada_em     TEXT    NOT NULL,\n"
        "    atualizada_em TEXT    NOT NULL\n"
        ");", lang="txt", titulo="SQL")
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
        f"az vm show -d --resource-group {AZ['grupo_recursos']} --name {AZ['vm_nome']} --query publicIps -o tsv",
        lang="sh", titulo="Azure CLI")
    st.append(P("7.2 Configuração da VM (deploy/setup-vm.sh)", "h2"))
    st.append(P(
        "Depois de conectar com <font name='Courier'>ssh azureuser@IP_PUBLICO</font>, o script instala "
        "python3-venv e git, clona o repositório em /opt/api-tarefas, cria o ambiente virtual, instala "
        "as dependências do requirements.txt, registra o serviço no systemd e testa o /health.", "body_k"))
    st += codigo(f"./setup-vm.sh {CFG['repo_url']}.git", lang="sh", titulo="dentro da VM")
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
        "sudo systemctl restart api-tarefas", lang="sh", titulo="dentro da VM")
    return st


def segunda_parte():
    st = []
    st.append(P("9. Testes", "h1"))
    st.append(P("9.1 Testes automatizados", "h2"))
    st.append(P(
        "O arquivo tests/test_api.py usa unittest e o cliente de testes do Flask, com banco temporário. "
        "Os 5 testes passaram na execução local (python -m unittest discover -s tests -v).", "body_k"))
    st += tabela([
        ["Teste", "O que verifica"],
        [f"<font name='Mono' size='7.8'>test_health</font>", "A rota /health responde 200 e acessa o banco."],
        [f"<font name='Mono' size='7.8'>test_crud_completo</font>", "Fluxo POST, GET, PUT (concluida), filtro ?concluida=1, DELETE e GET final com 404."],
        [f"<font name='Mono' size='7.8'>test_validacao</font>", "400 para corpo vazio, título em branco, título com 121 caracteres e corpo que não é JSON."],
        [f"<font name='Mono' size='7.8'>test_sql_injection_nao_funciona</font>", "Um título com SQL malicioso é gravado como texto e a tabela continua existindo."],
        [f"<font name='Mono' size='7.8'>test_404</font>", "Rota inexistente e PUT em id inexistente retornam 404."],
    ], [6.0 * cm, LARGURA - 6.0 * cm], forte=False)
    st.append(P("9.2 Teste na nuvem", "h2"))
    st.append(P(
        "Depois do deploy, os testes manuais são feitos de fora da VM, apontando para o IP público "
        f"(<font name='Courier'>http://{e(CFG['ip_publico'])}</font>). Os resultados estão nas "
        "evidências 7 a 11 da seção 8."))

    st.append(P("10. Segurança, limitações e melhorias", "h1"))
    st += tabela([
        ["Ponto", "Situação atual", "Melhoria sugerida"],
        ["Tráfego HTTP", "Sem criptografia (porta 80)", "Colocar nginx como proxy reverso com certificado Let's Encrypt (HTTPS)."],
        ["Acesso SSH", "Porta 22 aberta para a internet, com login do usuário azureuser", "Restringir a origem ao IP do administrador no NSG, usar chave SSH em vez de senha ou usar o Azure Bastion."],
        ["Autenticação da API", "Rotas públicas, sem login", "Chave de API ou token (JWT) nas rotas de escrita."],
        ["Banco SQLite", "Uma gravação por vez; arquivo em um único disco", "Backup por snapshot ou cópia para Blob; migrar para PostgreSQL/Azure SQL se crescer."],
        ["Disponibilidade", "Uma única VM", "Zonas de disponibilidade e balanceador, o que exigiria banco em serviço gerenciado."],
        ["Entrega do código", "Deploy manual com git pull", "Pipeline de CI/CD (GitHub Actions) com testes automáticos antes de publicar."],
    ], [3.4 * cm, 5.4 * cm, LARGURA - 8.8 * cm], dividir=True)

    st.append(P("11. Repositório e referências", "h1"))
    st.append(P(f"Repositório no GitHub: <b>{e(CFG['repo_url'])}</b>", "body_k"))
    st += codigo(
        "GS-cloud/\n"
        "  app.py                  API Flask + SQLite\n"
        "  requirements.txt        Flask e gunicorn\n"
        "  README.md               Resumo, rotas e como rodar\n"
        "  tests/test_api.py       Testes automatizados\n"
        "  docs/                   Scripts, diagramas e fontes que geram este PDF\n"
        "  deploy/                 Scripts de infraestrutura e o serviço systemd",
        lang="txt", titulo="estrutura do repositório")
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
        st += codigo(f.read(), lang="py", titulo="app.py", numeros=True)
    st.append(PageBreak())
    st.append(P("Anexo B - Arquivos de deploy", "h1"))
    for nome, lang in (("azure-cli.sh", "sh"), ("setup-vm.sh", "sh"), ("api-tarefas.service", "ini")):
        with open(os.path.join(ROOT, "deploy", nome), encoding="utf-8") as f:
            st += codigo(f.read(), lang=lang, titulo=f"deploy/{nome}", numeros=True)
    return st


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------
def main():
    doc = Doc(
        SAIDA, pagesize=A4, leftMargin=MARGEM_E, rightMargin=MARGEM_D,
        topMargin=2.5 * cm, bottomMargin=2.3 * cm,
        title="Documentação - API de Tarefas (Flask + SQLite na Azure)",
        author=CFG["aluno"], subject=CFG["disciplina"],
    )
    quadro = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f",
                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=[quadro], onPage=desenhar_capa),
        PageTemplate(id="miolo", frames=[quadro], onPage=desenhar_miolo),
    ])

    with tempfile.TemporaryDirectory() as tmp:
        story = [Spacer(1, 1), NextPageTemplate("miolo"), PageBreak()]
        story.append(SecaoH1("", "Sumário", entrada=False))
        story.append(Spacer(1, 4))
        story.append(sumario())
        story += conteudo()

        story.append(P("8. Evidências (prints de tela)", "h1"))
        story.append(P(
            "Cada print abaixo recebe, automaticamente, a marca d'água com o nome do aluno e a expressão "
            "\"Evidência Original\". Os arquivos originais ficam intactos em docs/prints."))
        encontrados = 0
        for ident, titulo, comprova in EVIDENCIAS:
            arquivos = achar_prints(ident)
            if not arquivos:
                PENDENCIAS.append(f"print {ident} - {titulo}")
                story.append(CartaoEvidencia(ident, titulo, comprova, [],
                                             pendente_txt=f"Salve em docs/prints/{ident}-nome.png e gere o PDF de novo."))
                continue
            marcadas = []
            for i, arq in enumerate(arquivos):
                encontrados += 1
                destino = os.path.join(tmp, f"{ident}-{i}.jpg")
                aplicar_marca_dagua(arq, destino)
                marcadas.append(destino)
            alt = 7.8 * cm if len(marcadas) == 1 else 6.4 * cm
            story.append(CartaoEvidencia(ident, titulo, comprova, marcadas, alt_max=alt))

        story += segunda_parte()
        doc.multiBuild(story)

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
