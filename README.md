<img src="https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.kia_uvo.total">

## Kia Connect EU

> **Independent and unsupported:** this integration is not affiliated with or authorized by Kia. Kia may restrict this use or suspend access under its terms.

Custom Home Assistant integration for Kia Connect vehicles registered in Europe. The vendored CCI flow is pinned to upstream `v4.29.1`; credentials are sent only through the allowlisted HTTPS endpoints.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=aetios80&repository=ha_kia&category=integration)

1. Install [HACS](https://hacs.xyz/) if you don't have it already
2. Open HACS in Home Assistant
3. Add `https://github.com/aetios80/ha_kia` as an Integration repository
4. Search for "Kia Connect EU" and install it

### Manual

1. Copy the `custom_components/kia_uvo` directory to your `config/custom_components/` directory
2. Restart Home Assistant

### Configuration

After installation, go to **Settings** -> **Devices & Services** -> **Integrations** and search for **Kia Connect EU**. Configure your vehicle using your Kia Connect username, password, and optional remote-command PIN.

- Only Kia Connect Europe is supported.
- Password and PIN are masked in the configuration flow. They are sent only to the allowlisted Kia HTTPS endpoints.
- Optional reverse geocoding is disabled by default. When enabled, it sends the vehicle coordinates to OpenStreetMap; enabling email sharing is a separate opt-in.
- Multiple cars and accounts are supported. To add additional accounts just go through setup a second time.
- Reconfigure flow is available from the integration options (change credentials or set PIN).
- Scan Interval - fetches cached information from servers every 30 minutes. **Configurable**
- Force Refresh Interval - asks your car for the latest data every 4 hours. **Configurable**
- Force Refresh is disabled between 10PM and 6AM by default. **Configurable**
- By default, distance unit is based on HA metric/imperial preference, you need to configure each entity if you would like other units.

## Supported entities

### Sensors

- Odometer, Total Range, EV Range, Fuel Range
- Car Battery Level (12v), EV Battery Level, EV Battery SOH, EV Battery Capacity, EV Battery Remain
- Estimated Charge Duration (current, fast, portable, station)
- EV Target Range (AC/DC charge)
- Air Temperature, Outside Temperature
- Fuel Level
- Total Power Consumed/Regenerated, Power Consumption 30d
- Front/Rear Seat Status and Heater
- Last Service Distance, Next Service Distance
- Engine Type, DTC Count
- EV Charging Power, EV Charging Current
- Geocoded Location (optional, disabled by default)
- Location Last Updated

### EV Diagnostics (CCS2 vehicles)

- EV Battery Pack Voltage
- EV Battery Temperature (min, max, water)
- EV Battery Chiller RPM
- EV Power Consumption (air conditioning, battery cooling, battery heater)
- EV Off-Peak Start/End Time, EV Departure Time (first/second)

### Binary Sensors

- Engine Running, Ignition, Accessory Status
- Defrost, Heated Rear Window, Heated Steering Wheel, Side Mirror Heater
- EV Battery Charging, EV Battery Plugged In, EV Charge Port Open
- EV Battery Winter Mode, EV Battery Precondition Enabled, EV Battery Heating State
- EV V2L/V2X Status
- EV Schedule Charge Enabled, EV Off-Peak Charge Only Enabled
- Door Open/Close (individual doors), Trunk, Hood
- Window Open/Close (individual windows)
- Lock Status (individual doors)
- Tire Pressure Warnings (individual and all)
- Low Fuel Light, Smart Key Battery Warning
- Brake Fluid Warning, Washer Fluid Warning
- Headlamp Status, Turn Signals, Stop Lamps
- Sunroof Open, Sleep Mode
- Transmission Condition

### Switches

- Climate Control
- EV Charging
- EV Schedule Charge Enabled
- EV Off-Peak Charge Only Enabled

### Number Entities

- EV Charge Limits (AC/DC)
- EV V2L Discharge Limit

### Covers

- Individual Window Control (front left, front right, rear left, rear right) — where supported

### Locks

- Door Lock/Unlock

### Climate

- Climate Control (temperature, mode, defrost) _(WIP — pending merge)_

### Buttons

- Force Refresh
- Open/Close Charge Port, Start/Stop Hazard Lights, Start/Stop Valet Mode, Open/Close Windows _(WIP — pending merge)_

### Device Tracker

- Vehicle Location (GPS)

## Supported services

These can be accessed via Developer Tools > Actions, or called from automations.

- `update`: get latest **cached** vehicle data
- `force_update`: ask the vehicle for its latest data — do not overuse!
- `start_climate` / `stop_climate`: start/stop climate control (starts ICE engine in some regions)
- `start_charge` / `stop_charge`: control EV charging
- `set_charge_limits`: set AC/DC charge capacity limits
- `set_charging_current`: set charging current level (100%, 90% or 60%)
- `open_charge_port` / `close_charge_port`: open or close the charge port
- `lock` / `unlock`: lock or unlock the vehicle
- `set_windows`: open/close individual windows (where supported)
- `start_hazard_lights` / `stop_hazard_lights`: hazard lights only
- `start_hazard_lights_and_horn` / `stop_hazard_lights_and_horn`: panic mode
- `schedule_charging_and_climate`: set planned departure schedule
- `start_valet_mode` / `stop_valet_mode`: valet mode
- `set_navigation`: send a destination to the vehicle's navigation system _(WIP — pending merge)_

Service availability depends on the Kia vehicle model, model year, and Kia Connect account capabilities.

## Screenshots

![Device Details](https://github.com/aetios80/ha_kia/blob/master/Device%20Details.PNG?raw=true)
![Configuration](https://github.com/aetios80/ha_kia/blob/master/Configuration.PNG?raw=true)

## Troubleshooting

If you receive an error while trying to login, please go through these steps:

1. Confirm that the vehicle is registered in Kia Connect Europe.
2. Enable integration debug logging only while troubleshooting. Debug logs intentionally omit request and response bodies.
3. Download diagnostics from the integration entry when reporting an issue. Tokens, credentials, device identifiers, GPS coordinates, and reverse-geocoded addresses are redacted.
