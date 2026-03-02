#!/usr/bin/env python3
"""HWID Implementation Verification Script"""

import os

print("="*70)
print("HWID IMPLEMENTATION VERIFICATION")
print("="*70)

checks = []

# 1. Check models.py
print("\n1. UserDevice Model (app/db/models.py)")
with open('app/db/models.py', 'r') as f:
    content = f.read()
    if 'disabled = Column(Boolean, nullable=False, default=False)' in content:
        print("   ✅ disabled field exists")
        checks.append(True)
    else:
        print("   ❌ disabled field missing")
        checks.append(False)

# 2. Check crud.py functions
print("\n2. CRUD Functions (app/db/crud.py)")
with open('app/db/crud.py', 'r') as f:
    content = f.read()
    
    funcs = [
        ('check_hwid_limit', 'def check_hwid_limit'),
        ('delete_user_device', 'def delete_user_device'),
        ('delete_all_user_devices', 'def delete_all_user_devices'),
        ('get_user_devices', 'def get_user_devices'),
        ('device_disabled reason', '"device_disabled"'),
        ('limit_reached reason', '"limit_reached"'),
        ('Marks as disabled', 'device.disabled = True'),
    ]
    
    for name, pattern in funcs:
        if pattern in content:
            print(f"   ✅ {name}")
            checks.append(True)
        else:
            print(f"   ❌ {name}")
            checks.append(False)

# 3. Check API endpoints
print("\n3. API Endpoints (app/routers/user.py)")
with open('app/routers/user.py', 'r') as f:
    content = f.read()
    
    endpoints = [
        ('GET /devices', '@router.get("/user/{username}/devices")'),
        ('DELETE /devices/{id}', '@router.delete("/user/{username}/devices/{device_id}")'),
        ('DELETE all devices', 'delete_all_user_devices'),
    ]
    
    for name, pattern in endpoints:
        if pattern in content:
            print(f"   ✅ {name}")
            checks.append(True)
        else:
            print(f"   ❌ {name}")
            checks.append(False)

# 4. Check subscription.py
print("\n4. Subscription Enforcement (app/routers/subscription.py)")
with open('app/routers/subscription.py', 'r') as f:
    content = f.read()
    
    patterns = [
        ('_enforce_hwid function', 'def _enforce_hwid'),
        ('check_hwid_limit call', 'check_hwid_limit'),
        ('x-hwid header', 'x-hwid'),
    ]
    
    for name, pattern in patterns:
        if pattern in content:
            print(f"   ✅ {name}")
            checks.append(True)
        else:
            print(f"   ❌ {name}")
            checks.append(False)

# 5. Check migration
print("\n5. Database Migration")
migration_file = 'app/db/migrations/versions/a1b2c3d4e5f6_add_disabled_field_to_user_devices.py'
if os.path.exists(migration_file):
    print(f"   ✅ Migration file exists")
    checks.append(True)
    with open(migration_file, 'r') as f:
        content = f.read()
        if 'add_column' in content and 'disabled' in content:
            print(f"   ✅ Adds disabled column")
            checks.append(True)
        else:
            print(f"   ❌ Missing add_column")
            checks.append(False)
else:
    print(f"   ❌ Migration file missing")
    checks.append(False)

# 6. Check Dashboard
print("\n6. Dashboard Components")
files_to_check = [
    ('DeviceManagement.tsx', 'app/dashboard/src/components/DeviceManagement.tsx'),
    ('UserDialog.tsx', 'app/dashboard/src/components/UserDialog.tsx'),
    ('User.ts types', 'app/dashboard/src/types/User.ts'),
    ('DashboardContext.tsx', 'app/dashboard/src/contexts/DashboardContext.tsx'),
]

for name, filepath in files_to_check:
    if os.path.exists(filepath):
        print(f"   ✅ {name}")
        checks.append(True)
    else:
        print(f"   ❌ {name}")
        checks.append(False)

# 7. Check translations
print("\n7. Translations")
for lang in ['en', 'fa', 'ru', 'zh']:
    filepath = f'app/dashboard/public/statics/locales/{lang}.json'
    with open(filepath, 'r') as f:
        content = f.read()
        if 'userDialog.blocked' in content and 'userDialog.active' in content:
            print(f"   ✅ {lang}.json")
            checks.append(True)
        else:
            print(f"   ❌ {lang}.json")
            checks.append(False)

# Summary
print("\n" + "="*70)
print(f"VERIFICATION RESULTS")
print("="*70)
passed = sum(checks)
total = len(checks)
print(f"Passed: {passed}/{total} ({passed/total*100:.1f}%)")

if passed == total:
    print("\n🎉 ALL CHECKS PASSED! HWID implementation is complete.")
else:
    print(f"\n⚠️  {total - passed} check(s) failed.")

print("="*70)
