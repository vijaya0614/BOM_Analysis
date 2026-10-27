"""Generate a Faker-backed synthetic BOM CSV that validates against BomComponent."""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, List, Sequence

from faker import Faker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas import BomComponent, Criticality, LifecycleStatus

CSV_FIELDS = [
    "part_number",
    "category",
    "package",
    "criticality",
    "qty",
    "unit_cost",
    "second_source",
    "lead_time_weeks",
    "lifecycle_status",
    "distributor_stock",
]

DEFAULT_COUNT = 500
DEFAULT_SEED = 42
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "synthetic_bom_components.csv"

# Category mix, packages, and cost/qty envelopes typical of electronics BOMs.
CATEGORY_PROFILES = {
    "Resistor": {
        "packages": ["0402", "0603", "0805", "1206"],
        "prefixes": ["RC", "ERJ", "CRCW"],
        "unit_cost": (0.002, 0.12),
        "qty": (10, 80),
        "criticality_weights": [0.70, 0.25, 0.05],
    },
    "Capacitor": {
        "packages": ["0402", "0603", "0805", "1206", "1210", "Electrolytic"],
        "prefixes": ["GRM", "C1608", "CL21"],
        "unit_cost": (0.01, 0.85),
        "qty": (4, 40),
        "criticality_weights": [0.55, 0.35, 0.10],
    },
    "Inductor": {
        "packages": ["0603", "0805", "1210", "SMD-Power"],
        "prefixes": ["LQH", "SRF", "NR"],
        "unit_cost": (0.08, 1.80),
        "qty": (1, 8),
        "criticality_weights": [0.40, 0.45, 0.15],
    },
    "MOSFET": {
        "packages": ["SOT-23", "SOT-223", "TO-220", "DPAK", "D2PAK"],
        "prefixes": ["IRF", "AO", "SI", "BSS"],
        "unit_cost": (0.12, 4.50),
        "qty": (1, 6),
        "criticality_weights": [0.15, 0.40, 0.45],
    },
    "Regulator": {
        "packages": ["SOT-23", "SOT-223", "TO-220", "TO-263", "QFN-16"],
        "prefixes": ["AMS", "LM", "TPS", "MP"],
        "unit_cost": (0.15, 3.80),
        "qty": (1, 4),
        "criticality_weights": [0.10, 0.40, 0.50],
    },
    "Microcontroller": {
        "packages": ["QFN-32", "LQFP-48", "LQFP-64", "module", "BGA-100"],
        "prefixes": ["STM32", "ESP32", "ATSAMD", "RP", "nRF"],
        "unit_cost": (0.90, 14.50),
        "qty": (1, 2),
        "criticality_weights": [0.05, 0.25, 0.70],
    },
    "Sensor": {
        "packages": ["LGA-8", "LGA-14", "SOT-23", "module"],
        "prefixes": ["BME", "MPU", "VL53", "TMP", "INA"],
        "unit_cost": (0.45, 8.50),
        "qty": (1, 3),
        "criticality_weights": [0.20, 0.50, 0.30],
    },
    "Connector": {
        "packages": ["Through-Hole", "SMD", "USB-C", "JST-PH"],
        "prefixes": ["CONN", "USB", "JST", "HDR"],
        "unit_cost": (0.08, 2.40),
        "qty": (1, 12),
        "criticality_weights": [0.45, 0.40, 0.15],
    },
    "Crystal": {
        "packages": ["3225", "5032", "HC-49"],
        "prefixes": ["XTAL", "ABM", "FXO"],
        "unit_cost": (0.12, 1.60),
        "qty": (1, 3),
        "criticality_weights": [0.25, 0.50, 0.25],
    },
    "LED": {
        "packages": ["0603", "0805", "1206", "5mm"],
        "prefixes": ["LED", "LTST", "WP"],
        "unit_cost": (0.02, 0.45),
        "qty": (2, 20),
        "criticality_weights": [0.75, 0.20, 0.05],
    },
}

CATEGORY_WEIGHTS = {
    "Resistor": 0.18,
    "Capacitor": 0.16,
    "Inductor": 0.06,
    "MOSFET": 0.10,
    "Regulator": 0.10,
    "Microcontroller": 0.08,
    "Sensor": 0.10,
    "Connector": 0.10,
    "Crystal": 0.04,
    "LED": 0.08,
}

