"""
Diagnostic script — tests every admin and user function independently.
Run: python test_everything.py
"""

import sys
sys.path.insert(0, ".")


print("=== 1. Database Init ===")
from storage import init_db, seed_default_data, ALL_GENERATORS
init_db()
seed_default_data()
print("OK — DB initialized and seeded")

print("\n=== 2. License Validation ===")
from storage import validate_license
r = validate_license("ADMIN-DEFAULT-KEY")
assert r is not None, "FAIL: ADMIN-DEFAULT-KEY not found!"
assert r["permissions"] == ALL_GENERATORS, "FAIL: Permissions mismatch!"
print(f"OK — Admin key valid, perms={r['permissions']}")

print("\n=== 3. API Login ===")
from api import APIClient
api = APIClient()
r = api.login("ADMIN-DEFAULT-KEY")
assert r["success"], f"FAIL: Login failed: {r}"
print(f"OK — Logged in as {r['username']}")

print("\n=== 4. API Profile ===")
r = api.get_profile()
assert r["success"], f"FAIL: {r}"
print(f"OK — Profile: {r['username']}, status={r['license_status']}")

print("\n=== 5. API Permissions ===")
r = api.get_permissions()
assert r["success"], f"FAIL: {r}"
print(f"OK — Perms: {r['permissions']}")

print("\n=== 6. API Generate ===")
r = api.generate_account("Discord")
assert r["success"], f"FAIL: {r}"
print(f"OK — Generated: {r['account']['email']}:{r['account']['password']}")

print("\n=== 7. API Stock ===")
r = api.get_stock()
assert r["success"], f"FAIL: {r}"
cats = list(r["categories"].keys())
print(f"OK — Stock: {len(cats)} categories")

print("\n=== 8. AdminAPI — List Licenses ===")
from api import AdminAPI
r = AdminAPI.list_licenses()
assert r["success"], f"FAIL: {r}"
print(f"OK — {len(r['licenses'])} licenses")

print("\n=== 9. AdminAPI — Create License ===")
r = AdminAPI.create_license(
    username="TestUser",
    permissions=["Discord", "Steam"],
    daily_limit=3,
    expiry_days=7,
    max_uses=10,
)
assert r["success"], f"FAIL: {r}"
print(f"OK — Created key: {r['license_key']}")

print("\n=== 10. AdminAPI — Get License ===")
r2 = AdminAPI.get_license(r["id"])
assert r2["success"], f"FAIL: {r2}"
assert r2["username"] == "TestUser"
print(f"OK — Retrieved key for {r2['username']}")

print("\n=== 11. AdminAPI — Toggle License ===")
r2 = AdminAPI.toggle_license(r["id"])
assert r2["success"], f"FAIL: {r2}"
print(f"OK — Toggled to {r2['status']}")
r2 = AdminAPI.toggle_license(r["id"])
print(f"OK — Toggled back to {r2['status']}")

print("\n=== 12. AdminAPI — Delete License ===")
r2 = AdminAPI.delete_license(r["id"])
assert r2["success"], f"FAIL: {r2}"
print(f"OK — Deleted")

print("\n=== 13. AdminAPI — Add Stock ===")
r = AdminAPI.add_stock("Steam", "test@stock.com", "test_pass")
assert r["success"], f"FAIL: {r}"
print(f"OK — Added stock: {r}")

print("\n=== 14. AdminAPI — Bulk Stock ===")
r = AdminAPI.add_stock_bulk("Discord", "bulk1@test.com:pw1\nbulk2@test.com:pw2\ninvalid_line")
assert r["success"], f"FAIL: {r}"
assert r["added"] == 2, f"FAIL: expected 2 added, got {r}"
print(f"OK — Bulk: added={r['added']}, dup={r['duplicates']}")

print("\n=== 15. AdminAPI — Get Stock ===")
r = AdminAPI.get_stock()
assert r["success"], f"FAIL: {r}"
print(f"OK — {len(r['accounts'])} accounts, categories: {r['categories']}")

print("\n=== 16. AdminAPI — Export Stock ===")
r = AdminAPI.export_stock()
assert r["success"], f"FAIL: {r}"
print(f"OK — {len(r['data'].splitlines())} lines exported")

print("\n=== 17. AdminAPI — Dedup Stock ===")
from storage import remove_duplicates
r = remove_duplicates()
print(f"OK — Removed {r['removed']} duplicates")

print("\n=== 18. AdminAPI — Clear Stock ===")
r = AdminAPI.clear_stock("Discord")
assert r["success"], f"FAIL: {r}"
print(f"OK — Cleared {r['deleted']} Discord accounts")

print("\n=== 19. AdminAPI — Get Stats ===")
r = AdminAPI.get_stats()
assert r["success"], f"FAIL: {r}"
print(f"OK — Licenses: {r['licenses']}, Stock: {r['stock']}, Gen: {r['generations']}")

print("\n=== 20. AdminAPI — Get Logs ===")
r = AdminAPI.get_logs()
assert r["success"], f"FAIL: {r}"
print(f"OK — Admin logs: {len(r['admin_logs'])}, Gen logs: {len(r['gen_logs'])}")

print("\n" + "=" * 50)
print("ALL 20 TESTS PASSED")
print("=" * 50)
