-- extensie pentru UUID Keycloak
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- utilizatori
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    role VARCHAR(50) DEFAULT 'PATIENT' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Specializari
CREATE TABLE IF NOT EXISTS specializations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cabinete
CREATE TABLE IF NOT EXISTS cabinets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    floor INTEGER,
    location VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Doctori
CREATE TABLE IF NOT EXISTS doctors (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
    specialization_id INTEGER NOT NULL REFERENCES specializations(id),
    cabinet_id INTEGER REFERENCES cabinets(id),
    bio TEXT,
    years_experience INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- program doctori
CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL CHECK (weekday >= 0 AND weekday <= 6),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_duration_minutes INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- programari
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES users(id),
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    cabinet_id INTEGER REFERENCES cabinets(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- evenimente programari
CREATE TABLE IF NOT EXISTS appointment_events (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB,
    is_processed BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- notificari
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    appointment_id INTEGER REFERENCES appointments(id),
    type VARCHAR(50) DEFAULT 'EMAIL' NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- indecsi pt a gasi mai repede informatia cu datele pe care le folosesc cel mai des
CREATE INDEX IF NOT EXISTS idx_users_external_id ON users(external_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_appointments_start_time ON appointments(start_time);
CREATE INDEX IF NOT EXISTS idx_appointment_events_is_processed ON appointment_events(is_processed);

-- date initiale cu care populez bd la specializarile doctorilor
INSERT INTO specializations (name, description) VALUES
('Cardiologie', 'Specialitatea care se ocupă cu diagnosticul și tratamentul bolilor cardiovasculare'),
('Dermatologie', 'Specialitatea care trateaza afectiunile pielii'),
('Pediatrie', 'Specialitatea care se ocupa cu sanatatea copiilor'),
('Neurologie', 'Specialitatea care trateaza afectiunile sistemului nervos'),
('Ortopedie', 'Specialitatea care trateaza afectiunile sistemului locomotor')
ON CONFLICT DO NOTHING;

-- date initiale pt cabinete
INSERT INTO cabinets (name, floor, location) VALUES
('Cabinet 101', 1, 'Etaj 1, Aripa Stânga'),
('Cabinet 102', 1, 'Etaj 1, Aripa Stânga'),
('Cabinet 201', 2, 'Etaj 2, Aripa Dreapta'),
('Cabinet 202', 2, 'Etaj 2, Aripa Dreapta'),
('Cabinet 301', 3, 'Etaj 3, Central')
ON CONFLICT DO NOTHING;