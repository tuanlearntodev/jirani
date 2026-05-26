import requests
import json

BASE_URL = "http://localhost:8000"

def test_reset_password_flow():
    
    print("=" * 60)
    print("TESTING PASSWORD RESET FUNCTIONALITY")
    print("=" * 60)
    
    print("\n[Step 1] Logging in as teacher...")
    teacher_login = {
        "username": "teacher1",
        "password": "teacherpassword123"
    }
    
    response = requests.post(
        f"{BASE_URL}/auth/token",  # Changed from /auth/login
        json=teacher_login
    )
    
    if response.status_code == 200:
        teacher_token = response.json()["access_token"]
        print("[SUCCESS] Teacher login successful!")
        print(f"   Token: {teacher_token[:30]}...")
    else:
        print("[FAILED] Teacher login failed!")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        return
    
    print("\n[Step 2] Testing student's OLD password...")
    student_login_old = {
        "username": "student1",
        "password": "studentpassword123"
    }
    
    response = requests.post(
        f"{BASE_URL}/auth/token",  # Changed from /auth/login
        json=student_login_old
    )
    
    if response.status_code == 200:
        print("[SUCCESS] Student can login with OLD password")
        print(f"   Token: {response.json()['access_token'][:30]}...")
    else:
        print("[INFO] Student cannot login with OLD password")
        print(f"   This might be expected if password was already changed")
    
    print("\n[Step 3] Teacher resetting student's password...")
    reset_data = {
        "username": "student1",
        "new_password": "NewStudentPass123456"
    }
    
    response = requests.post(
        f"{BASE_URL}/auth/reset-password",
        json=reset_data,
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    
    if response.status_code == 200:
        print("[SUCCESS] Password reset successful!")
        print(f"   Response: {response.json()}")
    else:
        print("[FAILED] Password reset failed!")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        return
    
    print("\n[Step 4] Trying student's OLD password (should fail)...")
    response = requests.post(
        f"{BASE_URL}/auth/token",  # Changed from /auth/login
        json=student_login_old
    )
    
    if response.status_code == 401:
        print("[SUCCESS] OLD password correctly rejected!")
    else:
        print(f"[WARNING] Unexpected result: Status {response.status_code}")
    
    print("\n[Step 5] Trying student's NEW password (should work)...")
    student_login_new = {
        "username": "student1",
        "password": "NewStudentPass123456"
    }
    
    response = requests.post(
        f"{BASE_URL}/auth/token",  # Changed from /auth/login
        json=student_login_new
    )
    
    if response.status_code == 200:
        student_token = response.json()["access_token"]
        print("[SUCCESS] Student can login with NEW password!")
        print(f"   Token: {student_token[:30]}...")
    else:
        print("[FAILED] Student cannot login with NEW password!")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        return
    
    print("\n[Step 6] Testing that student CANNOT reset passwords...")
    reset_data_student = {
        "username": "teacher1",
        "new_password": "HackedPassword123456"
    }
    
    response = requests.post(
        f"{BASE_URL}/auth/reset-password",
        json=reset_data_student,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    
    if response.status_code == 403:
        print("[SUCCESS] Student correctly DENIED from resetting passwords!")
        print(f"   Response: {response.json()}")
    else:
        print("[SECURITY ISSUE] Student was able to reset password!")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_reset_password_flow()
    except Exception as e:
        print(f"\n[ERROR] {e}")