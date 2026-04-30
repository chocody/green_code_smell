# Carbon Emission Validation

This note records carbon measurement parity checks between PyGreenSense and
direct CodeCarbon usage.

## Snapshot

### PyGreenSense

- Average carbon emission: `1.7463339e-07 kg CO2`
- Minimum carbon emission: `1.516343e-07 kg CO2`
- Maximum carbon emission: `2.863806e-07 kg CO2`
- Average diff between consecutive runs (signed): `-4.5652333e-09 kg CO2`
- Average absolute diff between consecutive runs: `3.8392633e-08 kg CO2`

### CodeCarbon

- Average carbon emission: `2.488713665990e-09 kgCO2eq`
- Minimum carbon emission: `1.404247309062e-09 kgCO2eq`
- Maximum carbon emission: `4.240361297175e-09 kgCO2eq`
- Average diff (signed): `-3.151237764570e-10 kgCO2eq`
- Average absolute diff: `5.768756903969e-10 kgCO2eq`

## Parity Check

`tests/validate_parity.py` isolates the carbon emission workflow and compares
PyGreenSense measurement against direct CodeCarbon tracking.

- Direct average: `9.085950555049e-06 kgCO2eq`
- Library average: `9.032015317825e-06 kgCO2eq`
- Mean absolute percentage difference: `0.59%`
- Ratio (`lib/direct`): `0.9941x`
