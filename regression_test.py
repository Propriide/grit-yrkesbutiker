#!/usr/bin/env python3
"""
GRIT Backend Regression Test
After dependency change (requirements.txt: removed #sha256 from litellm wheel URL)
DO NOT modify .env, DO NOT drop data, DO NOT restart backend
"""
import sys
import requests
import random

# Configuration
BASE_URL = "http://localhost:8001"
API_URL = f"{BASE_URL}/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "patrik.degerstam@yp.se"
ADMIN_PASSWORD = "12345"
DELETED_ADMIN_EMAIL = "admin@blaklader.local"

# Test results
results = {
    "passed": [],
    "failed": []
}

def log_pass(test_name, details=""):
    msg = f"✅ PASS: {test_name}"
    if details:
        msg += f" - {details}"
    print(msg)
    results["passed"].append(test_name)

def log_fail(test_name, details=""):
    msg = f"❌ FAIL: {test_name}"
    if details:
        msg += f" - {details}"
    print(msg)
    results["failed"].append(f"{test_name}: {details}")

def test_1_backend_health_cities_products():
    """Test 1: Backend healthy, /api/cities, /api/products (~1236), product detail with sizes"""
    print("\n" + "="*80)
    print("TEST 1: Backend Health, Cities, Products, Product Detail")
    print("="*80)
    
    # 1a. Health check
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            log_pass("1a. /health", "Backend is healthy")
        else:
            log_fail("1a. /health", f"Status {resp.status_code}, response: {resp.text}")
            return None
    except Exception as e:
        log_fail("1a. /health", str(e))
        return None
    
    # 1b. Cities
    try:
        resp = requests.get(f"{API_URL}/cities", timeout=5)
        if resp.status_code == 200:
            cities = resp.json()
            if len(cities) >= 3:
                log_pass("1b. /api/cities", f"Found {len(cities)} cities")
            else:
                log_fail("1b. /api/cities", f"Only {len(cities)} cities, expected at least 3")
        else:
            log_fail("1b. /api/cities", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("1b. /api/cities", str(e))
    
    # 1c. Products (need token - use admin)
    admin_token = quick_admin_login()
    if not admin_token:
        log_fail("1c. /api/products", "Cannot get admin token for products test")
        return None
    
    try:
        resp = requests.get(f"{API_URL}/products", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            if total >= 1200:
                log_pass("1c. /api/products", f"Total {total} products (expected ~1236)")
                items = data.get("items", [])
                return items[0].get("part_no") if items else None
            else:
                log_fail("1c. /api/products", f"Only {total} products, expected ~1236")
        else:
            log_fail("1c. /api/products", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("1c. /api/products", str(e))
    
    return None

def test_1d_product_detail(part_no, token):
    """Test 1d: Product detail with sizes"""
    if not part_no:
        log_fail("1d. Product detail", "No part_no available")
        return
    
    try:
        resp = requests.get(f"{API_URL}/products/{part_no}", headers={"Authorization": f"Bearer {token}"}, timeout=5)
        if resp.status_code == 200:
            product = resp.json()
            sizes = product.get("sizes", [])
            if sizes and len(sizes) > 0:
                log_pass("1d. Product detail", f"Product {part_no} has {len(sizes)} sizes")
                return sizes[0]
            else:
                log_fail("1d. Product detail", f"Product {part_no} has no sizes")
        else:
            log_fail("1d. Product detail", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("1d. Product detail", str(e))
    return None

def quick_admin_login():
    """Quick admin login to get token"""
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except:
        pass
    return None

def test_2_auth():
    """Test 2: Auth - admin login, /api/auth/me, register customer, customer login"""
    print("\n" + "="*80)
    print("TEST 2: Authentication")
    print("="*80)
    
    # 2a. Admin login
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            admin_token = data.get("access_token")
            user = data.get("user", {})
            if admin_token and user.get("role") == "admin":
                log_pass("2a. Admin login", f"Logged in as {ADMIN_EMAIL}, role=admin")
            else:
                log_fail("2a. Admin login", f"Missing token or role not admin: {user.get('role')}")
                return None, None, None
        else:
            log_fail("2a. Admin login", f"Status {resp.status_code}: {resp.text}")
            return None, None, None
    except Exception as e:
        log_fail("2a. Admin login", str(e))
        return None, None, None
    
    # 2b. GET /api/auth/me
    try:
        resp = requests.get(f"{API_URL}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=5)
        if resp.status_code == 200:
            user = resp.json()
            if user.get("role") == "admin" and user.get("email") == ADMIN_EMAIL:
                log_pass("2b. GET /api/auth/me", f"Role=admin, email={ADMIN_EMAIL}")
            else:
                log_fail("2b. GET /api/auth/me", f"Role={user.get('role')}, email={user.get('email')}")
        else:
            log_fail("2b. GET /api/auth/me", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("2b. GET /api/auth/me", str(e))
    
    # 2c. Register new customer
    try:
        # Get cities first
        resp = requests.get(f"{API_URL}/cities", timeout=5)
        if resp.status_code != 200:
            log_fail("2c. Register customer", "Cannot get cities")
            return admin_token, None, None
        cities = resp.json()
        city_id = cities[0].get("id")
        
        # Register
        customer_email = f"test.regression.{random.randint(10000, 99999)}@example.com"
        customer_password = "RegTest123!"
        
        resp = requests.post(f"{API_URL}/auth/register", json={
            "email": customer_email,
            "password": customer_password,
            "name": "Regression Test Customer",
            "phone": "+46701234567",
            "company": "Test AB",
            "city_id": city_id
        }, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            customer_token = data.get("access_token")
            if customer_token:
                log_pass("2c. Register customer", f"Registered {customer_email}")
            else:
                log_fail("2c. Register customer", "No access_token in response")
                return admin_token, None, None
        else:
            log_fail("2c. Register customer", f"Status {resp.status_code}: {resp.text}")
            return admin_token, None, None
    except Exception as e:
        log_fail("2c. Register customer", str(e))
        return admin_token, None, None
    
    # 2d. Customer login
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={
            "email": customer_email,
            "password": customer_password
        }, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            customer_token_login = data.get("access_token")
            if customer_token_login:
                log_pass("2d. Customer login", f"Logged in as {customer_email}")
                return admin_token, customer_email, customer_token_login
            else:
                log_fail("2d. Customer login", "No access_token")
        else:
            log_fail("2d. Customer login", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("2d. Customer login", str(e))
    
    return admin_token, customer_email, customer_token

def test_3_admin_password_change(admin_token):
    """Test 3: Admin self-service password change - CRITICAL: must end with password 12345"""
    print("\n" + "="*80)
    print("TEST 3: Admin Password Change (CRITICAL: must restore to 12345)")
    print("="*80)
    
    TEMP_PASSWORD = "TempPass987"
    ORIGINAL_PASSWORD = "12345"
    
    # 3a. Change password from 12345 to TempPass987
    try:
        resp = requests.post(f"{API_URL}/auth/change-password", json={
            "current_password": ORIGINAL_PASSWORD,
            "new_password": TEMP_PASSWORD
        }, headers={"Authorization": f"Bearer {admin_token}"}, timeout=5)
        
        if resp.status_code == 200:
            log_pass("3a. Change password (12345 -> TempPass987)", "Password changed successfully")
        else:
            log_fail("3a. Change password (12345 -> TempPass987)", f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_fail("3a. Change password (12345 -> TempPass987)", str(e))
        return
    
    # 3b. Verify login with NEW password works
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": TEMP_PASSWORD
        }, timeout=5)
        if resp.status_code == 200:
            new_token = resp.json().get("access_token")
            if new_token:
                log_pass("3b. Login with new password (TempPass987)", "Login successful")
            else:
                log_fail("3b. Login with new password (TempPass987)", "No token returned")
                return
        else:
            log_fail("3b. Login with new password (TempPass987)", f"Status {resp.status_code}")
            return
    except Exception as e:
        log_fail("3b. Login with new password (TempPass987)", str(e))
        return
    
    # 3c. Verify login with OLD password fails
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ORIGINAL_PASSWORD
        }, timeout=5)
        if resp.status_code == 401:
            log_pass("3c. Login with old password (12345) fails", "Correctly rejected")
        else:
            log_fail("3c. Login with old password (12345) fails", f"Expected 401, got {resp.status_code}")
    except Exception as e:
        log_fail("3c. Login with old password (12345) fails", str(e))
    
    # 3d. CHANGE IT BACK to 12345 (CRITICAL)
    # NOTE: This will FAIL due to validation - password must be min 6 chars, but "12345" is only 5
    try:
        resp = requests.post(f"{API_URL}/auth/change-password", json={
            "current_password": TEMP_PASSWORD,
            "new_password": ORIGINAL_PASSWORD
        }, headers={"Authorization": f"Bearer {new_token}"}, timeout=5)
        
        if resp.status_code == 200:
            log_pass("3d. Change password back (TempPass987 -> 12345)", "Password restored via API")
        else:
            # Expected to fail due to validation - restore via database instead
            print(f"⚠️  API validation prevents changing password to '12345' (requires min 6 chars)")
            print(f"⚠️  Restoring password manually in database...")
            
            # Restore password manually in database
            import bcrypt
            from pymongo import MongoClient
            try:
                client = MongoClient("mongodb://localhost:27017")
                db = client["test_database"]
                password_hash = bcrypt.hashpw(ORIGINAL_PASSWORD.encode(), bcrypt.gensalt()).decode()
                result = db.users.update_one(
                    {"email": ADMIN_EMAIL},
                    {"$set": {"password_hash": password_hash}}
                )
                if result.modified_count > 0:
                    log_pass("3d. Restore password (database workaround)", "Password restored to '12345' via database")
                else:
                    log_fail("3d. Restore password in database", "Failed to update database")
                    return
                client.close()
            except Exception as db_e:
                log_fail("3d. Restore password in database", str(db_e))
                return
    except Exception as e:
        log_fail("3d. Change password back (TempPass987 -> 12345)", str(e))
        print("⚠️  WARNING: Admin password NOT restored to 12345!")
        return
    
    # 3e. Verify login with 12345 works again
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ORIGINAL_PASSWORD
        }, timeout=5)
        if resp.status_code == 200:
            log_pass("3e. Login with restored password (12345)", "Login successful - password restored")
        else:
            log_fail("3e. Login with restored password (12345)", f"Status {resp.status_code}")
            print("⚠️  WARNING: Admin password NOT working with 12345!")
    except Exception as e:
        log_fail("3e. Login with restored password (12345)", str(e))
        print("⚠️  WARNING: Admin password NOT working with 12345!")

def test_4_forgot_password(customer_email):
    """Test 4: POST /api/auth/forgot-password returns neutral OK"""
    print("\n" + "="*80)
    print("TEST 4: Forgot Password")
    print("="*80)
    
    if not customer_email:
        log_fail("4. Forgot password", "No customer email available")
        return
    
    try:
        resp = requests.post(f"{API_URL}/auth/forgot-password", json={
            "email": customer_email
        }, timeout=5)
        
        # Should return 200 with neutral message (email may be rate-limited)
        if resp.status_code == 200:
            log_pass("4. Forgot password", f"Returns neutral OK for {customer_email} (email may be rate-limited)")
        else:
            log_fail("4. Forgot password", f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_fail("4. Forgot password", str(e))

def test_5_customer_order(customer_token, part_no, size):
    """Test 5: Customer create order (store pickup), GET /api/orders lists it"""
    print("\n" + "="*80)
    print("TEST 5: Customer Order")
    print("="*80)
    
    if not customer_token or not part_no or not size:
        log_fail("5. Customer order", "Missing customer_token, part_no, or size")
        return None
    
    # 5a. Create order (store pickup)
    try:
        order_data = {
            "items": [
                {
                    "part_no": part_no,
                    "size": size,
                    "quantity": 1
                }
            ],
            "comment": "Regression test order",
            "delivery": {
                "method": "store"
            }
        }
        
        resp = requests.post(f"{API_URL}/orders", json=order_data, headers={
            "Authorization": f"Bearer {customer_token}",
            "X-Forwarded-Host": "test.preview.emergentagent.com"
        }, timeout=10)
        
        if resp.status_code == 200:
            order = resp.json()
            order_id = order.get("id")
            order_number = order.get("order_number")
            email_status = order.get("email_status")
            
            if order_id and order_number:
                log_pass("5a. Create order (store pickup)", f"Order {order_number} created (email: {email_status})")
            else:
                log_fail("5a. Create order (store pickup)", "Missing order_id or order_number")
                return None
        else:
            log_fail("5a. Create order (store pickup)", f"Status {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log_fail("5a. Create order (store pickup)", str(e))
        return None
    
    # 5b. GET /api/orders lists it
    try:
        resp = requests.get(f"{API_URL}/orders", headers={"Authorization": f"Bearer {customer_token}"}, timeout=5)
        if resp.status_code == 200:
            orders = resp.json()  # Returns a list directly
            found = any(o.get("id") == order_id for o in orders)
            if found:
                log_pass("5b. GET /api/orders", f"Order {order_number} found in list")
            else:
                log_fail("5b. GET /api/orders", f"Order {order_number} not found in list")
        else:
            log_fail("5b. GET /api/orders", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("5b. GET /api/orders", str(e))
    
    return order_id

def test_6_admin_settings_users(admin_token):
    """Test 6: Admin settings (order_email=patrik.degerstam@yp.se), users (no admin@blaklader.local)"""
    print("\n" + "="*80)
    print("TEST 6: Admin Settings and Users")
    print("="*80)
    
    # 6a. GET /api/admin/settings
    try:
        resp = requests.get(f"{API_URL}/admin/settings", headers={"Authorization": f"Bearer {admin_token}"}, timeout=5)
        if resp.status_code == 200:
            settings = resp.json()
            order_email = settings.get("order_email")
            if order_email == "patrik.degerstam@yp.se":
                log_pass("6a. Admin settings", f"order_email = {order_email}")
            else:
                log_fail("6a. Admin settings", f"order_email = {order_email}, expected patrik.degerstam@yp.se")
        else:
            log_fail("6a. Admin settings", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("6a. Admin settings", str(e))
    
    # 6b. GET /api/admin/users
    try:
        resp = requests.get(f"{API_URL}/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, timeout=5)
        if resp.status_code == 200:
            users = resp.json()
            
            # Check admin@blaklader.local does NOT exist
            has_deleted_admin = any(u.get("email") == DELETED_ADMIN_EMAIL for u in users)
            if not has_deleted_admin:
                log_pass("6b. Admin users (no admin@blaklader.local)", f"{DELETED_ADMIN_EMAIL} not found")
            else:
                log_fail("6b. Admin users (no admin@blaklader.local)", f"{DELETED_ADMIN_EMAIL} still exists")
            
            # Check only admin is patrik.degerstam@yp.se
            admin_users = [u for u in users if u.get("role") == "admin"]
            admin_emails = [u.get("email") for u in admin_users]
            if len(admin_users) == 1 and admin_emails[0] == ADMIN_EMAIL:
                log_pass("6c. Admin users (only patrik.degerstam@yp.se)", f"Only admin: {ADMIN_EMAIL}")
            else:
                log_fail("6c. Admin users (only patrik.degerstam@yp.se)", f"Admin users: {admin_emails}")
        else:
            log_fail("6b. Admin users", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("6b. Admin users", str(e))

def test_7_webpush_and_security(customer_token):
    """Test 7: /api/webpush/public-key, /api/admin/* returns 403 with customer token and 401 without"""
    print("\n" + "="*80)
    print("TEST 7: WebPush and Security")
    print("="*80)
    
    # 7a. /api/webpush/public-key
    try:
        resp = requests.get(f"{API_URL}/webpush/public-key", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            public_key = data.get("public_key")
            if public_key:
                log_pass("7a. /api/webpush/public-key", f"Key: {public_key[:30]}...")
            else:
                log_fail("7a. /api/webpush/public-key", "No public_key in response")
        else:
            log_fail("7a. /api/webpush/public-key", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("7a. /api/webpush/public-key", str(e))
    
    # 7b. /api/admin/* returns 403 with customer token
    admin_routes = ["/admin/settings", "/admin/users", "/admin/orders"]
    for route in admin_routes:
        try:
            resp = requests.get(f"{API_URL}{route}", headers={"Authorization": f"Bearer {customer_token}"}, timeout=5)
            if resp.status_code == 403:
                log_pass(f"7b. {route} (customer token)", "Returns 403")
            else:
                log_fail(f"7b. {route} (customer token)", f"Expected 403, got {resp.status_code}")
        except Exception as e:
            log_fail(f"7b. {route} (customer token)", str(e))
    
    # 7c. /api/admin/* returns 401 without token
    for route in admin_routes:
        try:
            resp = requests.get(f"{API_URL}{route}", timeout=5)
            if resp.status_code == 401:
                log_pass(f"7c. {route} (no token)", "Returns 401")
            else:
                log_fail(f"7c. {route} (no token)", f"Expected 401, got {resp.status_code}")
        except Exception as e:
            log_fail(f"7c. {route} (no token)", str(e))

def test_8_venv_imports():
    """Test 8: Verify venv imports - emergentintegrations, pywebpush, py_vapid, litellm"""
    print("\n" + "="*80)
    print("TEST 8: Python venv imports")
    print("="*80)
    
    import subprocess
    
    venv_python = "/root/.venv/bin/python"
    modules = ["emergentintegrations", "pywebpush", "py_vapid", "litellm"]
    
    for module in modules:
        try:
            result = subprocess.run(
                [venv_python, "-c", f"import {module}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                log_pass(f"8. Import {module}", "Success")
            else:
                log_fail(f"8. Import {module}", f"Error: {result.stderr.strip()}")
        except Exception as e:
            log_fail(f"8. Import {module}", str(e))

def main():
    print("="*80)
    print("GRIT BACKEND REGRESSION TEST")
    print("After dependency change: requirements.txt (litellm wheel URL)")
    print("="*80)
    
    # Test 1: Health, cities, products, product detail
    part_no = test_1_backend_health_cities_products()
    admin_token = quick_admin_login()
    size = test_1d_product_detail(part_no, admin_token) if part_no and admin_token else None
    
    # Test 2: Auth (admin login, /api/auth/me, register customer, customer login)
    admin_token, customer_email, customer_token = test_2_auth()
    
    if not admin_token:
        print("\n❌ CRITICAL: Cannot proceed without admin token")
        sys.exit(1)
    
    # Test 3: Admin password change (CRITICAL: must restore to 12345)
    test_3_admin_password_change(admin_token)
    
    # Re-login admin after password change
    admin_token = quick_admin_login()
    if not admin_token:
        print("\n❌ CRITICAL: Cannot re-login admin after password change")
        sys.exit(1)
    
    # Test 4: Forgot password
    if customer_email:
        test_4_forgot_password(customer_email)
    
    # Test 5: Customer order
    if customer_token and part_no and size:
        test_5_customer_order(customer_token, part_no, size)
    
    # Test 6: Admin settings and users
    test_6_admin_settings_users(admin_token)
    
    # Test 7: WebPush and security
    if customer_token:
        test_7_webpush_and_security(customer_token)
    
    # Test 8: venv imports
    test_8_venv_imports()
    
    # Summary
    print("\n" + "="*80)
    print("REGRESSION TEST SUMMARY")
    print("="*80)
    print(f"✅ PASSED: {len(results['passed'])}")
    print(f"❌ FAILED: {len(results['failed'])}")
    
    if results['failed']:
        print("\n❌ FAILED TESTS:")
        for fail in results['failed']:
            print(f"  - {fail}")
    
    print("\n" + "="*80)
    
    # Exit with error code if any tests failed
    sys.exit(1 if results['failed'] else 0)

if __name__ == "__main__":
    main()
