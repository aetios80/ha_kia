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

## Release notes 4.0.6

- Climate entity uses the native temperature members introduced by Home Assistant 2026.11 (`native_temperature_unit`, `native_current_temperature`, `native_target_temperature`); the old members stop working in 2027.11.
- Device tracker imports `TrackerEntity` from `homeassistant.components.device_tracker` (the `device_tracker.config_entry` alias is removed in 2027.6).
- Minimum Home Assistant version raised to 2026.11.0 in `hacs.json`, because the native climate members do not exist before it.

## Release notes 4.0.5

- Fixes the setup failure of 4.0.4 (`_async_refresh() got an unexpected keyword argument 'log_failures'`): a coordinator helper shadowed a private Home Assistant method. A source-level test now prevents redefining private `DataUpdateCoordinator` methods.

## Release notes 4.0.4

- Fixes the EU signin rejected since 2026-10-22 (current browser User-Agent) and signs the CCI auth calls with X-Fingerprint as the official app does; the legacy route is used once per login cycle, and only when Kia's fingerprint gate rejects the signed request.
- Full password logins are limited as described above. After a failed full login (Kia block, server error, timeout) the cheap token refresh is retried within 30 minutes at most; a new full login still waits for the 6-hour window. The 30-minute value is a deliberate choice, not a Kia-provided number.
- A stored 48-character refresh token used as the password now opens the reauthentication flow at setup, without any login attempt.
- Tests: the automated tests of this release were run with a temporary stub runner (no pytest, no Home Assistant) and the signing vectors with the Python standard library only. The RSA password encryption (pycryptodome) was not exercised by them, and nothing was tested against the live Kia service before release: read the log lines `signin outcome=...` and `exchange_failed endpoint=... status=... code=...` on the first live run.

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
