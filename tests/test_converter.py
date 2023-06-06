"""
Test serialize and deserialize from cif files to json
and vice versa.
"""

def test_cifs_to_json():
    """Test that cif files are correctly converted to json"""
    cif_files = Path(__file__).parent.joinpath("cif_files")
    for cif_file in cif_files.glob("*.cif"):
        json_file = cif_file.with_suffix(".json")
        if json_file.exists():
            json_file.unlink()
        converter.cif_to_json(cif_file)
        assert json_file.exists()
        
def test_json_to_cifs():
    """Test that json files are correctly converted to cif"""
    json_file = Path(__file__).parent.joinpath("json_file")
    with open(json_file, "w") as handle:
        handle.write('{"test": "test"}')
        
    cif_content_list = converter.json_to_cifs(json_file)
    
    # Test that the content is correct as original cif files
    for cif_content in cif_content_list:
        assert cif_content == '{"test": "test"}'
        
def test_json_to_jsonl():
    """test that json files are correctly converted to jsonl"""
    
def test_jsonl_to_json():
    """test that jsonl files are correctly converted to json"""
    
    