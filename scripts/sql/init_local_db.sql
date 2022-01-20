-- create read-only user local-db-user
CREATE ROLE "local-db-user" WITH NOSUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'local-db-user';

-- create the schema

CREATE SCHEMA "service-wmts";

GRANT ALL ON SCHEMA "service-wmts" TO "local-db-user";

-- create tables
CREATE TABLE public.tileset
(
    fk_dataset_id character varying COLLATE pg_catalog."default" NOT NULL,
    format character varying COLLATE pg_catalog."default",
    bgdi_id SERIAL NOT NULL,
    wms_gutter integer NOT NULL DEFAULT 0,
    cache_ttl integer DEFAULT 31556952,
    resolution_min numeric DEFAULT 4000.0,
    resolution_max numeric DEFAULT 1,
    published boolean DEFAULT true,
    s3_resolution_max numeric,
    CONSTRAINT tileset_pkey PRIMARY KEY (bgdi_id),
    CONSTRAINT tileset_unique_constraint UNIQUE (fk_dataset_id, format, resolution_min, resolution_max, s3_resolution_max, cache_ttl, wms_gutter, published),
    CONSTRAINT no_newlines_fk_dataset_id CHECK (strpos(fk_dataset_id::text, '
'::text) = 0),
    CONSTRAINT tileset_check CHECK (s3_resolution_max > resolution_max AND s3_resolution_max <= resolution_min)
)
TABLESPACE pg_default;

CREATE TABLE public.tileset_timestamps
(
    fk_dataset_id character varying COLLATE pg_catalog."default" NOT NULL,
    "timestamp" character varying COLLATE pg_catalog."default" NOT NULL,
    bgdi_id SERIAL NOT NULL,
    CONSTRAINT tileset_timestamps_pkey PRIMARY KEY (fk_dataset_id, "timestamp")
)
TABLESPACE pg_default;

-- create view

CREATE VIEW "service-wmts".view_tileset_concatenated
 AS
  SELECT tileset.fk_dataset_id,
    array_agg(DISTINCT timestamp ORDER BY timestamp DESC) AS timestamps,
    array_agg(DISTINCT format) AS formats,
    max(resolution_min::double precision) AS resolution_min,
    min(resolution_max::double precision) AS resolution_max,
    COALESCE(min(s3_resolution_max::float), min(resolution_max::float)) AS s3_resolution_max,
    cache_ttl,
	  max(wms_gutter) AS wms_gutter
  FROM tileset tileset
    LEFT JOIN tileset_timestamps time ON tileset.fk_dataset_id::text = time.fk_dataset_id::text
  GROUP BY tileset.fk_dataset_id, tileset.cache_ttl
  ORDER BY tileset.fk_dataset_id;

GRANT SELECT ON TABLE "service-wmts".view_tileset_concatenated TO "local-db-user";

-- populate tables with dummy data layer from simple.map
    -- valid format: png
    -- valid wms_gutter: 30
    -- valid timestamps: current

INSERT INTO public.tileset(fk_dataset_id, format, wms_gutter)
    VALUES (
            'inline_points'
            , 'png', 30
            );


INSERT INTO public.tileset_timestamps(
    fk_dataset_id, "timestamp")
    VALUES (
            'inline_points'
            , 'current'
            );

GRANT SELECT ON TABLE public.tileset TO "local-db-user";
GRANT SELECT ON TABLE public.tileset_timestamps TO "local-db-user";