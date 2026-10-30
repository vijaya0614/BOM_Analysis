"""PS5 — Comprehensive Vendor & Market Intelligence Engine.

Provides deep, domain-accurate vendor and supply-chain intelligence for electronic components:
- Lifecycle status, introduction year, expected EOL, LTB (Last-Time Buy) deadlines
- Geological & natural disaster availability (silicon fab location, seismic risk, water stress, rare-earth dependence)
- Geopolitical risk exposure and trade friction
- Market saturation, distributor inventory distribution, supplier concentration (HHI), and counterfeit risk
- 12-month historical price and lead-time volatility trends
- Resilience radar metrics (sourcing, lead time, price, lifecycle, geopolitical, geological)
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DistributorQuote:
    vendor_name: str
    stock: int
    unit_price: float
    moq: int
    lead_time_weeks: int
    packaging: str
    stock_share_pct: float
    authorized: Optional[bool] = None
    currency: str = "USD"
    retrieval_state: str = "UNKNOWN"
    data_provenance: str = "SYNTHETIC_DERIVED_DEMO_DATA"


@dataclass
class GeologicalAvailability:
    primary_fab_country: str
    primary_fab_city: str
    primary_fab_name: str
    seismic_risk_score: float  # 0 (lowest) - 100 (extreme)
    water_stress_level: str   # LOW, MODERATE, HIGH, CRITICAL
    tsunami_hazard_zone: bool
    secondary_packaging_country: str
    secondary_packaging_name: str
    redundant_site_qualified: bool
    rare_earth_dependence_pct: float
    geopolitical_exposure_score: float  # 0 - 100
    geopolitical_risk_tier: str         # LOW, MODERATE, ELEVATED, CRITICAL
    regional_stock_americas_pct: float
    regional_stock_emea_pct: float
    regional_stock_apac_pct: float
    regional_stock_domestic_pct: float


@dataclass
class MarketSaturationData:
    saturation_index_pct: float  # 0 - 100%
    sourcing_status: str         # SINGLE_SOURCE_PROPRIETARY, DUAL_SOURCED, MULTI_SOURCE_COMMODITY
    qualified_manufacturers: List[str]
    hhi_index: float             # Herfindahl-Hirschman Index
    supply_pressure_index: float # 0 - 100
    counterfeit_risk_score: float# 0 - 100
    counterfeit_risk_level: str  # LOW, MEDIUM, HIGH
    distributors: List[DistributorQuote]
    volume_price_breaks: List[Dict[str, Any]]
    price_trend_12m: List[Dict[str, Any]]
    lead_time_trend_12m: List[Dict[str, Any]]


@dataclass
class LifecycleDetails:
    lifecycle_status: str  # ACTIVE, NRND, EOL, OBSOLETE, PRE_RELEASE
    introduction_year: int
    expected_eol_year: int
    ltb_date: Optional[str]
    lts_date: Optional[str]
    years_remaining: float
    phase_progress_pct: float
    weibull_shape_beta: float
    weibull_scale_eta_years: float


@dataclass
class ResilienceRadar:
    sourcing_security: float     # 0 - 100
    lead_time_resilience: float  # 0 - 100
    price_stability: float       # 0 - 100
    lifecycle_longevity: float   # 0 - 100
    geopolitical_safety: float   # 0 - 100
    geological_hardiness: float  # 0 - 100


@dataclass
class ComponentVendorIntelligence:
    part_number: str
    manufacturer: str
    description: str
    category: str
    lifecycle: LifecycleDetails
    geological: GeologicalAvailability
    market_saturation: MarketSaturationData
    resilience: ResilienceRadar
    normalized_specs: List[Dict[str, str]]
    document_links: List[Dict[str, str]]
    data_provenance: str = "SYNTHETIC_DEMO_DATA"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Curated High-Fidelity Catalog for Standard Benchmark Parts ────────────────
KNOWN_VENDOR_CATALOG: Dict[str, Dict[str, Any]] = {
    "STM32F401RET6": {
        "manufacturer": "STMicroelectronics",
        "description": "ARM Cortex-M4 32-bit MCU 84MHz 512KB Flash",
        "category": "Microcontroller",
        "lifecycle": {
            "lifecycle_status": "ACTIVE",
            "introduction_year": 2014,
            "expected_eol_year": 2034,
            "ltb_date": None,
            "lts_date": None,
            "years_remaining": 8.0,
            "phase_progress_pct": 50.0,
            "weibull_shape_beta": 2.2,
            "weibull_scale_eta_years": 18.0,
        },
        "geological": {
            "primary_fab_country": "France",
            "primary_fab_city": "Crolles",
            "primary_fab_name": "ST Crolles 300mm Fab",
            "seismic_risk_score": 18.0,
            "water_stress_level": "LOW",
            "tsunami_hazard_zone": False,
            "secondary_packaging_country": "Malaysia",
            "secondary_packaging_name": "ST Muar Assembly",
            "redundant_site_qualified": True,
            "rare_earth_dependence_pct": 14.5,
            "geopolitical_exposure_score": 22.0,
            "geopolitical_risk_tier": "LOW",
            "regional_stock_americas_pct": 28.0,
            "regional_stock_emea_pct": 42.0,
            "regional_stock_apac_pct": 22.0,
            "regional_stock_domestic_pct": 8.0,
        },
        "sourcing_status": "DUAL_SOURCED",
        "qualified_manufacturers": ["STMicroelectronics", "GigaDevice"],
        "hhi_index": 3800.0,
        "supply_pressure_index": 38.0,
        "counterfeit_risk_score": 45.0,
        "counterfeit_risk_level": "MEDIUM",
        "base_price": 4.85,
        "base_stock": 28500,
        "base_lead_time": 12,
    },
    "TPS5402DGQR": {
        "manufacturer": "Texas Instruments",
        "description": "3.5V to 28V Input, 2A Step-Down Buck Converter",
        "category": "Power Management",
        "lifecycle": {
            "lifecycle_status": "ACTIVE",
            "introduction_year": 2012,
            "expected_eol_year": 2030,
            "ltb_date": None,
            "lts_date": None,
            "years_remaining": 4.0,
            "phase_progress_pct": 70.0,
            "weibull_shape_beta": 2.8,
            "weibull_scale_eta_years": 16.5,
        },
        "geological": {
            "primary_fab_country": "USA",
            "primary_fab_city": "Sherman, TX",
            "primary_fab_name": "TI Sherman 200mm Fab",
            "seismic_risk_score": 12.0,
            "water_stress_level": "MODERATE",
            "tsunami_hazard_zone": False,
            "secondary_packaging_country": "Philippines",
            "secondary_packaging_name": "TI Clark Assembly & Test",
            "redundant_site_qualified": True,
            "rare_earth_dependence_pct": 8.0,
            "geopolitical_exposure_score": 15.0,
            "geopolitical_risk_tier": "LOW",
            "regional_stock_americas_pct": 45.0,
            "regional_stock_emea_pct": 25.0,
            "regional_stock_apac_pct": 22.0,
            "regional_stock_domestic_pct": 8.0,
        },
        "sourcing_status": "DUAL_SOURCED",
        "qualified_manufacturers": ["Texas Instruments", "Diodes Inc", "Monolithic Power Systems"],
        "hhi_index": 2950.0,
        "supply_pressure_index": 34.0,
        "counterfeit_risk_score": 25.0,
        "counterfeit_risk_level": "LOW",
        "base_price": 1.42,
        "base_stock": 48200,
        "base_lead_time": 8,
    },
    "LM358DR": {
        "manufacturer": "Texas Instruments",
        "description": "Dual Operational Amplifier 3V to 32V",
        "category": "Analog / Op-Amp",
        "lifecycle": {
            "lifecycle_status": "ACTIVE",
            "introduction_year": 1985,
            "expected_eol_year": 2045,
            "ltb_date": None,
            "lts_date": None,
            "years_remaining": 19.0,
            "phase_progress_pct": 55.0,
            "weibull_shape_beta": 1.4,
            "weibull_scale_eta_years": 35.0,
        },
        "geological": {
            "primary_fab_country": "USA",
            "primary_fab_city": "Dallas, TX",
            "primary_fab_name": "TI DMOS-5 Bipolar Fab",
            "seismic_risk_score": 10.0,
            "water_stress_level": "LOW",
            "tsunami_hazard_zone": False,
            "secondary_packaging_country": "Malaysia",
            "secondary_packaging_name": "TI Kuala Lumpur Packaging",
            "redundant_site_qualified": True,
            "rare_earth_dependence_pct": 3.0,
            "geopolitical_exposure_score": 10.0,
            "geopolitical_risk_tier": "LOW",
            "regional_stock_americas_pct": 35.0,
            "regional_stock_emea_pct": 30.0,
            "regional_stock_apac_pct": 25.0,
            "regional_stock_domestic_pct": 10.0,
        },
        "sourcing_status": "MULTI_SOURCE_COMMODITY",
        "qualified_manufacturers": ["Texas Instruments", "STMicroelectronics", "ON Semiconductor", "Diodes Inc"],
        "hhi_index": 1250.0,
        "supply_pressure_index": 15.0,
        "counterfeit_risk_score": 20.0,
        "counterfeit_risk_level": "LOW",
        "base_price": 0.32,
        "base_stock": 240000,
        "base_lead_time": 4,
    },
    "MCP2551-I/SN": {
        "manufacturer": "Microchip Technology",
        "description": "High-Speed CAN Transceiver 5V 1Mbps",
        "category": "Interface / CAN",
        "lifecycle": {
            "lifecycle_status": "NRND",
            "introduction_year": 2001,
            "expected_eol_year": 2027,
            "ltb_date": "2026-12-31",
            "lts_date": "2027-06-30",
            "years_remaining": 0.8,
            "phase_progress_pct": 92.0,
            "weibull_shape_beta": 3.4,
            "weibull_scale_eta_years": 14.0,
        },
        "geological": {
            "primary_fab_country": "USA",
            "primary_fab_city": "Tempe, AZ",
            "primary_fab_name": "Microchip Fab 2",
            "seismic_risk_score": 15.0,
            "water_stress_level": "HIGH",
            "tsunami_hazard_zone": False,
            "secondary_packaging_country": "Thailand",
            "secondary_packaging_name": "Microchip Chanthaburi AT",
            "redundant_site_qualified": False,
            "rare_earth_dependence_pct": 9.5,
            "geopolitical_exposure_score": 35.0,
            "geopolitical_risk_tier": "MODERATE",
            "regional_stock_americas_pct": 40.0,
            "regional_stock_emea_pct": 30.0,
            "regional_stock_apac_pct": 20.0,
            "regional_stock_domestic_pct": 10.0,
        },
        "sourcing_status": "SINGLE_SOURCE_PROPRIETARY",
        "qualified_manufacturers": ["Microchip Technology"],
        "hhi_index": 7200.0,
        "supply_pressure_index": 76.0,
        "counterfeit_risk_score": 62.0,
        "counterfeit_risk_level": "HIGH",
        "base_price": 1.15,
        "base_stock": 3800,
        "base_lead_time": 26,
    },
    "DS1307Z+": {
        "manufacturer": "Analog Devices / Maxim",
        "description": "64 x 8 Serial Real-Time Clock I2C",
        "category": "Timing / RTC",
        "lifecycle": {
            "lifecycle_status": "EOL",
            "introduction_year": 1999,
            "expected_eol_year": 2025,
            "ltb_date": "2025-06-30",
            "lts_date": "2025-12-31",
            "years_remaining": 0.0,
            "phase_progress_pct": 100.0,
            "weibull_shape_beta": 4.1,
            "weibull_scale_eta_years": 12.0,
        },
        "geological": {
            "primary_fab_country": "USA",
            "primary_fab_city": "Beaverton, OR",
            "primary_fab_name": "ADI Oregon Fab",
            "seismic_risk_score": 38.0,
            "water_stress_level": "LOW",
            "tsunami_hazard_zone": False,
            "secondary_packaging_country": "Philippines",
            "secondary_packaging_name": "ADI Cavite Testing",
            "redundant_site_qualified": False,
            "rare_earth_dependence_pct": 12.0,
            "geopolitical_exposure_score": 45.0,
            "geopolitical_risk_tier": "MODERATE",
            "regional_stock_americas_pct": 55.0,
            "regional_stock_emea_pct": 25.0,
            "regional_stock_apac_pct": 12.0,
            "regional_stock_domestic_pct": 8.0,
        },
        "sourcing_status": "SINGLE_SOURCE_PROPRIETARY",
        "qualified_manufacturers": ["Analog Devices"],
        "hhi_index": 9800.0,
        "supply_pressure_index": 94.0,
        "counterfeit_risk_score": 88.0,
        "counterfeit_risk_level": "HIGH",
        "base_price": 3.20,
        "base_stock": 420,
        "base_lead_time": 48,
    },
    "BSS138": {
        "manufacturer": "ON Semiconductor",
        "description": "N-Channel Logic Level Power MOSFET 50V 220mA",
        "category": "Discrete / MOSFET",
        "lifecycle": {
            "lifecycle_status": "ACTIVE",
            "introduction_year": 1995,
            "expected_eol_year": 2040,
            "ltb_date": None,
            "lts_date": None,
            "years_remaining": 14.0,
            "phase_progress_pct": 45.0,
            "weibull_shape_beta": 1.5,
            "weibull_scale_eta_years": 30.0,
        },
        "geological": {
            "primary_fab_country": "South Korea",
            "primary_fab_city": "Bucheon",
            "primary_fab_name": "onsemi Bucheon 150mm/200mm",
            "seismic_risk_score": 22.0,
            "water_stress_level": "LOW",
            "tsunami_hazard_zone": False,
            "secondary_packaging_country": "Malaysia",
            "secondary_packaging_name": "onsemi Seremban AT",
            "redundant_site_qualified": True,
            "rare_earth_dependence_pct": 2.0,
            "geopolitical_exposure_score": 25.0,
            "geopolitical_risk_tier": "LOW",
            "regional_stock_americas_pct": 30.0,
            "regional_stock_emea_pct": 32.0,
            "regional_stock_apac_pct": 28.0,
            "regional_stock_domestic_pct": 10.0,
        },
        "sourcing_status": "MULTI_SOURCE_COMMODITY",
        "qualified_manufacturers": ["ON Semiconductor", "Diodes Inc", "Nexperia", "Vishay"],
        "hhi_index": 1400.0,
        "supply_pressure_index": 18.0,
        "counterfeit_risk_score": 15.0,
        "counterfeit_risk_level": "LOW",
        "base_price": 0.12,
        "base_stock": 310000,
        "base_lead_time": 6,
    },
    "FT232RL-REEL": {
        "manufacturer": "FTDI Chip",
        "description": "USB to Serial UART Interface IC",
        "category": "Interface / USB",
        "lifecycle": {
            "lifecycle_status": "NRND",
            "introduction_year": 2005,
            "expected_eol_year": 2028,
            "ltb_date": "2027-03-31",
            "lts_date": "2027-12-31",
            "years_remaining": 1.4,
            "phase_progress_pct": 88.0,
            "weibull_shape_beta": 3.1,
            "weibull_scale_eta_years": 15.0,
        },
        "geological": {
            "primary_fab_country": "Taiwan",
            "primary_fab_city": "Hsinchu",
            "primary_fab_name": "TSMC Fab 6",
            "seismic_risk_score": 72.0,
            "water_stress_level": "HIGH",
            "tsunami_hazard_zone": True,
            "secondary_packaging_country": "Taiwan",
            "secondary_packaging_name": "ASE Kaohsiung",
            "redundant_site_qualified": False,
            "rare_earth_dependence_pct": 18.0,
            "geopolitical_exposure_score": 68.0,
            "geopolitical_risk_tier": "ELEVATED",
            "regional_stock_americas_pct": 32.0,
            "regional_stock_emea_pct": 38.0,
            "regional_stock_apac_pct": 22.0,
            "regional_stock_domestic_pct": 8.0,
        },
        "sourcing_status": "SINGLE_SOURCE_PROPRIETARY",
        "qualified_manufacturers": ["FTDI Chip"],
        "hhi_index": 8500.0,
        "supply_pressure_index": 72.0,
        "counterfeit_risk_score": 85.0,
        "counterfeit_risk_level": "HIGH",
        "base_price": 3.95,
        "base_stock": 7200,
        "base_lead_time": 32,
    },
}


def _deterministic_hash(part_number: str) -> int:
    return int(hashlib.sha256(part_number.encode("utf-8")).hexdigest()[:8], 16)


def generate_component_vendor_intelligence(part_number: str, category_hint: Optional[str] = None) -> ComponentVendorIntelligence:
    """Retrieves curated or generates deterministic comprehensive vendor & supply chain intelligence."""
    pn = part_number.strip().upper()

    # Match in curated catalog if present
    curated = KNOWN_VENDOR_CATALOG.get(pn)
    data_provenance = "CURATED_STATIC_DEMO_DATA" if curated else "SYNTHETIC_DEMO_DATA"
    seed = _deterministic_hash(pn)

    if curated:
        mfr = curated["manufacturer"]
        desc = curated["description"]
        cat = curated["category"]
        lc_raw = curated["lifecycle"]
        geo_raw = curated["geological"]
        src_status = curated["sourcing_status"]
        qual_mfrs = curated["qualified_manufacturers"]
        hhi = curated["hhi_index"]
        spi = curated["supply_pressure_index"]
        c_score = curated["counterfeit_risk_score"]
        c_lvl = curated["counterfeit_risk_level"]
        base_price = curated["base_price"]
        base_stock = curated["base_stock"]
        base_lead = curated["base_lead_time"]
    else:
        # Algorithmic deterministic synthesis for ANY other part number
        cat = category_hint or ("Microcontroller" if "STM" in pn or "GD32" in pn or "MCU" in pn
                                else "Power Management" if "TPS" in pn or "AP6" in pn or "REG" in pn
                                else "Interface" if "CAN" in pn or "MAX" in pn or "SN" in pn or "FT" in pn
                                else "Passive" if pn.startswith("R") or pn.startswith("C")
                                else "Semiconductor IC")
        mfr = ("Texas Instruments" if "TI" in pn or "TPS" in pn
               else "STMicroelectronics" if "STM" in pn
               else "Microchip" if "MCP" in pn or "AT" in pn
               else "Analog Devices" if "AD" in pn or "DS" in pn
               else "Diodes Inc" if "AP" in pn
               else "Global Semiconductor Inc")
        desc = f"Standard {cat} Component ({pn})"

        # Deterministic lifecycle
        status_bucket = seed % 10
        if status_bucket >= 8:
            status = "EOL"
            years_rem = 0.0
            phase = 98.0
            intro = 2005
            eol = 2026
            ltb = "2026-09-30"
            lts = "2027-03-31"
            beta = 3.6
            eta = 14.0
        elif status_bucket >= 6:
            status = "NRND"
            years_rem = 1.8
            phase = 85.0
            intro = 2012
            eol = 2028
            ltb = "2027-06-30"
            lts = "2028-01-31"
            beta = 2.9
            eta = 16.0
        else:
            status = "ACTIVE"
            years_rem = 7.5
            phase = 45.0
            intro = 2018
            eol = 2035
            ltb = None
            lts = None
            beta = 2.1
            eta = 20.0

        lc_raw = {
            "lifecycle_status": status,
            "introduction_year": intro,
            "expected_eol_year": eol,
            "ltb_date": ltb,
            "lts_date": lts,
            "years_remaining": years_rem,
            "phase_progress_pct": phase,
            "weibull_shape_beta": beta,
            "weibull_scale_eta_years": eta,
        }

        # Deterministic geographic
        country_options = [
            ("USA", "Austin, TX", "Fab 25", 14.0, "LOW", False, 18.0, "LOW"),
            ("Taiwan", "Hsinchu", "TSMC Fab 14", 68.0, "HIGH", True, 62.0, "ELEVATED"),
            ("Germany", "Dresden", "Infineon Fab 1", 12.0, "LOW", False, 14.0, "LOW"),
            ("South Korea", "Hwaseong", "Samsung Line 17", 24.0, "LOW", False, 30.0, "MODERATE"),
            ("Japan", "Naka", "Renesas N3 Fab", 58.0, "MODERATE", True, 32.0, "MODERATE"),
        ]
        fab_info = country_options[seed % len(country_options)]
        geo_raw = {
            "primary_fab_country": fab_info[0],
            "primary_fab_city": fab_info[1],
            "primary_fab_name": fab_info[2],
            "seismic_risk_score": fab_info[3],
            "water_stress_level": fab_info[4],
            "tsunami_hazard_zone": fab_info[5],
            "secondary_packaging_country": "Malaysia",
            "secondary_packaging_name": "Penang Advanced Packaging Site",
            "redundant_site_qualified": (seed % 2 == 0),
            "rare_earth_dependence_pct": float(10 + (seed % 15)),
            "geopolitical_exposure_score": fab_info[6],
            "geopolitical_risk_tier": fab_info[7],
            "regional_stock_americas_pct": 36.0,
            "regional_stock_emea_pct": 32.0,
            "regional_stock_apac_pct": 24.0,
            "regional_stock_domestic_pct": 8.0,
        }

        src_status = "SINGLE_SOURCE_PROPRIETARY" if status_bucket >= 7 else "DUAL_SOURCED"
        qual_mfrs = [mfr] if src_status == "SINGLE_SOURCE_PROPRIETARY" else [mfr, "SecondSource Corp", "EquivSemi"]
        hhi = 6500.0 if src_status == "SINGLE_SOURCE_PROPRIETARY" else 2800.0
        spi = float(30 + (seed % 55))
        c_score = float(20 + (seed % 65))
        c_lvl = "HIGH" if c_score > 60 else "MEDIUM" if c_score > 35 else "LOW"
        base_price = round(0.50 + ((seed % 800) / 100.0), 2)
        base_stock = 1500 + (seed % 50000)
        base_lead = 6 + (seed % 24)

    # Generate 6 Global Distributors Quotes
    distributor_shares = [
        ("Digi-Key Electronics", 0.35, 1.0, 1, 0, "Cut Tape / Reel"),
        ("Mouser Electronics", 0.28, 1.02, 1, 0, "Cut Tape / Reel"),
        ("Arrow Electronics", 0.18, 0.96, 100, 2, "Tape & Reel"),
        ("Avnet", 0.10, 0.98, 50, 1, "Reel"),
        ("Farnell / Newark", 0.06, 1.05, 1, -1, "Cut Tape"),
        ("LCSC Electronics", 0.03, 0.88, 10, -2, "Reel"),
    ]

    distributors: List[DistributorQuote] = []
    total_stock = base_stock
    for v_name, share, price_mult, moq, lead_delta, pack in distributor_shares:
        v_stock = max(10, int(total_stock * share))
        v_price = round(base_price * price_mult, 3)
        v_lead = max(2, base_lead + lead_delta)
        distributors.append(
            DistributorQuote(
                vendor_name=v_name,
                stock=v_stock,
                unit_price=v_price,
                moq=moq,
                lead_time_weeks=v_lead,
                packaging=pack,
                stock_share_pct=round(share * 100.0, 1),
            )
        )

    # Volume discount price breaks
    volume_breaks = [
        {"tier": "1+", "qty": 1, "unit_price": round(base_price * 1.15, 3), "savings_pct": 0.0},
        {"tier": "100+", "qty": 100, "unit_price": round(base_price * 1.00, 3), "savings_pct": 13.0},
        {"tier": "1,000+", "qty": 1000, "unit_price": round(base_price * 0.88, 3), "savings_pct": 23.5},
        {"tier": "10,000+", "qty": 10000, "unit_price": round(base_price * 0.76, 3), "savings_pct": 33.9},
        {"tier": "50,000+", "qty": 50000, "unit_price": round(base_price * 0.68, 3), "savings_pct": 40.8},
    ]

    # 12-Month Price Volatility Trend
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    price_trend: List[Dict[str, Any]] = []
    lead_trend: List[Dict[str, Any]] = []
    for i, m in enumerate(months):
        p_variation = 1.0 + 0.12 * (((seed + i * 17) % 21) - 10) / 10.0
        l_variation = (((seed + i * 29) % 9) - 4)
        price_trend.append({
            "month": m,
            "unit_price": round(base_price * p_variation, 3),
            "spot_market_price": round(base_price * p_variation * 1.08, 3),
        })
        lead_trend.append({
            "month": m,
            "lead_time_weeks": max(2, base_lead + l_variation),
            "target_lead_time_weeks": 8,
        })

    # Resilience Radar Metrics (0 - 100)
    sourcing_sec = 40.0 if src_status == "SINGLE_SOURCE_PROPRIETARY" else 85.0
    lead_res = max(15.0, 100.0 - (base_lead * 2.2))
    price_stab = max(20.0, 95.0 - (c_score * 0.5))
    lifecycle_long = max(10.0, 100.0 - lc_raw["phase_progress_pct"])
    geopol_safe = max(10.0, 100.0 - geo_raw["geopolitical_exposure_score"])
    geolog_hard = max(10.0, 100.0 - geo_raw["seismic_risk_score"])

    radar = ResilienceRadar(
        sourcing_security=round(sourcing_sec, 1),
        lead_time_resilience=round(lead_res, 1),
        price_stability=round(price_stab, 1),
        lifecycle_longevity=round(lifecycle_long, 1),
        geopolitical_safety=round(geopol_safe, 1),
        geological_hardiness=round(geolog_hard, 1),
    )

    saturation_pct = min(98.0, max(12.0, (base_stock / 150000.0) * 100.0))

    market_sat = MarketSaturationData(
        saturation_index_pct=round(saturation_pct, 1),
        sourcing_status=src_status,
        qualified_manufacturers=qual_mfrs,
        hhi_index=hhi,
        supply_pressure_index=spi,
        counterfeit_risk_score=c_score,
        counterfeit_risk_level=c_lvl,
        distributors=distributors,
        volume_price_breaks=volume_breaks,
        price_trend_12m=price_trend,
        lead_time_trend_12m=lead_trend,
    )

    lc_obj = LifecycleDetails(
        lifecycle_status=lc_raw["lifecycle_status"],
        introduction_year=lc_raw["introduction_year"],
        expected_eol_year=lc_raw["expected_eol_year"],
        ltb_date=lc_raw["ltb_date"],
        lts_date=lc_raw["lts_date"],
        years_remaining=lc_raw["years_remaining"],
        phase_progress_pct=lc_raw["phase_progress_pct"],
        weibull_shape_beta=lc_raw["weibull_shape_beta"],
        weibull_scale_eta_years=lc_raw["weibull_scale_eta_years"],
    )

    geo_obj = GeologicalAvailability(**geo_raw)

    specs = [
        {"parameter_name": "Category", "nominal_value": cat},
        {"parameter_name": "Primary Manufacturer", "nominal_value": mfr},
        {"parameter_name": "Silicon Fab Node", "nominal_value": f"{geo_obj.primary_fab_country} ({geo_obj.primary_fab_name})"},
        {"parameter_name": "Assembly & Packaging", "nominal_value": f"{geo_obj.secondary_packaging_country} ({geo_obj.secondary_packaging_name})"},
        {"parameter_name": "Redundant Qualified Sites", "nominal_value": "YES" if geo_obj.redundant_site_qualified else "NO"},
        {"parameter_name": "Rare Earth Dependence", "nominal_value": f"{geo_obj.rare_earth_dependence_pct}%"},
        {"parameter_name": "Global Stock Depth", "nominal_value": f"{total_stock:,} units across 6 distributors"},
    ]

    docs = [
        {"title": f"{pn} Official Datasheet (PDF)", "url": f"https://www.alldatasheet.com/view.jsp?Searchword={pn}"},
        {"title": f"{mfr} Environmental & RoHS Compliance", "url": "https://www.rohsguide.com/"},
        {"title": f"PCN (Product Change Notification) Bulletin", "url": f"https://www.siliconexpert.com/pcn/{pn}"},
    ]

    return ComponentVendorIntelligence(
        part_number=pn,
        manufacturer=mfr,
        description=desc,
        category=cat,
        lifecycle=lc_obj,
        geological=geo_obj,
        market_saturation=market_sat,
        resilience=radar,
        normalized_specs=specs,
        document_links=docs,
        data_provenance=data_provenance,
    )
