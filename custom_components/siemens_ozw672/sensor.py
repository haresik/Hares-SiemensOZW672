"""Sensor platform for Siemens OZW672."""
from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import ICON
from .const import SENSOR
from .const import CONF_MENUITEMS
from .const import CONF_DATAPOINTS
from .const import CONF_ENERGY_DATAPOINTS
from .const import CONF_PREFIX_FUNCTION
from .const import CONF_PREFIX_OPLINE
from .const import CONF_USE_DEVICE_LONGNAME
from .const import CONF_DEVICE
from .const import CONF_DEVICE_LONGNAME
from .const import ICON_THERMOMETER
from .const import ICON_PERCENT
from .const import ICON_NUMERIC
from .const import ICON_POWER

from .entity import SiemensOzw672Entity
from homeassistant.helpers.entity import Entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfEnergy,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify
from datetime import datetime
from homeassistant.components.select import SelectEntity

import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)

def is_float(string):
    if "." in string:
        if string.replace(".", "").isnumeric():
            return True
    else:
        return False

async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    _LOGGER.debug(f"SENSOR - Setup_Entry.  DATA: {hass.data[DOMAIN]}")
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug(f"SENSOR ***** Data: {coordinator.data}")
    _LOGGER.debug(f"SENSOR ***** Config: {entry.as_dict()}")

    datapoints = coordinator.data
    # Add sensors
    entities=[]
    entityconfig=""
    for item in datapoints:
        _LOGGER.debug(f"SENSOR Data Point Item: {datapoints[item]}")
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
                # device_name = pro kartu zařízení (long/short dle volby). Entity_id vždy používá krátký název.
                use_device_name = (entry.data.get(CONF_DEVICE_LONGNAME) or entry.data.get(CONF_DEVICE)) if entry.options.get(CONF_USE_DEVICE_LONGNAME) else entry.data.get(CONF_DEVICE)
                dp_config.update({'device_name': use_device_name or entry.data.get("devicename", "")})
                short_name = entry.data.get(CONF_DEVICE) or entry.data.get("devicename", "")
                prefix_display = ""
                if entry.data.get(CONF_PREFIX_FUNCTION) == True: prefix_display = prefix_display + f'{dp_data["MenuItem"]} - '
                if entry.data.get(CONF_PREFIX_OPLINE) == True: prefix_display = prefix_display + f'{dp_data["OpLine"]} '
                dp_config.update({'entity_prefix_display': prefix_display})
                # Test: pevný prefix ozw → sensor.ozw_39_venkovni_teplota
                object_id = f"ozw_{slugify(prefix_display + dp_data['Name'])}"
                suggested = f"{SENSOR}.{object_id}"
                dp_config.update({'suggested_entity_id': suggested})
                dp_config.update({'entity_prefix': prefix_display})
                break
        # At this point - the config for the datapoint is in dp_config
        #               - the data is in dp_data
        if not dp_config == "":
            if dp_config["DPDescr"]["HAType"] == "sensor":
                _LOGGER.debug(f"SENSOR Adding Entity with config: {dp_config} and data: {dp_data}")
                if datapoints[item]["Data"]["Type"] == "Numeric" and datapoints[item]["Data"]["Unit"] in ['°C', '°F', 'K']:
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672TempSensor(coordinator,dp_config)])
                elif datapoints[item]["Data"]["Type"] == "Numeric" and datapoints[item]["Data"]["Unit"] in ['%']:
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672PercentSensor(coordinator,dp_config)])
                elif datapoints[item]["Data"]["Type"] == "Numeric" and datapoints[item]["Data"]["Unit"] in ['kWh', 'Wh']:
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672EnergySensor(coordinator,dp_config)])
                elif datapoints[item]["Data"]["Type"] == "Numeric" and datapoints[item]["Data"]["Unit"] in ['kW', 'W']:
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672PowerSensor(coordinator,dp_config)])
                elif datapoints[item]["Data"]["Type"] == "Numeric":
                    entities.append(dp_config)
                    async_add_entities([SiemensOzw672NumberSensor(coordinator,dp_config)])
                else:
                    # All unknown data types will produce a read only sensor
                    async_add_entities([SiemensOzw672Sensor(coordinator,dp_config)])
                continue
    
    # Vytvořit energetické senzory pro datapointy z CONF_ENERGY_DATAPOINTS
    energy_datapoints = entry.data.get(CONF_ENERGY_DATAPOINTS, [])
    if energy_datapoints:
        _LOGGER.info(f"Creating {len(energy_datapoints)} energy sensors")
        for edp_data in energy_datapoints:
            edp_id = edp_data.get("Id")
            if edp_id and edp_id in datapoints:
                # Vytvořit konfiguraci pro energetický senzor
                edp_config = dict(edp_data)
                if int(edp_data.get("OpLine", 0)) > 1:
                    identifier = edp_data["OpLine"]
                else:
                    identifier = "00" + edp_id
                edp_config.update({'entry_id': entry.entry_id + "_energy_OZW_" + identifier})
                edp_config.update({'device_id': entry.entry_id})
                use_device_name = (entry.data.get(CONF_DEVICE_LONGNAME) or entry.data.get(CONF_DEVICE)) if entry.options.get(CONF_USE_DEVICE_LONGNAME) else entry.data.get(CONF_DEVICE)
                edp_config.update({'device_name': use_device_name or entry.data.get("devicename", "Unknown")})
                short_name = entry.data.get(CONF_DEVICE) or entry.data.get("devicename", "")
                prefix_display = ""
                if entry.data.get(CONF_PREFIX_FUNCTION, False):
                    prefix_display = prefix_display + f'{edp_data.get("MenuItem", "")} - '
                if entry.data.get(CONF_PREFIX_OPLINE, False):
                    prefix_display = prefix_display + f'{edp_data.get("OpLine", "")} '
                edp_config.update({'entity_prefix_display': prefix_display})
                object_id = f"ozw_{slugify(prefix_display + edp_data.get('Name', 'Energy') + ' Energy')}"
                suggested_energy = f"{SENSOR}.{object_id}"
                edp_config.update({'suggested_entity_id': suggested_energy})
                edp_config.update({'entity_prefix': prefix_display})
                _LOGGER.debug(f"Creating energy sensor for datapoint: {edp_id}, config: {edp_config}")
                async_add_entities([SiemensOzw672EnergyCalculatedSensor(coordinator, edp_config)])


