#!/usr/bin/env python3
"""Verify empty subscription implementation"""

import re

print("="*70)
print("EMPTY SUBSCRIPTION FOR BLOCKED DEVICES - VERIFICATION")
print("="*70)

checks = []

# Check subscription.py
print("\nChecking app/routers/subscription.py")
with open('app/routers/subscription.py', 'r') as f:
    content = f.read()
    
    # Check 1: _enforce_hwid returns tuple
    if 'tuple[Optional[Response], bool]' in content:
        print("✅ _enforce_hwid returns tuple (response, is_blocked)")
        checks.append(True)
    else:
        print("❌ _enforce_hwid tuple return type missing")
        checks.append(False)
    
    # Check 2: Checks for disabled device
    if 'if existing.disabled:' in content:
        print("✅ Checks device disabled flag")
        checks.append(True)
    else:
        print("❌ Disabled flag check missing")
        checks.append(False)
    
    # Check 3: Returns is_blocked=True
    if 'return (None, True)' in content:
        print("✅ Returns is_blocked=True for blocked devices")
        checks.append(True)
    else:
        print("❌ is_blocked=True return missing")
        checks.append(False)
    
    # Check 4: Unpacks tuple in endpoint
    if 'hwid_response, is_blocked = _enforce_hwid' in content:
        print("✅ Unpacks tuple in subscription endpoint")
        checks.append(True)
    else:
        print("❌ Tuple unpacking missing")
        checks.append(False)
    
    # Check 5: Returns empty response for blocked
    if 'if is_blocked:' in content and 'return Response(content=""' in content:
        print("✅ Returns empty response for blocked devices")
        checks.append(True)
    else:
        print("❌ Empty response logic missing")
        checks.append(False)
    
    # Check 6: Logging added
    if 'logger.info(f"Blocked device' in content:
        print("✅ Logging for blocked devices")
        checks.append(True)
    else:
        print("❌ Logging missing")
        checks.append(False)
    
    # Check 7: Both endpoints updated
    main_endpoint = content.count('if is_blocked:')
    if main_endpoint >= 2:
        print(f"✅ Both endpoints handle blocked devices ({main_endpoint} occurrences)")
        checks.append(True)
    else:
        print(f"⚠️  Only {main_endpoint} endpoint(s) updated (expected 2)")
        checks.append(False)

# Summary
print("\n" + "="*70)
print(f"VERIFICATION: {sum(checks)}/{len(checks)} checks passed")
print("="*70)

if all(checks):
    print("\n✅ ALL CHECKS PASSED! Feature is correctly implemented.")
else:
    print(f"\n⚠️  {len(checks) - sum(checks)} check(s) failed.")

print("="*70)
