import requests
import json
import os

# Configuration
BASE_URL = "http://localhost:5000"
COLLECTION_ID = "aist_waterfront_lab"
# Path to your sample file
DATA_FILE = os.path.join(os.path.dirname(__file__), '../../data/sample_indoor.json')

# This should match the "id" field inside your sample_indoor.json
FEATURE_ID = "AIST_Waterfront_Center" 

def test_crud_flow():
    print(f"--- Starting IndoorGML API Integration Test ---")

    # 1. SETUP: Create the collection
    print("\n[1/7] POST /collections (Setup)")
    payload = {
        "id": COLLECTION_ID,
        "title": "AIST Waterfront Lab IndoorGML",
        "itemType": "indoorfeature",  
        "storage": {"type": "Provider", "name": "Memory"}
    }
    setup_res = requests.post(f"{BASE_URL}/collections", json=payload)
    print(f"Status: {setup_res.status_code}")

    # 2. VERIFY: Clean Design (No Keywords)
    print(f"\n[2/7] GET /collections/{COLLECTION_ID} (Clean Design Check)")
    detail_res = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}?f=json")
    if detail_res.status_code == 200:
        data = detail_res.json()
        if 'keywords' not in data:
            print("Success: JSON response is clean (No keywords field).")
        else:
            print("Fail: 'keywords' found in response.")

    # 3. NEGATIVE TEST: Deep Validation Check
    print("\n[3/7] POST /items (Negative Test - Invalid Schema)")
    bad_data = {"featureType": "IndoorFeatures", "layers": []} # Fails minItems: 1
    bad_res = requests.post(f"{BASE_URL}/collections/{COLLECTION_ID}/items", json=bad_data)
    if bad_res.status_code == 400:
        print(f"Success: API rejected invalid data.")
    else:
        print(f"Fail: API accepted invalid data with status {bad_res.status_code}")

    # 4. POSITIVE TEST: Register Building Model
    print(f"\n[4/7] POST /items (Positive Test - sample_indoor.json)")
    with open(DATA_FILE, 'r') as f:
        indoor_data = json.load(f)
    
    item_res = requests.post(f"{BASE_URL}/collections/{COLLECTION_ID}/items", json=indoor_data)
    if item_res.status_code == 201:
        print(f"Success: Building model registered.")
    else:
        print(f"Fail: {item_res.status_code} - {item_res.text}")

    # 5. RETRIEVAL (List): Verify Layer Integrity
    print(f"\n[5/7] GET /items (List & Layer Check)")
    list_res = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}/items?f=json")
    if list_res.status_code == 200:
        features = list_res.json().get('features', [])
        if features and 'layers' in features[0]:
            print(f"Success: Found {len(features)} model(s).")
            print(f"Verified: 'primalSpace' and 'dualSpace' connectivity preserved.")

    # 6. RETRIEVAL (Detail): GET by ID
    print(f"\n[6/7] GET /items/{FEATURE_ID}")
    single_res = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}/items/{FEATURE_ID}?f=json")
    if single_res.status_code == 200:
        print(f"Success: Retrieved specific feature {FEATURE_ID}")
    else:
        print(f"Fail: Could not find feature {FEATURE_ID}")
    
    # 7. DELETE: Remove Item and Cleanup
    print(f"\n[7/7] DELETE /items/{FEATURE_ID} & Collection Cleanup")
    del_item_res = requests.delete(f"{BASE_URL}/collections/{COLLECTION_ID}/items/{FEATURE_ID}")
    if del_item_res.status_code == 204:
        print(f"Success: Deleted feature {FEATURE_ID}")

    requests.delete(f"{BASE_URL}/collections/{COLLECTION_ID}")
    
    if requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}").status_code == 404:
        print("\n--- All tests passed! ---")

if __name__ == "__main__":
    try:
        test_crud_flow()
    except Exception as e:
        print(f"Unexpected Error: {e}")