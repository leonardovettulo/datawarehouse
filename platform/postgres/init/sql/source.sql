-- Local stand-in for the SQL Server replica.
-- Pilot circuit: compra → entrega de Farmacia → HC → facturación.
-- HC and facturación are intentionally partial so marts can show gaps.

CREATE TABLE insumos (
    codigo          TEXT PRIMARY KEY,
    nombre          TEXT NOT NULL,
    unidad          TEXT NOT NULL,
    familia         TEXT NOT NULL
);

INSERT INTO insumos (codigo, nombre, unidad, familia) VALUES
    ('JER-21G',    'Jeringa 21G',                 'unidad', 'descartables'),
    ('SUE-1000',   'Suero fisiológico 1000 ml',   'frasco', 'soluciones'),
    ('ATB-AMX',    'Amoxicilina 500 mg',          'comp',   'antibioticos'),
    ('GAS-10',     'Gasa estéril 10x10',          'paquete','curaciones'),
    ('DIP-500',    'Dipirona 500 mg',             'ampolla','analgesicos');

CREATE TABLE compras (
    id              INTEGER PRIMARY KEY,
    insumo_codigo   TEXT NOT NULL REFERENCES insumos (codigo),
    insumo_nombre   TEXT NOT NULL,
    fecha           DATE NOT NULL,
    cantidad        NUMERIC(12, 2) NOT NULL,
    unidad          TEXT NOT NULL,
    proveedor       TEXT NOT NULL,
    nro_comprobante TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE entregas_farmacia (
    id              INTEGER PRIMARY KEY,
    insumo_codigo   TEXT NOT NULL REFERENCES insumos (codigo),
    insumo_nombre   TEXT NOT NULL,
    fecha           DATE NOT NULL,
    cantidad        NUMERIC(12, 2) NOT NULL,
    unidad          TEXT NOT NULL,
    sector_destino  TEXT NOT NULL,
    nro_remito      TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE hc_registros (
    id              INTEGER PRIMARY KEY,
    insumo_codigo   TEXT NOT NULL REFERENCES insumos (codigo),
    insumo_nombre   TEXT NOT NULL,
    fecha           DATE NOT NULL,
    cantidad        NUMERIC(12, 2) NOT NULL,
    unidad          TEXT NOT NULL,
    nro_historia    TEXT NOT NULL,
    profesional     TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE facturacion (
    id              INTEGER PRIMARY KEY,
    insumo_codigo   TEXT NOT NULL REFERENCES insumos (codigo),
    insumo_nombre   TEXT NOT NULL,
    fecha           DATE NOT NULL,
    cantidad        NUMERIC(12, 2) NOT NULL,
    unidad          TEXT NOT NULL,
    nro_factura     TEXT NOT NULL,
    obra_social     TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

-- Weekly purchases for 6 weeks starting 2026-07-06 (30 rows).
INSERT INTO compras (
    id, insumo_codigo, insumo_nombre, fecha, cantidad, unidad,
    proveedor, nro_comprobante, updated_at
)
SELECT
    row_number() OVER () AS id,
    i.codigo,
    i.nombre,
    DATE '2026-07-06' + (w.n * 7),
    i.qty,
    i.unidad,
    i.proveedor,
    format('FC-%s-%s', i.codigo, to_char(DATE '2026-07-06' + (w.n * 7), 'YYYYMMDD')),
    ((DATE '2026-07-06' + (w.n * 7)) + TIME '18:00') AT TIME ZONE 'UTC'
FROM (
    VALUES
        ('JER-21G',  'Jeringa 21G',               'unidad', 200, 'Descartables SA'),
        ('SUE-1000', 'Suero fisiológico 1000 ml', 'frasco',  80, 'Soluciones del Sur'),
        ('ATB-AMX',  'Amoxicilina 500 mg',        'comp',   500, 'Laboratorio Andino'),
        ('GAS-10',   'Gasa estéril 10x10',        'paquete', 60, 'Descartables SA'),
        ('DIP-500',  'Dipirona 500 mg',           'ampolla',150, 'Laboratorio Andino')
) AS i(codigo, nombre, unidad, qty, proveedor)
CROSS JOIN generate_series(0, 5) AS w(n);

-- Weekday deliveries in the first two weeks of August 2026 (5 insumos × 10 weekdays = 50).
INSERT INTO entregas_farmacia (
    id, insumo_codigo, insumo_nombre, fecha, cantidad, unidad,
    sector_destino, nro_remito, updated_at
)
SELECT
    row_number() OVER () AS id,
    i.codigo,
    i.nombre,
    d.dia,
    CASE i.codigo
        WHEN 'JER-21G'  THEN 12
        WHEN 'SUE-1000' THEN 6
        WHEN 'ATB-AMX'  THEN 20
        WHEN 'GAS-10'   THEN 4
        WHEN 'DIP-500'  THEN 8
    END,
    i.unidad,
    CASE (row_number() OVER ()) % 3
        WHEN 0 THEN 'Internación'
        WHEN 1 THEN 'Guardia'
        ELSE 'Quirofano'
    END,
    format('RM-%s-%s', i.codigo, to_char(d.dia, 'YYYYMMDD')),
    (d.dia + TIME '14:00') AT TIME ZONE 'UTC'
FROM insumos i
CROSS JOIN generate_series(DATE '2026-08-03', DATE '2026-08-14', INTERVAL '1 day') AS d(dia)
WHERE extract(ISODOW FROM d.dia) < 6;

-- HC is partial: only Internación + Guardia, and only 3 of 5 insumos (~24 rows).
INSERT INTO hc_registros (
    id, insumo_codigo, insumo_nombre, fecha, cantidad, unidad,
    nro_historia, profesional, updated_at
)
SELECT
    row_number() OVER () AS id,
    e.insumo_codigo,
    e.insumo_nombre,
    e.fecha,
    e.cantidad,
    e.unidad,
    format('HIST-%s', 1000 + (row_number() OVER ())),
    CASE (row_number() OVER ()) % 2 WHEN 0 THEN 'Dra. Gómez' ELSE 'Dr. Pérez' END,
    e.updated_at + INTERVAL '2 hours'
FROM entregas_farmacia e
WHERE e.sector_destino IN ('Internación', 'Guardia')
  AND e.insumo_codigo IN ('JER-21G', 'SUE-1000', 'DIP-500');

-- Facturación is partial: weekdays in the first week of August only (~25 rows).
INSERT INTO facturacion (
    id, insumo_codigo, insumo_nombre, fecha, cantidad, unidad,
    nro_factura, obra_social, updated_at
)
SELECT
    row_number() OVER () AS id,
    e.insumo_codigo,
    e.insumo_nombre,
    e.fecha,
    e.cantidad,
    e.unidad,
    format('FA-%s', 8000 + (row_number() OVER ())),
    CASE (row_number() OVER ()) % 3
        WHEN 0 THEN 'PAMI'
        WHEN 1 THEN 'OSDE'
        ELSE 'APROSS'
    END,
    e.updated_at + INTERVAL '1 day'
FROM entregas_farmacia e
WHERE e.fecha BETWEEN DATE '2026-08-03' AND DATE '2026-08-07';
