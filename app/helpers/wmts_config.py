import logging
import time

import psycopg2 as psy

from app import settings

logger = logging.getLogger(__name__)

RESTRICTIONS = {}


def get_wmts_config_by_layer(layer_id):
    try:
        restriction = RESTRICTIONS[layer_id]
        logger.debug('Restriction for layer %s: %s', layer_id, restriction)
        return restriction
    except KeyError as error:
        logger.error('No wmts configuration found for layer %s', layer_id)
        return None


def connect_to_db():
    retries = settings.BOD_DB_CONNECT_RETRIES
    while True:
        logger.debug(
            'Connecting to %s db on host %s',
            settings.BOD_DB_NAME,
            settings.BOD_DB_HOST
        )
        try:
            connection = psy.connect(
                dbname=settings.BOD_DB_NAME,
                user=settings.BOD_DB_USER,
                password=settings.BOD_DB_PASSWD,
                host=settings.BOD_DB_HOST,
                port=settings.BOD_DB_PORT,
                connect_timeout=settings.BOD_DB_CONNECT_TIMEOUT
            )
            return connection
        except psy.Error as error:
            logger.error(
                "Unable to connect to %s:%d (retries=%d): %s",
                settings.BOD_DB_HOST,
                settings.BOD_DB_PORT,
                retries,
                error
            )
            if error.pgerror:
                logger.error('pgerror: %s', error.pgerror)
            if error.diag.message_detail:
                logger.error('message detail: %s', error.diag.message_detail)
            retries -= 1
            if retries < 0:
                raise


def get_wmts_config_from_db():
    # Connect to database
    connection = connect_to_db()

    # Open cursor for DB-Operations
    cursor = connection.cursor()

    try:
        # select records from DB
        cursor.execute(
            """
            SELECT * FROM "service-wmts".view_tileset_concatenated
            """
        )
    except psy.Error as error:
        logger.exception('Failed to retrieve wms config from DB: %s', error)
        raise

    total_records = cursor.rowcount
    logger.debug(
        "Found %s tileset records for wmts config in DB", total_records
    )

    # iterate through table
    restrictions = {}
    for i, record in enumerate(cursor):
        # logger.debug('WMS config record %d: %s', i, record)
        restrictions[record[0]] = {
            'timestamps': record[1],
            'formats': record[2],
            'resolution_min': record[3],
            'resolution_max': record[4],
            's3_resolution_max': record[5],
            'cache_ttl': record[6],
            'wms_gutter': record[7]
        }

    return restrictions


def init_wmts_config():
    global RESTRICTIONS  # pylint: disable=global-statement
    started = time.time()
    RESTRICTIONS = get_wmts_config_from_db()
    logger.debug('WMTS config initialized in %.3fs', time.time() - started)
