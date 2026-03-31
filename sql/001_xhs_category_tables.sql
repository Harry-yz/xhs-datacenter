CREATE TABLE IF NOT EXISTS xhs_category_dim (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL DEFAULT 'xhs',
    category_id BIGINT NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    parent_category_id BIGINT,
    parent_category_name VARCHAR(100),
    level INT NOT NULL,
    sort_no INT,
    raw_payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(platform, category_id)
);

CREATE INDEX IF NOT EXISTS idx_xhs_category_dim_parent
ON xhs_category_dim(parent_category_id);

CREATE INDEX IF NOT EXISTS idx_xhs_category_dim_level
ON xhs_category_dim(level);

CREATE TABLE IF NOT EXISTS xhs_category_watchlist (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL DEFAULT 'xhs',
    industry_name VARCHAR(100) NOT NULL,
    category_id BIGINT NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    parent_category_id BIGINT,
    parent_category_name VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'enabled',
    priority INT NOT NULL DEFAULT 100,
    remark VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(platform, category_id)
);

CREATE INDEX IF NOT EXISTS idx_xhs_category_watchlist_status
ON xhs_category_watchlist(status, priority);