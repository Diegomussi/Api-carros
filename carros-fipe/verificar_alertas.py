"""Confere os alertas ativos e avisa quando o preço FIPE chega ao preço-alvo.

Rode à mão (python verificar_alertas.py) ou agende. A FIPE atualiza uma vez por
mês, então rodar 1 vez por semana já basta. Cada alerta avisa uma vez por mês.
"""
import sys
from datetime import datetime

import db
import fipe


def brl(v: int) -> str:
    return "R$ " + f"{v:,}".replace(",", ".")


def main() -> int:
    db.init_db()
    alertas = db.listar_alertas(somente_ativos=True)
    if not alertas:
        print("Nenhum alerta cadastrado.")
        return 0

    disparados = 0
    for a in alertas:
        try:
            v = fipe.veiculo(a["tipo"], a["marca_id"], a["modelo_id"], a["ano_id"])
        except fipe.FipeError as e:
            print(f'[erro] {a["descricao"]}: {e}')
            continue
        db.salvar_preco(v, a["ano_id"])

        if v["preco"] <= a["preco_alvo"] and a["avisado_ref"] != v["referencia"]:
            msg = (f'{datetime.now():%Y-%m-%d %H:%M} ALERTA: {a["descricao"]} está em '
                   f'{brl(v["preco"])} (alvo {brl(a["preco_alvo"])}) na FIPE de {v["referencia"]}')
            print(msg)
            with open("alertas.log", "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            db.marcar_avisado(a["id"], v["referencia"])
            disparados += 1
        else:
            print(f'[ok] {a["descricao"]}: {brl(v["preco"])} (alvo {brl(a["preco_alvo"])})')
    return disparados


if __name__ == "__main__":
    main()
    sys.exit(0)
