-- Extensions (optional)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Feature presets
CREATE TABLE IF NOT EXISTS feature_preset (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key              text NOT NULL UNIQUE,
  name             text NOT NULL,
  system_prompt    text,
  default_params   jsonb NOT NULL DEFAULT '{}'::jsonb,
  params_schema    jsonb,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- Conversations
CREATE TABLE IF NOT EXISTS conversation (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_preset_id  uuid NOT NULL REFERENCES feature_preset(id) ON DELETE RESTRICT,
  title              text,
  feature_params     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversation_updated_at ON conversation (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_preset ON conversation (feature_preset_id);

-- Messages
CREATE TABLE IF NOT EXISTS message (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id  uuid NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
  role             text NOT NULL CHECK (role IN ('user','assistant','system')),
  content          text NOT NULL,
  metadata         jsonb,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_message_conversation_time ON message (conversation_id, created_at);

-- Sources
CREATE TABLE IF NOT EXISTS article_source (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  domain        text NOT NULL UNIQUE,
  name          text NOT NULL,
  homepage_url  text,
  rss_url       text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Articles
CREATE TABLE IF NOT EXISTS article (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id     uuid REFERENCES article_source(id) ON DELETE RESTRICT,
  url           text NOT NULL UNIQUE,
  title         text NOT NULL,
  author        text,
  content_text  text NOT NULL,
  content_html  text,
  lang          text NOT NULL DEFAULT 'vi',
  category      text,
  tags          text[],
  image_url     text,
  published_at  timestamptz,
  fetched_at    timestamptz NOT NULL DEFAULT now(),
  metadata      jsonb
);
CREATE INDEX IF NOT EXISTS idx_article_title_trgm ON article USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_article_url_trgm   ON article USING gin (url gin_trgm_ops);

ALTER TABLE article
  ADD COLUMN IF NOT EXISTS tsv tsvector GENERATED ALWAYS AS (
    to_tsvector('simple', unaccent(coalesce(title,'') || ' ' || coalesce(content_text,'')))
  ) STORED;
CREATE INDEX IF NOT EXISTS idx_article_tsv ON article USING gin (tsv);

-- Daily suggestions
CREATE TABLE IF NOT EXISTS daily_suggestion (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id       uuid NOT NULL REFERENCES article(id) ON DELETE CASCADE,
  suggestion_date  date NOT NULL,
  rank             int  NOT NULL CHECK (rank >= 1),
  reason           text
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_suggestion ON daily_suggestion (suggestion_date, article_id);
CREATE INDEX IF NOT EXISTS idx_daily_suggestion_rank ON daily_suggestion (suggestion_date, rank);

-- Citations
CREATE TABLE IF NOT EXISTS message_citation (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id   uuid NOT NULL REFERENCES message(id) ON DELETE CASCADE,
  article_id   uuid NOT NULL REFERENCES article(id) ON DELETE CASCADE,
  rank         int,
  offset_start int,
  offset_end   int,
  snippet      text
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_message_citation ON message_citation (message_id, article_id);
CREATE INDEX IF NOT EXISTS idx_citation_article ON message_citation (article_id);

-- Trigger to touch conversation.updated_at
CREATE OR REPLACE FUNCTION touch_conversation_updated_at() RETURNS trigger AS $$
BEGIN
  UPDATE conversation SET updated_at = now() WHERE id = NEW.conversation_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_message_touch_conversation ON message;
CREATE TRIGGER trg_message_touch_conversation
AFTER INSERT ON message
FOR EACH ROW EXECUTE FUNCTION touch_conversation_updated_at();


