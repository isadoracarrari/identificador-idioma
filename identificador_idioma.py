"""
identificador_idioma.py
=======================
Identifica o idioma de uma página web comparando a frequência de letras
do texto com perfis de referência carregados de 'letter_frequency.csv'.

Uso:
    python identificador_idioma.py
    (o programa pedirá a URL interativamente)

Ou direto:
    python identificador_idioma.py https://pt.wikipedia.org/wiki/Brasil

Dependências:
    pip install requests
"""

import sys #para argumentos de linha de comando e saída de erros
import re #para expressões regulares na limpeza do HTML, localizar e substituir texto
import csv #para ler o arquivo CSV de perfis de frequência
import math #fornece funções matemáticas para cálculos de distância e similaridade
import unicodedata #para lidar com complexidade de caracteres, normalização e remoção de acentos
from pathlib import Path #para manipulação de caminhos de arquivos em qualquer sistema operacional (Windows, Linux, etc.)

try: #é uma rede de segurança em caso de erro
    import requests #para fazer requisições HTTP e baixar o conteúdo da página
except ImportError:
    sys.exit("Erro: instale a biblioteca requests  →  pip install requests")


# ─────────────────────────────────────────────
# 1. Download do texto bruto
# ─────────────────────────────────────────────

def baixar_texto(url: str) -> str:
    """Faz o download de uma URL e retorna o texto bruto da resposta."""
    try:
        headers = { 
            "User-Agent": ( #User-Agent comum para evitar bloqueios por parte de alguns sites, se "disfarça" de navegador moderno
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resposta = requests.get(url, headers=headers, timeout=15) #O programa acessa a URL e baixa seu conteúdo. Timeout de 15 segundos para evitar ficar preso em sites lentos ou que nao respondem
        resposta.raise_for_status() #Verifica se o programa deu certo
    except requests.exceptions.MissingSchema:
        sys.exit(f"Erro: URL inválida -> '{url}'. Inclua o esquema (https://...)") #Verifica se a URL tem um esquema válido (http:// ou https://)
    except requests.exceptions.ConnectionError:
        sys.exit(f"Erro: nao foi possivel conectar a '{url}'.")
    except requests.exceptions.Timeout:
        sys.exit("Erro: tempo de conexao esgotado.")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"Erro HTTP: {e}")

    resposta.encoding = resposta.apparent_encoding #Tenta detectar a codificação correta do texto para evitar problemas com acentuação
    return resposta.text #Retorna o conteúdo HTML bruto da página como uma string


# ─────────────────────────────────────────────
# 2. Limpeza do texto
# ─────────────────────────────────────────────

# Remove blocos inteiros sem conteudo textual util (JS, CSS, menus, etc.)
_RE_BLOCOS_RUIDO = re.compile(
    r"<(script|style|head|noscript|nav|footer|header|meta|link)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Extrai apenas paragrafos e titulos — as tags mais confiáveis de conteudo
# (div/span sao excluidas pois em sites como Wikipedia carregam muito lixo de UI)
_RE_PARAGRAFOS = re.compile(
    r"<(p|h[1-6]|blockquote|figcaption|article|main|td|th)[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Fallback: extrai li e section se parágrafos não forem encontrados
_RE_FALLBACK = re.compile(
    r"<(li|section|div)[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Remove qualquer tag HTML restante
_RE_TAG_GENERICA = re.compile(r"<[^>]+>")

# Remove entidades HTML (&amp; &nbsp; &#123; etc.)
_RE_ENTIDADE = re.compile(r"&[a-zA-Z0-9#]+;")


def _extrair_texto_html(html: str) -> str:
    """
    Extrai o texto visivel de uma pagina HTML:
    1. Remove blocos de ruido (script, style, nav, footer, head) por completo.
    2. Coleta apenas <p>, <h1>-<h6>, <blockquote>, <article>, <main>, <td>, <th>.
       Essas tags sao as mais confiaveis — div e span sao evitadas pois carregam
       muito conteudo de interface (menus, categorias, widgets) em sites como Wikipedia.
    3. Fallback para <li>/<section>/<div> se nenhum paragrafo for encontrado.
    """
    # Passo 1: apaga blocos irrelevantes inteiros
    html = _RE_BLOCOS_RUIDO.sub(" ", html) #Substitui blocos inteiros por espaço para evitar concatenação de palavras quando removemos as tags

    # Passo 2: coleta paragrafos e titulos
    trechos = _RE_PARAGRAFOS.findall(html) #Retorna uma lista de tuplas (tag, conteúdo) para cada bloco encontrado

    if not trechos:
        # Fallback: tenta li/section/div se a pagina nao usa <p>
        trechos = _RE_FALLBACK.findall(html) #Se ainda assim nao encontrar nada, o resultado final sera vazio

    if trechos:
        conteudo = " ".join(c for _, c in trechos) #Concatena apenas o conteúdo dos blocos encontrados, ignorando as tags
    else:
        # Último recurso: remove todas as tags genericamente
        conteudo = _RE_TAG_GENERICA.sub(" ", html) #Se não encontrar nenhum bloco confiável, extrair o texto bruto removendo todas as tags. Isso pode incluir muito ruído, mas evita que o resultado fique vazio.

    # Remove tags internas residuais e entidades HTML
    conteudo = _RE_TAG_GENERICA.sub(" ", conteudo) #Remove qualquer tag que tenha sobrado dentro do conteúdo extraído (ex: <p>Texto <b>importante</b></p> -> "Texto importante")
    conteudo = _RE_ENTIDADE.sub(" ", conteudo) #Remove entidades HTML comuns (ex: &amp; -> " ", &nbsp; -> " ", &#123; -> " "). Isso evita que caracteres como & ou espaços extras aparecam no texto final.
    return conteudo #Retorna o texto limpo, contendo apenas o conteúdo textual relevante da página


def limpar_texto(texto: str, remover_acentos: bool = False) -> str: 
    """
    Extrai texto relevante do HTML e retorna apenas letras em minúsculas.
    Se remover_acentos=True, converte letras acentuadas para base ASCII.
    """
    texto = _extrair_texto_html(texto)

    # Normaliza unicode NFC (forma canonica composta)
    texto = unicodedata.normalize("NFC", texto).lower()

    if remover_acentos:
        # Decomposicao NFD + remocao de marcas diacriticas
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    # Mantém apenas letras (categoria Unicode "L*")
    texto = "".join(c for c in texto if unicodedata.category(c).startswith("L"))

    return texto


# ─────────────────────────────────────────────
# 3. Cálculo de frequência
# ─────────────────────────────────────────────

def calcular_frequencia(texto_limpo: str) -> dict:
    """
    Calcula a frequência relativa (0-100) de cada letra no texto.
    Retorna um dicionário, uma lista de pares chave: valor, onde a chave é a letra e o valor é seu percentual {letra: percentual}.
    """
    if not texto_limpo:
        sys.exit("Erro: o texto ficou vazio apos a limpeza. Verifique a URL.")

    contagem = {}
    for letra in texto_limpo: #percorre o texto, uma letra de cada vez, e conta quantas vezes cada letra aparece. O resultado é um dicionário onde a chave é a letra e o valor é a quantidade de vezes que ela aparece no texto
        contagem[letra] = contagem.get(letra, 0) + 1

    total = sum(contagem.values()) #soma a contagem de todas as letras para saber o total
    return {letra: (qtd / total) * 100 for letra, qtd in contagem.items()} #Gera o dicionário final. Para cada par letra: quantidade no dicionário contagem, ele calcula o percentual ((qtd / total) * 100) e retorna o resultado.


# ─────────────────────────────────────────────
# 4. Carregamento dos perfis do CSV
# ─────────────────────────────────────────────

def _parse_pct(valor: str) -> float:
    """Converte '7.636%', '7.636%*' ou '9.600%*' para float. Retorna 0.0 se vazio."""
    valor = valor.strip().replace("%", "").replace("*", "").strip()
    return float(valor) if valor else 0.0


def carregar_perfis(caminho_csv: str = "letter_frequency.csv") -> dict:
    """
    Lê o arquivo CSV e retorna:
        { idioma: { letra: percentual, ... }, ... }
    """
    caminho = Path(caminho_csv)
    if not caminho.exists():
        sys.exit(
            f"Erro: arquivo '{caminho_csv}' nao encontrado.\n"
            "Coloque o arquivo letter_frequency.csv na mesma pasta do script."
        )

    perfis = {}

    with open(caminho, newline="", encoding="utf-8") as f: #Abre o arquivo CSV de forma segura
        leitor = csv.DictReader(f, delimiter=";") #Usa a ferramenta de CSV para ler o arquivo como uma série de dicionários, o que facilita o acesso aos dados por nome de coluna
        idiomas = [col for col in leitor.fieldnames if col != "Letter"] #Pega os nomes de todas as colunas do cabeçalho do CSV

        for idioma in idiomas:
            perfis[idioma] = {}

        for linha in leitor: #Lê o arquivo linha por linha
            letra = linha["Letter"].strip()
            for idioma in idiomas:
                perfis[idioma][letra] = _parse_pct(linha[idioma]) #Monta o dicionário de perfis

    return perfis


# ─────────────────────────────────────────────
# 5. Comparacao de perfis
# ─────────────────────────────────────────────

def _distancia_euclidiana(freq_a: dict, freq_b: dict) -> float:
    """Distancia euclidiana entre dois perfis de frequencia."""
    todas_letras = set(freq_a) | set(freq_b)
    return math.sqrt(
        sum((freq_a.get(l, 0) - freq_b.get(l, 0)) ** 2 for l in todas_letras)
    )


def _similaridade_cosseno(freq_a: dict, freq_b: dict) -> float:
    """Similaridade de cosseno entre dois perfis (0 = ortogonal, 1 = identico).
    Calcula a similaridade entre o texto da URL e cada idioma do gabarito."""
    todas_letras = set(freq_a) | set(freq_b)
    dot = sum(freq_a.get(l, 0) * freq_b.get(l, 0) for l in todas_letras)
    norm_a = math.sqrt(sum(v ** 2 for v in freq_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in freq_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _bonus_exclusividade(freq_texto: dict, perfis: dict) -> dict:
    """
    Calcula um bônus por idioma baseado em letras que aparecem no texto
    e que sao exclusivas (ou quase) de certos idiomas.
    Ex: 'a tilde' (a com til) só existe em português — se o texto tem essa letra,
    é um forte sinal de que o idioma é portugues.
    """
    bonus = {idioma: 0.0 for idioma in perfis}
    for letra, freq_t in freq_texto.items():
        if freq_t == 0:
            continue
        tem = {i for i in perfis if perfis[i].get(letra, 0) > 0}
        nao_tem = {i for i in perfis if perfis[i].get(letra, 0) == 0}
        if not tem or not nao_tem:
            continue
        # Quanto menos idiomas tiverem a letra, mais exclusiva ela é
        exclusividade = len(nao_tem) / len(perfis)
        for idioma in tem:
            bonus[idioma] += freq_t * exclusividade
    return bonus


def comparar_perfis(freq_texto: dict, perfis: dict, metodo: str = "cosseno") -> tuple:
    """
    Compara freq_texto com cada perfil usando dois criterios combinados:
      1. Similaridade de cosseno (ou distancia euclidiana) — 60%
      2. Bonus por letras exclusivas do idioma — 40%
         Ex: 'a tilde' aponta fortemente para portugues; 'enhe' para espanhol.
    Retorna (idioma_mais_provavel, score_melhor, todos_os_scores).
    """
    scores_base = {}
    for idioma, perfil in perfis.items():
        if metodo == "euclidiana":
            # Inverte para que maior = melhor (consistente com cosseno)
            scores_base[idioma] = 1 / (1 + _distancia_euclidiana(freq_texto, perfil))
        else:
            scores_base[idioma] = _similaridade_cosseno(freq_texto, perfil)

    bonus = _bonus_exclusividade(freq_texto, perfis)

    # Normaliza cada componente para [0, 1]
    max_b = max(scores_base.values()); min_b = min(scores_base.values())
    max_x = max(bonus.values()) if max(bonus.values()) > 0 else 1.0

    scores_final = {}
    for idioma in perfis:
        b_norm = (scores_base[idioma] - min_b) / (max_b - min_b + 1e-9)
        x_norm = bonus[idioma] / (max_x + 1e-9)
        scores_final[idioma] = b_norm * 0.6 + x_norm * 0.4

    melhor = max(scores_final, key=scores_final.get) #encontra o idioma com o melhor score final
    return melhor, scores_final[melhor], scores_final


# ─────────────────────────────────────────────
# 6. Função principal
# ─────────────────────────────────────────────

def main():
    # URL: Verifica se utilizou argumento de linha de comando ou input interativo
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Digite a URL da pagina a analisar: ").strip()

    pasta_script = Path(__file__).parent
    caminho_csv = pasta_script / "letter_frequency.csv"

    print(f"\n[+] Baixando conteudo de: {url}")
    texto_bruto = baixar_texto(url)

    print("[+] Limpando texto (extraindo apenas conteudo textual do HTML)...")
    texto_limpo = limpar_texto(texto_bruto, remover_acentos=False)
    print(f"    {len(texto_limpo):,} letras analisadas.")

    print("[+] Calculando frequencias...")
    freq = calcular_frequencia(texto_limpo)

    print("[+] Carregando perfis de referencia...")
    perfis = carregar_perfis(str(caminho_csv))
    print(f"    {len(perfis)} idiomas carregados: {', '.join(perfis.keys())}")

    print("[+] Comparando perfis (similaridade de cosseno)...")
    idioma, score, todos = comparar_perfis(freq, perfis, metodo="cosseno")

    print("\n" + "=" * 55)
    print(f"  Resultado: {idioma}")
    print(f"  Grau de similaridade: {score:.4f}  (escala 0-1)")
    print("=" * 55)

    # Ranking completo dos idiomas
    ranking = sorted(todos.items(), key=lambda x: x[1], reverse=True)
    print("\n  Ranking completo de idiomas:")
    for pos, (lang, s) in enumerate(ranking, 1):
        marcador = " <-- melhor" if lang == idioma else ""
        print(f"    {pos:2}. {lang:<12}  {s:.4f}{marcador}")

    # Top-5 letras mais frequentes no texto
    top5 = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n  Top 5 letras no texto:")
    for letra, pct in top5:
        print(f"    '{letra}'  ->  {pct:.2f}%")
    print()


if __name__ == "__main__":
    main()