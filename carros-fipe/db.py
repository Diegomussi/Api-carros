"""Persistência em SQLite: histórico de preços e alertas."""
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.getenv("FIPE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fipe.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS precos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo          TEXT NOT NULL,
    codigo_fipe   TEXT NOT NULL,
    ano_id        TEXT NOT NULL,
    marca         TEXT, modelo TEXT, combustivel TEXT,
    referencia    TEXT NOT NULL,
    preco         INTEGER NOT NULL,
    consultado_em TEXT NOT NULL,
    UNIQUE (tipo, codigo_fipe, ano_id, referencia)
);
CREATE TABLE IF NOT EXISTS alertas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo          TEXT NOT NULL,
    marca_id      TEXT NOT NULL,
    modelo_id     TEXT NOT NULL,
    ano_id        TEXT NOT NULL,
    codigo_fipe   TEXT NOT NULL,
    descricao     TEXT NOT NULL,
    preco_alvo    INTEGER NOT NULL,
    ativo         INTEGER NOT NULL DEFAULT 1,
    criado_em     TEXT NOT NULL,
    avisado_ref   TEXT
);
"""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conexao():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with conexao() as con:
        con.executescript(SCHEMA)


def salvar_preco(v: dict, ano_id: str) -> None:
    """Guarda um preço por mês de referência (repetir a consulta não duplica)."""
    with conexao() as con:
        con.execute(
            """INSERT OR IGNORE INTO precos
               (tipo, codigo_fipe, ano_id, marca, modelo, combustivel, referencia, preco, consultado_em)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (v["tipo"], v["codigo_fipe"], ano_id, v["marca"], v["modelo"], v["combustivel"],
             v["referencia"], v["preco"], _agora()),
        )


def salvar_historico_api(tipo: str, codigo: str, ano_id: str, itens: list[dict], base: dict) -> None:
    with conexao() as con:
        for i in itens:
            con.execute(
                """INSERT OR IGNORE INTO precos
                   (tipo, codigo_fipe, ano_id, marca, modelo, combustivel, referencia, preco, consultado_em)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (tipo, codigo, ano_id, base["marca"], base["modelo"], base["combustivel"],
                 i["referencia"], i["preco"], _agora()),
            )


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _chave_mes(referencia: str) -> tuple[int, int]:
    """'novembro de 2026' -> (2026, 11), para ordenar do mais antigo ao mais novo."""
    m = re.match(r"\s*(\w+)\s+de\s+(\d{4})", referencia.lower())
    if not m or m.group(1) not in MESES:
        return (0, 0)
    return (int(m.group(2)), MESES.index(m.group(1)) + 1)


def historico(tipo: str, codigo: str, ano_id: str) -> list[dict]:
    with conexao() as con:
        linhas = con.execute(
            "SELECT referencia, preco FROM precos WHERE tipo=? AND codigo_fipe=? AND ano_id=?",
            (tipo, codigo, ano_id),
        ).fetchall()
    return sorted((dict(l) for l in linhas), key=lambda l: _chave_mes(l["referencia"]))


def criar_alerta(a: dict) -> int:
    with conexao() as con:
        cur = con.execute(
            """INSERT INTO alertas (tipo, marca_id, modelo_id, ano_id, codigo_fipe, descricao, preco_alvo, criado_em)
               VALUES (?,?,?,?,?,?,?,?)""",
            (a["tipo"], a["marca_id"], a["modelo_id"], a["ano_id"], a["codigo_fipe"],
             a["descricao"], a["preco_alvo"], _agora()),
        )
        return cur.lastrowid


def listar_alertas(somente_ativos: bool = False) -> list[dict]:
    sql = "SELECT * FROM alertas" + (" WHERE ativo=1" if somente_ativos else "") + " ORDER BY id DESC"
    with conexao() as con:
        return [dict(l) for l in con.execute(sql).fetchall()]


def remover_alerta(alerta_id: int) -> bool:
    with conexao() as con:
        return con.execute("DELETE FROM alertas WHERE id=?", (alerta_id,)).rowcount > 0


def marcar_avisado(alerta_id: int, referencia: str) -> None:
    with conexao() as con:
        con.execute("UPDATE alertas SET avisado_ref=? WHERE id=?", (referencia, alerta_id))
