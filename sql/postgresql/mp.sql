-- ============================
-- mp_account
-- ============================

CREATE SEQUENCE IF NOT EXISTS mp_account_seq
    INCREMENT 1 MINVALUE 1 START 1 CACHE 1;

DROP TABLE IF EXISTS mp_account;
CREATE TABLE mp_account (
    id            BIGINT PRIMARY KEY DEFAULT nextval('mp_account_seq'),
    name          VARCHAR(255) NOT NULL,
    account       VARCHAR(128) NOT NULL,
    app_id        VARCHAR(128) NOT NULL,
    app_secret    VARCHAR(256) NOT NULL,
    token         VARCHAR(128),
    aes_key       VARCHAR(128),
    qr_code_url   VARCHAR(1024),
    remark        VARCHAR(500),

    -- TenantBaseDO
    tenant_id     BIGINT NOT NULL DEFAULT 0,

    -- BaseDO common fields
    creator       VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updater       VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mp_account_app_id   ON mp_account(app_id);
CREATE INDEX IF NOT EXISTS idx_mp_account_tenant_id ON mp_account(tenant_id);


-- ============================
-- mp_material
-- ============================

CREATE SEQUENCE IF NOT EXISTS mp_material_seq
    INCREMENT 1 MINVALUE 1 START 1 CACHE 1;

DROP TABLE IF EXISTS mp_material;
CREATE TABLE mp_material (
    id            BIGINT PRIMARY KEY DEFAULT nextval('mp_material_seq'),
    account_id    BIGINT NOT NULL,
    app_id        VARCHAR(128) NOT NULL,

    media_id      VARCHAR(255) NOT NULL,
    type          VARCHAR(32)  NOT NULL,
    permanent     BOOLEAN      NOT NULL DEFAULT FALSE,
    url           VARCHAR(1024) NOT NULL,

    name          VARCHAR(255),
    mp_url        VARCHAR(1024),
    title         VARCHAR(255),
    introduction  VARCHAR(512),

    creator       VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updater       VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mp_material_account_id ON mp_material(account_id);
CREATE INDEX IF NOT EXISTS idx_mp_material_app_id     ON mp_material(app_id);
CREATE INDEX IF NOT EXISTS idx_mp_material_media_id   ON mp_material(media_id);


-- ============================
-- mp_menu
-- ============================

CREATE SEQUENCE IF NOT EXISTS mp_menu_seq
    INCREMENT 1 MINVALUE 1 START 1 CACHE 1;

DROP TABLE IF EXISTS mp_menu;
CREATE TABLE mp_menu (
    id                    BIGINT PRIMARY KEY DEFAULT nextval('mp_menu_seq'),
    account_id            BIGINT NOT NULL,
    app_id                VARCHAR(128) NOT NULL,

    name                  VARCHAR(255) NOT NULL,
    menu_key              VARCHAR(255),
    parent_id             BIGINT NOT NULL DEFAULT 0,

    -- button action
    type                  VARCHAR(32),
    url                   VARCHAR(1024),
    mini_program_app_id   VARCHAR(128),
    mini_program_page_path VARCHAR(255),
    article_id            VARCHAR(255),

    -- reply content
    reply_message_type    VARCHAR(32),
    reply_content         VARCHAR(2048),
    reply_media_id        VARCHAR(255),
    reply_media_url       VARCHAR(1024),
    reply_title           VARCHAR(255),
    reply_description     VARCHAR(512),
    reply_thumb_media_id  VARCHAR(255),
    reply_thumb_media_url VARCHAR(1024),

    -- JacksonTypeHandler List<Article>
    reply_articles        JSONB,

    reply_music_url       VARCHAR(1024),
    reply_hq_music_url    VARCHAR(1024),

    creator       VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updater       VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mp_menu_account_id ON mp_menu(account_id);
CREATE INDEX IF NOT EXISTS idx_mp_menu_app_id     ON mp_menu(app_id);
CREATE INDEX IF NOT EXISTS idx_mp_menu_parent_id  ON mp_menu(parent_id);


-- ============================
-- mp_auto_reply
-- ============================

CREATE SEQUENCE IF NOT EXISTS mp_auto_reply_seq
    INCREMENT 1 MINVALUE 1 START 1 CACHE 1;

DROP TABLE IF EXISTS mp_auto_reply;
CREATE TABLE mp_auto_reply (
    id                    BIGINT PRIMARY KEY DEFAULT nextval('mp_auto_reply_seq'),
    account_id            BIGINT NOT NULL,
    app_id                VARCHAR(128) NOT NULL,

    type                  INT NOT NULL,

    request_keyword       VARCHAR(255),
    request_match         INT,
    request_message_type  VARCHAR(32),

    response_message_type VARCHAR(32) NOT NULL,
    response_content      VARCHAR(2048),
    response_media_id     VARCHAR(255),
    response_media_url    VARCHAR(1024),
    response_title        VARCHAR(255),
    response_description  VARCHAR(512),
    response_thumb_media_id  VARCHAR(255),
    response_thumb_media_url VARCHAR(1024),

    response_articles     JSONB,

    response_music_url    VARCHAR(1024),
    response_hq_music_url VARCHAR(1024),

    creator       VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updater       VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mp_auto_reply_account_id ON mp_auto_reply(account_id);
CREATE INDEX IF NOT EXISTS idx_mp_auto_reply_app_id     ON mp_auto_reply(app_id);
CREATE INDEX IF NOT EXISTS idx_mp_auto_reply_type       ON mp_auto_reply(type);


-- ============================
-- mp_message_template
-- ============================

CREATE SEQUENCE IF NOT EXISTS mp_message_template_seq
    INCREMENT 1 MINVALUE 1 START 1 CACHE 1;

DROP TABLE IF EXISTS mp_message_template;
CREATE TABLE mp_message_template (
    id                BIGINT PRIMARY KEY DEFAULT nextval('mp_message_template_seq'),
    account_id        BIGINT NOT NULL,
    app_id            VARCHAR(128) NOT NULL,

    template_id       VARCHAR(255) NOT NULL,
    title             VARCHAR(255),
    content           VARCHAR(4000),
    example           VARCHAR(2000),
    primary_industry  VARCHAR(255),
    deputy_industry   VARCHAR(255),

    creator       VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updater       VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mp_msg_tpl_account_id ON mp_message_template(account_id);
CREATE INDEX IF NOT EXISTS idx_mp_msg_tpl_app_id     ON mp_message_template(app_id);
CREATE INDEX IF NOT EXISTS idx_mp_msg_tpl_template_id ON mp_message_template(template_id);


-- ============================
-- mp_tag
-- ============================

CREATE SEQUENCE IF NOT EXISTS mp_tag_seq
    INCREMENT 1 MINVALUE 1 START 1 CACHE 1;

DROP TABLE IF EXISTS mp_tag;
CREATE TABLE mp_tag (
    -- 你代码里是 IdType.INPUT：如果你希望由程序传入 id，就去掉 DEFAULT nextval(...)
    id          BIGINT PRIMARY KEY DEFAULT nextval('mp_tag_seq'),

    tag_id      BIGINT NOT NULL,
    name        VARCHAR(255) NOT NULL,
    count       INT NOT NULL DEFAULT 0,

    account_id  BIGINT NOT NULL,
    app_id      VARCHAR(128) NOT NULL,

    creator       VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updater       VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mp_tag_account_id ON mp_tag(account_id);
CREATE INDEX IF NOT EXISTS idx_mp_tag_app_id     ON mp_tag(app_id);
CREATE INDEX IF NOT EXISTS idx_mp_tag_tag_id     ON mp_tag(tag_id);
