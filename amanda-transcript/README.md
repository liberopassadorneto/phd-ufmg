# Transcrições Whisper

Esse codigo pode ser separado em 5 partes:

Transcrição: a partir de um audio retorna a transcrição. Os audios inicialemnte precisam estar em uma pasta "audios" (alterar depois de implementar o banco). 

Legendas: faz a limpeza e carregamento de legendas .srt e comparação com o Whisper.

Métricas: levanta métricas de comparação entre textos: WER, CER e similaridade semântica (usado para comparar modelos e legendas).

Idioma: detecta o idioma de um áudio usando só os primeiros 30s de cada áudio.

Análise: faz testes e gera gráficos para comparação.


## Como funciona

1. **Transcrição** (`transcricao.py`): transcreve cada `.mp3` com `large-v1` e `medium`. Cada resultado é gravado na hora em um `.jsonl`; se a execução for interrompida, ao rodar de novo ela retoma de onde parou.
2. **Métricas** (`metricas.py`): compara dois textos por WER, CER e similaridade semântica (cosseno entre embeddings, com textos longos divididos em chunks de 80 palavras).
3. **Legendas** (`legendas.py`): converte os `.srt` em texto corrido (guardando backup do original) e compara cada legenda com as duas transcrições.
4. **Idioma** (`idioma.py`): detecta o idioma pelos primeiros 30 s de cada áudio com o modelo `tiny` e lista os casos suspeitos (não-pt ou confiança < 0,95).
5. **Análise** (`analise.py`): resumos estatísticos, piores casos, tempos de processamento, gráficos e teste de Wilcoxon (WER large × medium).
6. **Orquestração** (`main.py`): executa tudo em sequência. Caminhos e parâmetros ficam em `config.py`.


## Requisitos

- Python 3.10+
- `ffmpeg` instalado no sistema 
- GPU com CUDA

```bash
pip install -r requirements.txt
```

## Como executar

```bash
python main.py
```


## Observações

- Para refazer uma transcrição, apague o `.jsonl` correspondente (ou a linha do áudio).
- WER/CER muito altos (ex.: 35) costumam vir de áudios com música/sem fala, em que um modelo gera quase nada e o outro alucina texto. Veja `piores_casos` e a detecção de idioma antes de interpretar as médias; a mediana é mais robusta que a média.