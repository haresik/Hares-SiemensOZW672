import asyncio
import logging
import socket
import time

import urllib.parse as Parse
import re
import json

import aiohttp
import async_timeout

from .const import TESTDATA

_LOGGER: logging.Logger = logging.getLogger(__package__)
HEADERS = {"Content-type": "application/json; charset=UTF-8"}

class SiemensOzw672ApiClient:
    def __init__(
        self, host: str, protocol: str, username: str, password: str, session: aiohttp.ClientSession, timeout: int, retries: int
    ) -> None:
        """Siemens OZW672 API Client."""
        _LOGGER.debug("OZW Init")
        self._host = host
        self._protocol = protocol
        self._username = username
        self._password = password
        self._session = session
        self._sessionid = "None"
        self._dpdata = None 
        self._timeout = timeout
        self._retries = retries

    async def async_get_sessionid(self) -> bool:
        """Login to the OZW672 and get a SessionID"""
        url=self._protocol + "://" + self._host + "/api/auth/login.json?user=" + self._username + "&pwd=" + Parse.quote(self._password)
        _LOGGER.debug(f"OZW Login to host: {self._host}")
        if (self._host == "test"):
            response=json.loads(TESTDATA["PREAUTH"])
        else:
            response = await self.api_wrapper("get_preauth", url)
        success = response["Result"]["Success"]
        if (success == "true"): 
            self._sessionid = response["SessionId"]
            return True
        _LOGGER.debug(f"Failed to Login: {response}")
        return False

    async def async_get_sysinfo(self) -> dict:
        """ Sample: ./api/device/info.json?SessionId=1278af3d-a62d-4def-938e-ae2df141500e """
        url=self._protocol + "://" + self._host + "/api/device/info.json?SessionId=" + self._sessionid
        if (self._host == "test"):
            response=json.loads(TESTDATA["SYSINFOLIST"])
        else:
            response = await self.api_wrapper("get", url)
        _LOGGER.debug(f'async_get_sysinfo - response: {response}')
        success = response["Result"]["Success"]
        if (success == "true"):
            return(response["Device"])
        return None

    async def async_get_devices(self) -> dict:
        """Get the device list from the OZW672. - IS THIS USED????"""
        """ Sample: ./api/devicelist/list.json?SessionId=af06e880-bd59-4fb7-873d-d7b3fbc9561f """
        url=self._protocol + "://" + self._host + "/api/devicelist/list.json?SessionId=" + self._sessionid
        if (self._host == "test"):
            response=json.loads(TESTDATA["DEVICELIST"])
        else:
            response = await self.api_wrapper("get", url)
        _LOGGER.debug(f'async_get_devices - response: {response}')
        success = response["Result"]["Success"]
        if (success == "true"):
            return(response["Devices"])
        return None

    async def async_get_menutree(self,id) -> dict:
        """Get the Menu Tree from the OZW672.  If Id="" - then it lists the devices"""
        """ Sample: ./api/menutree/list.json?SessionId=29090e86-3c9a-4eb3-9e95-d5c1729c41e3&Id="""
        url=self._protocol + "://" + self._host + "/api/menutree/list.json?SessionId=" + self._sessionid +"&Id=" + id
        if (self._host == "test") and (id==""):
            response=json.loads(TESTDATA["MENUTREEDEVICELIST"])
        elif (self._host == "test") and (int(id) > 0):
            response=json.loads(TESTDATA["MENUITEMLIST"][id])
        elif (self._host == "test"):
            response=json.loads(TESTDATA["MENUITEMLIST"])
        else:
            response = await self.api_wrapper("get", url)
        _LOGGER.debug(f"async_get_menutree reponse: {response}")
        success = response["Result"]["Success"]
        if (success == "true"):
            return(response)
        return None

    async def async_get_datapoints(self,id) -> dict:
        """Get the DataPoint(s) from the OZW672. """
        url=self._protocol + "://" + self._host + "/api/menutree/list.json?SessionId=" + self._sessionid +"&Id=" + id       
        _LOGGER.debug(f"async_get_datapoints: url={url} id={id}")
        if (self._host == "test"):
            response=json.loads(TESTDATA["DATAPOINTLIST"][id])
        else:
            response = await self.api_wrapper("get", url)
        _LOGGER.debug(f"async_get_datapoints Datapoint Data reponse: {response}")
        success = response["Result"]["Success"]
        if (success == "true"):
            return(response["DatapointItems"])
        return None
        #Sample response: {"MenuItems": [], "DatapointItems": [{"Id": "1438", "Address": "0x310571", "DpSubKey": "0", "WriteAccess": "true", "Text": {"CatId": "2", "GroupId": "2", "Id": "3514", "Long": "DHW operating mode", "Short": "DHW OptgMode"}}], "WidgetItems": [], "Result": {"Success": "true"}}"""

    async def async_get_data(self, datapoints) -> dict:
        """Get the Data for multiple datapoints from the OZW6722."""
        start_time = time.time()
        _LOGGER.debug(f"async_get_data Getting data for datapoints : {datapoints}")
        consolidated_response={}
        for dp in datapoints:
            if (type(dp) == str):
                dpdata = json.loads(dp)
            else:
                dpdata = dp
            id = dpdata["Id"]
            url=self._protocol + "://" + self._host + "/api/menutree/read_datapoint.json?SessionId=" + self._sessionid +"&Id=" + id
            if (self._host == "test"):
                response=json.loads(TESTDATA["DATAPOINT"][id])
            else:
                response = await self.api_wrapper("get", url)
            _LOGGER.debug(f"async_get_data response for ID {id}: {response}")
            if (response["Result"]["Success"] == "true"):
                if (response["Data"]["Value"] == '----'):
                    response["Data"]["Value"] = '0'
                consolidated_response[id]=response
            else:
                # Logovat chybu, ale pokračovat s dalšími datapointy
                error_msg = response.get("Result", {}).get("Error", {}).get("Txt", "Unknown error")
                _LOGGER.warning(f"Failed to get data for datapoint ID {id}: {error_msg}")
        elapsed_time = time.time() - start_time
        _LOGGER.debug(f"async_get_data: Requested {len(datapoints)} datapoints, got {len(consolidated_response)} successful responses")
        if elapsed_time > 60:
            _LOGGER.warn(f"OZW672 Data Poll time exceeding 60 seconds. Last Poll Time: {round(elapsed_time)} seconds")
        _LOGGER.debug(f"OZW672 Data Poll time: {round(elapsed_time)} seconds")
        return consolidated_response
        # Sample response {"Data": {"Type": "Enumeration", "Value": "On", "Unit": ""}, "Result": {"Success": "true"}}

    async def async_write_data(self, datapoint, value) -> dict:
        """Write the Data for a single datapoints to the OZW6722."""
        _LOGGER.debug(f"async_get_data Writing data for datapoint : {datapoint}")
        if (type(datapoint) == str):
            dpdata = json.loads(datapoint)
        else:
            dpdata = datapoint
        id = dpdata["Id"]
        hasValid='false'
        dptype = dpdata["DPDescr"]["Type"]
        if (dptype == "Numeric"): # and ("HasValid" in dpdata["DPDescr"]):
            hasValid='true'
        url=self._protocol + "://" + self._host + "/api/menutree/write_datapoint.json?SessionId=" + self._sessionid +"&Id=" + id + "&Type=" + dptype + "&Value=" + value
        if (hasValid == 'true'):
            url=url + '&IsValid=true'
        if (self._host == "test"):
            # I could do something here to make the test work using the DPDescr cached data
            response=json.loads(TESTDATA["DATAPOINT"][id])
        else:
            response = await self.api_wrapper("get", url)
        _LOGGER.debug(f"async_get_data Datapoint Data response : {response}")
        if (response["Result"]["Success"] == "true"):
            _LOGGER.debug(f"GetData Response: {response}")
            return response
        else:
            return {}


    async def async_get_data_descr(self,datapoints,all_dpdata,force=False) -> dict:
        """Get the DataPoint Descriptions for multiple datapoints from the OZW672. """
        _LOGGER.debug(f"async_get_data_descr Getting data descriptions for datapoints : {datapoints}")
        consolidated_response={}
        for dp in datapoints:
            if (type(dp) == str):
                dpjson = json.loads(dp)
            else:
                dpjson = dp
            id = dpjson["Id"]
            dpdata=all_dpdata[id]
            writeable = dpjson["WriteAccess"]
            #_LOGGER.debug(f"GetDataDescr config: {dp}")
            #_LOGGER.debug(f"GetDataDescr data: {dpdata}")
            url=self._protocol + "://" + self._host + "/api/menutree/datapoint_desc.json?SessionId=" + self._sessionid +"&Id=" + id       
            if (self._host == "test"):
                response=json.loads(TESTDATA["DATAPOINTDESCR"][id])
            else:
                if writeable == "true" or force:  #We only need descriptions for Writeable datapoints.
                    response = await self.api_wrapper("get", url)
                else:  #Just return the Type - save the OZW a load of queries.
                    response=json.loads("""{"Description":{"Type":\""""+dpdata['Data']['Type']+"""\"},"Result": {"Success": "true"}}""")
            if (response["Result"]["Success"] == "true"):
                _LOGGER.debug(f"DatapointItem description reponse: {response}")
                ### This is the main place where the sensors are categorised into domains
                ### Data Point Descriptions are only polled at the time of discovery
                ###
                # Enumeration + Writeable + NOT On/Off = Select Entity
                # Enumeration + Writeable + On/Off = Switch
                # RadioButton/Enumeration + NOT Writeable + On/Off = BinarySensor
                # Number + Writeable + Percent/Temp = Number
                # Number + NOT Writeable + Percent/Temp = Sensor
                # Number + Writeable/NOT Writeable + OtherType = Sensor
                # Everything Else = Sensor
                ###
                if response["Description"]["Type"] == "Enumeration":
                    if writeable == "true":
                        if dpdata["Data"]["Value"] in ['On', 'Off'] :
                            response["Description"]["HAType"] = "switch"
                        else:
                            response["Description"]["HAType"] = "select" 
                    else:
                        if dpdata["Data"]["Value"] in ['On', 'Off'] :
                            response["Description"]["HAType"] = "binarysensor"
                        else:
                            response["Description"]["Enums"] = []  #Some Enums are huge - don't need them for read only sensors.
                            response["Description"]["HAType"] = "sensor"
                elif response["Description"]["Type"] == "RadioButton":
                    if writeable == "true":
                        response["Description"]["HAType"] = "switch"
                    else:
                        if dpdata["Data"]["Value"] in ['On', 'Off'] :
                            response["Description"]["HAType"] = "binarysensor"
                        else:
                            response["Description"]["HAType"] = "sensor"
                elif response["Description"]["Type"] == "Numeric":
                    if writeable == "true" and response["Description"]["Unit"] in ['°C', '°F', 'K', '%', 'kWh', 'Wh']:
                        response["Description"]["HAType"] = "number"
                    else:
                        response["Description"]["HAType"] = "sensor"
                elif response["Description"]["Type"] == "TimeOfDay":
                    if writeable == "true":
                        response["Description"]["HAType"] = "time"
                    else:
                        response["Description"]["HAType"] = "sensor"
                else:   
                        response["Description"]["HAType"] = "sensor"
                consolidated_response[id]=response
        _LOGGER.debug(f"async_get_data_descr DatapointItem description reponse: {consolidated_response}")
        return consolidated_response

    async def api_wrapper(
        self, method: str, url: str, data: dict = {}, headers: dict = {}
    ) -> dict:
        """Get information from the OZW WebAPI."""

        for x in range(self._retries):  #### YES - WE NEED TO RETRY OCCASSIONALY
            try:
                async with async_timeout.timeout(self._timeout): #, loop=asyncio.get_event_loop()):
                    if method == "get_preauth":
                        response = await self._session.get(url, headers=headers,verify_ssl=False)
                        jsonresponse = await response.json()
                        _LOGGER.debug(f"PREAuth: {jsonresponse}")
                        return jsonresponse
                    elif method == "get":
                        cache_sessionid = self._sessionid
                        logurl=url.replace(f"SessionId={cache_sessionid}", "SessionId=XXXXXX")
                        _LOGGER.debug(f"HTTP GET url: {logurl}")
                        response = await self._session.get(url, headers=headers,verify_ssl=False)
                        
                        # Zkusit parsovat JSON, pokud selže kvůli HTML, zkusit přečíst text
                        try:
                            jsonresponse = await response.json()
                        except aiohttp.ContentTypeError:
                            # Server vrátil HTML místo JSON (např. chyba 502)
                            # Zkusit přečíst text a parsovat jako JSON
                            text_response = await response.text()
                            _LOGGER.debug(f"Server returned non-JSON response (status {response.status}), trying to parse as JSON: {text_response[:200]}")
                            try:
                                jsonresponse = json.loads(text_response)
                                # Pokud se podařilo parsovat JSON, pokračovat normálně
                            except json.JSONDecodeError:
                                # Pokud není JSON, zalogaovat chybu s informací o session
                                _LOGGER.error(f'Server returned error {response.status} with non-JSON response for url:{logurl}. Response preview: {text_response[:200]}')
                                # Zkusit obnovit session, protože může být neplatná
                                _LOGGER.warning(f"Obnovuji session kvůli chybě {response.status}...")
                                await self.async_get_sessionid()
                                newurl = url.replace(f"SessionId={cache_sessionid}", f"SessionId={self._sessionid}")
                                if x < self._retries - 1:
                                    return await self.api_wrapper("get", newurl)
                                else:
                                    raise aiohttp.ClientResponseError(
                                        request_info=response.request_info,
                                        history=response.history,
                                        status=response.status,
                                        message=f"Server returned {response.status} with non-JSON response"
                                    )
                        
                        _LOGGER.debug(f"API GET: {jsonresponse}")
                        if (jsonresponse["Result"]["Success"] == "false"):
                            error_nr = jsonresponse.get("Result", {}).get("Error", {}).get("Nr")
                            error_txt = jsonresponse.get("Result", {}).get("Error", {}).get("Txt", "Unknown error")
                            if error_nr in ['1','2']:
                                # Neplatná session - zalogaovat a obnovit
                                _LOGGER.warning(f"Session not valid (Nr: {error_nr}, Txt: {error_txt}) for URL: {logurl}. Obnovuji session...")
                                await self.async_get_sessionid()
                                # Search and replace SessionId
                                newurl = url.replace(f"SessionId={cache_sessionid}", f"SessionId={self._sessionid}")
                                return await self.api_wrapper("get", newurl)
                            else :
                                _LOGGER.error(f'Failed API call with error: {error_txt} (Nr: {error_nr}) for url:{logurl}')
                                return jsonresponse
                        else:
                            return jsonresponse

            except asyncio.TimeoutError as exception:
                _LOGGER.error(
                    "Timeout error fetching information from %s - %s",
                    url,
                    exception,
                )
                if x < self._retries:
                    _LOGGER.error("**** Module will retry ****")
                    pass

            except (KeyError, TypeError) as exception:
                _LOGGER.error(
                    "Error parsing information from %s - %s",
                    url,
                    exception,
                )
            except aiohttp.ContentTypeError as exception:
                # Tato výjimka by měla být zachycena už v try bloku, ale pro jistotu ji zachytíme i zde
                _LOGGER.error(
                    "ContentTypeError fetching information from %s - %s (možná neplatná session)",
                    url,
                    exception,
                )
                # Zkusit obnovit session a zkusit znovu
                if x < self._retries - 1:
                    cache_sessionid = self._sessionid
                    logurl = url.replace(f"SessionId={cache_sessionid}", "SessionId=XXXXXX")
                    _LOGGER.warning(f"Obnovuji session kvůli ContentTypeError pro URL: {logurl}...")
                    await self.async_get_sessionid()
                    newurl = url.replace(f"SessionId={cache_sessionid}", f"SessionId={self._sessionid}")
                    return await self.api_wrapper("get", newurl)
            except (aiohttp.ClientError, socket.gaierror) as exception:
                _LOGGER.error(
                    "Error fetching information from %s - %s",
                    url,
                    exception,
                )
                if x < self._retries - 1:
                    _LOGGER.error("**** Module will retry ****")
                    pass
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.error("Something really wrong happened! - %s", exception)
