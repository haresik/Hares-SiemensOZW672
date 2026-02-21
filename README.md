# Hares-SiemensOZW672

Modified integration for the Siemens OZW672 device (Web server platform for remote plant monitoring of Siemens LPB/BSB plants). This integration has been used to control a **Hotjet heat pump** with the **RVS41.813/109** control unit.

## Source & inspiration

This integration is based on and inspired by the original work:

**[Home Assistant Custom Component for Siemens OZW672](https://github.com/johnaherninfotrack/homeassistant_custom_siemensozw672)** by johnaherninfotrack.

## Modifications

Additional changes have been made to support **adding and removing tracked entities** — you can manage which entities are polled and monitored without reinstalling or reconfiguring the integration from scratch.

Installation and usage follow the same principles as the original integration; configure via the Home Assistant UI (Settings → Devices & Services → Add Integration → Siemens OZW672).

<img width="2052" height="300" alt="obrazek" src="https://github.com/user-attachments/assets/7b8ba1bd-9f50-40b3-b4f1-f28a28ea2b99" />

<img width="1974" height="1641" alt="obrazek" src="https://github.com/user-attachments/assets/b2fb99f0-e1a3-410d-81f9-3c7d850a6d74" />

Configuration, adding or delete entity ...

<img width="803" height="1421" alt="obrazek" src="https://github.com/user-attachments/assets/3add3134-bdb1-4ed9-a45d-8207d845c694" />

Energy entity:

<img width="2667" height="1379" alt="obrazek" src="https://github.com/user-attachments/assets/6b1446f2-4e1d-4a5d-ae7f-2b017855e44d" />

## Installation

### Register the component as a HACS custom repository

If you want to add this component via HACS (Home Assistant Community Store), follow these steps:

1. Open Home Assistant and go to **HACS** → **Integrations**.
2. Click **Menu** (3 dots in the upper right corner) → **Custom repositories**.
3. Enter the repository URL `https://github.com/haresik/Hares-SiemensOZW672.git` in the **Repository** field.
4. In the **Category** field, select **Integration**.
5. Click **Add**.

Then search for "Siemens OZW672" (or "Hares-SiemensOZW672") in HACS, download the integration, restart Home Assistant, and add it via **Settings** → **Devices & Services** → **Add Integration**.
