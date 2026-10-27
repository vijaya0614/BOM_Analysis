from src.bom_parser import expand_reference_range, expand_reference_token, parse_bom

def test_expand_reference_token_range():
    assert expand_reference_token("R1-R6") == ["R1", "R2", "R3", "R4", "R5", "R6"]
    assert expand_reference_token("LED1-LED3") == ["LED1", "LED2", "LED3"]
    assert expand_reference_token("C01-C04") == ["C01", "C02", "C03", "C04"]

def test_expand_reference_range_combined():
    ref_str = "R1-R3, R5, LED1-LED2"
    expected = ["R1", "R2", "R3", "R5", "LED1", "LED2"]
    assert expand_reference_range(ref_str) == expected

def test_parse_bom_sample_burglar_alarm(tmp_path):
    csv_content = (
        "Part Number,Designator,Qty\n"
        "REED-SW-14MM,SW1,1\n"
        "RES-10K-0201,R1-R4,4\n"
        "TBD-FET-OPTIONAL,Q1,1\n"
    )
    bom_file = tmp_path / "test_bom.csv"
    bom_file.write_text(csv_content, encoding="utf-8")
    
    profiles = parse_bom(str(bom_file))
    assert len(profiles) == 3
    
    # REED switch
    p0 = profiles[0]
    assert p0.part_number == "REED-SW-14MM"
    assert p0.references == ["SW1"]
    assert p0.qty == 1
    
    # Resistors range
    p1 = profiles[1]
    assert p1.part_number == "RES-10K-0201"
    assert p1.references == ["R1", "R2", "R3", "R4"]
    assert p1.qty == 4
    
    # TBD component
    p2 = profiles[2]
    assert p2.part_number is None  # TBD should be normalized to None
    assert "part_number" in p2.missing_fields
