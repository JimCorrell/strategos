-- migrations/001_initial_schema.sql

CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    causation_id UUID,
    correlation_id UUID,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_created_at ON events(created_at);

CREATE TABLE checkpoints (
    timestamp DOUBLE PRECISION PRIMARY KEY,
    state_data BYTEA NOT NULL,
    event_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_timestamp ON checkpoints(timestamp DESC);
```