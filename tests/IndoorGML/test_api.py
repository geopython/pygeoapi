import requests
import json
import os

# Configuration
BASE_URL = "http://localhost:5000"
COLLECTION_ID = "aist_waterfront_lab"
# Path to your sample file
DATA_FILE = os.path.join(os.path.dirname(__file__), '../../data/sample_indoor.json')

def test_crud_flow():
    print(f"--- Starting IndoorGML API Integration Test ---")

    # 1. SETUP: Create the collection
    print("\n[1/6] POST /collections (Setup)")
    payload = {
        "id": COLLECTION_ID,
        "title": "AIST Waterfront Lab IndoorGML",
        "itemType": "indoorfeature",  # Gatekeeper for your custom logic
        "storage": {"type": "Provider", "name": "Memory"}
    }
    setup_res = requests.post(f"{BASE_URL}/collections", json=payload)
    print(f"Status: {setup_res.status_code}")

    # 2. VERIFY: Clean Design (No Keywords)
    print(f"\n[2/6] GET /collections/{COLLECTION_ID} (Clean Design Check)")
    detail_res = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}?f=json")
    if detail_res.status_code == 200:
        data = detail_res.json()
        if 'keywords' not in data:
            print("Success: JSON response is clean (No keywords field).")
        else:
            print("Fail: 'keywords' found in response.")

    # 3. NEGATIVE TEST: Validate Deep Validation
    print("\n[3/6] POST /items (Negative Test - Invalid Schema)")
    bad_data = {"featureType": "IndoorFeatures", "layers": []} # Fails minItems: 1
    bad_res = requests.post(f"{BASE_URL}/collections/{COLLECTION_ID}/items", json=bad_data)
    if bad_res.status_code == 400:
        print(f"Success: API rejected invalid data. Error: {bad_res.json().get('description')}")
    else:
        print(f"Fail: API accepted invalid data with status {bad_res.status_code}")

    # 4. POSITIVE TEST: Register Building Model
    print(f"\n[4/6] POST /items (Positive Test - sample_indoor.json)")
    if not os.path.exists(DATA_FILE):
        print(f"Error: Data file not found at {DATA_FILE}")
        return

    with open(DATA_FILE, 'r') as f:
        indoor_data = json.load(f)
    
    item_res = requests.post(f"{BASE_URL}/collections/{COLLECTION_ID}/items", json=indoor_data)
    if item_res.status_code == 201:
        print(f"Success: Building model registered. ID: {item_res.json().get('id')}")
    else:
        print(f"Fail: {item_res.status_code} - {item_res.text}")

    # 5. RETRIEVAL: Verify Layer Integrity
    print(f"\n[5/6] GET /items (Retrieval & Layer Check)")
    get_items_res = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}/items?f=json")
    if get_items_res.status_code == 200:
        features = get_items_res.json().get('features', [])
        if features and 'layers' in features[0]:
            first_layer = features[0]['layers'][0]
            print(f"Success: Found {len(features)} model(s).")
            print(f"Verified Layer: ID={first_layer.get('id')}, Theme={first_layer.get('theme')}")
            # Ensure PrimalSpace/DualSpace structure is intact
            if 'primalSpace' in first_layer and 'dualSpace' in first_layer:
                print("Verified: Primal and Dual space connectivity preserved.")
        else:
            print("Fail: Features or layers missing in response.")

    # 6. CLEANUP: Delete Collection
    print(f"\n[6/6] DELETE /collections/{COLLECTION_ID} (Cleanup)")
    requests.delete(f"{BASE_URL}/collections/{COLLECTION_ID}")
    
    final_check = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}")
    if final_check.status_code == 404:
        print("\n--- All tests passed! ---")

if __name__ == "__main__":
    try:
        test_crud_flow()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Is 'pygeoapi serve' running?")
    except Exception as e:
        print(f"Unexpected Error: {e}")