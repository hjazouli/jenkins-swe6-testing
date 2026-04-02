import requests
import xml.etree.ElementTree as ET
import sys
from datetime import datetime
import argparse

# Updated for local mock server
POLARION_URL = "http://localhost:8082"
PROJECT_ID = "ECU_BRAKE_SYSTEM"
USERNAME = "jenkins_bot"
PASSWORD = "secure_token_here"

def upload_test_results(xml_file, testrun_id):
    """Push pytest XML results to Polarion (Mock)."""
    
    print(f"Reading results from {xml_file}...")
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"❌ Error parsing XML: {e}")
        sys.exit(1)
    
    # Prepare Mock Polarion XML format
    polarion_xml = ET.Element("testrecords", project=PROJECT_ID)
    
    for testcase in root.findall(".//testcase"):
        name = testcase.get("name")
        status = "passed" if testcase.find("failure") is None else "failed"
        
        req_id = "unknown"
        prop = testcase.find(".//property[@name='polarion-testcase-id']")
        if prop is not None:
            req_id = prop.get("value")
        
        record = ET.SubElement(polarion_xml, "testrecord")
        ET.SubElement(record, "test-case-id").text = req_id
        ET.SubElement(record, "test-run-id").text = testrun_id
        ET.SubElement(record, "result").text = status
        ET.SubElement(record, "executed").text = datetime.now().isoformat()
        ET.SubElement(record, "duration").text = testcase.get("time")
    
    # Upload via Mock REST API
    print(f"Uploading to {POLARION_URL}/import/xunit...")
    try:
        response = requests.post(
            f"{POLARION_URL}/import/xunit",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/xml"},
            data=ET.tostring(polarion_xml, encoding="unicode")
        )
        
        if response.status_code == 200:
            print(f"✅ Test results uploaded to Polarion testrun: {testrun_id}")
        else:
            print(f"❌ Failed to upload: {response.status_code} - {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", required=True)
    parser.add_argument("--testrun", required=True)
    args = parser.parse_args()
    
    upload_test_results(args.xml, args.testrun)
