"""Servidor Flask: consulta à tabela FIPE, histórico de preços e alertas."""
from flask import Flask, jsonify, render_template, request

import db
import fipe

app = Flask(__name__)
db.init_db()


@app.errorhandler(fipe.FipeError)
def erro_fipe(e: fipe.FipeError):
    return jsonify(erro=str(e)), e.status


def _consultar(tipo, marca, modelo, ano) -> dict:
    v = fipe.veiculo(tipo, marca, modelo, ano)
    db.salvar_preco(v, ano)
    try:  # o histórico da API é um extra: se falhar, seguimos só com o que temos no banco
        db.salvar_historico_api(tipo, v["codigo_fipe"], ano, fipe.historico(tipo, v["codigo_fipe"], ano), v)
    except fipe.FipeError:
        app.logger.warning("Histórico da API indisponível para %s", v["codigo_fipe"])
    v["historico"] = db.historico(tipo, v["codigo_fipe"], ano)
    return v


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/<tipo>/marcas")
def api_marcas(tipo):
    return jsonify(fipe.marcas(tipo))


@app.get("/api/<tipo>/marcas/<marca>/modelos")
def api_modelos(tipo, marca):
    return jsonify(fipe.modelos(tipo, marca))


@app.get("/api/<tipo>/marcas/<marca>/modelos/<modelo>/anos")
def api_anos(tipo, marca, modelo):
    return jsonify(fipe.anos(tipo, marca, modelo))


@app.get("/api/<tipo>/marcas/<marca>/modelos/<modelo>/anos/<ano>")
def api_veiculo(tipo, marca, modelo, ano):
    return jsonify(_consultar(tipo, marca, modelo, ano))


@app.get("/api/alertas")
def api_alertas_listar():
    return jsonify(db.listar_alertas())


@app.post("/api/alertas")
def api_alertas_criar():
    d = request.get_json(silent=True) or {}
    try:
        alvo = int(d.get("preco_alvo"))
    except (TypeError, ValueError):
        return jsonify(erro="Informe o preço-alvo em reais, só números."), 400
    if not 0 < alvo < 100_000_000:
        return jsonify(erro="Preço-alvo fora do intervalo válido."), 400

    tipo, marca, modelo, ano = (str(d.get(k, "")) for k in ("tipo", "marca", "modelo", "ano"))
    v = fipe.veiculo(tipo, marca, modelo, ano)  # valida os ids e descobre o código FIPE
    alerta_id = db.criar_alerta(
        {
            "tipo": tipo, "marca_id": marca, "modelo_id": modelo, "ano_id": ano,
            "codigo_fipe": v["codigo_fipe"],
            "descricao": f'{v["marca"]} {v["modelo"]} ({v["ano_modelo"]})',
            "preco_alvo": alvo,
        }
    )
    return jsonify(id=alerta_id), 201


@app.delete("/api/alertas/<int:alerta_id>")
def api_alertas_remover(alerta_id):
    if not db.remover_alerta(alerta_id):
        return jsonify(erro="Alerta não encontrado."), 404
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
