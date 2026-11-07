# Input sources

Retrieved 2026-11-05. Values are transcribed from manufacturer publications; scenario entries are explicitly authored assumptions. Distributor links below host manufacturer-authored datasheets. No private records are used.

## sb

[p.3, Table SB4.1 reproduced by Mersen](https://www.mersen.com/sites/default/files/files_imported_ep/WP-Achieving-Higher-Short-Circuit-Current-Ratings-for-Industrial-Control-Panels.pdf)

Unmarked contactor/motor controller and overload 5 kA; terminal block 10 kA. No tested-combination uplift.

## method

[p.70, weakest-link procedure](https://www.eaton.com/content/dam/eaton/markets/machinebuilding/protect-personnel-assets-and-machine-reliability/documents/documents-english-language/eaton-control-panel-design-guide-ul-508a-br033001en-us.pdf)

Main circuit minimum; feeder protective device interrupting rating must also cover panel rating.

## control

[SB3.2.1 quotation](https://electrification.us.abb.com/nec409ul-508a-support)

Control supply primary branch protection is included. Downstream control-only devices are excluded.

## breaker

[Performance Ratings / Certifications](https://www.eaton.com/us/en-us/skuPage.FAZ-C6%7B%7D3-NA.html)

UL 489, 10 kA conservative interrupting rating, 277/480Y V; use only grounded-wye supply.

## breaker_loss

[Eaton 102244 FAZ-C6/3-NA datasheet, p.2, design verification](https://www.scatts.co.uk/datasheets/496661?desc=Technical-Datasheet)

3.5 W whole device at 6 A, not per pole. Manufacturer document mirrored by distributor.

## control_breaker

[Eaton 102160 FAZ-C2/2-NA, p.1](https://www.farnell.com/datasheets/3049687.pdf)

2.8 W whole device at 2 A; UL489 10 kA at 480Y/277 V. Manufacturer datasheet mirror.

## contactor

[LC1D09BD, power dissipation per pole / hold-in consumption](https://iportal.se.com/Contents/docs/SQD-LC1D09BD.PDF)

0.2 W/pole AC-3 plus 5.4 W DC coil. Three power poles = 6.0 W total; no AC-coil FAQ used.

## coil

[Resolution](https://www.se.com/in/en/faqs/FA114908/)

Standard DC coil 5.4 W.

## overload

[LRD07 row](https://www.se.com/ie/en/faqs/FA142123/)

1.67 VA at maximum setting, taken as 1.67 W resistive thermal loss for complete device.

## supply

[p.1 HDR-60-24; p.3 derating; p.4 dimensions](https://www.meanwell.com/Upload/PDF/HDR-60/HDR-60-SPEC.PDF)

24 V 2.5 A 60 W, typical 90% efficiency at full load, 52.5 x 90 x 54.5 mm. Loss estimate 60*(1/.90-1), not a guaranteed maximum at all loads.

## plc

[Basic PLC units C0-00DR-D row](https://cdn.automationdirect.com/static/specs/clickpower.pdf)

120 mA at 24 V logic supply; all 2.88 W assumed to heat panel.

## plc_wiring

[C0-00DR-D wiring and dimensions](https://cdn.automationdirect.com/static/specs/c000drd.pdf)

8 DC inputs and 6 relay outputs. CPU 24 V x 0.120 A = 2.88 W; seven wired inputs bounded by (2 x 0.006 + 5 x 0.005) A x 26.4 V = 0.9768 W. Sum 3.8568 W included in heat and DC budget. Maximum channel currents are specified at 26.4 V.

## cooling

[Calculation basis for enclosure climate control, p.13](https://www.rittal.com/imf3/none/3_8419/3305500_Catalogo_tecnico_EN/)

Qsurface=k*A*(Ti-Ta), natural rise=Q/(k*A); steel k=5.5 W/m2K.

## air

[Calculation of required air flow](https://www.rittal.com/imf3/none/3_8419/3305500_Catalogo_tecnico_EN/)

Sea-level air-flow factor 3.1 m3 K/(Wh). Residual heat method after enclosure surface cooling.

## fan

[p.2 performance and dimensions](https://www.rittal.com/pdf-creator/variant/us-en/3237124)

24 V DC; rated 2.4 W; 16 m3/h WITH two 3237200 outlets (15 with one), 20 free-air; 92 x 92 mm cutout. p.4 legacy tender text says 3 W, used conservatively in heat and DC budget.

## scenario

[Design inputs, authored scenario assumptions](docs/design.md#design-inputs)

Simulated machine nameplate, environment, wiring allowances, generic field loads and layout envelopes. These are design choices, not measured/manufacturer claims.
