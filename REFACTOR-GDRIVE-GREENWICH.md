# Conclusão do refactor do Google Drive em Greenwich

Este documento orienta a continuação do trabalho em Greenwich. A branch
`amanda/whisper-s3` contém o fluxo implementado em Cuba até o commit `48e0dc0`.
Confira a branch e os commits disponíveis antes de aplicar alterações em outro checkout.

## Estado atual

- Greenwich hospeda o PostgreSQL e o S3 compatível, acessados localmente nas portas
  `15432` e `19000`. Cuba acessa esses serviços por túnel SSH.
- O Whisper em `amanda/whisper-transcript/src/main_s3.py` busca áudios no Drive,
  grava transcrições no Drive, grava no S3 uma referência JSON e registra no
  PostgreSQL o bucket e a chave dessa referência.
- `armazenamento.ler_transcricao` resolve essas referências e também lê textos
  antigos diretamente no S3. As referências novas registram caminho rclone,
  tamanho e SHA-256 do texto.
- O claim-extractor envia resultados ao Drive ao finalizar cada modelo. O
  script `backup-outputs.sh` copia resultados existentes sob demanda.
- O fluxo completo com áudio real, S3 e PostgreSQL ainda precisa ser validado.
  Não foi confirmada a quantidade de transcrições antigas no S3.
- O yt-scraper e os demais projetos ainda precisam de integração própria se suas
  saídas também forem destinadas ao Drive.

## Configurar o acesso em Greenwich

1. Atualize o checkout com a branch que contém o commit acima, preservando
   alterações locais existentes. Instale o rclone para o usuário que executará
   os processos e crie um remote chamado `phd-drive` para a mesma conta e os
   mesmos arquivos do Drive usados em Cuba. Autorize a conta Google pelo
   navegador conforme as instruções de configuração remota do rclone.
2. Use preferencialmente um cliente OAuth próprio. O cliente compartilhado do
   rclone exibe aviso de descontinuação. Verifique se o escopo concedido permite
   acessar os áudios e as transcrições existentes. A permissão `drive.file`
   pode limitar a visibilidade aos arquivos autorizados para o aplicativo.
3. Confira o acesso com `rclone lsd phd-drive:phd-ufmg` e liste os áudios em
   `phd-drive:phd-ufmg/amanda/whisper-transcript/audios`. O código aceita
   `<youtube_id>.mp3` ou um `.mp3` dentro de uma pasta `<youtube_id>`.
4. Garanta que os serviços compartilhados e as credenciais de Greenwich estejam
   configurados conforme o README do repositório. Os processos executados em
   Greenwich acessam os serviços localmente. O túnel é necessário para Cuba.

Os caminhos padrão espelham o repositório dentro de `phd-drive:phd-ufmg`:

```text
amanda/whisper-transcript/audios/
amanda/whisper-transcript/transcricoes/
libero/claim-extractor/results/
libero/claim-extractor/cuba-results/
libero/claim-extractor/runs/
```

`DRIVE_OUTPUT_DESTINATION` altera a raiz usada pelos uploads. `WHISPER_AUDIO_DRIVE`
altera a pasta de entrada do Whisper. As referências S3 existentes contêm o nome
do remote e o caminho completos. Para lê-las em Greenwich, configure o mesmo
nome de remote e acesso aos mesmos arquivos.

## Validação de ponta a ponta

1. Selecione um vídeo pendente no PostgreSQL e disponibilize seu áudio na pasta
   do Drive. Confirme que o rclone em Greenwich consegue listar e baixar o arquivo.
2. Execute o fluxo Whisper em ambiente configurado para os serviços locais e
   confirme que o texto foi criado em `amanda/whisper-transcript/transcricoes/`.
3. Confira a linha de `phd_pipeline.whisper_transcript`, incluindo `video_id`,
   `s3_bucket`, `bucket_key` e `size_bytes`. Leia o objeto JSON apontado pela
   linha no bucket `youtube-transcripts` e confirme o caminho do Drive.
4. Use `armazenamento.ler_transcricao(s3, bucket, chave)` para recuperar o texto
   pela referência e validar tamanho e SHA-256. Confira também uma transcrição
   antiga em S3, caso exista.
5. Simule uma falha de upload ou registro e confirme que a transcrição local
   permanece em `amanda/whisper-transcript/src/transcricoes_pendentes/` para
   recuperação. Avalie a limpeza de referências ou arquivos órfãos antes de
   configurar retentativas automatizadas.

## Trabalho restante

- Inventariar as transcrições e outros resultados existentes no S3, bem como
  os consumidores que ainda esperam receber o texto diretamente de uma chave S3.
  Atualizar esses consumidores para resolver as referências antes de migrar dados.
- Planejar e testar uma migração recuperável dos arquivos antigos, preservando
  os registros existentes até confirmar a leitura e integridade no Drive.
- Definir e implementar o envio das saídas de yt-scraper e de outros projetos
  executados em Greenwich, respeitando os caminhos do repositório e os fluxos
  que removem arquivos locais após upload.
- Atualizar a documentação geral de arquitetura depois da validação e da decisão
  sobre a migração. O README principal ainda descreve S3 como armazenamento dos
  conteúdos, o que não reflete as novas transcrições do Whisper.

Documentação de referência: [Google Drive no rclone](https://rclone.org/drive/) e
[configuração remota](https://rclone.org/remote_setup/).
