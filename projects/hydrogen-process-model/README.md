# hydrogen-process-model

I built a hydrogen process model because I kept seeing two routes described as the cheap way to make hydrogen, and I wanted to check the energy and cost myself. It compares **steam methane reforming** (SMR, where natural gas is turned into hydrogen with hot steam) with **water electrolysis** (where electricity splits water). It uses the same kind of mass and energy balance I already do for my gas-capture measurements in [co2-capture-data-analysis](../co2-capture-data-analysis/).

The model answers three questions: how much energy each route needs for 1 kg of hydrogen, what that hydrogen costs per kg with the prices I enter, and how the reformer changes with temperature and steam. All prices and capital costs in the shipped file are examples I chose so the model runs. They are not quotes.

```sh
cd projects/hydrogen-process-model
uv sync --locked --extra dev
uv run h2-compare --output h2-output
```

The command prints the comparison and writes `h2-output/hydrogen_comparison.xlsx`. With the example inputs it reports:

- SMR at 900 degrees C, steam-to-carbon ratio 3, 25 bar: **55 kWh per kg H2**, about **$2.80 per kg** with the example prices.
- Electrolysis at 70% efficiency (higher heating value basis): **56 kWh per kg H2**, about **$6.03 per kg**.

The energy figures are similar, but the cost gap is mostly price. Most of the 55 kWh for SMR is methane in the feed, and with the example prices electricity costs about $19 per GJ of energy against $4 per GJ for gas. Change `data/assumptions.toml` to test your own prices.

## How the reformer works

Methane and steam are fed into a hot tube filled with catalyst. The reaction makes hydrogen, carbon monoxide and carbon dioxide. The model does not simulate the tube. It asks what mix of gases is most stable at the chosen temperature and pressure. That is called **chemical equilibrium**, and it is what the reactor approaches when it has enough catalyst and time.

I use [Cantera](https://cantera.org), an open-source thermodynamics library, with its bundled GRI-Mech 3.0 gas mechanism. For each temperature, steam-to-carbon ratio and pressure, Cantera returns the outlet composition. The model then gives:

- **Hydrogen per methane**, and the **methane conversion** (how much of the feed methane is used up).
- **Hydrogen fraction in the dry gas**, which is what the product looks like after the steam is removed.
- **Heat duty**: the energy the furnace must add to take the feed from 25 degrees C to the reformer outlet. Reforming absorbs heat, so this energy has to come from burning some of the gas.

The furnace fuel is added to the feed methane to get the total energy per kg of hydrogen. The furnace efficiency is an input.

Cantera does not model solid carbon. Carbon can form on the catalyst at low steam-to-carbon ratios, so the model is only meaningful at the ratios I sweep (2.5 to 3.5).

## How electrolysis is modelled

Electrolysis needs `kWh per kg = 39.4 / efficiency`, using the higher heating value of hydrogen (141.8 MJ per kg). At 70% efficiency this is 56 kWh per kg. The model also gives the water and oxygen per kg: 8.94 kg of water in, 1 kg of hydrogen and 7.94 kg of oxygen out. The model does not describe the stack chemistry or electrode materials.

## Cost

The cost per kg adds three parts:

1. **Energy**: the gas or electricity bought, at the price in the assumptions file.
2. **Capital**: the plant cost spread over its life with a capital recovery factor, a standard way to turn a one-time cost into equal yearly payments at a given interest rate. The plant is sized to the same output for both routes, and each route's capital is scaled from its own price per kg per day or per kW.
3. **Fixed operating cost**: a yearly share of capital for maintenance.

Costs are divided by the kilograms made in a year (daily output times 365 times availability).

## What is in the folder

- `src/process_model/smr.py` runs the Cantera equilibrium and returns the closure checks.
- `src/process_model/electrolysis.py` holds the electricity, water and oxygen numbers.
- `src/process_model/cost.py` reads the assumptions and calculates cost per kg.
- `src/process_model/report.py` runs the sweep and the electrolyser cases.
- `src/process_model/workbook.py` writes the Excel file with Summary, SMR sweep, Electrolysis, Mass balance and Assumptions sheets.
- `data/assumptions.toml` holds every price, capital figure and operating point. Each line has a comment.

## Tests and mass balance

```sh
uv run ruff check .
uv run pytest -q
```

There are 35 tests. For every reformer point, they check that carbon, hydrogen and oxygen atoms and total mass leave the reactor unchanged. They also check that more temperature raises methane conversion, that more steam raises hydrogen per methane, that lower pressure favours conversion, and that the heat duty is at least the reforming reaction enthalpy. The electrolysis tests check that water balances hydrogen plus oxygen, and the cost tests check the results against hand calculations. The workbook has a Mass balance sheet with the largest closure error, which is about 1e-12 in my runs. CI runs the same checks in `.github/workflows/hydrogen-process-model-ci.yml`.

## Limits

- The prices, capital and efficiencies are examples, not quotes or market data.
- Equilibrium is an upper limit on conversion. A real reformer runs close to it only with enough catalyst and residence time.
- The model does not include solid carbon formation, catalyst deactivation, carbon capture, the water-gas shift section or compression. Those would change the cost.
- Electrolyser stack replacement is not included in the fixed cost.
