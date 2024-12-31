CREATE TABLE interactions (
  id SERIAL PRIMARY KEY,
  redis_key VARCHAR(255) UNIQUE, 
  redis_timestamp VARCHAR(100) NOT NULL,
  query TEXT NOT NULL,
  reply TEXT NOT NULL,
  feedback VARCHAR(50) NOT NULL,
  feedback_comment TEXT,
  request_duration_in_seconds DOUBLE PRECISION NOT NULL,
  chat_completions_req_duration_in_seconds DOUBLE PRECISION NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE stats_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
