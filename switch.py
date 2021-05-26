import logging
from typing import Optional
import requests

from homeassistant.helpers import config_validation as cv, entity_platform

from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Table, create_engine
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
# DOMAIN = 'pihole_group_mgmt'


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Pi-hole binary sensor."""
    # name = entry.data[CONF_NAME]
    _LOGGER.info(entry.as_dict())
    # _data = hass.data[DOMAIN][entry.entry_id]
    Pihole.URL = entry.data['filename']
    Pihole.PORTAINER_URL = entry.data['portainer_url']
    Pihole.PORTAINER_AUTH = entry.data['portainer_auth']
    # Pihole.URL = entry['data']['filename']

    for domain in Pihole.list_domains():
        async_add_entities([PiholeDomainSwitch(domain)], True)
    # switch = [
    #     PiholeDomainSwitch(
    #         hole_data[DATA_KEY_API],
    #         hole_data[DATA_KEY_COORDINATOR],
    #         name,
    #         entry.entry_id,
    #     )
    # ]
    # async_add_entities(switch, True)

    # register service
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        'restart_dns',
        {
            vol.Required('restart_url'): cv.string,
            vol.Optional('restart_auth'): cv.string_with_no_html,
        },
        "async_restart",
    )


Base = declarative_base()
association_table = Table('domainlist_by_group', Base.metadata,
    Column('domainlist_id', Integer, ForeignKey('domainlist.id')),
    Column('group_id', Integer, ForeignKey('group.id'))
)

class DomainList(Base):
    __tablename__ = 'domainlist'
    id = Column(Integer, primary_key=True)
    type = Column(Integer)
    domain = Column(String)
    enabled = Column(Boolean)
    date_added = Column(Integer)
    date_modified = Column(Integer)
    comment = Column(String)
    groups = relationship("Group",
                    secondary=association_table,
                    backref="domainlists")
    

class Group(Base):
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    enabled = Column(Boolean)
    description = Column(String)
    
    
class Pihole:

    # def __init__(self, db_filename):
    #     self.db_filename = db_filename

    CONN_ARGS = {'check_same_thread': False}
    URL = ''
    PORTAINER_URL = None
    PORTAINER_AUTH = None
    # URL = 'sqlite:////Users/ckirby/git/pihole-group-mgmt/pihole/gravity.db'

    @staticmethod
    def list_domains():
        engine = create_engine(Pihole.URL, connect_args=Pihole.CONN_ARGS)
        Session = sessionmaker(bind=engine)
        session = Session()
        domains = session.query(DomainList).all()

        return [domain.domain for domain in domains]

    @staticmethod
    async def disable_domain(url):
        engine = create_engine(Pihole.URL, connect_args=Pihole.CONN_ARGS)
        Session = sessionmaker(bind=engine)
        session = Session()
        domain = session.query(DomainList).filter(DomainList.domain == url).one()
        domain.enabled = False
        return session.commit()

    @staticmethod
    async def enable_domain(url):
        engine = create_engine(Pihole.URL, connect_args=Pihole.CONN_ARGS)
        Session = sessionmaker(bind=engine)
        session = Session()
        domain = session.query(DomainList).filter(DomainList.domain == url).one()
        domain.enabled = True
        return session.commit()

    @staticmethod
    def domain_status(url):
        engine = create_engine(Pihole.URL, connect_args=Pihole.CONN_ARGS)
        Session = sessionmaker(bind=engine)
        session = Session()
        domain = session.query(DomainList).filter(DomainList.domain == url).first()
        return domain.enabled

    @staticmethod
    async def restart_container(url, auth):
        headers = {'Authorization': f'Bearer {auth}'}
        requests.post(url, headers=headers)

    @staticmethod
    # async def restart_dns(**kwargs):
    #     _LOGGER.debug(kwargs)
    def restart_dns():
        # _LOGGER.info(data)
        # url = data.data.get('portainer_url')
        # auth = data.data.get('portainer_auth')
        headers = {'Authorization': f'Bearer {Pihole.PORTAINER_AUTH}'}
        body = {'Cmd': ['sudo', 'pihole', 'restartdns']}
        res = requests.post(Pihole.PORTAINER_URL, headers=headers, json=body)
        # _LOGGER.info(f'auth: {Pihole.PORTAINER_AUTH}')
        # _LOGGER.info(f"Headers: {headers}")
        # _LOGGER.info(f'URL: {Pihole.PORTAINER_URL}')
        # _LOGGER.info(f"portainer response: {res.text}")
        exec_id = res.json()['Id']
        _url = f'http://brains.lan:9000/api/endpoints/1/docker/exec/{exec_id}/start'
        body = {'Detach': True}
        requests.post(_url, headers=headers, json=body)


# Import the device class from the component that you want to support
from homeassistant.components.switch import SwitchEntity, PLATFORM_SCHEMA
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_FILE_PATH


# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FILE_PATH): cv.string
})
class PiholeDomainSwitch(SwitchEntity):

    def __init__(self, domain):
        self.pihole_domain = domain
        self._name = domain


    @property
    def device_info(self):
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self.pihole_domain)},
            "name": self.pihole_domain,
            "manufacturer": "Pi-hole",
        }

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the switch."""
        return f"{self.pihole_domain}/Switch"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:pi-hole"

    @property
    def is_on(self):
        """Return if the service is on."""
        return Pihole.domain_status(self.pihole_domain) #self.api.data.get("status") == "enabled"

    async def async_turn_on(self, **kwargs):
        """Turn on the service."""
        _LOGGER.info('Turning domain on.')
        # _LOGGER.info(self)
        # _LOGGER.info(str(kwargs))
        try:
            await Pihole.enable_domain(self.pihole_domain) 
            await self.hass.async_add_executor_job(Pihole.restart_dns)
            # await self.async_update()
        except Exception as err:
            _LOGGER.error("Unable to enable Pi-hole: %s", err)

    async def async_turn_off(self, **kwargs):
        """Turn off the service."""
        await self.async_disable()

    async def async_restart(self, **kwargs):
        await Pihole.restart_dns(Pihole.PORTAINER_URL, Pihole.PORTAINER_AUTH)

    async def async_disable(self, duration=None, **kwargs):
        """Disable the service for a given duration."""
        # duration_seconds = True  # Disable infinitely by default
        # if duration is not None:
        #     duration_seconds = duration.total_seconds()
        _LOGGER.info( "Disabling Pi-hole '%s'", self.name)
        _LOGGER.info(str(kwargs))
        try:
            await Pihole.disable_domain(self.pihole_domain) #self.api.disable(duration_seconds)
            await self.hass.async_add_executor_job(Pihole.restart_dns)
            # await self.async_update()
        except Exception as err:
            _LOGGER.error("Unable to disable Pi-hole: %s", err)

# from homeassistant.helpers.entity import Entity


# def setup_platform(hass, config, add_entities, discovery_info=None):
#     """Set up the sensor platform."""
#     for domain in Pihole.list_domains():
#         add_entities([PiholeDomainSwitch(domain)])


# def setup(hass, config):
# # async def async_setup(hass, config):
#     setup_platform(hass, config)

#     return True

# from sqlalchemy import create_engine
# engine = create_engine('sqlite:///pihole/gravity.db')

# from sqlalchemy.orm import sessionmaker
# Session = sessionmaker(bind=engine)
# session = Session()

# domains = session.query(DomainList).all()

# for domain in domains:
#     # domain.enabled = False
#     print(domain.domain)

# session.commit()

# print(Pihole.domain_status('google.com'))