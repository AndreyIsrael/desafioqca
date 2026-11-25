from pathlib import Path

import httpx
import pandas as pd
import pytest

from coleta_ibge import api
from coleta_ibge.extrator import extrair_dados
from coleta_ibge.navegador import montar_url
from coleta_ibge.planilha import converter_numero_br
from coleta_ibge.texto import chave_ordenacao

HTML_RECIFE = (Path(__file__).parent / "fixtures" / "recife.html").read_text(encoding="utf-8")


def test_extrai_campos_da_pagina_de_recife():
    dados = extrair_dados(HTML_RECIFE)

    assert dados["prefeito"] == "JOÃO HENRIQUE DE ANDRADE LIMA CAMPOS"
    assert dados["gentilico"] == "recifense"
    assert dados["populacao_estimada"] == "1.588.983"
    assert dados["ano_populacao"] == "2026"
    assert dados["area_km2"] == "218,843"
    assert dados["ano_area"] == "2025"


def test_campo_ausente_fica_vazio():
    html = HTML_RECIFE.replace("Gentílico", "Outro indicador")

    dados = extrair_dados(html)

    assert dados["gentilico"] is None
    assert dados["prefeito"] == "JOÃO HENRIQUE DE ANDRADE LIMA CAMPOS"


def test_html_sem_indicadores_nao_inventa_valores():
    dados = extrair_dados("<html><body><p>Página fora do ar</p></body></html>")

    assert all(valor is None for valor in dados.values())


def test_converte_numeros_no_formato_brasileiro():
    convertido = converter_numero_br(pd.Series(["1.588.983", "218,843", "6.803,60", None]))

    assert convertido.iloc[0] == 1588983
    assert convertido.iloc[1] == 218.843
    assert convertido.iloc[2] == 6803.60
    assert pd.isna(convertido.iloc[3])


def test_monta_url_com_acentos_apostrofos_e_nomes_compostos():
    assert montar_url("PE", "Recife").endswith("/pe/recife.html")
    assert montar_url("PE", "Água Preta").endswith("/pe/agua-preta.html")
    assert montar_url("RO", "Alta Floresta D'Oeste").endswith("/ro/alta-floresta-doeste.html")
    assert montar_url("SP", "São João da Boa Vista").endswith("/sp/sao-joao-da-boa-vista.html")


def test_ordenacao_ignora_acentos():
    nomes = ["Agrestina", "Água Preta", "Afrânio"]

    assert sorted(nomes, key=chave_ordenacao) == ["Afrânio", "Agrestina", "Água Preta"]


def _cliente_simulado(respostas: list[httpx.Response]) -> tuple[httpx.Client, list]:
    chamadas = []

    def responder(request: httpx.Request) -> httpx.Response:
        chamadas.append(request.url)
        return respostas[min(len(chamadas), len(respostas)) - 1]

    return httpx.Client(transport=httpx.MockTransport(responder)), chamadas


ESTADOS_JSON = [{"sigla": "PE", "nome": "Pernambuco", "regiao": {"nome": "Nordeste"}}]


def test_repete_requisicao_quando_api_responde_5xx(monkeypatch):
    monkeypatch.setattr(api, "PAUSA_5XX_S", 0)
    cliente, chamadas = _cliente_simulado([httpx.Response(503), httpx.Response(200, json=ESTADOS_JSON)])

    estados = api.listar_estados(cliente)

    assert len(chamadas) == 2
    assert estados == [{"sigla": "PE", "nome": "Pernambuco", "regiao": "Nordeste"}]


def test_desiste_apos_esgotar_tentativas_5xx(monkeypatch):
    monkeypatch.setattr(api, "PAUSA_5XX_S", 0)
    cliente, chamadas = _cliente_simulado([httpx.Response(500)])

    with pytest.raises(api.ErroAPI, match="500"):
        api.listar_estados(cliente)
    assert len(chamadas) == api.TENTATIVAS_5XX


def test_erro_4xx_nao_e_repetido():
    cliente, chamadas = _cliente_simulado([httpx.Response(404)])

    with pytest.raises(api.ErroAPI, match="404"):
        api.listar_estados(cliente)
    assert len(chamadas) == 1
