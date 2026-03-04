-- Migration script: Original Marzban DB -> Fork DB
-- Run with: sqlite3 db.sqlite3 < migrate_to_fork.sql

-- Add missing columns to users
ALTER TABLE users ADD COLUMN device_limit INTEGER;
ALTER TABLE users ADD COLUMN smart_host_address VARCHAR(256);

-- Add missing columns to admins
ALTER TABLE admins ADD COLUMN user_limit INTEGER;
ALTER TABLE admins ADD COLUMN traffic_limit BIGINT;

-- Create user_devices table
CREATE TABLE user_devices (
    id INTEGER NOT NULL PRIMARY KEY,
    hwid VARCHAR(256) NOT NULL,
    user_id INTEGER NOT NULL,
    platform VARCHAR(64),
    os_version VARCHAR(64),
    device_model VARCHAR(128),
    user_agent VARCHAR(512),
    created_at DATETIME,
    updated_at DATETIME,
    disabled BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id),
    UNIQUE(hwid, user_id)
);
CREATE INDEX ix_user_devices_hwid ON user_devices(hwid);

-- Update alembic version to match the fork
UPDATE alembic_version SET version_num = 'c4d5e6f7a8b9';
