CREATE TABLE IF NOT EXISTS codeids (
    id SERIAL PRIMARY KEY,
    codeid TEXT UNIQUE NOT NULL
);


CREATE TABLE IF NOT EXISTS effective_movement (
    id SERIAL PRIMARY KEY,
    codeid_id INT REFERENCES codeids(id),  -- Relación con codeids
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration NUMERIC NOT NULL,
    leg TEXT NOT NULL -- "Left" o "Right"
);

-- Índices para optimizar búsquedas
CREATE INDEX IF NOT EXISTS idx_effective_movement_codeid_id ON effective_movement(codeid_id);
CREATE INDEX IF NOT EXISTS idx_effective_movement_leg ON effective_movement(leg);

CREATE TABLE IF NOT EXISTS activity_leg (
    id SERIAL PRIMARY KEY,
    codeid_id INT REFERENCES codeids(id),  -- Relación con codeids
    foot TEXT NOT NULL,  -- "Left" o "Right"
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration NUMERIC NOT NULL,  -- Duración de la ventana en segundos
    mac TEXT,  -- Dirección MAC del dispositivo
    device_name TEXT,  -- Nombre del dispositivo
    total_value NUMERIC
);

CREATE TABLE IF NOT EXISTS activity_all (
    id SERIAL PRIMARY KEY,
    codeid_ids INTEGER[] NOT NULL,  -- Relación con la tabla codeids (Left y Right)
    codeleg_ids INTEGER[] NOT NULL, -- Punteros a activity_leg.id (uno por pierna)
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration NUMERIC NOT NULL,
    macs TEXT[],                    -- MACs de los sensores (Left y Right)
    device_names TEXT[],           -- Nombres de dispositivos (Left y Right)
    active_legs TEXT[],            -- ["Left", "Right"]
    is_effective BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS fullref_sensor_codeid (
    id SERIAL PRIMARY KEY,
    codeid_id INT REFERENCES codeids(id),
    foot TEXT NOT NULL,  -- "Left" o "Right"
    device_name TEXT,
    mac TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Índices para optimizar búsquedas
CREATE INDEX IF NOT EXISTS idx_fullref_codeid ON fullref_sensor_codeid(codeid_id);
CREATE INDEX IF NOT EXISTS idx_fullref_foot ON fullref_sensor_codeid(foot);
CREATE INDEX IF NOT EXISTS idx_fullref_time ON fullref_sensor_codeid(start_time, end_time);
