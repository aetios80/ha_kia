# Kia Connect EU

Custom Home Assistant integration for Kia Connect vehicles registered in Europe.

> **Independent and unsupported:** this project is not affiliated with or authorized by Kia. Kia may restrict this use or suspend access under its terms.

## Scope

- Kia Connect Europe only.
- Kia vehicles only.
- The integration uses a vendored CCI client subset for status and supported remote controls.
- The separate official Vehicle Data API path is read-only, prepared but disabled, and does not replace remote control capabilities.
- Remote capability depends on the vehicle model, account entitlement, and Kia service availability.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=aetios80&repository=ha_kia&category=integration)

1. Install [HACS](https://hacs.xyz/) if it is not already installed.
2. Add `https://github.com/aetios80/ha_kia` as an Integration repository.
3. Install "Kia Connect EU" and restart Home Assistant.

### Manual

Copy `custom_components/kia_uvo` to `config/custom_components/`, then restart Home Assistant.

## Configuration

In Home Assistant, open **Settings** -> **Devices & Services** -> **Integrations** and add **Kia Connect EU**. The wizard first selects the data backend. `Kia Connect CCI` is the active backend and then requests the Kia Connect username, password, and optional remote-command PIN. `Official Data API` is intentionally unavailable until Kia grants third-party access; it never requests Kia account credentials.

`kia_uvo` remains the Home Assistant domain identifier for compatibility with existing configuration entries. It is not a statement of product branding or regional support.

## Security and Privacy

- Password and PIN fields are masked in the configuration flow.
- The integration accepts only allowlisted Kia HTTPS endpoints, expected ports, and same-host redirects. Insecure TLS overrides are rejected.
- Persisted tokens do not duplicate username, password, or PIN.
- Debug logging redacts credentials, tokens, cookies, vehicle identifiers, coordinates, and addresses.
- Reverse geocoding is disabled by default. When explicitly enabled, coordinates are sent to OpenStreetMap; email sharing is a separate opt-in.

## Capabilities

The integration provides vehicle state entities, optional location tracking, force refresh, and supported remote controls. Remote door lock has been validated manually with the CCI flow. Other actions, including unlock, charging, climate, windows, charge port, valet mode, and hazard lights, remain dependent on the individual vehicle and Kia account.

Sending navigation destinations is not exposed because the Kia EU CCI adapter does not implement it, and the official Vehicle Data API documents data access rather than remote commands.

## Troubleshooting

1. Confirm that the vehicle is registered in Kia Connect Europe and works in the official Kia application.
2. Enable integration debug logging only while investigating a fault. Request and response bodies are intentionally not logged.
3. Before sharing diagnostics, review the exported file even though credentials, tokens, device identifiers, coordinates, and addresses are redacted.

## License and Attribution

This repository is distributed under the MIT License. It contains a vendored third-party API subset; the applicable attribution is retained in [LICENSE](LICENSE) and [NOTICE](NOTICE).
