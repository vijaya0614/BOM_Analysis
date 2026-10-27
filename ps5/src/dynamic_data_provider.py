import re
from typing import Dict, Any, Optional

def classify_mpn_taxonomy(mpn: str) -> Dict[str, Any]:
    """
    Dynamically analyzes electronics MPN taxonomy and applies category rules 
    to synthesize realistic supply chain data when explicit CSV records are absent.
    """
    if not mpn:
        return {
            "category": "Unknown Placeholder",
            "lifecycle_status": "NRND",
            "lead_time_weeks": 26,
            "stock": 0,
            "has_second_source": False,
            "criticality": "High",
            "unit_cost_usd": 5.00,
            "confidence_score": 0.20,
            "taxonomy_reason": "Unassigned TBD component placeholder"
        }
        
    mpn_upper = mpn.strip().upper()
    
    # 1. Known Legacy / EOL / Obsolete Patterns
    if any(p in mpn_upper for p in ["REED-SW", "MPU9250", "L298N", "TSL2561", "TPS61090"]):
        return {
            "category": "Legacy / EOL Component",
            "lifecycle_status": "Obsolete",
            "lead_time_weeks": 48,
            "stock": 0,
            "has_second_source": False,
            "criticality": "High",
            "unit_cost_usd": 4.50,
            "confidence_score": 0.95,
            "taxonomy_reason": "Matched EOL/Obsolete component taxonomy"
        }

    if any(p in mpn_upper for p in ["ATTINY85", "STM32F103", "ESP8266", "BUZZER-5V", "CP2102"]):
        return {
            "category": "NRND Legacy Microcontroller/IC",
            "lifecycle_status": "NRND",
            "lead_time_weeks": 26,
            "stock": 450,
            "has_second_source": False,
            "criticality": "High",
            "unit_cost_usd": 2.80,
            "confidence_score": 0.90,
            "taxonomy_reason": "Matched NRND (Not Recommended for New Designs) series"
        }

    # 2. Microcontrollers & Processors
    if re.search(r"^(STM32|ESP32|ATMEGA|NRF52|RP2040|SAMD|PIC16|PIC18|MSP430|IMX|AM335)", mpn_upper):
        return {
            "category": "Microcontroller / SoC",
            "lifecycle_status": "Active",
            "lead_time_weeks": 16,
            "stock": 8500,
            "has_second_source": False,
            "criticality": "High",
            "unit_cost_usd": 3.50,
            "confidence_score": 0.85,
            "taxonomy_reason": "Inferred from MCU/SoC series prefix (single-sourced, high criticality)"
        }

    # 3. Sensors & MEMS
    if re.search(r"^(DHT|MPU|BME|BMP|VL53|HC-SR|ADXL|TCS|TSL|MQ-|MAX30|SGP|LIS3D)", mpn_upper):
        return {
            "category": "Sensor / MEMS Module",
            "lifecycle_status": "Active",
            "lead_time_weeks": 10,
            "stock": 15000,
            "has_second_source": "DHT" in mpn_upper or "BMP" in mpn_upper,
            "criticality": "Medium",
            "unit_cost_usd": 2.20,
            "confidence_score": 0.85,
            "taxonomy_reason": "Inferred from Sensor/MEMS series prefix"
        }

    # 4. Power Management & Voltage Regulators
    if re.search(r"^(LM78|LM317|AMS1117|TP4056|MP2307|TPS|XL6009|MT3608|SY808|L78|AP2112)", mpn_upper):
        return {
            "category": "Power IC / Voltage Regulator",
            "lifecycle_status": "Active",
            "lead_time_weeks": 4,
            "stock": 120000,
            "has_second_source": True,
            "criticality": "Low",
            "unit_cost_usd": 0.45,
            "confidence_score": 0.90,
            "taxonomy_reason": "Inferred from Power IC family (multi-sourced commodity regulator)"
        }

    # 5. Interface, Driver & Logic ICs
    if re.search(r"^(ULN2003|DRV88|CH340|FT232|CP210|MAX485|PCA9685|PCF857|CD40|74HC|NE555|LM358|LM393)", mpn_upper):
        is_single = "FT232" in mpn_upper or "CP210" in mpn_upper
        return {
            "category": "Interface / Logic IC",
            "lifecycle_status": "Active",
            "lead_time_weeks": 6,
            "stock": 65000,
            "has_second_source": not is_single,
            "criticality": "High" if is_single else "Low",
            "unit_cost_usd": 0.85,
            "confidence_score": 0.85,
            "taxonomy_reason": "Inferred from Interface/Logic IC family"
        }

    # 6. Standard Passives & Diodes/MOSFETs
    if re.search(r"^(RES-|CAP-|IND-|LED-|1N4007|1N4148|2N2222|2N3904|BC547|IRFZ|AO3400|2N7000|SS14|BAT54)", mpn_upper):
        return {
            "category": "Passive / Discrete Semiconductor",
            "lifecycle_status": "Active",
            "lead_time_weeks": 2,
            "stock": 500000,
            "has_second_source": True,
            "criticality": "Low",
            "unit_cost_usd": 0.05,
            "confidence_score": 0.95,
            "taxonomy_reason": "Inferred from Standard Passive/Discrete component taxonomy (multi-sourced, high stock)"
        }

    # 7. Connectors & Displays
    if re.search(r"^(OLED|LCD|USB|HEADER|TERM|XT60|SW-|TACT-|RELAY-)", mpn_upper):
        return {
            "category": "Electromechanical / Connector / Display",
            "lifecycle_status": "Active",
            "lead_time_weeks": 4,
            "stock": 45000,
            "has_second_source": True,
            "criticality": "Low",
            "unit_cost_usd": 1.20,
            "confidence_score": 0.85,
            "taxonomy_reason": "Inferred from Connector/Display taxonomy"
        }

    # Default fallback for unlisted arbitrary MPN
    return {
        "category": "General Component",
        "lifecycle_status": "Active",
        "lead_time_weeks": 6,
        "stock": 25000,
        "has_second_source": True,
        "criticality": "Medium",
        "unit_cost_usd": 1.00,
        "confidence_score": 0.70,
        "taxonomy_reason": "Synthesized default profile based on general component taxonomy"
    }
