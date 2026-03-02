#!/usr/bin/env python3
"""
HWID Device Limiting - Manual Test Suite
Tests for hardware ID-based device limiting feature in Marzban
"""

import sys
import os
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test results tracking
test_results = {
    'passed': 0,
    'failed': 0,
    'tests': []
}

def run_test(name, test_func):
    """Run a test and track results"""
    try:
        test_func()
        test_results['passed'] += 1
        test_results['tests'].append({'name': name, 'status': 'PASS', 'error': None})
        print(f"✅ PASS: {name}")
        return True
    except AssertionError as e:
        test_results['failed'] += 1
        test_results['tests'].append({'name': name, 'status': 'FAIL', 'error': str(e)})
        print(f"❌ FAIL: {name}")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        test_results['failed'] += 1
        test_results['tests'].append({'name': name, 'status': 'ERROR', 'error': str(e)})
        print(f"💥 ERROR: {name}")
        print(f"   Error: {e}")
        return False

def assert_equal(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"Expected {expected}, got {actual}. {msg}")

def assert_true(condition, msg=""):
    if not condition:
        raise AssertionError(f"Expected True. {msg}")

def assert_false(condition, msg=""):
    if condition:
        raise AssertionError(f"Expected False. {msg}")

def assert_in(needle, haystack, msg=""):
    if needle not in haystack:
        raise AssertionError(f"Expected '{needle}' in '{haystack}'. {msg}")

# Import after path setup
from app.db.models import User, UserDevice
from app.db import crud
from app.models.user import UserResponse, UserDeviceResponse


def create_mock_db():
    """Create a mock database session"""
    db = Mock()
    db.query = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db

def create_mock_user():
    """Create a mock user"""
    user = Mock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.device_limit = 2
    return user


# ============== TEST CASES ==============

def test_unlimited_device_limit():
    """Test user with device_limit=0 (unlimited)"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 0
    
    allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "test-hwid")
    
    assert_true(allowed, "Should allow unlimited devices")
    assert_equal(reason, None, "Should have no reason")

def test_null_device_limit_uses_fallback():
    """Test user with device_limit=None uses HWID_FALLBACK_LIMIT"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = None
    
    with patch('app.db.crud.HWID_FALLBACK_LIMIT', 3):
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            mock_query = Mock()
            mock_query.filter = Mock(return_value=mock_query)
            mock_query.scalar = Mock(return_value=2)  # 2 devices already
            mock_db.query.return_value = mock_query
            
            allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
            
            assert_true(allowed, "Should allow when under fallback limit (2 < 3)")
            assert_equal(reason, None, "Should have no reason")

def test_no_hwid_provided():
    """Test when no HWID is provided"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 2
    
    allowed, reason = crud.check_hwid_limit(mock_db, mock_user, None)
    
    assert_false(allowed, "Should not allow without HWID")
    assert_equal(reason, "no_hwid", "Should return no_hwid reason")

def test_disabled_hwid_blocked():
    """Test that disabled HWID is blocked from reconnecting"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 2
    
    disabled_device = Mock()
    disabled_device.disabled = True
    
    with patch('app.db.crud.get_user_device_by_hwid', return_value=disabled_device):
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "disabled-hwid")
        
        assert_false(allowed, "Should not allow disabled device")
        assert_equal(reason, "device_disabled", "Should return device_disabled reason")

def test_existing_active_hwid_allowed():
    """Test that existing active HWID is allowed"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 2
    
    active_device = Mock()
    active_device.disabled = False
    
    with patch('app.db.crud.get_user_device_by_hwid', return_value=active_device):
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "existing-hwid")
        
        assert_true(allowed, "Should allow existing active device")
        assert_equal(reason, None, "Should have no reason")

def test_limit_reached():
    """Test when device limit is reached"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 2
    
    with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.scalar = Mock(return_value=2)  # Already at limit
        mock_db.query.return_value = mock_query
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
        
        assert_false(allowed, "Should not allow when at limit")
        assert_equal(reason, "limit_reached", "Should return limit_reached reason")

