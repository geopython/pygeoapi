import requests
import json

BASE_URL = "http://localhost:5000"
COLLECTION_ID = "aist_waterfront_lab"

def test_crud_flow():
    print(f"--- Starting Test for Collection: {COLLECTION_ID} ---")

    # 1. POST: Create the collection
    payload = {
        "id": COLLECTION_ID,
        "title": "AIST Waterfront Lab IndoorGML",
        "description": "Experimental IndoorGML data for AIST project",
        "itemType": "indoorfeature",
        "storage": {
            "type": "Provider",
            "name": "Memory"
        }
    }
    
    print("\n[1/4] POST /collections")
    post_res = requests.post(f"{BASE_URL}/collections", json=payload)
    print(f"Status: {post_res.status_code}")
    print(f"Response: {post_res.text}")

    # 2. GET (List): Check if it appears in the list
    print("\n[2/4] GET /collections (List)")
    list_res = requests.get(f"{BASE_URL}/collections?f=json")
    if COLLECTION_ID in list_res.text:
        print(f"Success: {COLLECTION_ID} found in list.")
    else:
        print("Failure: Collection not found in list.")

    # 3. GET (Detail): Check your clean design (No Keywords)
    print(f"\n[3/4] GET /collections/{COLLECTION_ID} (Detail)")
    detail_res = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}?f=json")
    print(f"Status: {detail_res.status_code}")
    
    if detail_res.status_code == 200:
        data = detail_res.json()
        print("Clean Design Verification:")
        print(f" - Title: {data.get('title')}")
        print(f" - ItemType: {data.get('itemType')}")
        # This is the critical test for you
        if 'keywords' not in data:
            print(" - Success: No 'keywords' found in JSON (as intended).")
        else:
            print(" - Warning: 'keywords' were found in JSON!")
    else:
        print(f"Error Detail: {detail_res.text}")

    # # 4. DELETE: Clean up
    # print(f"\n[4/4] DELETE /collections/{COLLECTION_ID}")
    # del_res = requests.delete(f"{BASE_URL}/collections/{COLLECTION_ID}")
    # print(f"Status: {del_res.status_code}")
    # print(f"Response: {del_res.text}")

    # Final Verification
    final_check = requests.get(f"{BASE_URL}/collections/{COLLECTION_ID}?f=json")
    if final_check.status_code == 404:
        print("\n--- All tests passed: Collection created, verified, and deleted. ---")

if __name__ == "__main__":
    try:
        test_crud_flow()
    except requests.exceptions.ConnectionError:
        print("Error: Is the pygeoapi server running on localhost:5000?")