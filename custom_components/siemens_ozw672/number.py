"""SelectEntity platform for Siemens OZW672."""
from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import ICON
from .const import ICON_THERMOMETER
from .const import ICON_PERCENT
from .const import ICON_NUMERIC
from .const import SENSOR
from .const import CONF_MENUITEMS
from .const import CONF_DATAPOINTS
from .const import NUMBER
from .const import CONF_PREFIX_FUNCTION
from .const import CONF_PREFIX_OPLINE
from .const import CONF_USE_DEVICE_LONGNAME
from .const import CONF_DEVICE
from .const import CONF_DEVICE_LONGNAME

from .entity import SiemensOzw672Entity
from homeassistant.helpers.entity import Entity
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.components.number import NumberEntity, NumberMode, NumberDeviceClass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature
)
from homeassistant.util import slugify

import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Setup number platform."""
    _LOGGER.debug(f"NUMBER - Setup_Entry.  DATA: {hass.data[DOMAIN]}")  
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug(f"NUMBER ***** Data: {coordinator.data}")
    _LOGGER.debug(f"NUMBER ***** Config: {entry.as_dict()}")

    datapoints = coordinator.data
    # Add sensors
    entities=[]
    entityconfig=""
    for item in datapoints:
        _LOGGER.debug(f"NUMBER Data Point Item: {datapoints[item]}")
        for dp_data in entry.data["datapoints"]:
            if dp_data["Id"] == item :
                dp_config=dp_data
                if int(dp_data["OpLine"]) > 1:
                    identifier = dp_data["OpLine"] 
                else:
                    identifier="00"+item
                ### Will use the OpLine as the identifier if it exists. If not - we will use the API ID.  
                #   Note: the API datapoint ID can change if the tree is re-created.  
                #   I am hoping that by using the OpLine as the identifier - we will avoid duplicate sensors
                dp_config.update({'entry_id': entry.entry_id + "_OZW_" + identifier})  
                dp_config.update({'device_id': entry.entry_id})
                use_device_name = (entry.data.get(CONF_DEVICE_LONGNAME) or entry.data.get(CONF_DEVICE)) if entry.options.get(CONF_USE_DEVICE_LONGNAME) else entry.data.get(CONF_DEVICE)
                dp_config.update({'device_name': use_device_name or entry.data.get("devicename", "")})
                short_name = entry.data.get(CONF_DEVICE) or entry.data.get("devicename", "")
                prefix_display = ""
                if entry.data.get(CONF_PREFIX_FUNCTION) == True: prefix_display = prefix_display + f'{dp_data["MenuItem"]} - '
                if entry.data.get(CONF_PREFIX_OPLINE) == True: prefix_display = prefix_display + f'{dp_data["OpLine"]} '
                dp_config.update({'entity_prefix_display': prefix_display})
                object_id = f"ozw_{slugify(prefix_display + dp_data['Name'])}"
                suggested = f"{NUMBER}.{object_id}"
                dp_config.update({'suggested_entity_id': suggested})
                dp_config.update({'entity_prefix': prefix_display})
                break
        # At this point - the config for the datapoint is in dp_config
        #               - the data is in dp_data
        if not dp_config == "":
            if dp_config["DPDescr"]["HAType"] == "number":
                _LOGGER.debug(f"NUMBER Adding Entity with config: {dp_config} and data: {dp_data}")          
                if datapoints[item]["Data"]["Unit"] in ['°C', '°F', 'K']:
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672TempControl(coordinator,dp_config)])
                elif datapoints[item]["Data"]["Unit"] in ['%']:
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672PercentControl(coordinator,dp_config)])
                elif datapoints[item]["Data"]["Unit"] in ['kWh', 'Wh', 'kW', 'W']:
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672EnergyControl(coordinator,dp_config)])
                elif datapoints[item]["Data"]["Type"] == "Numeric":
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672NumberControl(coordinator,dp_config)])
                else:
                    continue
            

class SiemensOzw672TempControl(SiemensOzw672Entity,NumberEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672TempControl: Config: {self.config_entry}")
        return self._display_name()

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672TempControl: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    async def async_set_native_value(self, value: float) -> None:
        """Update Temp ."""
        _LOGGER.debug(f'SiemensOzw672TempControl: Set_native_Value: {value}')
        item=self.config_entry["Id"]
        opline=self.config_entry["OpLine"]
        name=self.config_entry["Name"]
        existing_value=self.coordinator.data[item]["Data"]["Value"].strip()
        decimals=self.config_entry["DPDescr"]["DecimalDigits"]
        if decimals == '0':
            new_value=round(float(value))
        else:
            new_value=round(float(value), int(decimals))
        _LOGGER.info(f'SiemensOzw672TempControl - Will update ID/Opline/Name: {item}/{opline}/{name} to Value: {str(new_value)} from Value: {str(existing_value)}')
        output = await self.coordinator.api.async_write_data(self.config_entry,str(new_value))
        await self.coordinator._async_update_data_forid(item)
        await self.coordinator.async_request_refresh()
        return 

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672TempControl: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_THERMOMETER

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return NumberDeviceClass.TEMPERATURE
    
    @property
    def native_min_value(self) -> float:
        """Return min Temp."""
        val = float(self.config_entry["DPDescr"]["Min"])
        return val

    @property
    def native_max_value(self) -> float:
        """Return max Temp."""
        val = float(self.config_entry["DPDescr"]["Max"])
        return val

    @property
    def native_step(self) -> float:
        """Return step/resolution."""
        val = float(self.config_entry["DPDescr"]["Resolution"])
        return val

    @property
    def native_unit_of_measurement(self):
        """Return the native_unit_of_measurement of the sensor."""
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Unit"].strip()
        if data == "°C":
            return UnitOfTemperature.CELSIUS
        elif data == "°F":
            return UnitOfTemperature.FAHRENHEIT
        elif data == "K":
            return UnitOfTemperature.KELVIN
        else:
            return UnitOfTemperature.CELSIUS


class SiemensOzw672PercentControl(SiemensOzw672Entity, NumberEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672PercentControl: Config: {self.config_entry}")
        return self._display_name()

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672PercentControl: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    async def async_set_native_value(self, value: float) -> None:
        """Update The Percentage ."""
        _LOGGER.debug(f'SiemensOzw672PercentControl: Set_native_Value: {value}')
        item=self.config_entry["Id"]
        opline=self.config_entry["OpLine"]
        name=self.config_entry["Name"]
        existing_value=self.coordinator.data[item]["Data"]["Value"].strip()
        decimals=self.config_entry["DPDescr"]["DecimalDigits"]
        if decimals == '0':
            new_value=round(float(value))
        else:
            new_value=round(float(value, int(decimals)))
        _LOGGER.info(f'SiemensOzw672PercentControl - Will update ID/Opline/Name: {item}/{opline}/{name} to Value: {str(new_value)} from Value: {str(existing_value)}')
        output = await self.coordinator.api.async_write_data(self.config_entry,str(new_value))
        await self.coordinator._async_update_data_forid(item)
        await self.coordinator.async_request_refresh()
        return 

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672PercentControl: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_PERCENT

    #@property
    #def device_class(self):
    #    """Return de device class of the sensor."""
    #    return NumberDeviceClass.PERCENTAGE

    @property
    def native_value(self) -> float:
        _LOGGER.debug(f'SiemensOzw672PercentControl: Native_Value: {value}')
        return value

    @property
    def native_min_value(self) -> float:
        """Return min Temp."""
        val = float(self.config_entry["DPDescr"]["Min"])
        return val

    @property
    def native_max_value(self) -> float:
        """Return max Temp."""
        val = float(self.config_entry["DPDescr"]["Max"])
        return val

    @property
    def native_step(self) -> float:
        """Return step/resolution."""
        val = float(self.config_entry["DPDescr"]["Resolution"])
        return val

    @property
    def native_unit_of_measurement(self) -> str:
        """Return percentage."""
        return PERCENTAGE



class SiemensOzw672EnergyControl(SiemensOzw672Entity,NumberEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672EnergyControl: Config: {self.config_entry}")
        return self._display_name()

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672EnergyControl: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    async def async_set_native_value(self, value: float) -> None:
        """Update Temp ."""
        _LOGGER.debug(f'SiemensOzw672EnergyControl: Set_native_Value: {value}')
        item=self.config_entry["Id"]
        opline=self.config_entry["OpLine"]
        name=self.config_entry["Name"]
        existing_value=self.coordinator.data[item]["Data"]["Value"].strip()
        decimals=self.config_entry["DPDescr"]["DecimalDigits"]
        if decimals == '0':
            new_value=round(float(value))
        else:
            new_value=round(float(value), int(decimals))
        _LOGGER.info(f'SiemensOzw672EnergyControl - Will update ID/Opline/Name: {item}/{opline}/{name} to Value: {str(new_value)} from Value: {str(existing_value)}')
        output = await self.coordinator.api.async_write_data(self.config_entry,str(new_value))
        await self.coordinator._async_update_data_forid(item)
        await self.coordinator.async_request_refresh()
        return 

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672EnergyControl: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_POWER

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self):
        """Return de device class of the sensor."""
        return SensorStateClass.TOTAL_INCREASING
    
    @property
    def native_min_value(self) -> float:
        """Return min Temp."""
        val = float(self.config_entry["DPDescr"]["Min"])
        return val

    @property
    def native_max_value(self) -> float:
        """Return max Temp."""
        val = float(self.config_entry["DPDescr"]["Max"])
        return val

    @property
    def native_step(self) -> float:
        """Return step/resolution."""
        val = float(self.config_entry["DPDescr"]["Resolution"])
        return val

    @property
    def native_unit_of_measurement(self):
        """Return the native_unit_of_measurement of the sensor."""
        item=self.config_entry["Id"]
        return self.coordinator.data[item]["Data"]["Unit"].strip()



class SiemensOzw672NumberControl(SiemensOzw672Entity, NumberEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672NumberControl: Config: {self.config_entry}")
        return self._display_name()

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672NumberControl: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    async def async_set_native_value(self, value: float) -> None:
        """Update The Percentage ."""
        _LOGGER.debug(f'SiemensOzw672NumberControl: Set_native_Value: {value}')
        item=self.config_entry["Id"]
        opline=self.config_entry["OpLine"]
        name=self.config_entry["Name"]
        existing_value=self.coordinator.data[item]["Data"]["Value"].strip()
        decimals=self.config_entry["DPDescr"]["DecimalDigits"]
        if decimals == '0':
            new_value=round(float(value))
        else:
            new_value=round(float(value, int(decimals)))
        _LOGGER.info(f'SiemensOzw672NumberControl - Will update ID/Opline/Name: {item}/{opline}/{name} to Value: {str(new_value)} from Value: {str(existing_value)}')
        output = await self.coordinator.api.async_write_data(self.config_entry,str(new_value))
        await self.coordinator._async_update_data_forid(item)
        await self.coordinator.async_request_refresh()
        return 

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672NumberControl: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return float(data)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_NUMERIC

    @property
    def native_min_value(self) -> float:
        """Return min Temp."""
        val = float(self.config_entry["DPDescr"]["Min"])
        return val

    @property
    def native_max_value(self) -> float:
        """Return max Temp."""
        val = float(self.config_entry["DPDescr"]["Max"])
        return val

    @property
    def native_step(self) -> float:
        """Return step/resolution."""
        val = float(self.config_entry["DPDescr"]["Resolution"])
        return val


