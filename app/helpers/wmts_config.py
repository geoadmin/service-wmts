import logging
import time
import psycopg2 as psy

from sqlalchemy import create_engine

from app import settings

from app.models import TileSetConcatenated as TileSetConcat

logger = logging.getLogger(__name__)

wmts_config = {}


def get_wmts_config_by_layer(layer_id):
    start = time.time()
    config = TileSetConcat.query.filter(TileSetConcat.id == layer_id).first()
    logger.debug(
        'Get wmts config for layer %s in %.3fs', layer_id, time.time() - start
    )
    return config


def get_wmts_config_from_db():
    start = time.time()
    tilesets = TileSetConcat.query.all()
    print('Get all wmts sqlalchemy query %.3fs' % (time.time() - start))
    return {tileset.id: tileset for tileset in tilesets}


def get_wmts_config_from_db_3(engine):
    with engine.connect() as connection:
        # cursor = connection.execute(TileSetConcat.__table__.select())
        cursor = connection.execute(
            'SELECT * FROM "service-wmts".view_tileset_concatenated'
        )
        config = {
            record[0]: {
                'timestamps': record[1],
                'formats': record[2],
                'min_resolution': record[3],
                'max_resolution': record[4],
                's3_max_resolution': record[5],
                'wms_gutter': record[6],
                'cache_ttl': record[7],
            } for record in cursor
        }
    # print(config)
    return config


def get_wmts_config_from_db_2():
    # Connect to database
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
            , coalesce(min(s3_resolution_max::float), min(resolution_max::float))
            , array_agg(DISTINCT format)
            , coalesce(cache_ttl,1800)
            , max(wms_gutter)
            FROM tileset tileset LEFT JOIN tileset_timestamps time ON
                tileset.fk_dataset_id = time.fk_dataset_id
            GROUP BY tileset.fk_dataset_id, format, cache_ttl
            ORDER BY tileset.fk_dataset_id
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


start = time.time()
wmts_config = get_wmts_config_from_db()
print('Get all wmts config in %.3fs' % (time.time() - start))

start = time.time()
wmts_config = get_wmts_config_from_db_2()
print('Get all wmts config in %.3fs (Using psycog)' % (time.time() - start))

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
start = time.time()
wmts_config = get_wmts_config_from_db_3(engine)
print(
    'Get all wmts config in %.3fs (Using CORE SQLAlchemy)' %
    (time.time() - start)
)
