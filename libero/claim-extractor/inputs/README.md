# Transcrições de entrada

Armazene aqui arquivos TXT e SRT. Para grandes coleções, organize por conjunto
ou identificador de vídeo, por exemplo `inputs/dataset/video-id/transcript.en.txt`
e `inputs/dataset/video-id/transcript.pt.srt`.

Os arquivos `automatic.en.txt` e `automatic.srt` são as entradas padrão atuais.
`automatic.en.aps-input.jsonl` é a entrada APS opcional, usada somente com
`--aps-input`. Os três arquivos representam o mesmo transcript.

Exemplo a partir de `claim-extractor/`:

```bash
bash run-cuba.sh run --models all \
  --input-en inputs/dataset/video-id/transcript.en.txt \
  --input-pt inputs/dataset/video-id/transcript.pt.srt
```

Cada comando processa uma transcrição (ou o par EN/PT correspondente).
Não há processamento automático de todas as subpastas.