class SiemensOzw672Sensor(SiemensOzw672Entity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672Sensor: Config: {self.config_entry}")
        return self._display_name()

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672Sensor: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() :
            return int(float(data))
        return data

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672Sensor: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() :
            return int(float(data))
        return data

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return "siemens_ozw672__custom_device_class"
    
    @property
    def state_class(self):
        """Return de device class of the sensor."""
        return None
    
    @property
    def native_unit_of_measurement(self):
        """Return the native_unit_of_measurement of the sensor."""
        return None


class SiemensOzw672TempSensor(SiemensOzw672Entity,SensorEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672Sensor: Config: {self.config_entry}")
        return self._display_name()
        

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672Sensor: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() :
            if is_float(data):
                return float(data)
            else:
                return int(float(data))
        return data

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672Sensor: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() :
            if is_float(data):
                return float(data)
            else:
                return int(float(data))
        return data

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_THERMOMETER

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return SensorDeviceClass.TEMPERATURE
    
    @property
    def state_class(self):
        """Return de device class of the sensor."""
        return SensorStateClass.MEASUREMENT
    
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


class SiemensOzw672PercentSensor(SiemensOzw672Entity,SensorEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672PercentSensor: Config: {self.config_entry}")
        return self._display_name()

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672PercentSensor: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        return f'{data}%'

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_PERCENT

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return "siemens_ozw672__percent_device_class"
    
    @property
    def state_class(self):
        """Return de device class of the sensor."""
        return SensorStateClass.MEASUREMENT

class SiemensOzw672EnergySensor(SiemensOzw672Entity,SensorEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672EnergySensor: Config: {self.config_entry}")
        return self._display_name()
        

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672EnergySensor: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() and self.config_entry["DPDescr"]["DecimalDigits"] != "0":
            return float(data)
        else:
            return int(float(data))
        return data

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672EnergySensor: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() and self.config_entry["DPDescr"]["DecimalDigits"] != "0":
            return float(data)
        else:
            return int(float(data))
        return data

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
    def native_unit_of_measurement(self):
        """Return the native_unit_of_measurement of the sensor."""
        item=self.config_entry["Id"]
        return self.coordinator.data[item]["Data"]["Unit"].strip()

class SiemensOzw672PowerSensor(SiemensOzw672Entity,SensorEntity):

    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672PowerSensor: Config: {self.config_entry}")
        return self._display_name()
        

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672PowerSensor: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() and self.config_entry["DPDescr"]["DecimalDigits"] != "0":
            return float(data)
        else:
            return int(float(data))
        return data

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672PowerSensor: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() and self.config_entry["DPDescr"]["DecimalDigits"] != "0":
            return float(data)
        else:
            return int(float(data))
        return data

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_POWER

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return SensorDeviceClass.POWER
    
    @property
    def state_class(self):
        """Return de device class of the sensor."""
        return SensorStateClass.MEASUREMENT
    
    @property
    def native_unit_of_measurement(self):
        """Return the native_unit_of_measurement of the sensor."""
        item=self.config_entry["Id"]
        return self.coordinator.data[item]["Data"]["Unit"].strip()

class SiemensOzw672NumberSensor(SiemensOzw672Entity,SensorEntity):
    @property
    def name(self):
        """Return the name of the sensor."""
        _LOGGER.debug(f"SiemensOzw672GenericNumberSensor: Config: {self.config_entry}")
        return self._display_name()
        
    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672GenericNumberSensor: Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() and self.config_entry["DPDescr"]["DecimalDigits"] != "0":
            return float(data)
        else:
            return int(float(data))
        return data

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.debug(f'SiemensOzw672GenericNumberSensor: Native Data: {self.coordinator.data}')
        item=self.config_entry["Id"]
        data=self.coordinator.data[item]["Data"]["Value"].strip()
        if data.isnumeric() and self.config_entry["DPDescr"]["DecimalDigits"] != "0":
            return float(data)
        else:
            return int(float(data))
        return data

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_NUMERIC

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return "siemens_ozw672__number_device_class"
    
    @property
    def state_class(self):
        """Return de device class of the sensor."""
        return SensorStateClass.MEASUREMENT
    
    #@property
    #def suggested_display_precision(self):
    #    """Return the suggested_display_precision of the sensor."""
    #    _LOGGER.debug(f'SiemensOzw672GenericNumberSensor: suggested_display_precision: {self.config_entry["DPDescr"]["DecimalDigits"]}')
    #    return int(self.config_entry["DPDescr"]["DecimalDigits"])


class SiemensOzw672EnergyCalculatedSensor(SiemensOzw672Entity, SensorEntity, RestoreEntity):
    """Senzor pro vypočítanou energii (kWh) na základě času sepnutého stavu datapointu."""
    
    def __init__(self, coordinator, config_entry):
        """Inicializace energetického senzoru."""
        super().__init__(coordinator, config_entry)
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = ICON_POWER
        self._total_energy_kwh = 0.0  # Celková spotřeba v kWh
        self._last_update_time = None
        self._last_datapoint_state = None
        # Načíst výkon z konfigurace datapointu, výchozí 3000W pro kompatibilitu
        self._power_watts = self.config_entry.get("power_watts", 3000)
        
    async def async_added_to_hass(self):
        """Obnovit stav po restartu Home Assistant."""
        await super().async_added_to_hass()
        
        # Obnovit předchozí stav z databáze
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in ("unknown", "unavailable", None):
            try:
                # Obnovit uloženou hodnotu energie
                restored_value = float(last_state.state)
                self._total_energy_kwh = restored_value
                _LOGGER.info("Restored Energy %s: %s kWh from previous session", 
                           self.config_entry.get("Id"), round(self._total_energy_kwh, 3))
            except (ValueError, TypeError):
                _LOGGER.warning("Could not restore energy value for datapoint %s: %s", 
                              self.config_entry.get("Id"), last_state.state)
        
        # Obnovit také čas posledního update (pokud je dostupný v atributech)
        if last_state is not None and last_state.attributes:
            last_update_str = last_state.attributes.get("last_update_time")
            if last_update_str:
                try:
                    self._last_update_time = datetime.fromisoformat(last_update_str)
                    last_state_str = last_state.attributes.get("last_datapoint_state", "OFF")
                    # Převést textový stav na boolean (podporuje "Zap"/"Vyp", "ON"/"OFF", True/False)
                    if isinstance(last_state_str, bool):
                        self._last_datapoint_state = last_state_str
                    else:
                        self._last_datapoint_state = self._is_datapoint_on(last_state_str)
                except (ValueError, TypeError):
                    pass
        
        # Inicializovat čas a stav, pokud není obnoven
        if self._last_update_time is None:
            self._last_update_time = datetime.now()
            # Zkontrolovat aktuální stav datapointu
            item = self.config_entry.get("Id")
            if item and item in self.coordinator.data:
                datapoint_data = self.coordinator.data[item]
                current_value = datapoint_data.get("Data", {}).get("Value", "").strip()
                self._last_datapoint_state = self._is_datapoint_on(current_value)
            else:
                self._last_datapoint_state = False
    
    def _is_datapoint_on(self, value):
        """Zkontrolovat, zda je datapoint zapnutý."""
        if value is None:
            return False
        value_str = str(value).strip()
        value_upper = value_str.upper()
        
        # Explicitně zapnuté hodnoty (česky i anglicky)
        on_values = ["ZAP", "ON", "1", "TRUE", "T"]
        if value_upper in on_values:
            return True
        
        # Explicitně vypnuté hodnoty (česky i anglicky)
        off_values = ["VYP", "OFF", "0", "FALSE", "F", ""]
        if value_upper in off_values:
            return False
        
        # Pokud není v seznamu, považovat za zapnuté (pro kompatibilitu)
        return True
    
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._display_name() + " Energy"
    
    @property
    def native_value(self):
        """Return the current energy value."""
        return round(self._total_energy_kwh, 3)
    
    def _async_update_data(self):
        """Aktualizovat data při změně coordinatoru."""
        item = self.config_entry.get("Id")
        if not item or item not in self.coordinator.data:
            return
        
        current_time = datetime.now()
        datapoint_data = self.coordinator.data[item]
        current_value = datapoint_data.get("Data", {}).get("Value", "").strip()
        is_on = self._is_datapoint_on(current_value)
        
        # Pokud máme předchozí update, počítat spotřebu
        if self._last_update_time is not None:
            time_delta = current_time - self._last_update_time
            hours_elapsed = time_delta.total_seconds() / 3600.0
            
            # Pokud byl datapoint zapnutý během tohoto období, přidat spotřebu
            if self._last_datapoint_state is not None and self._last_datapoint_state:
                # Přidat spotřebu: výkon (W) * čas (h) / 1000 = kWh
                energy_added = (self._power_watts * hours_elapsed) / 1000.0
                self._total_energy_kwh += energy_added
                _LOGGER.debug("Energy %s: Added %s kWh (power: %s W, time: %s h, total: %s kWh)", 
                             item, round(energy_added, 6), 
                             self._power_watts, round(hours_elapsed, 4), round(self._total_energy_kwh, 3))
        
        # Aktualizovat čas a stav
        self._last_update_time = current_time
        self._last_datapoint_state = is_on
        
        _LOGGER.debug("Updated Energy %s: %s kWh (state: %s, value: %s)", 
                     item, round(self._total_energy_kwh, 3), "ON" if is_on else "OFF", current_value)
    
    @property
    def extra_state_attributes(self):
        """Vrátí dodatečné atributy pro uložení stavu."""
        attrs = {}
        if self._last_update_time is not None:
            attrs["last_update_time"] = self._last_update_time.isoformat()
        if self._last_datapoint_state is not None:
            # Uložit stav jako text (česky) pro lepší čitelnost
            attrs["last_datapoint_state"] = "Zap" if self._last_datapoint_state else "Vyp"
        attrs["power_watts"] = self._power_watts
        item = self.config_entry.get("Id")
        if item and item in self.coordinator.data:
            datapoint_data = self.coordinator.data[item]
            attrs["current_value"] = datapoint_data.get("Data", {}).get("Value", "")
        return attrs
    
    async def async_update(self):
        """Aktualizovat senzor při změně coordinatoru."""
        self._async_update_data()
    
    def _handle_coordinator_update(self):
        """Zpracovat aktualizaci z coordinatoru - volá se automaticky při změně coordinatoru."""
        self._async_update_data()
        self.async_write_ha_state()
