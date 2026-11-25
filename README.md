# Coleta de municípios do IBGE

Gera uma planilha Excel com dados dos municípios de um estado, juntando a API de Localidades do IBGE com as informações do portal Cidades e Estados.

As duas fontes se completam. A API informa quais municípios existem, com código, UF e região, mas não traz prefeito, gentílico, população estimada nem área; esses dados só aparecem nas páginas do portal, que exigem um navegador de verdade para carregar. O programa usa o código IBGE vindo da API como chave para associar cada página ao município certo, e entrega tudo tipado e validado em uma planilha, com o registro do que não pôde ser coletado.

- **httpx**: busca os estados e os municípios da UF escolhida na API.
- **Playwright**: abre a página de cada município no portal e captura o HTML.
- **BeautifulSoup**: extrai prefeito, gentílico, população estimada e área, com os anos de referência.
- **pandas**: limpa, converte os números e exporta o Excel.

A planilha também traz o PIB de cada município (API de Agregados) e abas com o resumo da coleta e os erros encontrados.

## Instalação

Python 3.11 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Execução

```bash
python -m coleta_ibge
```

Escolha o estado pelo número ou pela sigla. Depois informe a quantidade de municípios: Enter usa o padrão de 5, ou digite outro valor até o total da UF. Entradas inválidas são recusadas e a pergunta é repetida.

Exemplo:

```
Escolha o número ou a sigla da UF: RJ
Rio de Janeiro tem 92 municípios na API de Localidades.
Quantidade de municípios [5] (máximo 92): 10
```

Os municípios são processados em ordem alfabética e o arquivo é salvo em `output/municipios_{uf}.xlsx`.

Testes:

```bash
python -m pytest
```

## Fontes

- API de Localidades: https://servicodados.ibge.gov.br/api/docs/localidades
- Portal Cidades e Estados: https://www.ibge.gov.br/cidades-e-estados
- API de Agregados (tabela 5938, PIB): https://servicodados.ibge.gov.br/api/docs/agregados?versao=3

## Decisões

**Dados sempre vindos da API.** Nenhum estado ou código de município fica fixo no código. A região é lida da resposta de estados, e não da hierarquia de cada município (`microrregiao → mesorregiao → UF → regiao`), porque municípios recentes como Boa Esperança do Norte (MT) vêm com `microrregiao` nula e esse caminho quebraria.

**Ordenação.** O `sorted` padrão compara pelo código Unicode, então "Água Preta" ficaria depois de "Vitória". Os nomes são comparados sem acento e sem diferença de maiúsculas (`unicodedata` + `casefold`).

**Montagem da URL.** O nome é normalizado (sem acentos, minúsculo, espaços viram hífen). O apóstrofo é removido em vez de virar hífen, que é o padrão do portal: `Alta Floresta D'Oeste` → `alta-floresta-doeste`. Verificando os 5.571 municípios da API, apóstrofo e hífen são os únicos caracteres fora letras e espaços, e testei casos como `Pingo-d'Água`, `Sant'Ana do Livramento` e `Mogi Guaçu`.

**URL não encontrada.** O portal não devolve 404: ele redireciona para a página do Brasil com status 200, que também tem indicadores. Por isso o status HTTP não serve para detectar o erro. Depois que o conteúdo carrega, comparo o caminho da URL final com o da URL pedida e, se forem diferentes, registro como `url_nao_encontrada`.

**Espera pelo conteúdo.** O Playwright navega até a página e espera o seletor `div.indicador p.ind-value` aparecer antes do `page.content()`, em vez de usar um tempo fixo. Um único navegador é aberto para toda a coleta, com pausa de 1,5 s entre as páginas para não sobrecarregar o portal, e fechado ao final pelo gerenciador de contexto, mesmo em caso de erro.

**Extração pelo nome do campo.** Cada dado da página fica em um bloco `div.indicador`, com o nome em `.ind-label`, o valor em `.ind-value` e o ano em `<small>[2025]</small>`. O extrator monta um dicionário nome → valor e busca os campos por nome, então continua funcionando se a ordem dos blocos mudar. Campo não encontrado vira `None`, nunca um valor padrão.

**Conversão no pandas.** O extrator devolve o texto como está na página (`1.588.983`, `218,843`). O pandas remove o separador de milhar, troca a vírgula decimal e converte com `errors="coerce"`, usando tipos que aceitam vazio (`Int64`, `Float64`). O `codigo_ibge` é validado como texto de 7 dígitos e duplicados são removidos por ele.

**Falhas isoladas.** Erros da API (HTTP, timeout, JSON inválido) viram mensagens claras. Respostas 5xx, que costumam ser instabilidade passageira, são repetidas até 3 vezes; erros 4xx falham direto. Se a página de um município falhar, ele continua na planilha com os dados da API e os campos do portal vazios, e o motivo vai para a aba `ocorrencias`.

## Limitações conhecidas

- O portal usa uma verificação da Cloudflare que bloqueia o modo headless, então o navegador abre visível e precisa de interface gráfica.
- Alguns municípios não exibem todos os campos. Boa Esperança do Norte (MT), por exemplo, não tem gentílico nem área no portal. Esses campos ficam vazios e são registrados em `ocorrencias`.
- Os anos de referência variam entre municípios, por isso são lidos da página.
- A extração depende da estrutura HTML atual do portal; se ela mudar, os campos passam a sair vazios.
- O PIB mais recente disponível é de 2023.
