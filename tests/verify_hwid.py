#!/usr/bin/env python3
"""
HWID Device Limiting - Code Verification Script
Verifies implementation by checking code structure
"""

import os
import re

def check_file_contains(filepath, patterns, description):
    """Check if file contains all required patterns"""
    print(f"\n{'='*70}")
    print(f"Checking: {description}")
    print(f"File: {filepath}")
    print('='*70)
    
    if not os.path.exists(filepath):
        print(f"❌ FAIL: File not found: {filepath}")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    all_found = True
    for pattern_desc, pattern in patterns:
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            print(f"✅ {pattern_desc}")
        else:
            print(f"❌ MISSING: {pattern_desc}")
            all_found = False
    
    return all_found

# Track results
results = []

# Test 1: Check UserDevice model has disabled field
results.append(check_file_contains(
    'app/db/models.py',
    [
        ("UserDevice class definition", r"class UserDevice\(Base\):"),
        ("disabled field", r"disabled\s*=\s*Column\(Boolean"),
        ("default=False", r"default\s*=\s*False"),
        ("UniqueConstraint hwid, user_id", r"UniqueConstraint.*hwid.*user_id"),
    ],
    "UserDevice Model - disabled field"
))

# Test 2: Check CRUD functions
results.append(check_file_contains(
    'app/db/crud.py',
    [
        ("check_hwid_limit function", r"def check_hwid_limit\(db.*hwid.*\):"),
        ("device_disabled check", r"device_disabled"),
        ("limit_reached check", r"limit_reached"),
        ("no_hwid check", r"no_hwid"),
        ("delete_user_device function", r"def delete_user_device\(db.*device_id.*user_id.*\):"),
        ("Marks as disabled", r"device\.disabled\s*=\s*True"),
        ("delete_all_user_devices function", r"def delete_all_user_devices\(db.*user_id.*\):"),
        ("get_user_devices function", r"def get_user_devices\(db.*dbuser.*include_disabled.*\):"),
        ("Filter disabled=False", r"disabled\s*==\s*False"),
    ],
    "CRUD Functions"
))

# Test 3: Check API endpoints
results.append(check_file_contains(
    'app/routers/user.py',
    [
        ("GET /devices endpoint", r"@router\.get.*\/devices"),
        ("DELETE /devices/{device_id} endpoint", r"@router\.delete.*\/devices\/\{device_id\}"),
        ("DELETE /devices endpoint (all)", r"@router\.delete.*\/devices[\"']\)"),
        ("include_disabled=True", r"include_disabled\s*=\s*True"),
    ],
    "Admin API Endpoints"
))

# Test 4: Check subscription enforcement
results.append(check_file_contains(
    'app/routers/subscription.py',
    [
        ("_enforce_hwid function", r"def _enforce_hwid\(.*hwid.*\):"),
        ("check_hwid_limit call", r"check_hwid_limit"),
        ("device_disabled handling", r"device_disabled"),
        ("x-hwid header", r"x-hwid"),
        ("x-hwid-limit header", r"x-hwid-limit"),
    ],
    "Subscription HWID Enforcement"
))

# Test 5: Check Pydantic models
results.append(check_file_contains(
    'app/models/user.py',
    [
        ("UserDeviceResponse class", r"class UserDeviceResponse"),
        ("disabled field in response", r"disabled:\s*bool"),
    ],
    "Pydantic UserDeviceResponse Model"
))

# Test 6: Check migration file
migration_files = [f for f in os.listdir('app/db/migrations/versions') if 'disabled' in f.lower()]
if migration_files:
    print(f"\n{'='*70}")
    print("Database Migration")
    print('='*70)
    print(f"✅ Migration file found: {migration_files[0]}")
    
    with open(f'app/db/migrations/versions/{migration_files[0]}', 'r') as f:
        content = f.read()
    
    checks = [
        ("upgrade function", r"def upgrade\(\):"),
        ("add_column disabled", r"add_column.*disabled"),
        ("downgrade function", r"def downgrade\(\):"),
        ("drop_column disabled", r"drop_column.*disabled"),
    ]
    
    migration_ok = True
    for desc, pattern in checks:
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            print(f"✅ {desc}")
        else:
            print(f"❌ MISSING: {desc}")
            migration_ok = False
    
    results.append(migration_ok)
else:
    print(f"\n{'='*70}")
    print("Database Migration")
    print('='*70)
    print("❌ Migration file not found")
    results.append(False)

# Test 7: Check Dashboard types
results.append(check_file_contains(
    'app/dashboard/src/types/User.ts',
    [
        ("UserDevice type", r"export type UserDevice"),
        ("disabled field", r"disabled:\s*boolean"),
    ],
    "Dashboard TypeScript Types"
))

# Test 8: Check DeviceManagement component
results.append(check_file_contains(
    'app/dashboard/src/components/DeviceManagement.tsx',
    [
        ("DeviceManagement component", r"export const DeviceManagement"),
        ("Block device button", r"blockDevice"),
        ("disabled check", r"device\.disabled"),
        ("Active/blocked badges", r"active.*blocked"),
        ("Mobile responsive", r"isMobile|useBreakpointValue"),
        ("Delete all devices", r"deleteAllDevices"),
    ],
    "DeviceManagement React Component"
))

# Test 9: Check translations
print(f"\n{'='*70}")
print("Translations")
print('='*70)

translation_keys = [
    "userDialog.blocked",
    "userDialog.active",
    "userDialog.blockDevice",
    "userDialog.connectedDevices",
]

translations_ok = True
for lang in ['en', 'fa', 'ru', 'zh']:
    filepath = f'app/dashboard/public/statics/locales/{lang}.json'
    with open(filepath, 'r') as f:
        content = f.read()
    
    lang_ok = True
    for key in translation_keys:
        if key in content:
            print(f"✅ {lang}.json: {key}")
        else:
            print(f"❌ {lang}.json MISSING: {key}")
            lang_ok = False
            translations_ok = False

results.append(translations_ok)

# Test 10: Check UserDialog integration
results.append(check_file_contains(
    'app/dashboard/src/components/UserDialog.tsx',
    [
        ("DeviceManagement import", r"import.*DeviceManagement"),
        ("fetchUserDevices call", r"fetchUserDevices"),
        ("handleDeleteDevice function", r"handleDeleteDevice"),
        ("DeviceManagement usage", r"<DeviceManagement"),
        ("devices state", r"const \\[devices.*setDevices\\]"),
    ],
    "UserDialog Integration"
))

# Print summary
print(f"\n{'='*70}")
print("VERIFICATION SUMMARY")
print('='*70)

passed = sum(results)
total = len(results)
percentage = (passed / total * 100) if total > 0 else 0

print(f"Categories Checked: {total}")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {total - passed}")
print(f"Success Rate: {percentage:.1f}%")

if passed == total:
    print("\n🎉 ALL CHECKS PASSED! Implementation is complete.")
else:
    print(f"\n⚠️  {total - passed} check(s) failed. Review the output above.")

print("\n" + "="*70)

# Exit with appropriate code
exit(0 if passed == total else 1)
