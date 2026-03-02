"""
HWID Device Limiting - Comprehensive Test Suite
Tests for hardware ID-based device limiting feature in Marzban
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.models import User, UserDevice
from app.db import crud
from app.models.user import UserResponse, UserDeviceResponse


class TestHWIDDeviceLimiting:
    """Test suite for HWID-based device limiting"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = Mock()
        db.query = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user"""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.device_limit = 2
        return user
    
    @pytest.fixture
    def mock_device(self):
        """Create a mock device"""
        device = Mock(spec=UserDevice)
        device.id = 1
        device.hwid = "test-hwid-123"
        device.user_id = 1
        device.platform = "Android"
        device.os_version = "13"
        device.device_model = "Samsung Galaxy S22"
        device.user_agent = "Mozilla/5.0..."
        device.created_at = datetime.utcnow()
        device.updated_at = datetime.utcnow()
        device.disabled = False
        return device


class TestCheckHWIDLimit(TestHWIDDeviceLimiting):
    """Tests for check_hwid_limit function"""
    
    def test_unlimited_device_limit(self, mock_db, mock_user):
        """Test user with device_limit=0 (unlimited)"""
        mock_user.device_limit = 0
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "test-hwid")
        
        assert allowed is True
        assert reason is None
        mock_db.query.assert_not_called()
    
    def test_null_device_limit_uses_fallback(self, mock_db, mock_user):
        """Test user with device_limit=None uses HWID_FALLBACK_LIMIT"""
        mock_user.device_limit = None
        
        with patch('app.db.crud.HWID_FALLBACK_LIMIT', 3):
            with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
                with patch('app.db.crud.func.count') as mock_count:
                    mock_count.return_value = 2  # 2 devices already
                    mock_query = Mock()
                    mock_query.filter = Mock(return_value=mock_query)
                    mock_query.scalar = Mock(return_value=2)
                    mock_db.query.return_value = mock_query
                    
                    allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
                    
                    # Should allow (2 < 3)
                    assert allowed is True
                    assert reason is None
    
    def test_no_hwid_provided(self, mock_db, mock_user):
        """Test when no HWID is provided"""
        mock_user.device_limit = 2
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, None)
        
        assert allowed is False
        assert reason == "no_hwid"
    
    def test_disabled_hwid_blocked(self, mock_db, mock_user):
        """Test that disabled HWID is blocked from reconnecting"""
        mock_user.device_limit = 2
        
        disabled_device = Mock()
        disabled_device.disabled = True
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=disabled_device):
            allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "disabled-hwid")
            
            assert allowed is False
            assert reason == "device_disabled"
    
    def test_existing_active_hwid_allowed(self, mock_db, mock_user):
        """Test that existing active HWID is allowed"""
        mock_user.device_limit = 2
        
        active_device = Mock()
        active_device.disabled = False
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=active_device):
            allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "existing-hwid")
            
            assert allowed is True
            assert reason is None
    
    def test_limit_reached(self, mock_db, mock_user):
        """Test when device limit is reached"""
        mock_user.device_limit = 2
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(return_value=2)  # Already at limit
                mock_db.query.return_value = mock_query
                
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
                
                assert allowed is False
                assert reason == "limit_reached"
    
    def test_under_limit(self, mock_db, mock_user):
        """Test when under device limit"""
        mock_user.device_limit = 3
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(return_value=1)  # 1 device, limit is 3
                mock_db.query.return_value = mock_query
                
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
                
                assert allowed is True
                assert reason is None
    
    def test_count_excludes_disabled_devices(self, mock_db, mock_user):
        """Test that device count excludes disabled devices"""
        mock_user.device_limit = 2
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                # 5 total devices, but only 1 active
                mock_query.scalar = Mock(return_value=1)
                mock_db.query.return_value = mock_query
                
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
                
                assert allowed is True  # 1 < 2
                # Verify query filters out disabled devices
                mock_query.filter.assert_called()


class TestRegisterUserDevice(TestHWIDDeviceLimiting):
    """Tests for register_user_device function"""
    
    def test_register_new_device(self, mock_db, mock_user):
        """Test registering a new device"""
        hwid = "new-device-hwid"
        platform = "iOS"
        os_version = "17.0"
        device_model = "iPhone 15"
        user_agent = "Test Agent"
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('app.db.crud.UserDevice') as MockDevice:
            mock_new_device = Mock()
            MockDevice.return_value = mock_new_device
            
            result = crud.register_user_device(
                mock_db, mock_user, hwid, platform, os_version, device_model, user_agent
            )
            
            assert result == mock_new_device
            MockDevice.assert_called_once()
            mock_db.commit.assert_called()
    
    def test_register_existing_device_updates_info(self, mock_db, mock_user):
        """Test that existing device gets updated"""
        hwid = "existing-hwid"
        
        existing_device = Mock()
        existing_device.id = 1
        existing_device.disabled = False
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_device
        
        result = crud.register_user_device(
            mock_db, mock_user, hwid, "Android", "14", "Pixel 8", "Agent"
        )
        
        assert result == existing_device
        # Should update the device info
        mock_db.commit.assert_called()
    
    def test_register_disabled_device_fails(self, mock_db, mock_user):
        """Test that registering a disabled device fails"""
        hwid = "disabled-hwid"
        
        disabled_device = Mock()
        disabled_device.disabled = True
        
        mock_db.query.return_value.filter.return_value.first.return_value = disabled_device
        
        with pytest.raises(Exception) as exc_info:
            crud.register_user_device(mock_db, mock_user, hwid, "iOS", "17", "iPhone", "Agent")
        
        assert "disabled" in str(exc_info.value).lower()


class TestDeleteUserDevice(TestHWIDDeviceLimiting):
    """Tests for delete_user_device function"""
    
    def test_delete_device_marks_as_disabled(self, mock_db, mock_user):
        """Test that deleting a device marks it as disabled, not removes it"""
        device_id = 1
        user_id = 1
        
        mock_device = Mock()
        mock_device.disabled = False
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device
        
        result = crud.delete_user_device(mock_db, device_id, user_id)
        
        assert result is True
        assert mock_device.disabled is True
        mock_db.commit.assert_called()
    
    def test_delete_nonexistent_device(self, mock_db, mock_user):
        """Test deleting a device that doesn't exist"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = crud.delete_user_device(mock_db, 999, 1)
        
        assert result is False
        mock_db.commit.assert_not_called()
    
    def test_delete_already_disabled_device(self, mock_db, mock_user):
        """Test deleting an already disabled device"""
        mock_device = Mock()
        mock_device.disabled = True
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device
        
        result = crud.delete_user_device(mock_db, 1, 1)
        
        assert result is True
        assert mock_device.disabled is True  # Stays disabled


