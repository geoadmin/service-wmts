import logging

import psycopg2 as psy

from app import settings

logger = logging.getLogger(__name__)

restrictions = {}


def get_wms_config_by_layer(layer_id):
    try:
        restriction = restrictions[layer_id]
        logger.debug('Restriction for layer %s: %s', layer_id, restriction)
        return restriction
    except KeyError as error:
        logger.error('No wms configuration found for layer %s', layer_id)
        return None


def get_wmsconfig_from_db():
    # Connect to database
    logger.debug(
        'Connecting to %s db on host %s',
        settings.WMS_DB_NAME,
        settings.WMS_DB_HOST
    )
    try:
        connection = psy.connect(
            dbname=settings.WMS_DB_NAME,
            user=settings.WMS_DB_USER,
            password=settings.WMS_DB_PASSWD,
            host=settings.WMS_DB_HOST,
            port=settings.WMS_DB_PORT,
            connect_timeout=5
        )
    except psy.Error as error:
        logger.error("Unable to connect: %s", error)
        if error.pgerror:
            logger.error('pgerror: %s', error.pgerror)
        if error.diag.message_detail:
            logger.error('message detail: %s', error.diag.message_detail)
        raise

    # Open cursor for DB-Operations
    cursor = connection.cursor()

    try:
        # select records from DB
        cursor.execute(
            """
            SELECT
            tileset.fk_dataset_id
            , array_agg(DISTINCT timestamp order by timestamp desc)
            , max(resolution_min::float)
            , min(resolution_max::float)
            , coalesce(min(s3_resolution_max::float)
            , min(resolution_max::float))
            , array_agg(DISTINCT format)
            , coalesce(cache_ttl,1800)
            , max(wms_gutter)
            FROM tileset tileset LEFT JOIN tileset_timestamps time ON
            tileset.fk_dataset_id = time.fk_dataset_id
            group by tileset.fk_dataset_id,
            format, cache_ttl  ORDER BY tileset.fk_dataset_id
            """
        )
    except psy.Error as error:
        logger.exception('Failed to retrieve wms config from DB: %s', error)
        raise

    total_records = cursor.rowcount
    logger.info("Found %s records", total_records)

    # iterate through table
    _restrictions = {}
    for i, record in enumerate(cursor):
        logger.debug('WMS config record %d: %s', i, record)
        _restrictions[record[0]] = {
            'timestamp': record[1],
            'min_resolution': record[2],
            'max_resolution': record[3],
            's3_max_resolution': record[4],
            'format': record[5],
            'cache_ttl': record[6],
            'wms_gutter': record[7]
        }

    logger.info("All restrictions generated")
    return _restrictions


restrictions = get_wmsconfig_from_db()