def test_under_limit():
    """Test when under device limit"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 3
    
    with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.scalar = Mock(return_value=1)  # 1 device, limit is 3
        mock_db.query.return_value = mock_query
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
        
        assert_true(allowed, "Should allow when under limit (1 < 3)")
        assert_equal(reason, None, "Should have no reason")

def test_count_excludes_disabled_devices():
    """Test that device count excludes disabled devices"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 2
    
    with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.scalar = Mock(return_value=1)  # Only 1 active device
        mock_db.query.return_value = mock_query
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
        
        assert_true(allowed, "Should allow when only 1 active device (1 < 2)")
        assert_equal(reason, None, "Should have no reason")

def test_register_new_device():
    """Test registering a new device"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    hwid = "new-device-hwid"
    
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    with patch('app.db.crud.UserDevice') as MockDevice:
        mock_new_device = Mock()
        MockDevice.return_value = mock_new_device
        
        result = crud.register_user_device(
            mock_db, mock_user, hwid, "iOS", "17.0", "iPhone 15", "Test Agent"
        )
        
        assert_equal(result, mock_new_device, "Should return new device")
        MockDevice.assert_called_once()

def test_register_existing_device_updates_info():
    """Test that existing device gets updated"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    hwid = "existing-hwid"
    
    existing_device = Mock()
    existing_device.id = 1
    existing_device.disabled = False
    
    mock_db.query.return_value.filter.return_value.first.return_value = existing_device
    
    result = crud.register_user_device(
        mock_db, mock_user, hwid, "Android", "14", "Pixel 8", "Agent"
    )
    
    assert_equal(result, existing_device, "Should return existing device")

def test_register_disabled_device_fails():
    """Test that registering a disabled device fails"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    hwid = "disabled-hwid"
    
    disabled_device = Mock()
    disabled_device.disabled = True
    
    mock_db.query.return_value.filter.return_value.first.return_value = disabled_device
    
    try:
        crud.register_user_device(mock_db, mock_user, hwid, "iOS", "17", "iPhone", "Agent")
        raise AssertionError("Should have raised an exception")
    except Exception as e:
        assert_in("disabled", str(e).lower(), "Error should mention disabled")

def test_delete_device_marks_as_disabled():
    """Test that deleting a device marks it as disabled, not removes it"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    
    mock_device = Mock()
    mock_device.disabled = False
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_device
    
    result = crud.delete_user_device(mock_db, 1, 1)
    
    assert_true(result, "Should return True on success")
    assert_true(mock_device.disabled, "Device should be marked as disabled")

def test_delete_nonexistent_device():
    """Test deleting a device that doesn't exist"""
    mock_db = create_mock_db()
    
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    result = crud.delete_user_device(mock_db, 999, 1)
    
    assert_false(result, "Should return False for non-existent device")

def test_delete_all_marks_all_as_disabled():
    """Test that delete_all marks all active devices as disabled"""
    mock_db = create_mock_db()
    
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.update = Mock(return_value=3)  # 3 devices updated
    mock_db.query.return_value = mock_query
    
    result = crud.delete_all_user_devices(mock_db, 1)
    
    assert_equal(result, 3, "Should return count of disabled devices")

def test_get_devices_excludes_disabled_by_default():
    """Test that get_user_devices excludes disabled devices by default"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [Mock(disabled=False), Mock(disabled=False)]
    mock_db.query.return_value = mock_query
    
    result = crud.get_user_devices(mock_db, mock_user)
    
    assert_equal(len(result), 2, "Should return 2 devices")
    assert_true(all(not d.disabled for d in result), "All should be active")

def test_get_devices_includes_disabled_when_requested():
    """Test that get_user_devices includes disabled when include_disabled=True"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [
        Mock(disabled=False),
        Mock(disabled=True),
        Mock(disabled=False)
    ]
    mock_db.query.return_value = mock_query
    
    result = crud.get_user_devices(mock_db, mock_user, include_disabled=True)
    
    assert_equal(len(result), 3, "Should return all 3 devices")

