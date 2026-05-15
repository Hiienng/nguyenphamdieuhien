-- Migration 005: Expand thumbnail_features with richer visual + signal features
-- These columns feed the LightGBM thumbnail scorer model

ALTER TABLE thumbnail_features
  -- Visual quality
  ADD COLUMN IF NOT EXISTS image_brightness      VARCHAR(16),   -- dark|medium|bright
  ADD COLUMN IF NOT EXISTS image_contrast        VARCHAR(16),   -- low|medium|high
  ADD COLUMN IF NOT EXISTS color_harmony         VARCHAR(32),   -- monochromatic|analogous|complementary|triadic|neutral
  ADD COLUMN IF NOT EXISTS color_count           SMALLINT,      -- number of dominant colors (1-5+)
  ADD COLUMN IF NOT EXISTS background_clutter    VARCHAR(16),   -- clean|minimal|moderate|busy

  -- Product presentation
  ADD COLUMN IF NOT EXISTS product_visibility    VARCHAR(32),   -- full|partial|close_up|multiple_angles
  ADD COLUMN IF NOT EXISTS product_size_in_frame VARCHAR(16),   -- small|medium|large|fills_frame
  ADD COLUMN IF NOT EXISTS personalization_visible BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS gift_cue_visible      BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS size_reference        BOOLEAN DEFAULT FALSE,  -- hand/ruler/coin for scale

  -- Audience & occasion signals
  ADD COLUMN IF NOT EXISTS gender_signal         VARCHAR(16),   -- neutral|feminine|masculine
  ADD COLUMN IF NOT EXISTS age_target            VARCHAR(16),   -- newborn|infant|toddler|adult|unknown
  ADD COLUMN IF NOT EXISTS occasion_signal       VARCHAR(32),   -- everyday|gift|seasonal|hospital|announcement
  ADD COLUMN IF NOT EXISTS style_aesthetic       VARCHAR(32),   -- modern|rustic|boho|classic|whimsical|minimal

  -- Label for ML training
  ADD COLUMN IF NOT EXISTS ml_label              SMALLINT;      -- 1=Bestseller/Popular now, 0=other, NULL=user upload

-- Index for training queries
CREATE INDEX IF NOT EXISTS idx_tf_ml_label ON thumbnail_features(ml_label);
CREATE INDEX IF NOT EXISTS idx_tf_product_type ON thumbnail_features(product_type);
