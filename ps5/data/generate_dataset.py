import csv
import os
import random

# Massive Catalog of 200+ realistic electronic part numbers
SERIES_TEMPLATES = [
    # Microcontrollers & Processors
    ("STM32F103C8T6", "NRND", 32, 20, False, "High", 3.50),
    ("STM32F401RCT6", "Active", 16, 4500, True, "High", 4.20),
    ("STM32F411CEU6", "Active", 12, 12500, True, "High", 3.80),
    ("STM32H743ZIT6", "Active", 24, 1200, False, "High", 14.50),
    ("STM32G030K6T6", "Active", 8, 38000, True, "Medium", 1.40),
    ("ESP32-WROOM-32U", "Active", 12, 4200, False, "High", 3.20),
    ("ESP32-S3-WROOM-1", "Active", 8, 18500, False, "High", 3.90),
    ("ESP32-C3-MINI-1", "Active", 6, 45000, False, "Medium", 1.85),
    ("ESP8266-12F", "NRND", 18, 8500, True, "Medium", 1.50),
    ("ATMEL-ATTINY85-20PU", "NRND", 26, 150, False, "High", 1.95),
    ("ATMEL-ATTINY13A-SSU", "Active", 6, 85000, True, "Low", 0.65),
    ("ATMEGA328P-PU", "Active", 14, 25000, True, "High", 2.40),
    ("ATMEGA328P-AU", "Active", 10, 62000, True, "High", 2.10),
    ("ATMEGA2560-16AU", "Active", 20, 3100, True, "High", 9.80),
    ("RP2040-QFN56", "Active", 4, 120000, False, "High", 0.95),
    ("NRF52840-QFAA-R", "Active", 16, 9500, False, "High", 4.80),
    ("SAMD21G18A-AUT", "Active", 10, 14000, True, "Medium", 2.90),
    ("PIC16F877A-I/P", "NRND", 28, 450, True, "Medium", 3.10),
    ("PIC18F4550-I/PT", "Active", 12, 18000, True, "Medium", 4.50),
    ("MSP430G2553IN20", "Active", 6, 32000, True, "Medium", 1.80),
    
    # Sensors
    ("DHT11-TEMP-HUM", "Active", 8, 3500, True, "Medium", 1.20),
    ("DHT22-AM2302", "Active", 6, 8900, True, "Medium", 3.40),
    ("MPU6050-GY521", "NRND", 20, 1200, False, "High", 2.10),
    ("MPU9250-IMU", "Obsolete", 48, 0, False, "High", 6.50),
    ("BME280-ENV-SEN", "Active", 10, 14200, True, "Medium", 4.80),
    ("BMP280-PRESS", "Active", 6, 28000, True, "Low", 1.45),
    ("HC-SR04-ULTRA", "Active", 4, 45000, True, "Low", 0.90),
    ("DS18B20-TEMP", "Active", 4, 65000, True, "Low", 1.10),
    ("VL53L0X-TOF", "Active", 12, 11000, False, "High", 3.90),
    ("TCS3200-COLOR", "Active", 8, 4200, True, "Medium", 2.70),
    ("TSL2561-LIGHT", "Obsolete", 52, 0, False, "Medium", 3.10),
    ("ADXL345-ACCEL", "Active", 6, 19000, True, "Medium", 2.25),
    ("PIR-HC-SR501", "Active", 4, 38000, True, "Low", 1.15),
    ("MQ-2-GAS-SEN", "Active", 6, 22000, True, "Medium", 1.60),
    ("MQ-7-CO-SEN", "Active", 8, 14000, True, "Medium", 1.80),
    ("PHOTO-RES-LDR", "Active", 4, 14000, True, "Low", 0.15),

    # Power & Regulators
    ("LM7805CT", "Active", 6, 12000, True, "Low", 0.45),
    ("LM7812CT", "Active", 4, 18000, True, "Low", 0.45),
    ("LM317T-DG", "Active", 4, 45000, True, "Low", 0.55),
    ("AMS1117-3.3V", "Active", 2, 250000, True, "Low", 0.12),
    ("AMS1117-5.0V", "Active", 2, 180000, True, "Low", 0.12),
    ("TP4056-SOP8", "Active", 8, 18000, True, "Medium", 0.25),
    ("MP2307-BUCK-IC", "Active", 6, 42000, True, "Medium", 0.65),
    ("XL6009-BOOST", "Active", 8, 15000, True, "Medium", 1.10),
    ("MT3608-SOT23", "Active", 4, 95000, True, "Low", 0.28),
    ("TPS61090-BOOST", "Obsolete", 44, 0, False, "High", 2.90),
    ("SY8089-BUCK-SOT23", "Active", 6, 82000, True, "Low", 0.32),

    # Drivers & Interface ICs
    ("L298N-DRIVER", "Obsolete", 40, 0, False, "High", 2.20),
    ("ULN2003A-DIP16", "Active", 4, 68000, True, "Low", 0.35),
    ("DRV8825-STEPPER", "Active", 8, 12500, True, "Medium", 1.90),
    ("CH340G-SOP16", "Active", 4, 140000, True, "Low", 0.45),
    ("FT232RL-SSOP28", "Active", 12, 18000, False, "High", 2.80),
    ("CP2102-QFN28", "NRND", 24, 2100, False, "High", 2.10),
    ("MAX485-SOP8", "Active", 4, 85000, True, "Medium", 0.40),
    ("PCA9685-PWM-DRIVER", "Active", 8, 16000, True, "Medium", 1.85),
    ("PCF8574-I2C-EXP", "Active", 6, 42000, True, "Low", 0.75),
    ("CD4017-BE-COUNTER", "Active", 4, 55000, True, "Low", 0.30),
    ("74HC595-SHIFT-REG", "Active", 2, 210000, True, "Low", 0.22),
    ("NE555P", "Active", 4, 50000, True, "Low", 0.18),
    ("LM358-OPAMP", "Active", 2, 340000, True, "Low", 0.15),
    ("LM393-COMPARATOR", "Active", 2, 280000, True, "Low", 0.16),

    # Discretes
    ("2N2222A", "Active", 2, 85000, True, "Low", 0.08),
    ("2N3904-BU", "Active", 2, 150000, True, "Low", 0.05),
    ("BC547-TO92", "Active", 2, 220000, True, "Low", 0.04),
    ("BS170-MOSFET", "Active", 4, 45000, True, "Low", 0.18),
    ("IRFZ44N-MOSFET", "Active", 4, 38000, True, "Medium", 0.85),
    ("AO3400-SOT23", "Active", 2, 450000, True, "Low", 0.06),
    ("2N7000-TA", "Active", 2, 180000, True, "Low", 0.10),
    ("1N4007", "Active", 2, 100000, True, "Low", 0.03),
    ("1N4148-DO35", "Active", 1, 500000, True, "Low", 0.02),
    ("SS14-SMA-DIODE", "Active", 2, 350000, True, "Low", 0.07),
    ("BAT54S-SOT23", "Active", 2, 420000, True, "Low", 0.05),
]

