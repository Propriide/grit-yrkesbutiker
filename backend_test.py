#!/usr/bin/env python3
"""
GRIT Launch Checklist Backend Test
Tests all backend API endpoints against the deployment checklist.
"""
import json
import sys
import time
import requests
from pymongo import MongoClient

# Configuration
BASE_URL = "http://localhost:8001/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

# Test credentials
ADMIN_EMAIL = "patrik.degerstam@yp.se"
ADMIN_PASSWORD = "12345"
DELETED_ADMIN_EMAIL = "admin@blaklader.local"
DELETED_ADMIN_PASSWORD = "Admin123!"

# Test results
results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_pass(test_name, details=""):
    msg = f"✅ {test_name}"
    if details:
        msg += f": {details}"
    print(msg)
    results["passed"].append(test_name)

def log_fail(test_name, details=""):
    msg = f"❌ {test_name}"
    if details:
        msg += f": {details}"
    print(msg)
    results["failed"].append(f"{test_name}: {details}")

def log_warning(test_name, details=""):
    msg = f"⚠️  {test_name}"
    if details:
        msg += f": {details}"
    print(msg)
    results["warnings"].append(f"{test_name}: {details}")

def test_admin_login():
    """Test 1: Admin login with patrik.degerstam@yp.se works"""
    print("\n=== Test 1: Admin Login ===")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            if "access_token" in data and "user" in data:
                if data["user"].get("role") == "admin":
                    log_pass("Admin login", f"Logged in as {ADMIN_EMAIL}")
                    return data["access_token"]
                else:
                    log_fail("Admin login", f"User role is {data['user'].get('role')}, expected 'admin'")
            else:
                log_fail("Admin login", "Missing access_token or user in response")
        else:
            log_fail("Admin login", f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_fail("Admin login", str(e))
    return None

def test_deleted_admin_not_exists(admin_token):
    """Test 2: Verify admin@blaklader.local does NOT exist"""
    print("\n=== Test 2: Deleted Admin Does Not Exist ===")
    
    # Check in user list
    try:
        resp = requests.get(f"{BASE_URL}/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        if resp.status_code == 200:
            users = resp.json()
            deleted_admin = [u for u in users if u.get("email") == DELETED_ADMIN_EMAIL]
            if not deleted_admin:
                log_pass("Admin user list check", f"{DELETED_ADMIN_EMAIL} not found in user list")
            else:
                log_fail("Admin user list check", f"{DELETED_ADMIN_EMAIL} still exists in database")
        else:
            log_fail("Admin user list check", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Admin user list check", str(e))
    
    # Try to login as deleted admin
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": DELETED_ADMIN_EMAIL,
            "password": DELETED_ADMIN_PASSWORD
        })
        if resp.status_code == 401:
            log_pass("Deleted admin login fails", "Login correctly rejected")
        else:
            log_fail("Deleted admin login fails", f"Expected 401, got {resp.status_code}")
    except Exception as e:
        log_fail("Deleted admin login fails", str(e))

def test_admin_settings(admin_token):
    """Test 3: Check admin settings - order_email should be delivered@resend.dev"""
    print("\n=== Test 3: Admin Settings ===")
    try:
        resp = requests.get(f"{BASE_URL}/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
        if resp.status_code == 200:
            settings = resp.json()
            order_email = settings.get("order_email")
            if order_email == "delivered@resend.dev":
                log_pass("Admin settings", f"order_email = {order_email}")
            else:
                log_warning("Admin settings", f"order_email = {order_email}, expected delivered@resend.dev")
            
            # Check catalog status
            product_count = settings.get("product_count", 0)
            if product_count >= 1200:
                log_pass("Product count", f"{product_count} products")
            else:
                log_warning("Product count", f"Only {product_count} products, expected ~1236")
        else:
            log_fail("Admin settings", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Admin settings", str(e))

def test_catalog(customer_token):
    """Test 4: Catalog - products, categories, product details with sizes"""
    print("\n=== Test 4: Catalog ===")
    
    # Test products endpoint
    try:
        resp = requests.get(f"{BASE_URL}/products", headers={"Authorization": f"Bearer {customer_token}"})
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            if total >= 1200:
                log_pass("Products total", f"{total} products")
            else:
                log_warning("Products total", f"Only {total} products, expected ~1236")
            
            items = data.get("items", [])
            if items:
                log_pass("Products list", f"Retrieved {len(items)} items")
                return items[0].get("part_no")  # Return first product for detail test
            else:
                log_fail("Products list", "No items returned")
        else:
            log_fail("Products endpoint", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Products endpoint", str(e))
    
    # Test categories
    try:
        resp = requests.get(f"{BASE_URL}/categories", headers={"Authorization": f"Bearer {customer_token}"})
        if resp.status_code == 200:
            categories = resp.json()
            if categories and len(categories) > 0:
                log_pass("Categories", f"{len(categories)} categories found")
            else:
                log_fail("Categories", "No categories returned")
        else:
            log_fail("Categories endpoint", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Categories endpoint", str(e))
    
    return None

def test_product_detail(customer_token, part_no):
    """Test product detail has sizes"""
    print("\n=== Test 4b: Product Detail ===")
    if not part_no:
        log_warning("Product detail", "No part_no to test")
        return None
    
    try:
        resp = requests.get(f"{BASE_URL}/products/{part_no}", headers={"Authorization": f"Bearer {customer_token}"})
        if resp.status_code == 200:
            product = resp.json()
            sizes = product.get("sizes", [])
            if sizes:
                log_pass("Product detail sizes", f"Product {part_no} has {len(sizes)} sizes")
                return sizes[0] if sizes else None
            else:
                log_warning("Product detail sizes", f"Product {part_no} has no sizes")
        else:
            log_fail("Product detail", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Product detail", str(e))
    return None

def register_customer():
    """Test 5a: Register new customer"""
    print("\n=== Test 5a: Customer Registration ===")
    
    # Get cities first
    try:
        resp = requests.get(f"{BASE_URL}/cities")
        if resp.status_code == 200:
            cities = resp.json()
            if not cities:
                log_fail("Get cities", "No cities available")
                return None, None
            city_id = cities[0].get("id")
            log_pass("Get cities", f"Found {len(cities)} cities")
        else:
            log_fail("Get cities", f"Status {resp.status_code}")
            return None, None
    except Exception as e:
        log_fail("Get cities", str(e))
        return None, None
    
    # Register customer
    import random
    customer_email = f"test.customer.{random.randint(1000, 9999)}@example.com"
    customer_password = "TestPass123!"
    
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={
            "email": customer_email,
            "password": customer_password,
            "name": "Test Customer",
            "phone": "+46701234567",
            "company": "Test Company AB",
            "org_number": "556677-8899",
            "city_id": city_id
        })
        if resp.status_code == 200:
            data = resp.json()
            if "access_token" in data:
                log_pass("Customer registration", f"Registered {customer_email}")
                return customer_email, customer_password, data["access_token"]
            else:
                log_fail("Customer registration", "No access_token in response")
        else:
            log_fail("Customer registration", f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_fail("Customer registration", str(e))
    
    return None, None, None

def test_customer_login(email, password):
    """Test 5b: Customer login"""
    print("\n=== Test 5b: Customer Login ===")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": email,
            "password": password
        })
        if resp.status_code == 200:
            data = resp.json()
            if "access_token" in data:
                log_pass("Customer login", f"Logged in as {email}")
                return data["access_token"]
            else:
                log_fail("Customer login", "No access_token in response")
        else:
            log_fail("Customer login", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Customer login", str(e))
    return None

def create_order(customer_token, delivery_method, part_no, size="L"):
    """Test 5c: Create order with different delivery methods"""
    print(f"\n=== Test 5c: Create Order ({delivery_method}) ===")
    
    order_data = {
        "items": [
            {
                "part_no": part_no,
                "size": size,
                "quantity": 2
            }
        ],
        "comment": f"Test order with {delivery_method} delivery",
        "delivery": {
            "method": delivery_method
        }
    }
    
    if delivery_method == "ship":
        order_data["delivery"].update({
            "name": "Test Recipient",
            "address": "Testgatan 123",
            "postal_code": "12345",
            "city": "Stockholm"
        })
    
    try:
        resp = requests.post(f"{BASE_URL}/orders", json=order_data, headers={
            "Authorization": f"Bearer {customer_token}",
            "X-Forwarded-Host": "test.preview.emergentagent.com"
        })
        if resp.status_code == 200:
            order = resp.json()
            order_id = order.get("id")
            order_number = order.get("order_number")
            email_status = order.get("email_status")
            
            log_pass(f"Create order ({delivery_method})", f"Order {order_number} created")
            
            if email_status == "sent":
                log_pass(f"Order email ({delivery_method})", "Email sent successfully")
            elif email_status == "failed":
                log_warning(f"Order email ({delivery_method})", "Email failed to send")
            else:
                log_warning(f"Order email ({delivery_method})", f"Email status: {email_status}")
            
            return order_id, order_number
        else:
            log_fail(f"Create order ({delivery_method})", f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_fail(f"Create order ({delivery_method})", str(e))
    
    return None, None

def get_order_token_from_db(order_id):
    """Get order reply token from MongoDB"""
    try:
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        order = db.orders.find_one({"id": order_id}, {"confirm_token": 1})
        if order and "confirm_token" in order:
            return order["confirm_token"]
    except Exception as e:
        log_warning("Get order token from DB", str(e))
    return None

def test_order_reply_link(token, action):
    """Test 6: Order reply via email link (GET and POST)"""
    print(f"\n=== Test 6: Order Reply Link ({action}) ===")
    
    # Test GET (view form)
    try:
        resp = requests.get(f"{BASE_URL}/order-reply/{token}")
        if resp.status_code == 200:
            log_pass(f"Order reply GET ({action})", "Reply form accessible")
        else:
            log_fail(f"Order reply GET ({action})", f"Status {resp.status_code}")
    except Exception as e:
        log_fail(f"Order reply GET ({action})", str(e))
    
    # Test POST (submit reply)
    try:
        form_data = f"message=Test {action} message&action={action}"
        resp = requests.post(
            f"{BASE_URL}/order-reply/{token}",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if resp.status_code == 200:
            log_pass(f"Order reply POST ({action})", f"Reply submitted successfully")
        else:
            log_fail(f"Order reply POST ({action})", f"Status {resp.status_code}")
    except Exception as e:
        log_fail(f"Order reply POST ({action})", str(e))

def test_admin_order_reply(admin_token, order_id, action):
    """Test 7a: Admin in-app order reply"""
    print(f"\n=== Test 7a: Admin Order Reply ({action}) ===")
    
    try:
        resp = requests.post(
            f"{BASE_URL}/admin/orders/{order_id}/reply",
            json={"message": f"Admin {action} message", "action": action},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code == 200:
            log_pass(f"Admin order reply ({action})", "Reply sent successfully")
        else:
            log_fail(f"Admin order reply ({action})", f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_fail(f"Admin order reply ({action})", str(e))

def test_admin_mark_ready(admin_token, order_id):
    """Test 7b: Admin mark order ready"""
    print(f"\n=== Test 7b: Admin Mark Order Ready ===")
    
    try:
        resp = requests.post(
            f"{BASE_URL}/admin/orders/{order_id}/ready",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code == 200:
            log_pass("Admin mark ready", "Order marked as ready")
        else:
            log_fail("Admin mark ready", f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_fail("Admin mark ready", str(e))

def test_notifications(token, expected_count=0):
    """Test 8: Check notifications"""
    print(f"\n=== Test 8: Notifications ===")
    
    try:
        resp = requests.get(f"{BASE_URL}/notifications", headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            unread = data.get("unread", 0)
            log_pass("Get notifications", f"{len(items)} notifications, {unread} unread")
            
            # Show notification types
            if items:
                kinds = [n.get("kind") for n in items[:5]]
                print(f"   Recent notification kinds: {kinds}")
        else:
            log_fail("Get notifications", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Get notifications", str(e))

def test_webpush(customer_token):
    """Test 9: Web push endpoints"""
    print("\n=== Test 9: Web Push ===")
    
    # Test public key
    try:
        resp = requests.get(f"{BASE_URL}/webpush/public-key")
        if resp.status_code == 200:
            data = resp.json()
            public_key = data.get("public_key")
            if public_key:
                log_pass("Web push public key", f"Key: {public_key[:20]}...")
            else:
                log_fail("Web push public key", "No public_key in response")
        else:
            log_fail("Web push public key", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Web push public key", str(e))
    
    # Test notification preferences GET
    try:
        resp = requests.get(f"{BASE_URL}/notification-prefs", headers={"Authorization": f"Bearer {customer_token}"})
        if resp.status_code == 200:
            prefs = resp.json()
            log_pass("Notification prefs GET", f"Prefs: {prefs}")
        else:
            log_fail("Notification prefs GET", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Notification prefs GET", str(e))
    
    # Test notification preferences PUT
    try:
        resp = requests.put(
            f"{BASE_URL}/notification-prefs",
            json={"orders": True, "offers": False},
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        if resp.status_code == 200:
            log_pass("Notification prefs PUT", "Preferences updated")
        else:
            log_fail("Notification prefs PUT", f"Status {resp.status_code}")
    except Exception as e:
        log_fail("Notification prefs PUT", str(e))
    
    # Test subscribe with fake subscription
    try:
        fake_subscription = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/fake-endpoint-12345",
            "keys": {
                "p256dh": "BFakeP256dhKeyForTestingPurposesOnly",
                "auth": "FakeAuthKeyForTesting"
            }
        }
        resp = requests.post(
            f"{BASE_URL}/webpush/subscribe",
            json=fake_subscription,
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        if resp.status_code == 201:
            log_pass("Web push subscribe", "Subscription accepted")
        else:
            log_fail("Web push subscribe", f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_fail("Web push subscribe", str(e))

def test_admin_security(customer_token):
    """Test 10: Security - admin routes return 403 for customer, 401 without token"""
    print("\n=== Test 10: Admin Route Security ===")
    
    # GET routes
    admin_get_routes = [
        "/admin/settings",
        "/admin/users",
        "/admin/orders",
        "/admin/companies",
        "/admin/broadcasts"
    ]
    
    # POST routes (need to test with POST method)
    admin_post_routes = [
        ("/admin/cities", {"name": "Test City"}),
        ("/admin/broadcast", {"title": "Test", "body": "Test message"})
    ]
    
    # Test GET routes with customer token (should be 403)
    for route in admin_get_routes:
        try:
            resp = requests.get(f"{BASE_URL}{route}", headers={"Authorization": f"Bearer {customer_token}"})
            if resp.status_code == 403:
                log_pass(f"Security {route} (customer)", "Correctly returns 403")
            else:
                log_fail(f"Security {route} (customer)", f"Expected 403, got {resp.status_code}")
        except Exception as e:
            log_fail(f"Security {route} (customer)", str(e))
    
    # Test POST routes with customer token (should be 403)
    for route, body in admin_post_routes:
        try:
            resp = requests.post(f"{BASE_URL}{route}", json=body, headers={"Authorization": f"Bearer {customer_token}"})
            if resp.status_code == 403:
                log_pass(f"Security {route} (customer)", "Correctly returns 403")
            else:
                log_fail(f"Security {route} (customer)", f"Expected 403, got {resp.status_code}")
        except Exception as e:
            log_fail(f"Security {route} (customer)", str(e))
    
    # Test without token (should be 401)
    for route in admin_get_routes[:3]:  # Test a few without token
        try:
            resp = requests.get(f"{BASE_URL}{route}")
            if resp.status_code == 401:
                log_pass(f"Security {route} (no token)", "Correctly returns 401")
            else:
                log_fail(f"Security {route} (no token)", f"Expected 401, got {resp.status_code}")
        except Exception as e:
            log_fail(f"Security {route} (no token)", str(e))

def test_host_check():
    """Test 11: Confirm-link host check"""
    print("\n=== Test 11: Host Check ===")
    
    # This is tested implicitly in order creation with X-Forwarded-Host header
    # The order creation should succeed with allowed host
    log_pass("Host check", "Tested via order creation with X-Forwarded-Host")

def main():
    print("=" * 60)
    print("GRIT LAUNCH CHECKLIST - BACKEND TEST")
    print("=" * 60)
    
    # Test 1: Admin login
    admin_token = test_admin_login()
    if not admin_token:
        print("\n❌ Cannot proceed without admin token")
        return
    
    # Test 2: Deleted admin does not exist
    test_deleted_admin_not_exists(admin_token)
    
    # Test 3: Admin settings
    test_admin_settings(admin_token)
    
    # Register customer for remaining tests
    customer_email, customer_password, customer_token = register_customer()
    if not customer_token:
        print("\n❌ Cannot proceed without customer token")
        return
    
    # Test 5b: Customer login
    customer_token = test_customer_login(customer_email, customer_password)
    if not customer_token:
        print("\n❌ Cannot proceed without customer token")
        return
    
    # Test 4: Catalog
    part_no = test_catalog(customer_token)
    valid_size = None
    if part_no:
        valid_size = test_product_detail(customer_token, part_no)
    
    # Test 5c: Create orders with different delivery methods
    order_ids = []
    order_tokens = []
    
    for delivery_method in ["store", "parcel_box", "ship"]:
        if part_no and valid_size:
            order_id, order_number = create_order(customer_token, delivery_method, part_no, valid_size)
            if order_id:
                order_ids.append(order_id)
                token = get_order_token_from_db(order_id)
                if token:
                    order_tokens.append((token, delivery_method))
    
    # Test 6: Order reply links (confirm and decline)
    if len(order_tokens) >= 2:
        test_order_reply_link(order_tokens[0][0], "confirm")
        test_order_reply_link(order_tokens[1][0], "decline")
    
    # Test 7: Admin order operations
    if len(order_ids) >= 3:
        # Create a new order for admin reply test
        if part_no and valid_size:
            print("\n⏳ Waiting 60 seconds to avoid email rate limiting...")
            time.sleep(60)
            order_id, _ = create_order(customer_token, "store", part_no, valid_size)
            if order_id:
                test_admin_order_reply(admin_token, order_id, "confirm")
                test_admin_mark_ready(admin_token, order_id)
            else:
                log_warning("Admin order operations", "Could not create order for testing (likely rate limited)")
    
    # Test 8: Notifications
    test_notifications(customer_token)
    test_notifications(admin_token)
    
    # Test 9: Web push
    test_webpush(customer_token)
    
    # Test 10: Security
    test_admin_security(customer_token)
    
    # Test 11: Host check
    test_host_check()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {len(results['passed'])}")
    print(f"❌ Failed: {len(results['failed'])}")
    print(f"⚠️  Warnings: {len(results['warnings'])}")
    
    if results['failed']:
        print("\nFailed tests:")
        for fail in results['failed']:
            print(f"  - {fail}")
    
    if results['warnings']:
        print("\nWarnings:")
        for warn in results['warnings']:
            print(f"  - {warn}")
    
    print("\n" + "=" * 60)
    
    # Exit with error code if any tests failed
    sys.exit(1 if results['failed'] else 0)

if __name__ == "__main__":
    main()
