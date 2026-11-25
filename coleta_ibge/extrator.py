import re

from bs4 import BeautifulSoup, Tag

from coleta_ibge.texto import chave_ordenacao

ROTULOS = {
    "prefeito": "Prefeito",
    "gentilico": "Gentílico",
    "populacao": "População estimada",
    "area": "Área Territorial",
}
VALORES_VAZIOS = {"", "-", "..."}


def _mapear_indicadores(soup: BeautifulSoup) -> dict[str, Tag]:
    indicadores = {}
    for bloco in soup.select("div.indicador"):
        rotulo = bloco.select_one(".ind-label")
        valor = bloco.select_one(".ind-value")
        if rotulo and valor:
            indicadores[chave_ordenacao(rotulo.get_text(" ", strip=True))] = valor
    return indicadores


def _ler_valor(tag: Tag | None) -> tuple[str | None, str | None]:
    if tag is None:
        return None, None
    texto = "".join(tag.find_all(string=True, recursive=False)).strip()
    ano = None
    if tag.small:
        encontrado = re.search(r"\d{4}", tag.small.get_text())
        ano = encontrado.group() if encontrado else None
    return (None if texto in VALORES_VAZIOS else texto), ano


def extrair_dados(html: str) -> dict:
    indicadores = _mapear_indicadores(BeautifulSoup(html, "html.parser"))

    def buscar(campo: str):
        return _ler_valor(indicadores.get(chave_ordenacao(ROTULOS[campo])))

    prefeito, _ = buscar("prefeito")
    gentilico, _ = buscar("gentilico")
    populacao, ano_populacao = buscar("populacao")
    area, ano_area = buscar("area")

    return {
        "prefeito": prefeito,
        "gentilico": gentilico,
        "populacao_estimada": populacao,
        "ano_populacao": ano_populacao,
        "area_km2": area,
        "ano_area": ano_area,
    }
