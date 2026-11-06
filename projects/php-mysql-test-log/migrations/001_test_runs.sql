CREATE TABLE IF NOT EXISTS test_runs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sample VARCHAR(120) NOT NULL,
    notes VARCHAR(2000) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX recent_runs (created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS measurements (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    run_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(80) COLLATE utf8mb4_0900_bin NOT NULL,
    unit VARCHAR(24) NOT NULL,
    value DECIMAL(18,6) NOT NULL,
    lower_limit DECIMAL(18,6) NOT NULL,
    upper_limit DECIMAL(18,6) NOT NULL,
    CONSTRAINT measurement_run FOREIGN KEY (run_id) REFERENCES test_runs(id),
    CONSTRAINT ordered_limits CHECK (lower_limit <= upper_limit),
    UNIQUE KEY unique_reading (run_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
