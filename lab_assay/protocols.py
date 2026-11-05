"""Conservative OT-2 single-channel plans. No hardware execution is performed."""

import math

from .importers import well_name

HEADER = """from opentrons import protocol_api

metadata = {"protocolName": "Lab assay preparation", "author": "Jack Lai", "apiLevel": "2.15"}

def run(protocol: protocol_api.ProtocolContext):
    tips = protocol.load_labware("opentrons_96_tiprack_300ul", "3")
    pipette = protocol.load_instrument("p300_single_gen2", "left", tip_racks=[tips])
"""


def volume(value, minimum=20, maximum=200):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"Volume must be a finite number between {minimum} and {maximum} uL")
    return float(value)


def serial_dilution(steps=8, factor=2, final_volume=80, row="A"):
    if isinstance(steps, bool) or not isinstance(steps, int) or not 2 <= steps <= 12:
        raise ValueError("Use 2 to 12 dilution wells")
    if row not in "ABCDEFGH" or len(row) != 1:
        raise ValueError("Choose a row A through H")
    if (
        isinstance(factor, bool)
        or not isinstance(factor, (int, float))
        or not math.isfinite(factor)
        or factor <= 1
    ):
        raise ValueError("Dilution factor must be finite and greater than one")
    final_volume = volume(final_volume)
    transfer = volume(final_volume / (factor - 1))
    first = volume(final_volume + transfer)
    wells = [f"{row}{i}" for i in range(1, steps + 1)]
    lines = [
        HEADER,
        '    plate = protocol.load_labware("corning_96_wellplate_360ul_flat", "1")',
        '    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "2")',
        '    protocol.comment("Load stock in reservoir A1 and diluent in A2. See exported plan for totals plus dead volume.")',
        f'    pipette.transfer({first!r}, reservoir["A1"], plate[{wells[0]!r}], new_tip="always")',
    ]
    for well in wells[1:]:
        lines.append(
            f'    pipette.transfer({final_volume!r}, reservoir["A2"], plate[{well!r}], new_tip="always")'
        )
    for previous, current in zip(wells, wells[1:]):
        lines.append(
            f'    pipette.transfer({transfer!r}, plate[{previous!r}], plate[{current!r}], mix_after=(3, {min(150, first)!r}), new_tip="always")'
        )
    lines.extend(
        [
            "    pipette.pick_up_tip()",
            f"    pipette.aspirate({transfer!r}, plate[{wells[-1]!r}])",
            f'    pipette.dispense({transfer!r}, protocol.fixed_trash["A1"])',
            "    pipette.drop_tip()",
        ]
    )
    plan = dict(
        stock_ul=first,
        diluent_ul=(steps - 1) * final_volume,
        discard_ul=transfer,
        final_well_volumes=[final_volume] * steps,
        concentration_fractions=[factor ** (-i) for i in range(steps)],
        wells=wells,
        tips=2 * steps,
        transfer_ul=transfer,
        deck={"1": "empty assay plate", "2": "reservoir A1 stock, A2 diluent", "3": "300 uL tip rack"},
        warning="Add reservoir dead volume and verify liquid heights, labware, mixing and calibration on hardware.",
    )
    return "\n".join(lines) + "\n", plan


def plate_transfer(moves, source_volumes):
    if not 1 <= len(moves) <= 96:
        raise ValueError("Use between 1 and 96 transfers with one fresh tip each")
    remaining = {well_name(k): volume(v, 0) for k, v in source_volumes.items()}
    if len(remaining) != len(source_volumes):
        raise ValueError("Duplicate normalized source wells")
    destination = {}
    normalized = []
    for move in moves:
        src, dst = well_name(move["source"]), well_name(move["destination"])
        amount = volume(move["volume"])
        if src not in remaining or remaining[src] - amount < 20:
            raise ValueError(f"Source {src} needs at least 20 uL left after transfers")
        remaining[src] -= amount
        destination[dst] = destination.get(dst, 0) + amount
        if destination[dst] > 200:
            raise ValueError(f"Destination {dst} exceeds conservative 200 uL working volume")
        normalized.append((src, dst, amount))
    lines = [
        HEADER,
        '    source = protocol.load_labware("corning_96_wellplate_360ul_flat", "1")',
        '    destination = protocol.load_labware("corning_96_wellplate_360ul_flat", "2")',
        '    protocol.comment("Destination plate must be empty; load the source volumes from the plan.")',
    ]
    for src, dst, amount in normalized:
        lines.append(
            f'    pipette.transfer({amount!r}, source[{src!r}], destination[{dst!r}], new_tip="always")'
        )
    plan = dict(
        source_remaining_ul=remaining,
        destination_ul=destination,
        tips=len(moves),
        deck={
            "1": "source plate with declared volumes",
            "2": "empty destination plate",
            "3": "300 uL tip rack",
        },
        warning="20 uL residual is a planning bound, not a measured dead volume. Verify on hardware.",
    )
    return "\n".join(lines) + "\n", plan
