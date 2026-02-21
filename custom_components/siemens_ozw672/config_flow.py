"""Adds config flow for Siemens OZW672."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers import selector
from datetime import timedelta

from .api import SiemensOzw672ApiClient
from .const import CONF_HOST
from .const import CONF_DEVICE
from .const import CONF_DEVICE_LONGNAME
from .const import CONF_DEVICE_ID
from .const import CONF_PROTOCOL
from .const import CONF_PASSWORD
from .const import CONF_USERNAME
from .const import CONF_MENUITEMS
from .const import CONF_DATAPOINTS
from .const import CONF_ENERGY_DATAPOINTS
from .const import CONF_PREFIX_FUNCTION
from .const import CONF_PREFIX_OPLINE
from .const import CONF_PREFIX_DEVICE
from .const import CONF_SCANINTERVAL
from .const import CONF_HTTPTIMEOUT
from .const import CONF_HTTPRETRIES
from .const import DOMAIN
from .const import PLATFORMS
from .const import DEFAULT_HTTPTIMEOUT
from .const import DEFAULT_HTTPRETRIES
from .const import DEFAULT_SCANINTERVAL
from .const import DEFAULT_PREFIX_FUNCTION
from .const import DEFAULT_PREFIX_OPLINE
from .const import DEFAULT_USE_DEVICE_LONGNAME
from .const import DEFAULT_OPTIONS
from .const import CONF_USE_DEVICE_LONGNAME

import json

PROTOCOL_OPTIONS = [
    selector.SelectOptionDict(value="http", label="HTTP"),
    selector.SelectOptionDict(value="https", label="HTTPS")
]



import logging
_LOGGER: logging.Logger = logging.getLogger(__package__)

class SiemensOzw672FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for siemens_ozw672."""

    VERSION = 1
    MINOR_VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._session = None
        self._client = None
        self._discovereddevices = dict()
        self._devicemenuitems = None
        self._sysinfo = None
        self._datapoints = []
        self._datapoints_descr = []
        self._deviceid = None
        self._data = None
        self._devserialnumber = ""
        self.alldevices = None
        self._options = dict(DEFAULT_OPTIONS)
        self._disablenamechoice = False

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        """ First Screen - Protocol, Hostname/IP, Username, Password, and some options"""
        self._errors = {}
        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_HOST], user_input[CONF_PROTOCOL], user_input[CONF_USERNAME], user_input[CONF_PASSWORD], DEFAULT_HTTPTIMEOUT, DEFAULT_HTTPRETRIES
            )
            if valid:
                # Get the list of devices:
                self._discovereddevices = (await self._get_menutree(""))["MenuItems"]
                # Get the device menutTrue ID
                self.alldevices=await self._get_devices()
                self._data=user_input
                if CONF_DEVICE_ID in self._data:
                    existing_entry = self.async_entry_for_existingdevice(self._data[CONF_DEVICE_ID])
                    if existing_entry:
                        self._disablenamechoice=True
                return await self.async_step_device()
            else:
                self._errors["base"] = "auth"
            return await self._show_config_form(user_input)
        
        # Pokud je user_input None, zkontrolovat, zda existuje config entry se stejnými přihlašovacími údaji
        existing_entries = self._async_current_entries()
        if existing_entries:
            # Najít první entry se stejnými přihlašovacími údaji
            for entry in existing_entries:
                existing_host = entry.data.get(CONF_HOST)
                existing_protocol = entry.data.get(CONF_PROTOCOL)
                existing_username = entry.data.get(CONF_USERNAME)
                existing_password = entry.data.get(CONF_PASSWORD)
                
                # Pokud máme přihlašovací údaje, zkusit je použít
                if existing_host and existing_protocol and existing_username and existing_password:
                    _LOGGER.debug(f"Našel existující config entry s přihlašovacími údaji: {existing_host}")
                    # Otestovat přihlašovací údaje
                    valid = await self._test_credentials(
                        existing_host, existing_protocol, existing_username, existing_password, DEFAULT_HTTPTIMEOUT, DEFAULT_HTTPRETRIES
                    )
                    if valid:
                        # Použít existující přihlašovací údaje a přeskočit formulář
                        self._data = {
                            CONF_HOST: existing_host,
                            CONF_PROTOCOL: existing_protocol,
                            CONF_USERNAME: existing_username,
                            CONF_PASSWORD: existing_password
                        }
                        # Get the list of devices:
                        self._discovereddevices = (await self._get_menutree(""))["MenuItems"]
                        # Get the device menutTrue ID
                        self.alldevices = await self._get_devices()
                        # Přeskočit přímo na výběr zařízení
                        return await self.async_step_device()
                    else:
                        _LOGGER.debug(f"Přihlašovací údaje z existujícího entry nejsou platné, zobrazit formulář")
        
        # Pokud neexistuje entry nebo přihlašovací údaje nejsou platné, zobrazit formulář
        return await self._show_config_form(user_input)

    async def async_step_device(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            device=json.loads(user_input[CONF_DEVICE])
            ### Support a Customized name for the Device being monitored.
            self._data[CONF_DEVICE]=device["Name"]
            self._data[CONF_DEVICE_LONGNAME]=device["LongName"]
            # Předpona s funkcí je skrytá v UI, v konfiguraci vždy False
            self._options[CONF_PREFIX_FUNCTION] = False
            self._options[CONF_PREFIX_OPLINE]=user_input[CONF_PREFIX_OPLINE]
            self._options[CONF_USE_DEVICE_LONGNAME]=False  # Skryto z GUI, vždy vypnuto
            self._data[CONF_PREFIX_FUNCTION] = False
            self._data[CONF_PREFIX_OPLINE]=user_input[CONF_PREFIX_OPLINE]
            self._data[CONF_USE_DEVICE_LONGNAME]=False
            ### Each device has a MenuTree root ID
            menutreeid=device["Id"]
            ### Get the System Info as discovery used Serial Number of the OZW672 and Serial Number of the Device.
            self._sysinfo = await self._get_sysinfo()
            self._data[CONF_DEVICE_ID]=f'{self._sysinfo["SerialNr"]}:{device["Text"]["Long"]}' #Redundant code - used as a default
            for d in self.alldevices:
                d_ident = f'{d["Addr"]} {d["Type"]}'
                if d_ident == device["Text"]["Long"]:
                    self._data[CONF_DEVICE_ID]=f'{self._sysinfo["SerialNr"]}:{d["SerialNr"]}'
            self._devserialnumber = self._data[CONF_DEVICE_ID]
            ### Support updating an existing device
            existing_entry = self.async_entry_for_existingdevice(self._data[CONF_DEVICE_ID])
            if existing_entry:
                self._datapoints = existing_entry.data.get(CONF_DATAPOINTS)
                # Detect if a change to the naming has occurred and updated all.
                _LOGGER.debug(f'Found existing datapoints: {self._datapoints}')
            await self.async_set_unique_id(self._devserialnumber)
            ### Now get a list of Functions/MenuItems (ignore datapoints at this level) for this device to enable the user to select what to monitor.
            self._devicemenuitems = (await self._get_menutree(menutreeid))["MenuItems"]
            return await self.async_step_mainmenu()
        else:
            return await self._show_device_selection_form(user_input)
        return await self._show_device_selection_form(user_input)

    async def async_step_mainmenu(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data[CONF_MENUITEMS]=user_input[CONF_MENUITEMS]
            self._alldevicemenuitems=user_input[CONF_MENUITEMS]
            _LOGGER.debug(f"Found: CONF_MENUITEMS: {self._data[CONF_MENUITEMS]}")
            ### Now we have selected a list of Functions/MenuItems/DataPointItmes to monitor, recursively call a function to enable the user to select entities to monitor.
            return await self.async_step_submenu()
        else:
            return await self._show_mainmenu_selection_form(user_input)
        return await self._show_mainmenu_selection_form(user_input)
    

    async def async_step_submenu(self, user_input=None):
        _LOGGER.debug(f"async_step_submenu - user_input: {user_input}")
        self._errors = {}
        if user_input is not None:
            ###### WE NEED TO PROCESS SELECTED SUBMENUS HERE
            if CONF_MENUITEMS in user_input:
                for submenu in user_input[CONF_MENUITEMS]:
                    _LOGGER.debug(f'Appending {submenu} in MenuItems to discover')
                    self._alldevicemenuitems.append(submenu)
            if CONF_DATAPOINTS in user_input:
                # Get DP Data as we need this to determine type.
                all_dpdata = await self._get_data(user_input[CONF_DATAPOINTS])
                _LOGGER.debug(f'async_step_submenu **** Intial DP Data: {all_dpdata}')
                all_dpdescr = await self._get_data_descr(user_input[CONF_DATAPOINTS], all_dpdata)
                _LOGGER.debug(f'async_step_submenu **** Initial DP Descriptions: {all_dpdescr}')
                for dp in user_input[CONF_DATAPOINTS]:
                    dpjson=json.loads(dp)
                    dpdescr = all_dpdescr[dpjson["Id"]]["Description"]
                    _LOGGER.debug(f'async_step_submenu - "Id": {dpjson["Id"]},"WriteAccess": {dpjson["WriteAccess"]},"OpLine": {dpjson["Text"]["Id"]}, "Name": {dpjson["Text"]["Long"]},"MenuItem": {dpjson["MenuItem"]}, "DPDescr": {dpdescr} ')
                    self._datapoints.append({"Id": dpjson["Id"],"WriteAccess": dpjson["WriteAccess"],"OpLine": dpjson["Text"]["Id"], "Name": dpjson["Text"]["Long"],"MenuItem": dpjson["MenuItem"], "DPDescr": dpdescr })
            self._data[CONF_DATAPOINTS]=self._datapoints
            _LOGGER.debug(f"DATAPOINTS: {self._data[CONF_DATAPOINTS]}")
            if len(self._alldevicemenuitems) > 0:
                ### Recursively traverse through all menu items.
                _LOGGER.debug("****** Recursing further through menu ******")
                return await self.async_step_submenu()
            else: ### FINALLY... Create our discovered entities. ###
                self._data["options"]=self._options
                use_device_longname = self._options.get(CONF_USE_DEVICE_LONGNAME)
                if (use_device_longname == True):
                    _LOGGER.debug(f'Options: {self._options} -- Will use Device Long Name')
                    dev_title=self._data[CONF_DEVICE_LONGNAME]
                else:
                    dev_title=self._data[CONF_DEVICE]
                _LOGGER.debug(f'Adding Entities now...Data: {self._data}')
                return self.async_create_entry(    
                    title=dev_title, data=self._data, options=self._options
                )
        else:
            if len(self._alldevicemenuitems) > 0:
                item = self._alldevicemenuitems.pop(0)
                _LOGGER.debug(f"Generating Config Form for item: {item} ")
                ### For each Function/MenuItem selected, list the entities available and allow the user to select what to monitor/poll
                ### Note - these could be submenus
                return await self._show_submenu_selection_form(item,user_input)
            else:
                # We are done
                return
        return await self._show_submenu_selection_form(item,user_input)


    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SiemensOzw672OptionsFlowHandler(config_entry)

    def async_entry_for_existingdevice(self, deviceserialnumber):
        """Find an existing entry for a serialnumber."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_DEVICE_ID) == deviceserialnumber:
                return entry
        return None

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
            {
                vol.Required(CONF_PROTOCOL, default="http"): selector.SelectSelector(selector.SelectSelectorConfig(options=PROTOCOL_OPTIONS)),
                vol.Required(CONF_HOST): str, 
                vol.Required(CONF_USERNAME): str, 
                vol.Required(CONF_PASSWORD): str
            }
            ),
            errors=self._errors,
        )

    async def _show_device_selection_form(self, user_input):  # pylint: disable=unused-argument
        """Show the device selection form. """
        _LOGGER.debug("Building device list from: " + str(self._discovereddevices))
        device_list_selector = []
        for device in self._discovereddevices:
            devchannel=str(device["Text"]["Long"]).split(' ',1)[0]
            devname=str(device["Text"]["Long"]).split(' ',1)[1]
            for dev in self.alldevices:
                if dev['Addr'] == devchannel:
                    device["Name"]=dev['Name']
                else:
                    device["Name"]=devname
            device["LongName"]=str(device["Text"]["Long"])
            device_list_selector.append(selector.SelectOptionDict(value=json.dumps(device), label="Address+Device: "+str(device["Text"]["Long"] +" (Name:"+device["Name"]+")")))
        # CONF_USE_DEVICE_LONGNAME skryto z GUI, vždy False
        if self._disablenamechoice == False:
            schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): selector.SelectSelector(selector.SelectSelectorConfig(options=device_list_selector)),
                    vol.Required(CONF_PREFIX_OPLINE, default=self._options[CONF_PREFIX_OPLINE]): bool,
                })
        else:
            schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): selector.SelectSelector(selector.SelectSelectorConfig(options=device_list_selector)),
                    vol.Required(CONF_PREFIX_OPLINE, default=self._options[CONF_PREFIX_OPLINE]): bool,
                })

        return self.async_show_form(
            step_id="device",
            data_schema=schema,
            errors=self._errors,
        )

    async def _show_mainmenu_selection_form(self, user_input):  # pylint: disable=unused-argument
        """Show the menu item selection form. """
        _LOGGER.debug("Building Menu Item list from " + str(self._devicemenuitems))
        menuitem_list_selector = []
        for menuitem in self._devicemenuitems:
            menuitem_list_selector.append(selector.SelectOptionDict(value=json.dumps(menuitem), label=menuitem["Text"]["Long"]))
        return self.async_show_form(
            step_id="mainmenu",
            data_schema=vol.Schema(
            {
                vol.Required(CONF_MENUITEMS,default=False): selector.SelectSelector(selector.SelectSelectorConfig(options=menuitem_list_selector, multiple=True))
            }
            ),
            errors=self._errors,
        )

    async def _show_submenu_selection_form(self, item, user_input):  # pylint: disable=unused-argument
        """Show the Sub Menu Itme and Data Point item selection form. """
        _LOGGER.debug(f"Building SubMenu list for item: {item} ")
        datapoint_list_selector = []
        menuitem_list_selector = []
        
        menutree_item=json.loads(item)
        menutree_id=menutree_item["Id"]
        menutree_name=menutree_item["Text"]["Long"]
        if "MenuItem" not in item:
            menutree_menulocation = menutree_name
        else:
            menutree_menulocation = menutree_item["MenuItem"] + "->" + menutree_name
        existing_menu_items = self._devicemenuitems
        existing_dp_items = self._datapoints
        
        new_all_items = await self._get_menutree(menutree_id)
        new_dp_items = new_all_items["DatapointItems"]
        new_menu_items = new_all_items["MenuItems"]

        _LOGGER.debug(f'Generating form for Submenus: {new_menu_items} and DataPoints: {new_dp_items} at menulocation: {menutree_menulocation} ')
        for menu in new_menu_items:
            menu["MenuItem"]=menutree_menulocation
            menuitem_list_selector.append(selector.SelectOptionDict(value=json.dumps(menu), label=menu["Text"]["Long"]) )

        for dp in new_dp_items:
            ### If we are already polling a variable - don't list it.
            already_exists=False
            for edp in existing_dp_items:
                if edp["Id"] == dp["Id"]:
                    already_exists=True
                    break
            ### If this is something new to monitor - add it to our Dict.
            if not already_exists:
                dp["MenuItem"]=menutree_menulocation
                datapoint_list_selector.append(selector.SelectOptionDict(value=json.dumps(dp), label=dp["Text"]["Long"]))
        this_data_schema=vol.Schema({vol.Optional(CONF_DATAPOINTS): "",vol.Optional(CONF_DATAPOINTS): ""})
        
        if len(datapoint_list_selector) == 0 and len(menuitem_list_selector) == 0:
            this_data_schema=vol.Schema(
            {
                vol.Optional(CONF_MENUITEMS): "",
                vol.Optional(CONF_DATAPOINTS): "" 
            }
            )
        elif len(datapoint_list_selector) == 0 and len(menuitem_list_selector) > 0:
            this_data_schema=vol.Schema(
            {
                vol.Optional(CONF_MENUITEMS, default=[]): selector.SelectSelector(selector.SelectSelectorConfig(options=menuitem_list_selector, multiple=True)),
                vol.Optional(CONF_DATAPOINTS): "" 
            }
            )
        elif len(datapoint_list_selector) > 0 and len(menuitem_list_selector) == 0:
            this_data_schema=vol.Schema(
                {
                vol.Optional(CONF_MENUITEMS): "",
                vol.Required(CONF_DATAPOINTS, default=[]): selector.SelectSelector(selector.SelectSelectorConfig(options=datapoint_list_selector, multiple=True))
                }
            )
        elif len(datapoint_list_selector) > 0 and len(menuitem_list_selector) > 0:
            this_data_schema=vol.Schema(
                {
                vol.Optional(CONF_MENUITEMS, default=[]): selector.SelectSelector(selector.SelectSelectorConfig(options=menuitem_list_selector, multiple=True)),
                vol.Required(CONF_DATAPOINTS, default=[]): selector.SelectSelector(selector.SelectSelectorConfig(options=datapoint_list_selector, multiple=True))
                }
            )
        _LOGGER.debug(f'Data schema: {this_data_schema}')
        return self.async_show_form(
            step_id="submenu",
            data_schema=this_data_schema,
            description_placeholders={"item_name": menutree_menulocation},
            errors=self._errors,
        )


    async def _test_credentials(self, host, protocol, username, password, timeout, retries):
        """Return true if credentials are valid."""
        try:
            self._session = async_create_clientsession(self.hass)
            self._client = SiemensOzw672ApiClient(host, protocol, username, password, self._session, timeout, retries)
            if (await self._client.async_get_sessionid()):
                return True
            return False
        except Exception:  # pylint: disable=broad-except
            pass
        return False

    async def _get_sysinfo(self):
        try:
            info = await self._client.async_get_sysinfo()
        except Exception:  # pylint: disable=broad-except
            pass
        return info

    async def _get_devices(self):
        try:
            devices = await self._client.async_get_devices()
        except Exception as err: # pylint: disable=broad-except
            _LOGGER.debug(f'Exception: {repr(err)}')
            pass
        return devices

    async def _get_menutree(self,id):
        try:
            output = await self._client.async_get_menutree(id)
        except Exception as err: # pylint: disable=broad-except
            _LOGGER.debug(f'Exception: {repr(err)}')
            pass
        return output

    async def _get_datapoints(self,id):
        try:
            output = await self._client.async_get_datapoints(id)
        except Exception as err: # pylint: disable=broad-except
            _LOGGER.debug(f'Exception: {repr(err)}')
            pass
        return output

    async def _get_data(self, datapoints):
        """Update data via OZW API."""
        try:
            return await self._client.async_get_data(datapoints)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug(f'Exception: {repr(err)}')
            pass
            return ''

    async def _get_data_descr(self,datapoints,all_dpdata):
        try:
            return await self._client.async_get_data_descr(datapoints, all_dpdata)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug(f'Exception: {repr(err)}')
            pass
            return ''

class SiemensOzw672OptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for siemens_ozw672."""

    def __init__(self, config_entry):
        """Initialize options flow. config_entry ukládáme do _config_entry, protože
        základní třída OptionsFlow má config_entry jako read-only property bez setteru."""
        self._config_entry = config_entry
        self.options = dict(config_entry.options)
        self.data = dict(config_entry.data)  # Přidáno pro změnu datapointů
        _LOGGER.debug(f'OptionsFlow - Existing options: {self.options}')
        self.conf_httptimeout = self.options.get(CONF_HTTPTIMEOUT)
        self.conf_httpretries = self.options.get(CONF_HTTPRETRIES)
        self.conf_scaninterval = self.options.get(CONF_SCANINTERVAL)
        if self.conf_httptimeout == None: self.conf_httptimeout=DEFAULT_HTTPTIMEOUT
        if self.conf_httpretries == None: self.conf_httpretries=DEFAULT_HTTPRETRIES
        if self.conf_scaninterval == None: self.conf_scaninterval=DEFAULT_SCANINTERVAL
        # Pro přidání datapointů
        self._client = None
        self._session = None
        self._alldevicemenuitems = []
        self._errors = {}

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            # Pokud uživatel chce přidat další datapointy, přejít na další krok
            if user_input.get("add_datapoints"):
                # Inicializovat API klienta
                if await self._init_client():
                    return await self.async_step_add_datapoints_menu()
                else:
                    self._errors["base"] = "connection_failed"
            
            # Pokud uživatel chce odebrat datapointy, přejít na další krok
            if user_input.get("remove_datapoints"):
                return await self.async_step_remove_datapoints()
            
            # Pokud uživatel chce přidat energetické datapointy, přejít na další krok
            if user_input.get("add_energy_datapoints"):
                return await self.async_step_add_energy_datapoints()
            
            # Pokud uživatel chce odebrat energetické datapointy, přejít na další krok
            if user_input.get("remove_energy_datapoints"):
                return await self.async_step_remove_energy_datapoints()
            
            # Zachovat hodnoty skrytých polí (switch, select, number, binary_sensor, sensor)
            # Tyto hodnoty nejsou ve formuláři, ale musíme je zachovat v options
            hidden_fields = ["switch", "select", "number", "binary_sensor", "sensor"]
            for field in hidden_fields:
                if field not in user_input:
                    user_input[field] = self.options.get(field, True)
            # Entity_id má vždy formát sensor.rvs41_813_109_39_venkovni_teplota – prefix zařízení se nevolí
            if CONF_PREFIX_DEVICE not in user_input:
                user_input[CONF_PREFIX_DEVICE] = True
            # CONF_USE_DEVICE_LONGNAME skryto z GUI, vždy vypnuto
            if CONF_USE_DEVICE_LONGNAME not in user_input:
                user_input[CONF_USE_DEVICE_LONGNAME] = False

            self.options.update(user_input)
            _LOGGER.debug(f'Updating Options.  New Options: {self.options}')
            return await self._update_options()
            

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HTTPTIMEOUT, default=self.conf_httptimeout): int,
                    vol.Required(CONF_HTTPRETRIES, default=self.conf_httpretries): int,
                    vol.Required(CONF_SCANINTERVAL, default=self.conf_scaninterval): int,
                    vol.Optional("add_datapoints", default=False): bool,  # Tlačítko pro přidání datapointů
                    vol.Optional("remove_datapoints", default=False): bool,  # Tlačítko pro odebrání datapointů
                    vol.Optional("add_energy_datapoints", default=False): bool,  # Tlačítko pro přidání energetických datapointů
                    vol.Optional("remove_energy_datapoints", default=False): bool,  # Tlačítko pro odebrání energetických datapointů
                    # CONF_USE_DEVICE_LONGNAME skryto, vždy False
                }
            ),
            errors=self._errors
        )

    async def _init_client(self):
        """Inicializovat API klienta pro připojení k OZW672."""
        try:
            # Načíst aktuální data z config_entry
            current_data = dict(self._config_entry.data)
            host = current_data.get(CONF_HOST)
            protocol = current_data.get(CONF_PROTOCOL)
            username = current_data.get(CONF_USERNAME)
            password = current_data.get(CONF_PASSWORD)
            
            self._session = async_create_clientsession(self.hass)
            self._client = SiemensOzw672ApiClient(
                host, protocol, username, password, 
                self._session, self.conf_httptimeout, self.conf_httpretries
            )
            
            if await self._client.async_get_sessionid():
                return True
            return False
        except Exception as err:
            _LOGGER.error(f'Failed to initialize client: {repr(err)}')
            return False

    async def async_step_add_datapoints_menu(self, user_input=None):
        """Krok pro výběr menu, ze kterého se budou přidávat datapointy."""
        if user_input is not None:
            if CONF_MENUITEMS in user_input and user_input[CONF_MENUITEMS]:
                # Uživatel vybral menu itemy - přejít na výběr datapointů
                self._alldevicemenuitems = user_input[CONF_MENUITEMS]
                return await self.async_step_add_datapoints_submenu()
            else:
                # Žádné menu nevybráno, vrátit se zpět
                return await self.async_step_user()
        
        # Varianta A: Získat výchozí zařízení z config_entry a automaticky ho použít
        current_device_id = self._config_entry.data.get(CONF_DEVICE_ID)
        current_device_longname = self._config_entry.data.get(CONF_DEVICE_LONGNAME)
        
        try:
            # Získat root menu
            menutree_response = await self._client.async_get_menutree("")
            if menutree_response and menutree_response.get("Result", {}).get("Success") == "true":
                menu_items = menutree_response.get("MenuItems", [])
                
                if not menu_items:
                    return self.async_show_form(
                        step_id="add_datapoints_menu",
                        data_schema=vol.Schema({}),
                        errors={"base": "no_menu_items"}
                    )
                
                # Získat sysinfo a devices pro porovnání
                sysinfo = await self._client.async_get_sysinfo()
                all_devices = await self._client.async_get_devices()
                
                # Najít výchozí zařízení v menu_items
                default_menu_item = None
                if current_device_id and current_device_longname:
                    # Najít device podle SerialNr nebo LongName
                    device_serial = current_device_id.split(":")[1] if ":" in current_device_id else None
                    
                    for menu in menu_items:
                        menu_ident = menu["Text"]["Long"]
                        # Porovnat s current_device_longname
                        if menu_ident == current_device_longname:
                            default_menu_item = menu
                            _LOGGER.debug(f"Nalezeno výchozí zařízení podle LongName: {menu_ident}")
                            break
                        # Nebo najít podle SerialNr
                        if device_serial and all_devices:
                            for d in all_devices:
                                d_ident = f'{d["Addr"]} {d["Type"]}'
                                if d_ident == menu_ident and d["SerialNr"] == device_serial:
                                    default_menu_item = menu
                                    _LOGGER.debug(f"Nalezeno výchozí zařízení podle SerialNr: {d_ident}")
                                    break
                            if default_menu_item:
                                break
                
                # Pokud bylo nalezeno výchozí zařízení, použít ho automaticky (Varianta A)
                if default_menu_item:
                    _LOGGER.info(f"Automaticky používáno výchozí zařízení: {default_menu_item['Text']['Long']}")
                    self._alldevicemenuitems = [json.dumps(default_menu_item)]
                    return await self.async_step_add_datapoints_submenu()
                
                # Jinak zobrazit formulář s výběrem (včetně výchozího zařízení)
                menu_list_selector = []
                for menu in menu_items:
                    # Označit výchozí zařízení v seznamu
                    label = menu["Text"]["Long"]
                    if current_device_longname and menu["Text"]["Long"] == current_device_longname:
                        label = f"{label} (výchozí)"
                    
                    menu_list_selector.append(
                        selector.SelectOptionDict(
                            value=json.dumps(menu), 
                            label=label
                        )
                    )
                
                return self.async_show_form(
                    step_id="add_datapoints_menu",
                    data_schema=vol.Schema({
                        vol.Required(CONF_MENUITEMS, default=[]): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=menu_list_selector, 
                                multiple=True
                            )
                        )
                    }),
                    description_placeholders={"info": "Vyberte menu, ze kterého chcete přidat datapointy. Výchozí zařízení je označeno."}
                )
        except Exception as err:
            _LOGGER.error(f'Error getting menu: {repr(err)}')
            return self.async_show_form(
                step_id="add_datapoints_menu",
                data_schema=vol.Schema({}),
                errors={"base": "menu_error"}
            )

    async def async_step_add_datapoints_submenu(self, user_input=None):
        """Krok pro výběr datapointů z menu."""
        self._errors = {}
        
        if user_input is not None:
            # Zpracovat vybrané submenu
            if CONF_MENUITEMS in user_input and user_input[CONF_MENUITEMS]:
                for submenu in user_input[CONF_MENUITEMS]:
                    self._alldevicemenuitems.append(submenu)
            
            # Zpracovat vybrané datapointy
            if CONF_DATAPOINTS in user_input and user_input[CONF_DATAPOINTS]:
                # Získat data a popisy pro nové datapointy
                all_dpdata = await self._get_data(user_input[CONF_DATAPOINTS])
                if not all_dpdata:
                    self._errors["base"] = "no_data"
                    return await self._show_add_datapoints_form(self._alldevicemenuitems[0] if self._alldevicemenuitems else None)
                
                # Použít force=True aby se získaly všechny popisy
                all_dpdescr = await self._get_data_descr(user_input[CONF_DATAPOINTS], all_dpdata, force=True)
                
                # Přidat nové datapointy do existujícího seznamu - načíst aktuální data
                current_data = dict(self._config_entry.data)
                existing_datapoints = current_data.get(CONF_DATAPOINTS, [])
                existing_ids = {dp["Id"] for dp in existing_datapoints}
                
                new_datapoints = []
                for dp in user_input[CONF_DATAPOINTS]:
                    dpjson = json.loads(dp)
                    dp_id = dpjson["Id"]
                    
                    # Zkontrolovat, zda už není v seznamu
                    if dp_id not in existing_ids:
                        # Získat popis - pokud není v all_dpdescr, vytvořit minimální
                        dpdescr_response = all_dpdescr.get(dp_id, {})
                        if dpdescr_response:
                            dpdescr = dpdescr_response.get("Description", {})
                        else:
                            # Pokud se nepodařilo získat popis, vytvořit minimální na základě dat
                            dpdata = all_dpdata.get(dp_id, {})
                            data_type = dpdata.get("Data", {}).get("Type", "Unknown")
                            dpdescr = {
                                "Type": data_type,
                                "HAType": "sensor"  # Default
                            }
                            _LOGGER.warning(f'Could not get full description for datapoint {dp_id}, using minimal description')
                        
                        new_datapoints.append({
                            "Id": dpjson["Id"],
                            "WriteAccess": dpjson["WriteAccess"],
                            "OpLine": dpjson["Text"]["Id"],
                            "Name": dpjson["Text"]["Long"],
                            "MenuItem": dpjson.get("MenuItem", ""),
                            "DPDescr": dpdescr
                        })
                        _LOGGER.info(f'Adding new datapoint: {dpjson["Text"]["Long"]} (ID: {dp_id}) with HAType: {dpdescr.get("HAType", "sensor")}')
                
                if new_datapoints:
                    # Přidat nové datapointy
                    existing_datapoints.extend(new_datapoints)
                    current_data[CONF_DATAPOINTS] = existing_datapoints
                    
                    _LOGGER.info(f"Total datapoints after adding: {len(existing_datapoints)}")
                    _LOGGER.info(f"New datapoints to add: {[{'Id': dp['Id'], 'Name': dp['Name'], 'HAType': dp.get('DPDescr', {}).get('HAType', 'unknown')} for dp in new_datapoints]}")
                    
                    # Aktualizovat entry.data - musí být synchronní, aby se změny projevily
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=current_data
                    )
                    # Aktualizovat také self.data pro další použití
                    self.data = current_data
                    
                    await self.hass.async_block_till_done()
                    # Vynutit zápis config entry na disk (po pouhém async_update_entry + reload to HA
                    # někdy neuloží před restartem; disable + enable vynutí persist stejně jako ruční postup v UI)
                    _LOGGER.info(f"Added {len(new_datapoints)} new datapoints. Persisting config (disable+enable)...")
                    await self.hass.config_entries.async_set_disabled_by(
                        self._config_entry.entry_id, ConfigEntryDisabler.USER
                    )
                    await self.hass.async_block_till_done()
                    await self.hass.config_entries.async_set_disabled_by(
                        self._config_entry.entry_id, None
                    )
                    return await self._update_options()
            
            # Pokud jsou ještě další submenu, pokračovat
            if len(self._alldevicemenuitems) > 0:
                return await self.async_step_add_datapoints_submenu()
            else:
                # Hotovo
                return await self._update_options()
        
        # Zobrazit formulář pro výběr datapointů
        if len(self._alldevicemenuitems) > 0:
            item = self._alldevicemenuitems.pop(0)
            return await self._show_add_datapoints_form(item)
        else:
            # Žádné další menu, vrátit se
            return await self._update_options()

    async def _show_add_datapoints_form(self, item):
        """Zobrazit formulář pro výběr datapointů z menu itemu."""
        try:
            menutree_item = json.loads(item)
            menutree_id = menutree_item["Id"]
            menutree_name = menutree_item["Text"]["Long"]
            
            if "MenuItem" not in item:
                menutree_menulocation = menutree_name
            else:
                menutree_menulocation = menutree_item["MenuItem"] + "->" + menutree_name
            
            # Získat menu a datapointy
            new_all_items = await self._client.async_get_menutree(menutree_id)
            if not new_all_items or new_all_items.get("Result", {}).get("Success") != "true":
                return self.async_show_form(
                    step_id="add_datapoints_submenu",
                    data_schema=vol.Schema({}),
                    errors={"base": "menu_error"}
                )
            
            new_dp_items = new_all_items.get("DatapointItems", [])
            new_menu_items = new_all_items.get("MenuItems", [])
            
            # Získat existující datapointy - načíst aktuální data z config_entry
            current_data = dict(self._config_entry.data)
            existing_dp_items = current_data.get(CONF_DATAPOINTS, [])
            existing_ids = {dp["Id"] for dp in existing_dp_items}
            
            # Vytvořit seznamy pro selector
            datapoint_list_selector = []
            menuitem_list_selector = []
            
            for menu in new_menu_items:
                menu["MenuItem"] = menutree_menulocation
                menuitem_list_selector.append(
                    selector.SelectOptionDict(
                        value=json.dumps(menu), 
                        label=menu["Text"]["Long"]
                    )
                )
            
            for dp in new_dp_items:
                # Zkontrolovat, zda už není v seznamu
                if dp["Id"] not in existing_ids:
                    dp["MenuItem"] = menutree_menulocation
                    datapoint_list_selector.append(
                        selector.SelectOptionDict(
                            value=json.dumps(dp), 
                            label=dp["Text"]["Long"]
                        )
                    )
            
            # Vytvořit schema
            schema_dict = {}
            if len(menuitem_list_selector) > 0:
                schema_dict[vol.Optional(CONF_MENUITEMS, default=[])] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=menuitem_list_selector, 
                        multiple=True
                    )
                )
            if len(datapoint_list_selector) > 0:
                schema_dict[vol.Optional(CONF_DATAPOINTS, default=[])] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=datapoint_list_selector, 
                        multiple=True
                    )
                )
            
            if not schema_dict:
                # Žádné nové položky
                return self.async_show_form(
                    step_id="add_datapoints_submenu",
                    data_schema=vol.Schema({}),
                    description_placeholders={"item_name": menutree_menulocation},
                    errors={"base": "no_new_items"}
                )
            
            return self.async_show_form(
                step_id="add_datapoints_submenu",
                data_schema=vol.Schema(schema_dict),
                description_placeholders={"item_name": menutree_menulocation},
                errors=self._errors
            )
        except Exception as err:
            _LOGGER.error(f'Error showing form: {repr(err)}')
            return self.async_show_form(
                step_id="add_datapoints_submenu",
                data_schema=vol.Schema({}),
                errors={"base": "form_error"}
            )

    async def _get_data(self, datapoints):
        """Získat data pro datapointy."""
        try:
            return await self._client.async_get_data(datapoints)
        except Exception as err:
            _LOGGER.error(f'Error getting data: {repr(err)}')
            return {}

    async def _get_data_descr(self, datapoints, all_dpdata, force=False):
        """Získat popisy datapointů."""
        try:
            return await self._client.async_get_data_descr(datapoints, all_dpdata, force=force)
        except Exception as err:
            _LOGGER.error(f'Error getting data descriptions: {repr(err)}')
            return {}

    async def async_step_remove_datapoints(self, user_input=None):
        """Krok pro odebrání datapointů."""
        # Načíst aktuální data z config_entry, ne z self.data (které může být zastaralé)
        current_data = dict(self._config_entry.data)
        datapoints = current_data.get(CONF_DATAPOINTS, [])
        
        if user_input is not None:
            # Zpracovat vybrané datapointy k odstranění
            if "datapoints_to_remove" in user_input and user_input["datapoints_to_remove"]:
                ids_to_remove = set(user_input["datapoints_to_remove"])
                
                # Filtrovat datapointy - ponechat jen ty, které nejsou v seznamu k odstranění
                remaining_datapoints = [
                    dp for dp in datapoints 
                    if dp["Id"] not in ids_to_remove
                ]
                
                removed_count = len(datapoints) - len(remaining_datapoints)
                
                if removed_count > 0:
                    _LOGGER.info(f"Removing {removed_count} datapoints. IDs: {ids_to_remove}")
                    
                    # Aktualizovat entry.data - použít aktuální data z config_entry
                    current_data = dict(self._config_entry.data)
                    current_data[CONF_DATAPOINTS] = remaining_datapoints
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=current_data
                    )
                    # Aktualizovat také self.data pro další použití
                    self.data = current_data
                    
                    await self.hass.async_block_till_done()
                    _LOGGER.info(f"Removed {removed_count} datapoints. Persisting config (disable+enable)...")
                    await self.hass.config_entries.async_set_disabled_by(
                        self._config_entry.entry_id, ConfigEntryDisabler.USER
                    )
                    await self.hass.async_block_till_done()
                    await self.hass.config_entries.async_set_disabled_by(
                        self._config_entry.entry_id, None
                    )
                
                return await self._update_options()
            else:
                # Žádné datapointy nebyly vybrány, vrátit se zpět
                return await self.async_step_user()
        
        # Zobrazit formulář se seznamem datapointů
        if not datapoints:
            return self.async_show_form(
                step_id="remove_datapoints",
                data_schema=vol.Schema({}),
                errors={"base": "no_datapoints"}
            )
        
        # Vytvořit seznam pro selector
        datapoint_list_selector = []
        for dp in datapoints:
            dp_id = dp.get("Id", "unknown")
            dp_name = dp.get("Name", f"Datapoint {dp_id}")
            dp_hatype = dp.get("DPDescr", {}).get("HAType", "sensor")
            dp_menuitem = dp.get("MenuItem", "")
            
            # Vytvořit popisek s informacemi
            label = f"{dp_name}"
            if dp_menuitem:
                label += f" ({dp_menuitem})"
            label += f" [{dp_hatype}]"
            
            datapoint_list_selector.append(
                selector.SelectOptionDict(
                    value=dp_id,
                    label=label
                )
            )
        
        return self.async_show_form(
            step_id="remove_datapoints",
            data_schema=vol.Schema({
                vol.Required("datapoints_to_remove", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=datapoint_list_selector,
                        multiple=True
                    )
                )
            }),
            description_placeholders={
                "count": str(len(datapoints))
            }
        )

    async def async_step_add_energy_datapoints(self, user_input=None):
        """Krok pro přidání energetických datapointů."""
        # Načíst aktuální data z config_entry
        current_data = dict(self._config_entry.data)
        all_datapoints = current_data.get(CONF_DATAPOINTS, [])
        energy_datapoints = current_data.get(CONF_ENERGY_DATAPOINTS, [])
        
        if user_input is not None:
            # Zpracovat vybrané datapointy k přidání
            if "datapoints_to_add" in user_input and user_input["datapoints_to_add"]:
                ids_to_add = set(user_input["datapoints_to_add"])
                
                # Získat existující ID energetických datapointů
                existing_energy_ids = {dp["Id"] for dp in energy_datapoints}
                
                # Najít datapointy k přidání (které ještě nejsou v energetických)
                new_energy_datapoints = []
                for dp in all_datapoints:
                    if dp["Id"] in ids_to_add and dp["Id"] not in existing_energy_ids:
                        new_energy_datapoints.append(dp)
                
                if new_energy_datapoints:
                    # Uložit vybrané datapointy do self pro další krok
                    self._pending_energy_datapoints = new_energy_datapoints
                    # Přejít na krok pro zadání výkonu
                    return await self.async_step_add_energy_datapoints_power()
                else:
                    return await self.async_step_user()
            else:
                # Žádné datapointy nebyly vybrány, vrátit se zpět
                return await self.async_step_user()
        
        # Zobrazit formulář se seznamem datapointů
        if not all_datapoints:
            return self.async_show_form(
                step_id="add_energy_datapoints",
                data_schema=vol.Schema({}),
                errors={"base": "no_datapoints"}
            )
        
        # Získat existující ID energetických datapointů pro filtrování
        existing_energy_ids = {dp["Id"] for dp in energy_datapoints}
        
        # Vytvořit seznam pro selector - pouze datapointy, které ještě nejsou v energetických
        datapoint_list_selector = []
        for dp in all_datapoints:
            if dp["Id"] not in existing_energy_ids:
                dp_id = dp.get("Id", "unknown")
                dp_name = dp.get("Name", f"Datapoint {dp_id}")
                dp_hatype = dp.get("DPDescr", {}).get("HAType", "sensor")
                dp_menuitem = dp.get("MenuItem", "")
                
                # Vytvořit popisek s informacemi
                label = f"{dp_name}"
                if dp_menuitem:
                    label += f" ({dp_menuitem})"
                label += f" [{dp_hatype}]"
                
                datapoint_list_selector.append(
                    selector.SelectOptionDict(
                        value=dp_id,
                        label=label
                    )
                )
        
        if not datapoint_list_selector:
            return self.async_show_form(
                step_id="add_energy_datapoints",
                data_schema=vol.Schema({}),
                errors={"base": "all_datapoints_already_added"}
            )
        
        return self.async_show_form(
            step_id="add_energy_datapoints",
            data_schema=vol.Schema({
                vol.Required("datapoints_to_add", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=datapoint_list_selector,
                        multiple=True
                    )
                )
            }),
            description_placeholders={
                "count": str(len(all_datapoints)),
                "energy_count": str(len(energy_datapoints))
            }
        )

    async def async_step_add_energy_datapoints_power(self, user_input=None):
        """Krok pro zadání výkonu pro energetické datapointy."""
        if not hasattr(self, '_pending_energy_datapoints') or not self._pending_energy_datapoints:
            return await self.async_step_user()
        
        if user_input is not None:
            # Zpracovat zadané výkony
            current_data = dict(self._config_entry.data)
            energy_datapoints = current_data.get(CONF_ENERGY_DATAPOINTS, [])
            
            # Přidat výkon ke každému datapointu
            for dp in self._pending_energy_datapoints:
                dp_id = dp.get("Id")
                dp_name = dp.get("Name", f"Datapoint {dp_id}")
                # Vytvořit stejný klíč jako v formuláři
                sanitized_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in dp_name)
                sanitized_name = sanitized_name.replace(' ', '_').replace('-', '_')
                if len(sanitized_name) > 30:
                    sanitized_name = sanitized_name[:30]
                power_key = f"výkon_{sanitized_name}_{dp_id}"
                # Zkusit najít hodnotu - buď podle nového klíče nebo starého (pro kompatibilitu)
                power_watts = user_input.get(power_key) or user_input.get(f"power_{dp_id}", 3000)
                if power_watts is None:
                    power_watts = 3000  # Výchozí 3000W
                
                # Přidat výkon do konfigurace datapointu
                dp["power_watts"] = int(power_watts)
                energy_datapoints.append(dp)
            
            pending_count = len(self._pending_energy_datapoints)
            pending_ids = [dp['Id'] for dp in self._pending_energy_datapoints]
            _LOGGER.info(f"Adding {pending_count} energy datapoints with power settings. IDs: {pending_ids}")
            
            # Aktualizovat entry.data
            current_data[CONF_ENERGY_DATAPOINTS] = energy_datapoints
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=current_data
            )
            # Aktualizovat také self.data pro další použití
            self.data = current_data
            
            # Vyčistit dočasné datapointy
            delattr(self, '_pending_energy_datapoints')
            
            await self.hass.async_block_till_done()
            _LOGGER.info(f"Added {pending_count} energy datapoints. Persisting config (disable+enable)...")
            await self.hass.config_entries.async_set_disabled_by(
                self._config_entry.entry_id, ConfigEntryDisabler.USER
            )
            await self.hass.async_block_till_done()
            await self.hass.config_entries.async_set_disabled_by(
                self._config_entry.entry_id, None
            )
            
            return await self._update_options()
        
        # Vytvořit formulář pro zadání výkonu pro každý datapoint
        schema_dict = {}
        datapoint_info = {}
        for dp in self._pending_energy_datapoints:
            dp_id = dp.get("Id", "unknown")
            dp_name = dp.get("Name", f"Datapoint {dp_id}")
            # Vytvořit popisnější klíč s názvem datapointu (sanitizovaný)
            # Odstranit speciální znaky a nahradit mezerami podtržítky
            sanitized_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in dp_name)
            sanitized_name = sanitized_name.replace(' ', '_').replace('-', '_')
            # Omezit délku a přidat ID pro unikátnost
            if len(sanitized_name) > 30:
                sanitized_name = sanitized_name[:30]
            power_key = f"výkon_{sanitized_name}_{dp_id}"
            # Uložit informace o datapointu pro description_placeholders
            datapoint_info[f"name_{dp_id}"] = dp_name
            # Vytvořit pole pro výkon s popisnějším názvem
            schema_dict[vol.Required(
                power_key, 
                default=3000
            )] = vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=50000, msg="Výkon musí být mezi 1 a 50000 W")
            )
        
        return self.async_show_form(
            step_id="add_energy_datapoints_power",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "count": str(len(self._pending_energy_datapoints)),
                **datapoint_info
            }
        )

    async def async_step_remove_energy_datapoints(self, user_input=None):
        """Krok pro odebrání energetických datapointů."""
        # Načíst aktuální data z config_entry
        current_data = dict(self._config_entry.data)
        energy_datapoints = current_data.get(CONF_ENERGY_DATAPOINTS, [])
        
        if user_input is not None:
            # Zpracovat vybrané datapointy k odstranění
            if "energy_datapoints_to_remove" in user_input and user_input["energy_datapoints_to_remove"]:
                ids_to_remove = set(user_input["energy_datapoints_to_remove"])
                
                # Filtrovat energetické datapointy - ponechat jen ty, které nejsou v seznamu k odstranění
                remaining_energy_datapoints = [
                    dp for dp in energy_datapoints 
                    if dp["Id"] not in ids_to_remove
                ]
                
                removed_count = len(energy_datapoints) - len(remaining_energy_datapoints)
                
                if removed_count > 0:
                    _LOGGER.info(f"Removing {removed_count} energy datapoints. IDs: {ids_to_remove}")
                    
                    # Aktualizovat entry.data
                    current_data = dict(self._config_entry.data)
                    current_data[CONF_ENERGY_DATAPOINTS] = remaining_energy_datapoints
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=current_data
                    )
                    # Aktualizovat také self.data pro další použití
                    self.data = current_data
                    
                    await self.hass.async_block_till_done()
                    _LOGGER.info(f"Removed {removed_count} energy datapoints. Persisting config (disable+enable)...")
                    await self.hass.config_entries.async_set_disabled_by(
                        self._config_entry.entry_id, ConfigEntryDisabler.USER
                    )
                    await self.hass.async_block_till_done()
                    await self.hass.config_entries.async_set_disabled_by(
                        self._config_entry.entry_id, None
                    )
                
                return await self._update_options()
            else:
                # Žádné datapointy nebyly vybrány, vrátit se zpět
                return await self.async_step_user()
        
        # Zobrazit formulář se seznamem energetických datapointů
        if not energy_datapoints:
            return self.async_show_form(
                step_id="remove_energy_datapoints",
                data_schema=vol.Schema({}),
                errors={"base": "no_energy_datapoints"}
            )
        
        # Vytvořit seznam pro selector
        datapoint_list_selector = []
        for dp in energy_datapoints:
            dp_id = dp.get("Id", "unknown")
            dp_name = dp.get("Name", f"Datapoint {dp_id}")
            dp_hatype = dp.get("DPDescr", {}).get("HAType", "sensor")
            dp_menuitem = dp.get("MenuItem", "")
            
            # Vytvořit popisek s informacemi
            label = f"{dp_name}"
            if dp_menuitem:
                label += f" ({dp_menuitem})"
            label += f" [{dp_hatype}]"
            
            datapoint_list_selector.append(
                selector.SelectOptionDict(
                    value=dp_id,
                    label=label
                )
            )
        
        return self.async_show_form(
            step_id="remove_energy_datapoints",
            data_schema=vol.Schema({
                vol.Required("energy_datapoints_to_remove", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=datapoint_list_selector,
                        multiple=True
                    )
                )
            }),
            description_placeholders={
                "count": str(len(energy_datapoints))
            }
        )

    async def _update_options(self):
        """Update config entry options."""
        _LOGGER.debug(
            "Recreating entry %s due to configuration change",
            self._config_entry.title
        )
        return self.async_create_entry(title="", data=self.options)



