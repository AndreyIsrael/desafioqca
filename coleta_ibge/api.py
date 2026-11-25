import time

import httpx

from coleta_ibge.texto import chave_ordenacao

URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades"
URL_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados"
TABELA_PIB = 5938
VARIAVEL_PIB = 37
TENTATIVAS_5XX = 3
PAUSA_5XX_S = 1.0


class ErroAPI(Exception):
    pass


def criar_cliente() -> httpx.Client:
    return httpx.Client(timeout=15.0, transport=httpx.HTTPTransport(retries=2))


def _requisitar(cliente: httpx.Client, url: str) -> httpx.Response:
    # Erros 5xx costumam ser instabilidade passageira do servidor do IBGE,
    # então vale tentar de novo; erros 4xx indicam problema real e falham direto.
    for tentativa in range(1, TENTATIVAS_5XX + 1):
        resposta = cliente.get(url)
        if resposta.status_code < 500 or tentativa == TENTATIVAS_5XX:
            return resposta
        time.sleep(PAUSA_5XX_S * tentativa)


def _obter_lista(cliente: httpx.Client, url: str) -> list[dict]:
    try:
        resposta = _requisitar(cliente, url)
        resposta.raise_for_status()
        dados = resposta.json()
    except httpx.TimeoutException as erro:
        raise ErroAPI(f"Tempo esgotado ao consultar {url}") from erro
    except httpx.HTTPStatusError as erro:
        raise ErroAPI(f"A API respondeu {erro.response.status_code} em {url}") from erro
    except httpx.HTTPError as erro:
        raise ErroAPI(f"Falha de conexão ao consultar {url}: {erro}") from erro
    except ValueError as erro:
        raise ErroAPI(f"A resposta de {url} não é um JSON válido") from erro

    if not isinstance(dados, list) or not dados:
        raise ErroAPI(f"A resposta de {url} veio vazia ou em formato inesperado")
    return dados


def listar_estados(cliente: httpx.Client) -> list[dict]:
    dados = _obter_lista(cliente, f"{URL_LOCALIDADES}/estados")
    try:
        estados = [
            {"sigla": item["sigla"], "nome": item["nome"], "regiao": item["regiao"]["nome"]}
            for item in dados
        ]
    except (KeyError, TypeError) as erro:
        raise ErroAPI("A lista de estados não tem os campos esperados") from erro
    return sorted(estados, key=lambda e: chave_ordenacao(e["nome"]))


def listar_municipios(cliente: httpx.Client, uf: str) -> list[dict]:
    dados = _obter_lista(cliente, f"{URL_LOCALIDADES}/estados/{uf}/municipios")
    municipios = {}
    try:
        for item in dados:
            codigo = str(item["id"])
            municipios[codigo] = {"codigo_ibge": codigo, "municipio": item["nome"]}
    except (KeyError, TypeError) as erro:
        raise ErroAPI(f"A lista de municípios de {uf} não tem os campos esperados") from erro
    return sorted(municipios.values(), key=lambda m: chave_ordenacao(m["municipio"]))


def buscar_pib(cliente: httpx.Client, codigos: list[str]) -> dict[str, dict]:
    localidades = ",".join(codigos)
    url = (
        f"{URL_AGREGADOS}/{TABELA_PIB}/periodos/-1/variaveis/{VARIAVEL_PIB}"
        f"?localidades=N6[{localidades}]"
    )
    dados = _obter_lista(cliente, url)
    pib = {}
    try:
        for serie in dados[0]["resultados"][0]["series"]:
            ano, valor = next(iter(serie["serie"].items()))
            pib[serie["localidade"]["id"]] = {"pib_mil_reais": valor, "ano_pib": ano}
    except (KeyError, IndexError, TypeError, StopIteration) as erro:
        raise ErroAPI("A resposta da API de Agregados não tem os campos esperados") from erro
    return pib
