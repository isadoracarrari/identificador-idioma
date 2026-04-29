# Identificador de Idioma por Frequência de Letras

Detecta o idioma de uma página web comparando a frequência relativa das letras do texto com perfis de referência extraídos do arquivo `letter-frequencies.csv`.

## Idiomas suportados

English, French, German, Spanish, Portuguese, Esperanto, Italian, Turkish, Swedish, Polish, Dutch, Danish, Icelandic, Finnish, Czech

## Dependências

Apenas a biblioteca `requests` (além da stdlib do Python):

```bash
pip install requests
```

## Como executar

Coloque `identificador_idioma.py` e `letter-frequencies.csv` na **mesma pasta**. Então:

```bash
# Modo interativo (o programa pede a URL)
python identificador_idioma.py

# Passando a URL direto
python identificador_idioma.py https://pt.wikipedia.org/wiki/Brasil
```

## Exemplo de saída

```
[+] Baixando conteudo de: https://pt.wikipedia.org/wiki/Brasil
[+] Limpando texto (extraindo apenas conteudo textual do HTML)...
    54,321 letras analisadas.
[+] Calculando frequencias...
[+] Carregando perfis de referencia...
    15 idiomas carregados: English, French, German, Spanish, Portuguese, ...
[+] Comparando perfis (similaridade de cosseno)...

=======================================================
  Resultado: Portuguese
  Grau de similaridade: 1.0000  (escala 0-1)
=======================================================

  Ranking completo de idiomas:
   1. Portuguese   1.0000 <-- melhor
   2. Spanish      0.8238
   3. Italian      0.6077
   4. French       0.5127
   ...

  Top 5 letras no texto:
    'a'  ->  13.85%
    'e'  ->  12.44%
    'o'  ->  10.21%
    's'  ->   7.13%
    'i'  ->   6.58%
```

## Como funciona

### 1. Download (`baixar_texto`)
Usa `requests.get()` com um header `User-Agent` simulando um navegador Chrome. Isso é necessário porque sites como a Wikipedia bloqueiam requisições sem User-Agent com erro 403.

### 2. Limpeza do HTML (`limpar_texto`)
A extração do texto ocorre em três etapas:

**Etapa 1 — Remove blocos de ruído inteiros:**
Tags `<script>`, `<style>`, `<head>`, `<noscript>`, `<nav>`, `<footer>` e `<header>` são apagadas por completo, incluindo seu conteúdo. Isso evita que código JavaScript, CSS e menus de navegação contaminem a análise.

**Etapa 2 — Extrai apenas tags de conteúdo textual:**
Coleta o interior de `<p>`, `<h1>`–`<h6>`, `<blockquote>`, `<figcaption>`, `<article>`, `<main>`, `<td>` e `<th>`. Tags como `<div>` e `<span>` são **excluídas** propositalmente — em sites como a Wikipedia elas carregam imenso conteúdo de interface (caixas de navegação, categorias, templates) que distorce o perfil de frequência.

**Etapa 3 — Fallback progressivo:**
Se nenhuma tag de parágrafo for encontrada, tenta `<li>`, `<section>` e `<div>`. Se ainda assim não houver resultado, remove todas as tags genericamente.

### 3. Cálculo de frequência (`calcular_frequencia`)
Conta cada letra e calcula seu percentual sobre o total de letras do texto limpo.

### 4. Carregamento dos perfis (`carregar_perfis`)
Lê o `letter-frequencies.csv` com delimitador `,` e detecta os idiomas automaticamente pelas colunas. Converte os valores percentuais (ex: `7.636`, `9.600*`) para float, ignorando o `*` que marca estimativas no CSV.

### 5. Comparação de perfis (`comparar_perfis`)
Usa dois critérios combinados para identificar o idioma:

**Critério A — Similaridade de cosseno (60%):**
Mede o ângulo entre o vetor de frequências do texto e o vetor de cada perfil de referência. Captura bem a distribuição geral das letras.

**Critério B — Bônus por letras exclusivas (40%):**
Letras que aparecem no texto e que pertencem a poucos idiomas recebem peso extra. Por exemplo, `ã` só existe no perfil do português — se o texto contém `ã`, isso é evidência forte de que o idioma é português. Quanto mais exclusiva for a letra (presente em menos idiomas), maior o bônus concedido ao idioma que a possui.

Esse segundo critério foi fundamental para separar idiomas próximos como **português, espanhol e italiano**, cujas frequências de letras base (a–z) são muito similares entre si.

Score final por idioma:
```
score = (cosseno_normalizado × 0.6) + (bonus_normalizado × 0.4)
```

## Formato do CSV de referência

O arquivo `letter-frequencies.csv` usa vírgula (`,`) como delimitador. A primeira coluna deve se chamar `Letter` e cada coluna seguinte representa um idioma:

```
Letter,English,French,German,Spanish,Portuguese,...
a,8.167,7.636,6.516,11.525,14.634,...
b,1.492,0.901,1.886,2.215,1.043,...
```

Para adicionar um novo idioma, basta incluir uma nova coluna com o nome do idioma e as frequências de cada letra — o programa detecta automaticamente.

## Personalização

| O que mudar | Onde | Efeito |
|---|---|---|
| `remover_acentos=True` | chamada de `limpar_texto()` na `main()` | Remove diacríticos antes da análise |
| `metodo="euclidiana"` | chamada de `comparar_perfis()` na `main()` | Usa distância euclidiana em vez de cosseno |
| Adicionar idioma | Nova coluna no `letter-frequencies.csv` | Detectado automaticamente |

## Fonte dos dados

O arquivo `letter-frequencies.csv` foi obtido de:
[Letter Frequencies CSV](https://gist.github.com/CliffordAnderson/b9b204a6d55b06bedd511326afd3e8b9#file-letter-frequencies-csv)
por **Clifford Anderson**, disponível publicamente no GitHub Gist.