"""Gera os diagramas PNG da documentacao (docs/diagramas/)."""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "diagramas")
try:
    with open(os.path.join(AQUI, "config.json"), encoding="utf-8") as _f:
        AZ = json.load(_f)["azure"]
except Exception:
    AZ = {}
REGIAO = AZ.get("regiao", "Canada Central")
SKU = AZ.get("sku", "Standard_B2ats_v2")
VMNOME = AZ.get("vm_nome", "vm-gs")
GRUPO = AZ.get("grupo_recursos", "rg-api-tarefas")
os.makedirs(OUT, exist_ok=True)

from matplotlib import font_manager as _fm

_FONTES = os.path.join(AQUI, "fonts")
if os.path.isdir(_FONTES):
    for _f in ("Inter-Regular.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf"):
        _p = os.path.join(_FONTES, _f)
        if os.path.exists(_p):
            _fm.fontManager.addfont(_p)
    plt.rcParams["font.family"] = "Inter"

AZUL = "#2A38D6"
AZUL_CLARO = "#ECEEFC"
VERDE_CLARO = "#E1F4EC"
LARANJA_CLARO = "#FFF1D6"
CINZA_CLARO = "#F3F4FA"
CINZA = "#6B7385"


def nova_figura(w, h, xmax, ymax):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def caixa(ax, x, y, w, h, texto, fc=AZUL_CLARO, ec=AZUL, size=10, bold=False, ls="-", lw=1.6, va="center"):
    p = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
        fc=fc, ec=ec, lw=lw, ls=ls,
    )
    ax.add_patch(p)
    if texto:
        ax.text(
            x + w / 2, y + h / 2 if va == "center" else y + h - 1.5, texto,
            ha="center", va=va, fontsize=size,
            fontweight="bold" if bold else "normal", color="#111111",
        )


def seta(ax, p1, p2, rotulo=None, dy=1.4, size=9, dx=0, ha="center"):
    ax.annotate(
        "", xy=p2, xytext=p1,
        arrowprops=dict(arrowstyle="-|>", color=CINZA, lw=1.6, shrinkA=0, shrinkB=0),
    )
    if rotulo:
        ax.text(
            (p1[0] + p2[0]) / 2 + dx, (p1[1] + p2[1]) / 2 + dy, rotulo,
            ha=ha, va="bottom", fontsize=size, color=CINZA,
        )


def salvar(fig, nome):
    caminho = os.path.join(OUT, nome)
    fig.savefig(caminho, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("ok", caminho)


# 1) Arquitetura -----------------------------------------------------------
def arquitetura():
    fig, ax = nova_figura(12, 7.0, 120, 72)

    caixa(ax, 2, 28, 15, 12, "Cliente\n(curl / navegador)", fc=CINZA_CLARO, ec=CINZA)
    caixa(ax, 2, 55, 18, 9, "GitHub\n(repositório)", fc=CINZA_CLARO, ec=CINZA)

    caixa(ax, 25, 3, 92, 63, "", fc="white", ec=AZUL, ls="--", lw=1.4)
    ax.text(115, 62.5, f"Azure · {REGIAO} · grupo de recursos {GRUPO}",
            ha="right", va="center", fontsize=9.5, color=AZUL, fontweight="bold")

    caixa(ax, 28, 29, 14, 10, "IP público\n(SKU Standard)", fc=LARANJA_CLARO, ec="#C77700", size=9)
    caixa(ax, 45, 29, 14, 10, "NSG\nporta 80 (HTTP)\nporta 22 (SSH)", fc=LARANJA_CLARO, ec="#C77700", size=8.5)

    caixa(ax, 63, 13, 52, 43, "", fc="white", ec=AZUL, lw=1.8)
    ax.text(89, 53, f"VM {VMNOME} · {SKU} · Ubuntu 22.04",
            ha="center", va="center", fontsize=9.5, fontweight="bold", color=AZUL)
    caixa(ax, 67, 38, 44, 9, "gunicorn (2 workers) · porta 80\nsystemd: api-tarefas.service", fc=VERDE_CLARO, ec="#0E9F6E", size=9)
    caixa(ax, 67, 26, 44, 8, "Flask · app.py (rotas REST)", fc=VERDE_CLARO, ec="#0E9F6E", size=9)
    caixa(ax, 67, 15, 44, 7, "SQLite · /var/lib/api-tarefas/tarefas.db", fc=VERDE_CLARO, ec="#0E9F6E", size=9)

    caixa(ax, 63, 4.5, 52, 5, "Disco de SO · Premium SSD · 30 GiB", fc=AZUL_CLARO, ec=AZUL, size=9)

    seta(ax, (17.4, 34), (27.6, 34), "HTTP :80", dy=2.2, size=8.5)
    seta(ax, (42.4, 34), (44.6, 34))
    seta(ax, (59.4, 34), (62.6, 34))
    seta(ax, (89, 37.6), (89, 34.4), dy=0)
    seta(ax, (89, 25.6), (89, 22.4), dy=0)
    ax.text(91, 24, "sqlite3", va="center", ha="left", fontsize=8, color=CINZA)
    seta(ax, (89, 14.6), (89, 10.1), dy=0)
    seta(ax, (20.4, 59), (62.6, 51), "git clone (deploy)", dy=2.8, dx=0)

    pass
    salvar(fig, "01-arquitetura.png")


# 2) Fluxo de uma requisicao ----------------------------------------------
def fluxo():
    fig, ax = nova_figura(12, 6.2, 120, 62)
    atores = [
        ("Cliente", 12), ("IP público\n+ NSG", 36), ("gunicorn", 60), ("Flask\n(app.py)", 84), ("SQLite", 108),
    ]
    for nome, x in atores:
        caixa(ax, x - 8, 51, 16, 7, nome, fc=AZUL_CLARO, size=9.5, bold=True)
        ax.plot([x, x], [4, 50.5], color="#999999", lw=1, ls=(0, (4, 3)))
    pass

    passos = [
        (12, 36, 45, "1. POST /tarefas (JSON)", False),
        (36, 60, 39, "2. porta 80 liberada na NSG", False),
        (60, 84, 33, "3. repassa à aplicação (WSGI)", False),
        (84, 84, 27.5, "4. valida o JSON", None),
        (84, 108, 22, "5. INSERT INTO tarefas", False),
        (108, 84, 16.5, "6. id da nova linha", True),
        (84, 12, 10.5, "7. 201 Created + JSON da tarefa", True),
    ]
    for x1, x2, y, txt, volta in passos:
        if volta is None:
            ax.annotate("", xy=(x1 + 0.6, y - 2.2), xytext=(x1 + 0.6, y + 1.2),
                        arrowprops=dict(arrowstyle="-|>", color=CINZA, lw=1.4,
                                        connectionstyle="arc3,rad=-0.9"))
            ax.text(x1 + 4, y - 0.5, txt, ha="left", va="center", fontsize=9, color=CINZA)
            continue
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="-|>", color=CINZA, lw=1.5,
                                    ls="--" if volta else "-"))
        ax.text((x1 + x2) / 2, y + 1.1, txt, ha="center", va="bottom", fontsize=9, color="#111111",
                bbox=dict(fc="white", ec="none", pad=1.0))
    salvar(fig, "02-fluxo-requisicao.png")