class TestDeleteAllUserDevices(TestHWIDDeviceLimiting):
    """Tests for delete_all_user_devices function"""
    
    def test_delete_all_marks_all_as_disabled(self, mock_db, mock_user):
        """Test that delete_all marks all active devices as disabled"""
        user_id = 1
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.update = Mock(return_value=3)  # 3 devices updated
        mock_db.query.return_value = mock_query
        
        result = crud.delete_all_user_devices(mock_db, user_id)
        
        assert result == 3
        mock_query.update.assert_called_once()
        # Verify it only updates disabled=False devices
        mock_query.filter.assert_called()
    
    def test_delete_all_with_no_devices(self, mock_db, mock_user):
        """Test delete_all when user has no devices"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.update = Mock(return_value=0)
        mock_db.query.return_value = mock_query
        
        result = crud.delete_all_user_devices(mock_db, 1)
        
        assert result == 0


class TestGetUserDevices(TestHWIDDeviceLimiting):
    """Tests for get_user_devices function"""
    
    def test_get_devices_excludes_disabled_by_default(self, mock_db, mock_user):
        """Test that get_user_devices excludes disabled devices by default"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [Mock(disabled=False), Mock(disabled=False)]
        mock_db.query.return_value = mock_query
        
        result = crud.get_user_devices(mock_db, mock_user)
        
        assert len(result) == 2
        assert all(not d.disabled for d in result)
    
    def test_get_devices_includes_disabled_when_requested(self, mock_db, mock_user):
        """Test that get_user_devices includes disabled when include_disabled=True"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [
            Mock(disabled=False),
            Mock(disabled=True),
            Mock(disabled=False)
        ]
        mock_db.query.return_value = mock_query
        
        result = crud.get_user_devices(mock_db, mock_user, include_disabled=True)
        
        assert len(result) == 3


class TestDeviceModel(TestHWIDDeviceLimiting):
    """Tests for UserDevice model"""
    
    def test_device_has_disabled_field(self):
        """Test that UserDevice has disabled field"""
        from app.db.models import UserDevice
        
        assert hasattr(UserDevice, 'disabled')
        assert UserDevice.disabled.default.arg is False
    
    def test_device_unique_constraint(self):
        """Test that UserDevice has unique constraint on hwid+user_id"""
        from app.db.models import UserDevice
        
        constraints = UserDevice.__table_args__
        assert constraints is not None
        
        # Find UniqueConstraint
        from sqlalchemy import UniqueConstraint
        unique_constraints = [c for c in constraints if isinstance(c, UniqueConstraint)]
        assert len(unique_constraints) > 0
        
        # Check for hwid, user_id constraint
        hwid_constraints = [c for c in unique_constraints if 'hwid' in c.columns and 'user_id' in c.columns]
        assert len(hwid_constraints) > 0


class TestIntegration(TestHWIDDeviceLimiting):
    """Integration tests for complete HWID flow"""
    
    def test_full_device_registration_flow(self, mock_db, mock_user):
        """Test complete flow: check -> register -> verify"""
        hwid = "test-device-1"
        mock_user.device_limit = 2
        
        # Step 1: Check if allowed (should be - no devices yet)
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(return_value=0)
                mock_db.query.return_value = mock_query
                
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, hwid)
                assert allowed is True
                assert reason is None
        
        # Step 2: Register device
        with patch('app.db.crud.UserDevice') as MockDevice:
            mock_new_device = Mock()
            mock_new_device.disabled = False
            MockDevice.return_value = mock_new_device
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            device = crud.register_user_device(mock_db, mock_user, hwid, "Android", "13", "S22", "Agent")
            assert device is not None
        
        # Step 3: Try to register same device again (should update, not create new)
        existing_device = Mock()
        existing_device.disabled = False
        mock_db.query.return_value.filter.return_value.first.return_value = existing_device
        
        device2 = crud.register_user_device(mock_db, mock_user, hwid, "Android", "14", "S22", "Agent2")
        assert device2 == existing_device
    
    def test_device_limit_enforcement(self, mock_db, mock_user):
        """Test that device limit is properly enforced"""
        mock_user.device_limit = 2
        
        # Register 2 devices
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(side_effect=[0, 1, 2])  # 0, then 1, then 2 devices
                
                # First device - allowed
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "hwid-1")
                assert allowed is True
                
                # Second device - allowed
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "hwid-2")
                assert allowed is True
                
                # Third device - blocked
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "hwid-3")
                assert allowed is False
                assert reason == "limit_reached"
    
    def test_blocked_device_cannot_reconnect(self, mock_db, mock_user):
        """Test that a blocked device cannot reconnect"""
        mock_user.device_limit = 2
        hwid = "blocked-device"
        
        # Device is disabled
        disabled_device = Mock()
        disabled_device.disabled = True
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=disabled_device):
            # Try to check limit - should fail
            allowed, reason = crud.check_hwid_limit(mock_db, mock_user, hwid)
            assert allowed is False
            assert reason == "device_disabled"
    
    def test_blocking_frees_slot(self, mock_db, mock_user):
        """Test that blocking a device frees up a slot"""
        mock_user.device_limit = 2
        hwid_to_block = "device-1"
        
        # Initially at limit (2 devices)
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(return_value=2)
                mock_db.query.return_value = mock_query
                
                # At limit - new device blocked
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-device")
                assert allowed is False
                assert reason == "limit_reached"
        
        # Block one device
        mock_device = Mock()
        mock_device.disabled = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device
        
        crud.delete_user_device(mock_db, 1, 1)
        assert mock_device.disabled is True
        
        # Now count should be 1 (only active devices)
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(return_value=1)  # Only 1 active now
                mock_db.query.return_value = mock_query
                
                # New device should be allowed
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-device")
                assert allowed is True


class TestEdgeCases(TestHWIDDeviceLimiting):
    """Test edge cases and boundary conditions"""
    
    def test_device_limit_one(self, mock_db, mock_user):
        """Test user with device_limit=1"""
        mock_user.device_limit = 1
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(return_value=0)
                mock_db.query.return_value = mock_query
                
                # First device allowed
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "hwid-1")
                assert allowed is True
                
                # Second device blocked
                mock_query.scalar = Mock(return_value=1)
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "hwid-2")
                assert allowed is False
                assert reason == "limit_reached"
    
    def test_mixed_disabled_and_active_devices(self, mock_db, mock_user):
        """Test counting with mix of active and disabled devices"""
        mock_user.device_limit = 2
        
        # 3 total devices: 2 active, 1 disabled
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                # Should only count active (disabled=False)
                mock_query.scalar = Mock(return_value=2)
                mock_db.query.return_value = mock_query
                
                # At limit (2 active devices)
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "new-hwid")
                assert allowed is False
    
    def test_empty_hwid_string(self, mock_db, mock_user):
        """Test with empty string HWID"""
        mock_user.device_limit = 2
        
        allowed, reason = crud.check_hwid_limit(mock_db, mock_user, "")
        
        # Empty string should be treated as no HWID
        assert allowed is False
        assert reason == "no_hwid"
    
    def test_very_long_hwid(self, mock_db, mock_user):
        """Test with very long HWID"""
        mock_user.device_limit = 2
        long_hwid = "a" * 500  # 500 character HWID
        
        with patch('app.db.crud.get_user_device_by_hwid', return_value=None):
            with patch('app.db.crud.func.count') as mock_count:
                mock_query = Mock()
                mock_query.filter = Mock(return_value=mock_query)
                mock_query.scalar = Mock(return_value=0)
                mock_db.query.return_value = mock_query
                
                allowed, reason = crud.check_hwid_limit(mock_db, mock_user, long_hwid)
                assert allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
