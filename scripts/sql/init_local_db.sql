-- create read-only user www-data
CREATE ROLE "www-data" WITH NOSUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'www-data';

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

GRANT SELECT ON TABLE public.tileset TO "www-data";
GRANT SELECT ON TABLE public.tileset_timestamps TO "www-data";