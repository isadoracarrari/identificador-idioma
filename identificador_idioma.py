"""
identificador_idioma.py
=======================
Identifica o idioma de uma página web comparando a frequência de letras
do texto com perfis de referência carregados de 'letter-frequencies.csv'.

Uso:
    python identificador_idioma.py
    (o programa pedirá a URL interativamente)

Ou direto:
    python identificador_idioma.py https://pt.wikipedia.org/wiki/Brasil

Dependências:
    pip install requests
"""

import sys
import re
import csv
import math
import html
import unicodedata
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Erro: instale a biblioteca requests  →  pip install requests")


# ─────────────────────────────────────────────
# 1. Download do texto bruto
# ─────────────────────────────────────────────

def baixar_texto(url: str) -> str:
    """Faz o download de uma URL e retorna o texto bruto da resposta."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resposta = requests.get(url, headers=headers, timeout=15)
        resposta.raise_for_status()
    except requests.exceptions.MissingSchema:
        sys.exit(f"Erro: URL inválida -> '{url}'. Inclua o esquema (https://...)")
    except requests.exceptions.ConnectionError:
        sys.exit(f"Erro: nao foi possivel conectar a '{url}'.")
    except requests.exceptions.Timeout:
        sys.exit("Erro: tempo de conexao esgotado.")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"Erro HTTP: {e}")

    resposta.encoding = resposta.apparent_encoding
    return resposta.text


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

# Fallback: extrai li e section se paragrafos nao forem encontrados
_RE_FALLBACK = re.compile(
    r"<(li|section|div)[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Remove qualquer tag HTML restante
_RE_TAG_GENERICA = re.compile(r"<[^>]+>")

# Remove entidades HTML (&amp; &nbsp; &#123; etc.)
_RE_ENTIDADE = re.compile(r"&[a-zA-Z0-9#]+;")


def _extrair_texto_html(texto_html: str) -> str:
    """
    Extrai o texto visivel de uma pagina HTML:
    1. Remove blocos de ruido (script, style, nav, footer, head) por completo.
    2. Coleta apenas <p>, <h1>-<h6>, <blockquote>, <article>, <main>, <td>, <th>.
       Essas tags sao as mais confiaveis — div e span sao evitadas pois carregam
       muito conteudo de interface (menus, categorias, widgets) em sites como Wikipedia.
    3. Fallback para <li>/<section>/<div> se nenhum paragrafo for encontrado.
    """
    # Passo 1: apaga blocos irrelevantes inteiros
    texto_html = _RE_BLOCOS_RUIDO.sub(" ", texto_html)

    # Passo 2: coleta paragrafos e titulos
    trechos = _RE_PARAGRAFOS.findall(texto_html)

    if not trechos:
        # Fallback: tenta li/section/div se a pagina nao usa <p>
        trechos = _RE_FALLBACK.findall(texto_html)

    if trechos:
        conteudo = " ".join(c for _, c in trechos)
    else:
        # Ultimo recurso: remove todas as tags genericamente
        conteudo = _RE_TAG_GENERICA.sub(" ", texto_html)

    # Remove tags internas residuais e converte entidades HTML para caracteres reais
    conteudo = _RE_TAG_GENERICA.sub(" ", conteudo)
    conteudo = html.unescape(conteudo)
    return conteudo


def limpar_texto(texto: str, remover_acentos: bool = False) -> str:
    """
    Extrai texto relevante do HTML e retorna apenas letras em minusculas.
    Se remover_acentos=True, converte letras acentuadas para base ASCII.
    """
    texto = _extrair_texto_html(texto)

    # Normaliza unicode NFC (forma canonica composta)
    texto = unicodedata.normalize("NFC", texto).lower()

    if remover_acentos:
        # Decomposicao NFD + remocao de marcas diacriticas
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    # Mantem apenas letras (categoria Unicode "L*")
    texto = "".join(c for c in texto if unicodedata.category(c).startswith("L"))

    return texto


# ─────────────────────────────────────────────
# 3. Calculo de frequencia
# ─────────────────────────────────────────────

def calcular_frequencia(texto_limpo: str) -> dict:
    """
    Calcula a frequencia relativa (0-100) de cada letra no texto.
    Retorna um dicionario {letra: percentual}.
    """
    if not texto_limpo:
        sys.exit("Erro: o texto ficou vazio apos a limpeza. Verifique a URL.")

    contagem = {}
    for letra in texto_limpo:
        contagem[letra] = contagem.get(letra, 0) + 1

    total = sum(contagem.values())
    return {letra: (qtd / total) * 100 for letra, qtd in contagem.items()}


# ─────────────────────────────────────────────
# 4. Carregamento dos perfis do CSV
# ─────────────────────────────────────────────

def _parse_pct(valor: str) -> float:
    """Converte '7.636%', '7.636%*' ou '9.600%*' para float. Retorna 0.0 se vazio."""
    valor = valor.strip().replace("%", "").replace("*", "").strip()
    return float(valor) if valor else 0.0


def carregar_perfis(caminho_csv: str = "letter-frequencies.csv") -> dict:
    """
    Le o arquivo CSV e retorna:
        { idioma: { letra: percentual, ... }, ... }
    """
    caminho = Path(caminho_csv)
    if not caminho.exists():
        sys.exit(
            f"Erro: arquivo '{caminho_csv}' nao encontrado.\n"
            "Coloque o arquivo letter-frequencies.csv na mesma pasta do script."
        )

    perfis = {}

    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f, delimiter=",")
        idiomas = [col for col in leitor.fieldnames if col != "Letter"]

        for idioma in idiomas:
            perfis[idioma] = {}

        for linha in leitor:
            letra = linha["Letter"].strip()
            for idioma in idiomas:
                perfis[idioma][letra] = _parse_pct(linha[idioma])

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
    """Similaridade de cosseno entre dois perfis (0 = ortogonal, 1 = identico)."""
    todas_letras = set(freq_a) | set(freq_b)
    dot = sum(freq_a.get(l, 0) * freq_b.get(l, 0) for l in todas_letras)
    norm_a = math.sqrt(sum(v ** 2 for v in freq_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in freq_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _bonus_exclusividade(freq_texto: dict, perfis: dict) -> dict:
    """
    Calcula um bonus por idioma baseado em letras que aparecem no texto
    e que sao exclusivas (ou quase) de certos idiomas.
    Ex: 'a tilde' (a com til) so existe em portugues — se o texto tem essa letra,
    e um forte sinal de que o idioma e portugues.
    """
    bonus = {idioma: 0.0 for idioma in perfis}
    for letra, freq_t in freq_texto.items():
        if freq_t == 0:
            continue
        tem = {i for i in perfis if perfis[i].get(letra, 0) > 0}
        nao_tem = {i for i in perfis if perfis[i].get(letra, 0) == 0}
        if not tem or not nao_tem:
            continue
        # Quanto menos idiomas tiverem a letra, mais exclusiva ela e
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

    melhor = max(scores_final, key=scores_final.get)
    return melhor, scores_final[melhor], scores_final


# ─────────────────────────────────────────────
# 6. Funcao principal
# ─────────────────────────────────────────────

def main():
    # URL: argumento de linha de comando ou input interativo
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Digite a URL da pagina a analisar: ").strip()

    pasta_script = Path(__file__).parent
    caminho_csv = pasta_script / "letter-frequencies.csv"

    print(f"\n[+] Baixando conteudo de: {url}")
    texto_bruto = baixar_texto(url)

    print("[+] Limpando texto (extraindo apenas conteudo textual do HTML)...")
    texto_limpo = limpar_texto(texto_bruto, remover_acentos=True)
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
