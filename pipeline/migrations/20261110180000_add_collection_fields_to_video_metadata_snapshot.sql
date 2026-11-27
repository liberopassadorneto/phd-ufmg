-- Campos da coleta do ytcollector que o schema original não guardava.
--
-- Esta migration é escrita para o Dbmate do repositório do pipeline: copie o
-- arquivo para pipeline/migrations/ e aplique lá. O scripts/export_to_db.py
-- deste repositório confere se as colunas existem e para, sem gravar nada,
-- se ela não tiver sido aplicada.
--
-- Os nomes levam o schema phd_pipeline explícito para não depender do
-- search_path da conexão. Sem o prefixo, com search_path "public, phd_pipeline",
-- os tipos seriam criados em public e as colunas em phd_pipeline.

-- migrate:up
CREATE TYPE phd_pipeline.language_prefilter_decision_enum AS ENUM (
    'KEEP',
    'DISCARD'
);

CREATE TYPE phd_pipeline.video_format_enum AS ENUM (
    'SHORT',
    'RV',
    'UNKNOWN'
);

ALTER TABLE phd_pipeline.video_metadata_snapshot
    -- Short ou vídeo regular (RV), pela classificação do coletor.
    ADD COLUMN video_format phd_pipeline.video_format_enum,
    -- contentDetails.caption da API: o canal enviou legenda. Não inclui a
    -- legenda automática do YouTube.
    ADD COLUMN has_caption BOOLEAN,
    -- Pré-filtro de idioma calculado sobre o título, a descrição e os campos de
    -- idioma deste snapshot. NULL = snapshot não avaliado.
    ADD COLUMN language_prefilter_decision phd_pipeline.language_prefilter_decision_enum,
    -- P(pt) do fastText no pré-filtro. NULL quando o texto limpo ficou vazio ou
    -- o snapshot não foi avaliado.
    ADD COLUMN language_prefilter_p_pt NUMERIC(8,6)
        CHECK (
            language_prefilter_p_pt IS NULL
            OR (language_prefilter_p_pt >= 0 AND language_prefilter_p_pt <= 1)
        );

-- migrate:down
ALTER TABLE phd_pipeline.video_metadata_snapshot
    DROP COLUMN language_prefilter_p_pt,
    DROP COLUMN language_prefilter_decision,
    DROP COLUMN has_caption,
    DROP COLUMN video_format;

DROP TYPE phd_pipeline.video_format_enum;
DROP TYPE phd_pipeline.language_prefilter_decision_enum;
