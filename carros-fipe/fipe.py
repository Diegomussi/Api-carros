"""Cliente da API pública da FIPE (fipe.online / fipe.api.br).

Não precisa de chave para o uso básico. Se o serviço passar a exigir token,
coloque FIPE_TOKEN no ambiente.
"""
import os
import re
import time

import requests

BASE_URL = os.getenv("FIPE_BASE_URL", "https://fipe.api.br/api/v2").rstrip("/")
TOKEN = os.getenv("FIPE_TOKEN", "")

TIPOS = ("cars", "motorcycles", "trucks")
_ID = re.compile(r"^[A-Za-z0-9._-]{1,20}$")  # ids entram na URL: valida antes

TTL_LISTAS = 24 * 3600   # marcas, modelos e anos quase não mudam
TTL_PRECO = 6 * 3600     # o preço só muda uma vez por mês
_cache: dict[str, tuple[float, object]] = {}


class FipeError(Exception):
    def __init__(self, mensagem: str, status: int = 502):
        super().__init__(mensagem)
        self.status = status


def validar(tipo: str, *ids: str) -> None:
    if tipo not in TIPOS:
        raise FipeError("Tipo de veículo inválido.", 400)
    for i in ids:
        if not _ID.match(str(i)):
            raise FipeError("Identificador inválido.", 400)


def _get(caminho: str, ttl: int):
    agora = time.time()
    hit = _cache.get(caminho)
    if hit and agora - hit[0] < ttl:
        return hit[1]

    headers = {"Accept": "application/json"}
    if TOKEN:
        headers["X-Subscription-Token"] = TOKEN
    try:
        r = requests.get(BASE_URL + caminho, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise FipeError("Não consegui falar com a API da FIPE. Tente de novo.") from e

    if r.status_code == 404:
        raise FipeError("Veículo não encontrado na FIPE.", 404)
    if r.status_code == 429:
        raise FipeError("Limite de consultas da API da FIPE atingido. Tente mais tarde.", 429)
    if not r.ok:
        raise FipeError(f"A API da FIPE respondeu com erro {r.status_code}.")
    try:
        dados = r.json()
    except ValueError as e:
        raise FipeError("Resposta inesperada da API da FIPE.") from e

    _cache[caminho] = (agora, dados)
    return dados


def _lista(dados) -> list[dict]:
    """Aceita lista direta ou o formato antigo {"modelos": [...]}."""
    if isinstance(dados, dict):
        dados = dados.get("modelos", [])
    return [
        {"code": str(d.get("code", d.get("codigo", ""))), "name": str(d.get("name", d.get("nome", "")))}
        for d in dados
        if isinstance(d, dict)
    ]


def parse_preco(texto) -> int:
    """'R$ 10.500,00' -> 10500"""
    if isinstance(texto, (int, float)):
        return int(round(texto))
    limpo = re.sub(r"[^\d,]", "", str(texto)).replace(",", ".")
    if not limpo:
        raise FipeError("Preço ausente na resposta da FIPE.")
    return int(round(float(limpo)))


def marcas(tipo: str) -> list[dict]:
    validar(tipo)
    return _lista(_get(f"/{tipo}/brands", TTL_LISTAS))


def modelos(tipo: str, marca: str) -> list[dict]:
    validar(tipo, marca)
    return _lista(_get(f"/{tipo}/brands/{marca}/models", TTL_LISTAS))


def anos(tipo: str, marca: str, modelo: str) -> list[dict]:
    validar(tipo, marca, modelo)
    return _lista(_get(f"/{tipo}/brands/{marca}/models/{modelo}/years", TTL_LISTAS))


def veiculo(tipo: str, marca: str, modelo: str, ano: str) -> dict:
    """Preço de referência do mês vigente para um veículo."""
    validar(tipo, marca, modelo, ano)
    d = _get(f"/{tipo}/brands/{marca}/models/{modelo}/years/{ano}", TTL_PRECO)
    if not isinstance(d, dict) or "price" not in d:
        raise FipeError("Resposta inesperada da API da FIPE.")
    return {
        "tipo": tipo,
        "marca": d.get("brand", ""),
        "modelo": d.get("model", ""),
        "ano_modelo": d.get("modelYear"),
        "combustivel": d.get("fuel", ""),
        "codigo_fipe": d.get("codeFipe", ""),
        "referencia": d.get("referenceMonth", ""),
        "preco": parse_preco(d["price"]),
    }


def historico(tipo: str, codigo_fipe: str, ano: str) -> list[dict]:
    """Histórico oferecido pela própria API (pode ser curto no plano gratuito)."""
    validar(tipo, codigo_fipe, ano)
    d = _get(f"/{tipo}/{codigo_fipe}/years/{ano}/history", TTL_PRECO)
    itens = d.get("priceHistory", []) if isinstance(d, dict) else []
    saida = []
    for i in itens:
        try:
            saida.append({"referencia": i.get("month", ""), "preco": parse_preco(i.get("price"))})
        except FipeError:
            continue
    return saida