def generate_expanded_catalog():
    catalog = list(SERIES_TEMPLATES)
    
    # Generate parametric variations for passive resistors, capacitors, LEDs, connectors to reach 200+
    res_values = ["10", "100", "220", "330", "470", "1K", "2.2K", "4.7K", "10K", "22K", "47K", "100K", "1M"]
    res_packages = ["0402", "0603", "0805", "1206"]
    for val in res_values:
        for pkg in res_packages:
            mpn = f"RES-{val}-{pkg}"
            if not any(item[0] == mpn for item in catalog):
                catalog.append((mpn, "Active", 1, random.randint(300000, 1500000), True, "Low", 0.01))
                
    cap_values = ["10PF", "22PF", "100NF", "1UF", "4.7UF", "10UF", "47UF", "100UF"]
    cap_packages = ["0402", "0603", "0805", "ELECTRO"]
    for val in cap_values:
        for pkg in cap_packages:
            mpn = f"CAP-{val}-{pkg}"
            if not any(item[0] == mpn for item in catalog):
                catalog.append((mpn, "Active", 2, random.randint(200000, 1000000), True, "Low", 0.03))

    led_colors = ["RED", "GREEN", "BLUE", "YELLOW", "WHITE", "RGB"]
    led_types = ["5MM", "0805", "0603"]
    for color in led_colors:
        for ltype in led_types:
            mpn = f"LED-{ltype}-{color}"
            if not any(item[0] == mpn for item in catalog):
                catalog.append((mpn, "Active", 1, random.randint(150000, 800000), True, "Low", 0.05))

    return catalog

def generate_reference_csvs(data_dir: str):
    os.makedirs(data_dir, exist_ok=True)
    catalog = generate_expanded_catalog()
    
    lifecycle_path = os.path.join(data_dir, "lifecycle.csv")
    lead_time_path = os.path.join(data_dir, "lead_times.csv")
    stock_path = os.path.join(data_dir, "stock.csv")
    second_source_path = os.path.join(data_dir, "second_source.csv")
    criticality_path = os.path.join(data_dir, "criticality.csv")
    unit_cost_path = os.path.join(data_dir, "unit_costs.csv")
    
    with open(lifecycle_path, "w", newline="", encoding="utf-8") as f_lc, \
         open(lead_time_path, "w", newline="", encoding="utf-8") as f_lt, \
         open(stock_path, "w", newline="", encoding="utf-8") as f_st, \
         open(second_source_path, "w", newline="", encoding="utf-8") as f_ss, \
         open(criticality_path, "w", newline="", encoding="utf-8") as f_cr, \
         open(unit_cost_path, "w", newline="", encoding="utf-8") as f_uc:
        
        w_lc = csv.writer(f_lc)
        w_lt = csv.writer(f_lt)
        w_st = csv.writer(f_st)
        w_ss = csv.writer(f_ss)
        w_cr = csv.writer(f_cr)
        w_uc = csv.writer(f_uc)
        
        w_lc.writerow(["Part Number", "Lifecycle Status"])
        w_lt.writerow(["Part Number", "Lead Time Weeks"])
        w_st.writerow(["Part Number", "Stock"])
        w_ss.writerow(["Part Number", "Has Second Source"])
        w_cr.writerow(["Part Number", "Criticality"])
        w_uc.writerow(["Part Number", "Unit Cost USD"])
        
        for item in catalog:
            mpn, lc, lt, st, ss, cr, cost = item
            w_lc.writerow([mpn, lc])
            w_lt.writerow([mpn, lt])
            w_st.writerow([mpn, st])
            w_ss.writerow([mpn, str(ss)])
            w_uc.writerow([mpn, f"{cost:.2f}"])
            if random.random() > 0.20:
                w_cr.writerow([mpn, cr])

    print(f"Generated {len(catalog)} dynamic component records in '{data_dir}' reference CSVs!")

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    generate_reference_csvs(base_dir)