# 3) Modelo de dados -------------------------------------------------------
def modelo():
    fig, ax = nova_figura(9, 4.6, 90, 46)
    pass
    caixa(ax, 12, 5, 66, 34, "", fc="white", ec=AZUL, lw=1.8)
    caixa(ax, 12, 33, 66, 6, "tarefas", fc=AZUL, ec=AZUL, size=11, bold=True)
    ax.texts[-1].set_color("white")
    linhas = [
        ("id", "INTEGER", "PRIMARY KEY AUTOINCREMENT"),
        ("titulo", "TEXT", "NOT NULL (máx. 120 caracteres na API)"),
        ("descricao", "TEXT", "NOT NULL DEFAULT ''"),
        ("concluida", "INTEGER", "NOT NULL DEFAULT 0  (0 = não, 1 = sim)"),
        ("criada_em", "TEXT", "NOT NULL  (ISO 8601, UTC)"),
        ("atualizada_em", "TEXT", "NOT NULL  (ISO 8601, UTC)"),
    ]
    for i, (c, t, r) in enumerate(linhas):
        y = 29.6 - i * 4.2
        ax.text(15, y, c, fontsize=10, fontweight="bold", va="center", family="monospace")
        ax.text(34, y, t, fontsize=10, va="center", color=AZUL, family="monospace")
        ax.text(46, y, r, fontsize=8.8, va="center", color=CINZA)
    salvar(fig, "03-modelo-dados.png")


# 4) Pipeline de deploy ----------------------------------------------------
def deploy():
    fig, ax = nova_figura(12, 5.2, 120, 52)
    pass
    passos = [
        ("1. Grupo de recursos", f"{GRUPO}\n(portal ou az group create)"),
        ("2. Máquina virtual", f"portal Azure\n{SKU} · Ubuntu 22.04"),
        ("3. Rede", "NSG: portas 22 e 80\n(marcadas na criação)"),
        ("4. Acesso e código", "ssh azureuser@IP\ngit clone do GitHub"),
        ("5. Ambiente Python", "python3 -m venv\npip install -r requirements.txt"),
        ("6. Serviço", "systemd + gunicorn\nenable --now api-tarefas"),
    ]
    # linha de cima: 1 -> 2 -> 3 ; linha de baixo (serpentina): 4 -> 5 -> 6
    pos = [(5, 27), (44, 27), (83, 27), (83, 5), (44, 5), (5, 5)]
    for (titulo, det), (x, y) in zip(passos, pos):
        caixa(ax, x, y, 32, 15, "", fc=AZUL_CLARO, ec=AZUL)
        ax.text(x + 16, y + 11, titulo, ha="center", va="center", fontsize=10.5, fontweight="bold", color=AZUL)
        ax.text(x + 16, y + 5, det, ha="center", va="center", fontsize=8.6, family="monospace", color="#111111")
    seta(ax, (37.6, 34.5), (43.4, 34.5), dy=0)
    seta(ax, (76.6, 34.5), (82.4, 34.5), dy=0)
    seta(ax, (99, 26.4), (99, 20.6), dy=0)
    seta(ax, (82.4, 12.5), (76.6, 12.5), dy=0)
    seta(ax, (43.4, 12.5), (37.6, 12.5), dy=0)
    salvar(fig, "04-deploy.png")


if __name__ == "__main__":
    arquitetura()
    fluxo()
    modelo()
    deploy()
