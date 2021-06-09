from sqlalchemy import or_

from flask_sqlalchemy import BaseQuery

from app import db


class TileSetConcatenated(db.Model):
    __tablename__ = 'view_tileset_concatenated'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})

    id = db.Column('fk_dataset_id', db.Unicode, primary_key=True)
    timestamps = db.Column('timestamps', db.ARRAY(db.Unicode))
    formats = db.Column('formats', db.ARRAY(db.Unicode))
    resolution_min = db.Column('resolution_min', db.Float)
    resolution_max = db.Column('resolution_max', db.Float)
    s3_resolution_max = db.Column('s3_resolution_max', db.Float)
    wms_gutter = db.Column('wms_gutter', db.Integer)
    cache_ttl = db.Column('cache_ttl', db.Integer)


class QueryGetCap(BaseQuery):  # pylint: disable=too-many-ancestors

    def filter_by_staging(self, staging):
        return {
            'test': self,
            'integration':
                self.filter(
                    or_(
                        GetCap.staging == 'integration',
                        GetCap.staging == 'prod'
                    )
                ),
            'prod': self.filter(GetCap.staging == staging)
        }[staging]

    def filter_by_topic(self, topic_name):
        if topic_name != 'all':
            clauses = []
            if topic_name == 'api':
                clauses.append(GetCap.topics.like(f'%{topic_name.lower()}%'))
            else:
                # we also want to always include all 'ech' layers
                # (except for api's)
                clauses.append(GetCap.topics.like(f'%{topic_name.lower()}%'))
                # whitelist hack
                clauses.append(GetCap.topics.like(r'%ech%'))
            return self.filter(or_(*clauses))
        return self


class GetCap(object):

    id = db.Column('fk_dataset_id', db.Unicode, primary_key=True)
    id_geocat = db.Column('id_geocat', db.Unicode)
    staging = db.Column('staging', db.Unicode)
    description = db.Column('description', db.Unicode)
    short_description = db.Column('short_description', db.Unicode)
    abstract = db.Column('abstract', db.Unicode)
    formats = db.Column('formats', db.ARRAY(db.Unicode))
    timestamps = db.Column('timestamps', db.ARRAY(db.Unicode))
    resolution_min = db.Column('resolution_min', db.Float)
    resolution_max = db.Column('resolution_max', db.Float)
    s3_resolution_max = db.Column('s3_resolution_max', db.Float)
    cache_ttl = db.Column('cache_ttl', db.Float)
    topics = db.Column('topics', db.ARRAY(db.Unicode))
    has_legend = db.Column('has_legend', db.Boolean)


class GetCapFr(db.Model, GetCap):
    __tablename__ = 'view_wmts_getcapabilities_fr'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})
    query_class = QueryGetCap


class GetCapDe(db.Model, GetCap):
    __tablename__ = 'view_wmts_getcapabilities_de'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})
    query_class = QueryGetCap


class GetCapEn(db.Model, GetCap):
    __tablename__ = 'view_wmts_getcapabilities_en'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})
    query_class = QueryGetCap


class GetCapIt(db.Model, GetCap):
    __tablename__ = 'view_wmts_getcapabilities_it'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})
    query_class = QueryGetCap


class GetCapRm(db.Model, GetCap):
    __tablename__ = 'view_wmts_getcapabilities_rm'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})
    query_class = QueryGetCap


class GetCapThemes(object):
    id = db.Column('inspire_id', db.Unicode, primary_key=True)
    inspire_name = db.Column('inspire_name', db.Unicode)
    inspire_abstract = db.Column('inspire_abstract', db.Unicode)
    inspire_upper_theme_name = db.Column('inspire_upper_theme_name', db.Unicode)
    inspire_upper_theme_id = db.Column('inspire_upper_theme_id', db.Unicode)
    inspire_upper_theme_abstract = db.Column(
        'inspire_upper_theme_abstract', db.Unicode
    )
    fk_dataset_ids = db.Column('fk_dataset_ids', db.ARRAY(db.Unicode))


class GetCapThemesFr(db.Model, GetCapThemes):
    __tablename__ = 'view_wmts_getcapabilities_themes_fr'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class GetCapThemesDe(db.Model, GetCapThemes):
    __tablename__ = 'view_wmts_getcapabilities_themes_de'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class GetCapThemesIt(db.Model, GetCapThemes):
    __tablename__ = 'view_wmts_getcapabilities_themes_it'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class GetCapThemesRm(db.Model, GetCapThemes):
    __tablename__ = 'view_wmts_getcapabilities_themes_rm'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class GetCapThemesEn(db.Model, GetCapThemes):
    __tablename__ = 'view_wmts_getcapabilities_themes_en'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class ServiceMetadata(object):
    id = db.Column('wms_id', db.Unicode, primary_key=True)
    pk_map_name = db.Column('pk_map_name', db.Unicode)
    title = db.Column('title', db.Unicode)
    abstract = db.Column('abstract', db.Unicode)
    keywords = db.Column('keywords', db.Unicode)
    fee = db.Column('fee', db.Unicode)
    access_constraint = db.Column('access_constraint', db.Unicode)
    fk_contact_id = db.Column('fk_contact_id', db.Integer)
    address_type = db.Column('address_type', db.Unicode)
    address = db.Column('address', db.Unicode)
    postcode = db.Column('postcode', db.Integer)
    city = db.Column('city', db.Unicode)
    country = db.Column('country', db.Unicode)
    contact_email_address = db.Column('contact_email_address', db.Unicode)
    contact_person = db.Column('contact_person', db.Unicode)
    contact_phone = db.Column('contact_phone', db.Unicode)
    state_or_province = db.Column('state_or_province', db.Unicode)
    fk_contact_organisation_id = db.Column(
        'fk_contact_organisation_id', db.Integer
    )
    abbreviation = db.Column('abbreviation', db.Unicode)
    name = db.Column('name', db.Unicode)


class ServiceMetadataDe(db.Model, ServiceMetadata):
    __tablename__ = 'view_wmts_service_metadata_de'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class ServiceMetadataFr(db.Model, ServiceMetadata):
    __tablename__ = 'view_wmts_service_metadata_fr'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class ServiceMetadataIt(db.Model, ServiceMetadata):
    __tablename__ = 'view_wmts_service_metadata_it'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class ServiceMetadataRm(db.Model, ServiceMetadata):
    __tablename__ = 'view_wmts_service_metadata_rm'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


class ServiceMetadataEn(db.Model, ServiceMetadata):
    __tablename__ = 'view_wmts_service_metadata_en'
    __table_args__ = ({'schema': 'service-wmts', 'autoload': False})


localized_models = {
    'de': {
        'GetCap': GetCapDe,
        'GetCapThemes': GetCapThemesDe,
        'ServiceMetadata': ServiceMetadataDe
    },
    'fr': {
        'GetCap': GetCapFr,
        'GetCapThemes': GetCapThemesFr,
        'ServiceMetadata': ServiceMetadataFr
    },
    'it': {
        'GetCap': GetCapIt,
        'GetCapThemes': GetCapThemesIt,
        'ServiceMetadata': ServiceMetadataIt
    },
    'rm': {
        'GetCap': GetCapRm,
        'GetCapThemes': GetCapThemesRm,
        'ServiceMetadata': ServiceMetadataRm
    },
    'en': {
        'GetCap': GetCapEn,
        'GetCapThemes': GetCapThemesEn,
        'ServiceMetadata': ServiceMetadataEn
    },
}
