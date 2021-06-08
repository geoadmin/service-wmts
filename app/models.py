from sqlalchemy import or_

from flask_sqlalchemy import BaseQuery

from app import db


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

    def filter_by_map(self, map_name):
        if map_name != 'all':
            clauses = []
            if map_name == 'api':
                clauses.append(GetCap.maps.like(f'%{map_name.lower()}%'))
            else:
                # we also want to always include all 'ech' layers
                # (except for api's)
                clauses.append(GetCap.maps.like(f'%{map_name.lower()}%'))
                # whitelist hack
                clauses.append(GetCap.maps.like(r'%ech%'))
            return self.filter(or_(*clauses))
        return self


class GetCap(object):

    id = db.Column('fk_dataset_id', db.Unicode, primary_key=True)
    formats = db.Column('format', db.Unicode)
    timestamps = db.Column('timestamp', db.Unicode)
    bod_layer_id = db.Column('bod_layer_id', db.Unicode)
    staging = db.Column('staging', db.Unicode)
    description = db.Column('bezeichnung', db.Unicode)
    short_description = db.Column('kurzbezeichnung', db.Unicode)
    abstract = db.Column('abstract', db.Unicode)
    inspire_name = db.Column('inspire_name', db.Unicode)
    inspire_abstract = db.Column('inspire_abstract', db.Unicode)
    inspire_upper_theme_name = db.Column('inspire_oberthema_name', db.Unicode)
    inspire_upper_theme_abstract = db.Column(
        'inspire_oberthema_abstract', db.Unicode
    )
    geo_base_data_set_name = db.Column('geobasisdatensatz_name', db.Unicode)
    data_owner = db.Column('datenherr', db.Unicode)
    wms_contact_abbreviation = db.Column('wms_kontakt_abkuerzung', db.Unicode)
    wms_contact_name = db.Column('wms_kontakt_name', db.Unicode)
    resolution_min = db.Column('resolution_min', db.Integer)
    resolution_max = db.Column('resolution_max', db.Integer)
    maps = db.Column('topics', db.Unicode)  # the topics
    chargeable = db.Column('chargeable', db.Boolean)
    id_geocat = db.Column('idgeocat', db.Unicode)
    has_legend = False  # TODO uses the hasLegend once it has been added


class GetCapFr(db.Model, GetCap):
    __tablename__ = 'view_bod_wmts_getcapabilities_fr'
    __table_args__ = ({'schema': 're3', 'autoload': False})
    query_class = QueryGetCap


class GetCapDe(db.Model, GetCap):
    __tablename__ = 'view_bod_wmts_getcapabilities_de'
    __table_args__ = ({'schema': 're3', 'autoload': False})
    query_class = QueryGetCap


class GetCapEn(db.Model, GetCap):
    __tablename__ = 'view_bod_wmts_getcapabilities_en'
    __table_args__ = ({'schema': 're3', 'autoload': False})
    query_class = QueryGetCap


class GetCapIt(db.Model, GetCap):
    __tablename__ = 'view_bod_wmts_getcapabilities_it'
    __table_args__ = ({'schema': 're3', 'autoload': False})
    query_class = QueryGetCap


class GetCapRm(db.Model, GetCap):
    __tablename__ = 'view_bod_wmts_getcapabilities_rm'
    __table_args__ = ({'schema': 're3', 'autoload': False})
    query_class = QueryGetCap


class GetCapThemes(object):
    id = db.Column('inspire_id', db.Unicode, primary_key=True)
    inspire_name = db.Column('inspire_name', db.Unicode)
    inspire_abstract = db.Column('inspire_abstract', db.Unicode)
    inspire_upper_theme_name = db.Column('inspire_oberthema_name', db.Unicode)
    upper_theme_id = db.Column('oberthema_id', db.Unicode)
    inspire_upper_theme_abstract = db.Column(
        'inspire_oberthema_abstract', db.Unicode
    )
    fk_dataset_id = db.Column('fk_dataset_id', db.Unicode)


class GetCapThemesFr(db.Model, GetCapThemes):
    __tablename__ = 'view_bod_wmts_getcapabilities_themes_fr'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class GetCapThemesDe(db.Model, GetCapThemes):
    __tablename__ = 'view_bod_wmts_getcapabilities_themes_de'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class GetCapThemesIt(db.Model, GetCapThemes):
    __tablename__ = 'view_bod_wmts_getcapabilities_themes_it'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class GetCapThemesRm(db.Model, GetCapThemes):
    __tablename__ = 'view_bod_wmts_getcapabilities_themes_rm'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class GetCapThemesEn(db.Model, GetCapThemes):
    __tablename__ = 'view_bod_wmts_getcapabilities_themes_en'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class ServiceMetadata(object):
    id = db.Column('wms_id', db.Unicode, primary_key=True)  # pylint: disable=invalid-name
    pk_map_name = db.Column('pk_map_name', db.Unicode)
    title = db.Column('title', db.Unicode)
    onlineresource = db.Column('onlineresource', db.Unicode)
    abstract = db.Column('abstract', db.Unicode)
    keywords = db.Column('keywords', db.Unicode)
    fee = db.Column('fee', db.Unicode)
    access_constraint = db.Column('accessconstraint', db.Unicode)
    encoding = db.Column('encoding', db.Unicode)
    fk_contact_id = db.Column('fk_contact_id', db.Integer)
    address_type = db.Column('addresstype', db.Unicode)
    address = db.Column('address', db.Unicode)
    postcode = db.Column('postcode', db.Integer)
    city = db.Column('city', db.Unicode)
    country = db.Column('country', db.Unicode)
    contact_email_address = db.Column(
        'contactelectronicmailaddress', db.Unicode
    )
    contact_person = db.Column('contactperson', db.Unicode)
    contact_phone = db.Column('contactvoicetelephon', db.Unicode)
    state_or_province = db.Column('stateorprovince', db.Unicode)
    fk_contact_organisation_id = db.Column(
        'fk_contactorganisation_id', db.Integer
    )
    abbreviation = db.Column('abkuerzung', db.Unicode)
    name = db.Column('name', db.Unicode)


class ServiceMetadataDe(db.Model, ServiceMetadata):
    __tablename__ = 'view_wms_service_metadata_de'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class ServiceMetadataFr(db.Model, ServiceMetadata):
    __tablename__ = 'view_wms_service_metadata_fr'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class ServiceMetadataIt(db.Model, ServiceMetadata):
    __tablename__ = 'view_wms_service_metadata_it'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class ServiceMetadataRm(db.Model, ServiceMetadata):
    __tablename__ = 'view_wms_service_metadata_rm'
    __table_args__ = ({'schema': 're3', 'autoload': False})


class ServiceMetadataEn(db.Model, ServiceMetadata):
    __tablename__ = 'view_wms_service_metadata_en'
    __table_args__ = ({'schema': 're3', 'autoload': False})


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
