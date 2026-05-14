-- Migration 003: thumbnail_features table for rich visual feature extraction
-- Run once against internal PostgreSQL DB

CREATE TABLE IF NOT EXISTS thumbnail_features (
    id                    SERIAL PRIMARY KEY,

    -- Source tracking
    source                VARCHAR(16)  NOT NULL,         -- 'market' | 'user'
    listing_id            VARCHAR(64),
    image_url             TEXT,
    product_type          VARCHAR(64),
    badge                 VARCHAR(64),                   -- 'Popular now' | 'Bestseller' | NULL
    extracted_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Subject
    subject               VARCHAR(256),
    subject_colors        JSONB,                         -- list of hex codes
    subject_color_names   JSONB,                         -- list of color names

    -- Background
    background_color      VARCHAR(16),                   -- hex
    background_color_name VARCHAR(64),
    background_type       VARCHAR(64),                   -- white_studio | lifestyle | gradient | texture | outdoor | flat_lay | other
    background_description TEXT,

    -- Theme & Style
    theme                 VARCHAR(128),
    fabric_material       VARCHAR(128),

    -- Decoration
    decoration_object     VARCHAR(256),
    decoration_technique  VARCHAR(64),                   -- embroidery | print | heat_transfer | applique | none
    decoration_colors     JSONB,                         -- list of hex codes

    -- Seasonal & Context
    seasonal_type         VARCHAR(64),                   -- christmas | halloween | easter | valentines | non_seasonal
    lifestyle_props       JSONB,                         -- list of strings

    -- Composition & Mood
    text_overlay          BOOLEAN DEFAULT FALSE,
    text_overlay_content  TEXT,
    composition           VARCHAR(64),                   -- centered | flat_lay | close_up | editorial | angled | hanging
    overall_mood          VARCHAR(128)
);

CREATE INDEX IF NOT EXISTS idx_thumbnail_features_product_type ON thumbnail_features(product_type);
CREATE INDEX IF NOT EXISTS idx_thumbnail_features_source ON thumbnail_features(source);
CREATE INDEX IF NOT EXISTS idx_thumbnail_features_badge ON thumbnail_features(badge);
CREATE INDEX IF NOT EXISTS idx_thumbnail_features_seasonal_type ON thumbnail_features(seasonal_type);
