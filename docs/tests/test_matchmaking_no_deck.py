import requests
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API Gateway URL
GATEWAY_URL = "https://localhost:8443"


def test_matchmaking_without_deck():
    """
    Test that a user cannot join matchmaking without creating a deck first.
    Expected: 400 Bad Request with error message about deck not found.
    """
    print("\n" + "="*60)
    print("  🧪 TEST: Matchmaking Without Deck Validation")
    print("="*60)
    
    # 1. Register new user
    username = "test_nodeck_user"
    password = "TestPass123!"
    
    print(f"\n✨ Step 1: Registering user '{username}'...")
    try:
        reg_resp = requests.post(
            f"{GATEWAY_URL}/users/register",
            json={
                "username": username,
                "email": f"{username}@test.com",
                "password": password
            },
            verify=False
        )
        
        if reg_resp.status_code in [200, 201]:
            print(f"✅ User registered successfully")
        else:
            print(f"⚠️  User might already exist, proceeding with login...")
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False
    
    # 2. Login
    print(f"\n✨ Step 2: Logging in as '{username}'...")
    try:
        login_resp = requests.post(
            f"{GATEWAY_URL}/users/login",
            json={
                "username": username,
                "password": password
            },
            verify=False
        )
        
        if login_resp.status_code != 200:
            print(f"❌ Login failed: {login_resp.text}")
            return False
        
        token = login_resp.json().get("token")
        print(f"✅ Login successful, token obtained")
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False
    
    # 3. Try to join matchmaking WITHOUT creating a deck (with deck_slot parameter)
    print(f"\n✨ Step 3: Attempting to join matchmaking with non-existent deck slot 2...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        matchmaking_resp = requests.post(
            f"{GATEWAY_URL}/game/match/join",
            headers=headers,
            json={"deck_slot": 2},  # Specify deck slot but deck doesn't exist
            verify=False
        )
        
        print(f"\n📊 Response Status Code: {matchmaking_resp.status_code}")
        print(f"📊 Response Body: {matchmaking_resp.text}")
        
        # Verify the expected behavior
        if matchmaking_resp.status_code == 400:
            error_data = matchmaking_resp.json()
            error_message = error_data.get("error", "")
            
            if "deck" in error_message.lower() and ("not found" in error_message.lower() or "create" in error_message.lower()):
                print(f"\n✅ TEST PASSED!")
                print(f"   Expected behavior: User blocked from matchmaking without deck")
                print(f"   Error message: {error_message}")
                return True
            else:
                print(f"\n⚠️  TEST PARTIALLY PASSED")
                print(f"   Got 400 status, but error message unexpected: {error_message}")
                return False
        else:
            print(f"\n❌ TEST FAILED!")
            print(f"   Expected: 400 Bad Request")
            print(f"   Got: {matchmaking_resp.status_code}")
            print(f"   The user should not be allowed to join matchmaking without a deck!")
            return False
            
    except Exception as e:
        print(f"❌ Matchmaking request error: {e}")
        return False


def test_matchmaking_without_deck_slot():
    """
    Test that matchmaking fails when deck_slot parameter is missing.
    Expected: 400 Bad Request with error about missing deck_slot.
    """
    print("\n" + "="*60)
    print("  🧪 TEST: Matchmaking Without deck_slot Parameter")
    print("="*60)
    
    username = "test_nodeck_param_user"
    password = "TestPass123!"
    
    # Register and login
    print(f"\n✨ Registering and logging in as '{username}'...")
    try:
        requests.post(f"{GATEWAY_URL}/users/register",
            json={"username": username, "email": f"{username}@test.com", "password": password},
            verify=False)
        
        login_resp = requests.post(f"{GATEWAY_URL}/users/login",
            json={"username": username, "password": password},
            verify=False)
        
        token = login_resp.json().get("token")
        print(f"✅ Ready to test")
    except Exception as e:
        print(f"❌ Setup error: {e}")
        return False
    
    # Try to join matchmaking WITHOUT deck_slot parameter
    print(f"\n✨ Attempting to join matchmaking WITHOUT deck_slot parameter...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        matchmaking_resp = requests.post(
            f"{GATEWAY_URL}/game/match/join",
            headers=headers,
            json={},  # Empty body - no deck_slot
            verify=False
        )
        
        print(f"\n📊 Response Status Code: {matchmaking_resp.status_code}")
        print(f"📊 Response Body: {matchmaking_resp.text}")
        
        if matchmaking_resp.status_code == 400:
            error_data = matchmaking_resp.json()
            error_message = error_data.get("error", "")
            
            if "deck_slot" in error_message.lower() and "required" in error_message.lower():
                print(f"\n✅ TEST PASSED!")
                print(f"   Expected behavior: deck_slot parameter is required")
                print(f"   Error message: {error_message}")
                return True
            else:
                print(f"\n⚠️  TEST PARTIALLY PASSED")
                print(f"   Got 400 status, but error message unexpected: {error_message}")
                return False
        else:
            print(f"\n❌ TEST FAILED!")
            print(f"   Expected: 400 Bad Request")
            print(f"   Got: {matchmaking_resp.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting test execution...")
    
    result1 = test_matchmaking_without_deck()
    result2 = test_matchmaking_without_deck_slot()
    
    if result1 and result2:
        print("\n" + "="*60)
        print("  ✅ ALL TESTS PASSED")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("  ❌ SOME TESTS FAILED")
        print("="*60 + "\n")
