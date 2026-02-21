"""SiemensOzw672Entity class"""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry

from .const import ATTRIBUTION
from .const import DOMAIN
from .const import NAME
from .const import VERSION

import json
import logging
_LOGGER: logging.Logger = logging.getLogger(__package__)


class SiemensOzw672Entity(CoordinatorEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.coordinator = coordinator
        # Navržené entity_id – HA ho použije jen u NOVÉ entity; u existující (stejný unique_id) bere entity_id z registry
        suggested = config_entry.get("suggested_entity_id")
        if suggested:
            self._attr_entity_id = suggested
            _LOGGER.info(
                "Entity nastavuje _attr_entity_id=%s (unique_id=%s). Po add: HA přiřadí entity_id z registry, ne z nás.",
                suggested,
                config_entry.get("entry_id"),
            )
        _LOGGER.debug(f"SiemensOzw672Entity - config_entry: {config_entry}")

    async def async_added_to_hass(self):
        """Po přidání entity: pokud v registru existuje záznam se starým entity_id, přepíšeme na suggested."""
        await super().async_added_to_hass()
        suggested = self.config_entry.get("suggested_entity_id")
        if not suggested:
            return
        unique_id = self.config_entry.get("entry_id")
        if not unique_id:
            return
        domain = suggested.split(".", 1)[0] if "." in suggested else None
        if not domain:
            return
        reg = entity_registry.async_get(self.hass)
        existing_id = reg.async_get_entity_id(domain, DOMAIN, unique_id)
        if existing_id and existing_id != suggested:
            _LOGGER.info(
                "Přepisuji entity_id v registru: %s -> %s",
                existing_id,
                suggested,
            )
            reg.async_update_entity(existing_id, new_entity_id=suggested)

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self.config_entry["entry_id"]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry["device_id"])},
            "name": self.config_entry["device_name"],
            "model": VERSION,
            "manufacturer": NAME,
        }

    def _display_name(self):
        """Název pro zobrazení v UI (bez prefixu zařízení), např. '39 Venkovní teplota'."""
        display_prefix = self.config_entry.get("entity_prefix_display", self.config_entry.get("entity_prefix", ""))
        return f"{display_prefix}{self.config_entry.get('Name', '')}"

    @property
    def name(self):
        """Výchozí zobrazený název – bez prefixu zařízení."""
        return self._display_name()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        _LOGGER.debug(f'SiemensOzw672Entity - device_state_attributes - id: {self.coordinator.data.get("id")}')
        return {
            "attribution": ATTRIBUTION,
            "id": str(self.coordinator.data.get("id")),
            "integration": DOMAIN,
        }