def test_device_has_disabled_field():
    """Test that UserDevice has disabled field"""
    from app.db.models import UserDevice
    
    assert_true(hasattr(UserDevice, 'disabled'), "UserDevice should have disabled field")

def test_device_limit_one():
    """Test user with device_limit=1"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 1
    
    with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.scalar = Mock(return_value=0)
        mock_db.query.return_value = mock_query
        
        # First device allowed
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "hwid-1")
        assert_true(allowed, "First device should be allowed")
        
        # Second device blocked
        mock_query.scalar = Mock(return_value=1)
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "hwid-2")
        assert_false(allowed, "Second device should be blocked")
        assert_equal(reason, "limit_reached", "Should return limit_reached")

def test_empty_hwid_string():
    """Test with empty string HWID"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 2
    
    allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "")
    
    assert_false(allowed, "Empty HWID should not be allowed")
    assert_equal(reason, "no_hwid", "Should return no_hwid reason")

def test_blocking_frees_slot():
    """Test that blocking a device frees up a slot"""
    mock_db = create_mock_db()
    mock_user = create_mock_user()
    mock_user.device_limit = 2
    
    # Initially at limit (2 devices)
    with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.scalar = Mock(return_value=2)
        mock_db.query.return_value = mock_query
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-device")
        assert_false(allowed, "Should be at limit")
    
    # Block one device
    mock_device = Mock()
    mock_device.disabled = False
    mock_db.query.return_value.filter.return_value.first.return_value = mock_device
    
    crud.delete_user_device(mock_db, 1, 1)
    assert_true(mock_device.disabled, "Device should be disabled")
    
    # Now count should be 1 (only active devices)
    with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.scalar = Mock(return_value=1)  # Only 1 active now
        mock_db.query.return_value = mock_query
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-device")
        assert_true(allowed, "New device should be allowed after blocking one")


# ============== RUN ALL TESTS ==============

def run_all_tests():
    """Run all test cases"""
    print("=" * 70)
    print("HWID Device Limiting - Test Suite")
    print("=" * 70)
    print()
    
    tests = [
        ("Unlimited device limit (device_limit=0)", test_unlimited_device_limit),
        ("Null device limit uses fallback", test_null_device_limit_uses_fallback),
        ("No HWID provided", test_no_hwid_provided),
        ("Disabled HWID blocked from reconnecting", test_disabled_hwid_blocked),
        ("Existing active HWID allowed", test_existing_active_hwid_allowed),
        ("Device limit reached", test_limit_reached),
        ("Under device limit", test_under_limit),
        ("Count excludes disabled devices", test_count_excludes_disabled_devices),
        ("Register new device", test_register_new_device),
        ("Register existing device updates info", test_register_existing_device_updates_info),
        ("Register disabled device fails", test_register_disabled_device_fails),
        ("Delete device marks as disabled", test_delete_device_marks_as_disabled),
        ("Delete non-existent device", test_delete_nonexistent_device),
        ("Delete all marks all as disabled", test_delete_all_marks_all_as_disabled),
        ("Get devices excludes disabled by default", test_get_devices_excludes_disabled_by_default),
        ("Get devices includes disabled when requested", test_get_devices_includes_disabled_when_requested),
        ("UserDevice has disabled field", test_device_has_disabled_field),
        ("Device limit = 1", test_device_limit_one),
        ("Empty HWID string", test_empty_hwid_string),
        ("Blocking frees slot", test_blocking_frees_slot),
    ]
    
    for name, test_func in tests:
        run_test(name, test_func)
    
    # Print summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {test_results['passed'] + test_results['failed']}")
    print(f"✅ Passed: {test_results['passed']}")
    print(f"❌ Failed: {test_results['failed']}")
    print()
    
    if test_results['failed'] > 0:
        print("Failed Tests:")
        print("-" * 70)
        for test in test_results['tests']:
            if test['status'] == 'FAIL' or test['status'] == 'ERROR':
                print(f"  {test['status']}: {test['name']}")
                print(f"    Error: {test['error']}")
        print()
    
    # Return exit code
    return 0 if test_results['failed'] == 0 else 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
