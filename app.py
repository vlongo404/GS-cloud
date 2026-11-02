"""API de Tarefas - Flask + SQLite.

CRUD minimo de tarefas. O caminho do banco vem da variavel DB_PATH
(na VM da Azure o banco fica em /var/lib/api-tarefas/tarefas.db).
"""
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "tarefas.db"))

app = Flask(__name__)
app.json.ensure_ascii = False  # mantem acentos no JSON

SCHEMA = """
CREATE TABLE IF NOT EXISTS tarefas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo        TEXT    NOT NULL,
    descricao     TEXT    NOT NULL DEFAULT '',
    concluida     INTEGER NOT NULL DEFAULT 0,
    criada_em     TEXT    NOT NULL,
    atualizada_em TEXT    NOT NULL
);
"""


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = conectar()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_db():
    if "db" not in g:
        g.db = conectar()
    return g.db


@app.teardown_appcontext
def fechar_db(_erro):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def tarefa_para_dict(row):
    return {
        "id": row["id"],
        "titulo": row["titulo"],
        "descricao": row["descricao"],
        "concluida": bool(row["concluida"]),
        "criada_em": row["criada_em"],
        "atualizada_em": row["atualizada_em"],
    }


def buscar(tarefa_id):
    return get_db().execute(
        "SELECT * FROM tarefas WHERE id = ?", (tarefa_id,)
    ).fetchone()


def erro(mensagem, status):
    return jsonify({"erro": mensagem}), status


def validar(dados, parcial):
    """Retorna (campos_validos, mensagem_de_erro)."""
    if not isinstance(dados, dict):
        return None, "o corpo deve ser um objeto JSON"

    campos = {}

    if "titulo" in dados:
        titulo = dados["titulo"]
        if not isinstance(titulo, str) or not titulo.strip():
            return None, "'titulo' deve ser um texto nao vazio"
        if len(titulo.strip()) > 120:
            return None, "'titulo' deve ter no maximo 120 caracteres"
        campos["titulo"] = titulo.strip()
    else:
        if not parcial:
            return None, "'titulo' e obrigatorio"

    if "descricao" in dados:
        if not isinstance(dados["descricao"], str):
            return None, "'descricao' deve ser um texto"
        campos["descricao"] = dados["descricao"]

    if "concluida" in dados:
        if not isinstance(dados["concluida"], bool):
            return None, "'concluida' deve ser true ou false"
        campos["concluida"] = int(dados["concluida"])

    return campos, None


@app.get("/")
def raiz():
    return jsonify(
        {
            "api": "API de Tarefas",
            "versao": "1.0",
            "rotas": [
                "GET /health",
                "GET /tarefas",
                "GET /tarefas/<id>",
                "POST /tarefas",
                "PUT /tarefas/<id>",
                "DELETE /tarefas/<id>",
            ],
        }
    )


@app.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return jsonify({"status": "ok", "banco": "sqlite"})


@app.get("/tarefas")
def listar():
    filtro = request.args.get("concluida")
    if filtro in ("0", "1"):
        rows = get_db().execute(
            "SELECT * FROM tarefas WHERE concluida = ? ORDER BY id", (int(filtro),)
        ).fetchall()
    else:
        rows = get_db().execute("SELECT * FROM tarefas ORDER BY id").fetchall()
    return jsonify([tarefa_para_dict(r) for r in rows])


@app.get("/tarefas/<int:tarefa_id>")
def obter(tarefa_id):
    row = buscar(tarefa_id)
    if row is None:
        return erro("tarefa nao encontrada", 404)
    return jsonify(tarefa_para_dict(row))


@app.post("/tarefas")
def criar():
    campos, msg = validar(request.get_json(silent=True), parcial=False)
    if msg is not None:
        return erro(msg, 400)

    db = get_db()
    ts = agora()
    cur = db.execute(
        "INSERT INTO tarefas (titulo, descricao, concluida, criada_em, atualizada_em)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            campos["titulo"],
            campos.get("descricao", ""),
            campos.get("concluida", 0),
            ts,
            ts,
        ),
    )
    db.commit()
    return jsonify(tarefa_para_dict(buscar(cur.lastrowid))), 201


@app.put("/tarefas/<int:tarefa_id>")
def atualizar(tarefa_id):
    if buscar(tarefa_id) is None:
        return erro("tarefa nao encontrada", 404)

    campos, msg = validar(request.get_json(silent=True), parcial=True)
    if msg is not None:
        return erro(msg, 400)

    db = get_db()
    for coluna, valor in campos.items():
        # 'coluna' vem do dicionario validado acima, nunca direto do cliente
        db.execute(
            f"UPDATE tarefas SET {coluna} = ? WHERE id = ?", (valor, tarefa_id)
        )
    db.execute(
        "UPDATE tarefas SET atualizada_em = ? WHERE id = ?", (agora(), tarefa_id)
    )
    db.commit()
    return jsonify(tarefa_para_dict(buscar(tarefa_id)))


@app.delete("/tarefas/<int:tarefa_id>")
def remover(tarefa_id):
    db = get_db()
    cur = db.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))
    db.commit()
    if cur.rowcount == 0:
        return erro("tarefa nao encontrada", 404)
    return "", 204


@app.errorhandler(404)
def nao_encontrado(_e):
    return erro("rota nao encontrada", 404)


@app.errorhandler(405)
def metodo_invalido(_e):
    return erro("metodo nao permitido", 405)


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
