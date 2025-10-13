import requests
import json

def get_firebase_token(email, password, api_key):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data['idToken']
    else:
        print(f"Error: {response.text}")
        return None

if __name__ == "__main__":
    # Get these from your Firebase project settings
    API_KEY = input("Enter your Firebase Web API Key: ")
    EMAIL = input("Enter admin email: ") or "admin@facilityfix.com"
    PASSWORD = input("Enter admin password: ")
    
    token = get_firebase_token(EMAIL, PASSWORD, API_KEY)
    if token:
        print(f"\nYour Firebase JWT Token:")
        print(f"Bearer {token}")
        print(f"\nCopy this token and paste it in the Swagger UI Authorization field")