LIFECYCLE_SHARE = {
    LifecycleStatus.ACTIVE: 0.70,
    LifecycleStatus.NRND: 0.20,
    LifecycleStatus.OBSOLETE: 0.10,
}


def lifecycle_quota(count: int) -> List[LifecycleStatus]:
    """Exact 70/20/10 split; leftover rows (from rounding) go to Active."""
    n_active = int(round(count * LIFECYCLE_SHARE[LifecycleStatus.ACTIVE]))
    n_nrnd = int(round(count * LIFECYCLE_SHARE[LifecycleStatus.NRND]))
    n_obsolete = count - n_active - n_nrnd
    if n_obsolete < 0:
        n_active += n_obsolete
        n_obsolete = 0
    statuses = (
        [LifecycleStatus.ACTIVE] * n_active
        + [LifecycleStatus.NRND] * n_nrnd
        + [LifecycleStatus.OBSOLETE] * n_obsolete
    )
    return statuses


def _supply_fields(fake: Faker, lifecycle: LifecycleStatus) -> dict:
    if lifecycle is LifecycleStatus.ACTIVE:
        return {
            "lead_time_weeks": fake.random_int(1, 12),
            "distributor_stock": fake.random_int(250, 180_000),
            "second_source": fake.boolean(chance_of_getting_true=72),
        }
    if lifecycle is LifecycleStatus.NRND:
        return {
            "lead_time_weeks": fake.random_int(12, 36),
            "distributor_stock": fake.random_int(0, 2_500),
            "second_source": fake.boolean(chance_of_getting_true=28),
        }
    return {
        "lead_time_weeks": fake.random_int(26, 52),
        "distributor_stock": fake.random_int(0, 40),
        "second_source": fake.boolean(chance_of_getting_true=6),
    }


def _part_number(fake: Faker, prefix: str) -> str:
    suffix = fake.unique.bothify(text="?-####", letters="ABCDEFGHJKLMNPQRSTUVWXYZ")
    return f"{prefix}-{suffix}"


def generate_components(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED) -> List[BomComponent]:
    fake = Faker()
    fake.seed_instance(seed)
    random.seed(seed)

    category_weights = OrderedDict((name, CATEGORY_WEIGHTS[name]) for name in CATEGORY_PROFILES)
    statuses = lifecycle_quota(count)
    random.shuffle(statuses)

    rows: List[BomComponent] = []
    for lifecycle in statuses:
        category = fake.random_element(elements=category_weights)
        profile = CATEGORY_PROFILES[category]
        lo, hi = profile["unit_cost"]
        qty_lo, qty_hi = profile["qty"]
        criticality_weights = OrderedDict(
            zip((item.value for item in Criticality), profile["criticality_weights"])
        )
        payload = {
            "part_number": _part_number(fake, fake.random_element(profile["prefixes"])),
            "category": category,
            "package": fake.random_element(profile["packages"]),
            "criticality": fake.random_element(elements=criticality_weights),
            "qty": fake.random_int(qty_lo, qty_hi),
            "unit_cost": round(fake.pyfloat(min_value=lo, max_value=hi, right_digits=4), 4),
            "lifecycle_status": lifecycle.value,
            **_supply_fields(fake, lifecycle),
        }
        rows.append(BomComponent.model_validate(payload))
    return rows


def write_csv(components: Iterable[BomComponent], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for component in components:
            writer.writerow(component.model_dump(mode="json", include=set(CSV_FIELDS)))
    return output_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a synthetic electronic BOM CSV for MVP ingestion.")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> Path:
    args = parse_args(argv)
    components = generate_components(count=args.count, seed=args.seed)
    path = write_csv(components, args.output)
    counts = {status.value: 0 for status in LifecycleStatus}
    for component in components:
        counts[component.lifecycle_status.value] += 1
    print(f"Wrote {len(components)} Pydantic-validated BOM rows to {path}")
    print(
        "Lifecycle mix: "
        + ", ".join(f"{name}={counts[name]} ({counts[name] / len(components):.0%})" for name in counts)
    )
    return path


if __name__ == "__main__":
    main()
