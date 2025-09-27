import httpx
import json
import sys

# Configuration
SERVER_URL = "http://localhost:8000"
API_BASE = ""

def test_join_endpoint():
    """Test the join game endpoint with your existing database"""
    
    print("🧪 Testing Join Game Endpoint (using httpx)")
    print("=" * 50)
    
    # Create httpx client
    with httpx.Client(timeout=10.0) as client:
        
        # Step 1: Check if server is running
        try:
            response = client.get(f"{SERVER_URL}{API_BASE}/test")
            print(f"✅ Server is running (status: {response.status_code})")
        except httpx.RequestError:
            print(f"❌ Cannot connect to {SERVER_URL}")
            print("Make sure your FastAPI server is running!")
            return False
        
        # Step 2: Get available rooms
        print("\n📋 Getting available rooms...")
        try:
            response = client.get(f"{SERVER_URL}{API_BASE}/game_list")
            if response.status_code != 200:
                print(f"❌ Failed to get room list: {response.status_code}")
                return False
            
            rooms = response.json()["items"]
            if not rooms:
                print("❌ No available rooms found!")
                print("Create a room in your database first.")
                return False
            
            print(f"✅ Found {len(rooms)} available rooms:")
            for room in rooms:
                print(f"   - {room['name']} (ID: {room['id']}) [{room['players_joined']}/{room['player_qty']} players]")
            
            # Use the first available room
            test_room = rooms[0]
            room_id = test_room["id"]
            print(f"\n🎯 Using room: {test_room['name']} (ID: {room_id})")
            
        except Exception as e:
            print(f"❌ Error getting rooms: {e}")
            return False
        
        # Step 3: Test joining the game
        print(f"\n🚀 Testing join game endpoint...")
        
        join_data = {
            "name": "HttpxTestPlayer",
            "avatar": "/assets/avatars/detective1.png", 
            "birthdate": "1995-06-15",
            "user_id": 98765
        }
        
        print(f"Sending data: {json.dumps(join_data, indent=2)}")
        
        try:
            response = client.post(
                f"{SERVER_URL}{API_BASE}/game/{room_id}/join", 
                json=join_data
            )
            
            print(f"\n📤 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                # Success!
                data = response.json()
                print("✅ JOIN SUCCESSFUL!")
                print(f"\n📋 Response Data:")
                print(f"   Room: {data['room']['name']} (ID: {data['room']['id']})")
                print(f"   Players in room: {len(data['players'])}")
                print(f"   Your player ID: {data['player_id']}")
                
                # Show all players
                print(f"\n👥 Players in room:")
                for player in data["players"]:
                    host_mark = " (HOST)" if player["is_host"] else ""
                    print(f"   - {player['name']}{host_mark}")
                
                # Show socket instructions
                socket_data = data["socket_instructions"]["data"]
                print(f"\n🔌 Socket Instructions:")
                print(f"   Action: {data['socket_instructions']['action']}")
                print(f"   Game ID: {socket_data['game_id']}")
                print(f"   Player ID: {socket_data['player_id']}")
                print(f"   User ID: {socket_data['user_id']}")
                
                return True
                
            else:
                # Error
                print(f"❌ JOIN FAILED!")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    print(f"   Raw response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return False

def test_error_cases():
    """Test some error cases"""
    print(f"\n🧪 Testing Error Cases")
    print("=" * 30)
    
    with httpx.Client(timeout=10.0) as client:
        # Test 1: Nonexistent room
        print("1. Testing nonexistent room...")
        try:
            response = client.post(
                f"{SERVER_URL}{API_BASE}/game/99999/join",
                json={
                    "name": "Test",
                    "avatar": "/test.png",
                    "birthdate": "1995-01-01", 
                    "user_id": 999
                }
            )
            if response.status_code == 404:
                print("   ✅ Correctly returned 404 for nonexistent room")
            else:
                print(f"   ❌ Expected 404, got {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 2: Invalid data
        print("2. Testing invalid birthdate...")
        try:
            # Get a valid room first
            rooms_response = client.get(f"{SERVER_URL}{API_BASE}/game_list")
            if rooms_response.status_code == 200:
                rooms = rooms_response.json()["items"]
                if rooms:
                    room_id = rooms[0]["id"]
                    response = client.post(
                        f"{SERVER_URL}{API_BASE}/game/{room_id}/join",
                        json={
                            "name": "Test",
                            "avatar": "/test.png", 
                            "birthdate": "invalid-date",
                            "user_id": 999
                        }
                    )
                    if response.status_code == 400:
                        print("   ✅ Correctly returned 400 for invalid birthdate")
                    else:
                        print(f"   ❌ Expected 400, got {response.status_code}")
                else:
                    print("   ⏭️  Skipped - no rooms available")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 3: Missing fields
        print("3. Testing missing required fields...")
        try:
            rooms_response = client.get(f"{SERVER_URL}{API_BASE}/game_list")
            if rooms_response.status_code == 200:
                rooms = rooms_response.json()["items"]
                if rooms:
                    room_id = rooms[0]["id"]
                    response = client.post(
                        f"{SERVER_URL}{API_BASE}/game/{room_id}/join",
                        json={
                            "name": "Test"
                            # Missing required fields
                        }
                    )
                    if response.status_code == 422:
                        print("   ✅ Correctly returned 422 for missing fields")
                    else:
                        print(f"   ❌ Expected 422, got {response.status_code}")
                else:
                    print("   ⏭️  Skipped - no rooms available")
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    print("🎮 Join Game Endpoint Tester (httpx version)")
    print("Starting tests...\n")
    
    success = test_join_endpoint()
    
    if success:
        test_error_cases()
        print(f"\n🎉 Tests completed successfully!")
    else:
        print(f"\n💥 Main test failed - check your setup")
        sys.exit(1)