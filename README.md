# Kia Connect EU

Custom Home Assistant integration for Kia Connect vehicles registered in Europe.

> **Independent and unsupported:** this project is not affiliated with or authorized by Kia. Kia may restrict this use or suspend access under its terms.

## Scope

- Kia Connect Europe only.
- Kia vehicles only.
- The integration uses a vendored CCI client subset for status and supported remote controls.
- The separate official Vehicle Data API path is read-only, prepared but disabled, and does not replace remote control capabilities.
- The integration emulates the official Kia application to reach the Kia Connect EU service; Kia can change that service without notice.
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

In Home Assistant, open **Settings** -> **Devices & Services** -> **Integrations** and add **Kia Connect EU**. The wizard first selects the data backend. `Kia Connect CCI` is the active backend and then requests the Kia Connect username, password, and optional remote-command PIN. `Official Data API` is not available in this release and never requests Kia account credentials. A private, access-controlled Pleos Vehicle Data API now exists under the EU Data Act regime; it is not integrated yet.

`kia_uvo` remains the Home Assistant domain identifier for compatibility with existing configuration entries. It is not a statement of product branding or regional support.

## Login behavior and limits

- When a token refresh fails, the integration may fall back to one full password login. It is limited to one full login every 6 hours per config entry; the limit survives Home Assistant restarts.
- A login rejected as invalid credentials starts the reauthentication flow at once. A redirect back to the login page (which can mean a rejected User-Agent or a wrong password) counts toward two consecutive rejections, then reauthentication starts and polling stops until you re-enter the password.
- Network errors, server errors and temporary Kia blocks never start reauthentication; the integration waits for the next login window.
- Passwords longer than 20 characters may be accepted by some Kia accounts only up to the first 20 characters.
- Breaking change: a 48-character refresh token used as the password is no longer supported. Reconfigure the entry with the real account password.

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
