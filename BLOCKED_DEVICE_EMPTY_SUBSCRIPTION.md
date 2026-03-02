# Blocked Device Empty Subscription Feature

## Overview

When a device is blocked by an admin, the device will receive an **empty subscription** (no inbounds/configs) when it tries to update its subscription. This provides a seamless way to block devices without completely rejecting their subscription requests.

---

## How It Works

### Before (Old Behavior)
1. Admin blocks a device
2. Device tries to update subscription
3. Server returns HTTP 429 (Too Many Requests) with `x-hwid-limit: true` header
4. Device shows an error to the user

### After (New Behavior)
1. Admin blocks a device
2. Device tries to update subscription
3. Server returns HTTP 200 OK with **empty content**
4. Device shows "No configurations available" or similar
5. Subscription appears valid but has no working proxies

---

## Implementation Details

### Modified Files

**`app/routers/subscription.py`**

#### 1. Updated `_enforce_hwid()` Function

```python
def _enforce_hwid(request: Request, db: Session, dbuser, user_agent: str) -> tuple[Optional[Response], bool]:
    """
    Enforce HWID-based device limiting.
    
    Returns:
        tuple: (response, is_blocked)
            - response: Response object if request should be blocked/limited
            - is_blocked: True if device is disabled/blocked (should return empty inbounds)
    """
    # ... existing limit checking code ...
    
    # Check if this HWID is disabled/blocked
    if hwid:
        existing = crud.get_user_device_by_hwid(db, dbuser.id, hwid)
        if existing:
            if existing.disabled:
                # Device is blocked - return is_blocked=True
                logger.info(f"Blocked device {hwid} updating subscription - returning empty inbounds")
                return (None, True)
    
    return (None, False)
```

**Key Changes:**
- Returns a tuple: `(response, is_blocked)`
- Checks if device `disabled` flag is `True`
- Sets `is_blocked=True` for blocked devices
- Logs the blocked subscription update attempt

#### 2. Updated `user_subscription()` Endpoint

```python
@router.get("/{token}/")
def user_subscription(...):
    # ... existing code ...
    
    hwid_response, is_blocked = _enforce_hwid(request, db, dbuser, user_agent)
    if hwid_response is not None:
        return hwid_response
    
    # ... existing code ...
    
    # If device is blocked, return empty subscription (no inbounds)
    if is_blocked:
        logger.info(f"Returning empty subscription for blocked device of user {user.username}")
        return Response(content="", media_type="text/plain", headers=response_headers)
    
    # Generate normal subscription configs...
```

**Key Changes:**
- Unpacks tuple from `_enforce_hwid()`
- Returns empty `Response` if `is_blocked=True`
- Includes all subscription headers (appears valid)
- Empty content means no proxy configurations

#### 3. Updated `user_subscription_with_client_type()` Endpoint

Same logic applied to the client_type-specific endpoint for consistency.

---

## Behavior by Client Type

### V2Ray/V2RayNG
- **Response:** Empty string
- **Client Shows:** "No profiles" or "Failed to import"

### Clash/ClashMeta
- **Response:** Empty string
- **Client Shows:** "Invalid config" or empty proxy list

### Sing-Box
- **Response:** Empty string
- **Client Shows:** "Config parsing failed"

### Outline
- **Response:** Empty string
- **Client Shows:** "No access keys"

### All Clients
- Subscription URL remains valid
- Headers are sent (looks like valid response)
- But no proxy configurations are included
- User cannot connect to any servers

---

## Logging

### Log Messages

When a blocked device updates subscription:

```
INFO: Blocked device {hwid} updating subscription for user {username} - returning empty inbounds
INFO: Returning empty subscription for blocked device of user {username}
```

### Monitoring

You can monitor blocked device activity by searching logs for:
- "Blocked device"
- "empty subscription"
- "empty inbounds"

---

## Testing

### Test Scenario 1: Block Device → Update Subscription

```bash
# 1. Create a user
# 2. Connect with a device (registers HWID)
# 3. Admin blocks the device in dashboard
# 4. Device updates subscription
# Expected: Empty response, HTTP 200
```

### Test Scenario 2: Verify Headers

```bash
curl -i "http://server:8000/sub/TOKEN/" \
  -H "x-hwid: test-device-123" \
  -H "user-agent: v2rayNG/1.8.29"

# Expected Headers:
# HTTP/1.1 200 OK
# content-disposition: attachment; filename="username"
# profile-title: ...
# subscription-userinfo: upload=0; download=12345; total=1073741824; expire=1234567890
# Content-Length: 0  # Empty body!
```

### Test Scenario 3: Compare Active vs Blocked

```bash
# Active device - should get configs
curl "http://server:8000/sub/TOKEN/" \
  -H "x-hwid: active-device" \
  -H "user-agent: v2rayNG/1.8.29"
# Response: Base64 encoded configs

# Blocked device - should get empty response
curl "http://server:8000/sub/TOKEN/" \
  -H "x-hwid: blocked-device" \
  -H "user-agent: v2rayNG/1.8.29"
# Response: Empty (Content-Length: 0)
```

---

## Advantages

### 1. **Stealth Blocking**
- Device doesn't get an explicit error
- Appears as temporary server issue
- User may not realize they're blocked

### 2. **Consistent Behavior**
- Same response for all client types
- No special error handling needed
- Works with all VPN apps

### 3. **Reversible**
- Admin can unblock device (by re-enabling in database)
- Device will get configs on next update
- No need to re-register HWID

### 4. **Security**
- Blocked devices cannot access any proxies
- No partial access
- Clear separation: active = access, blocked = no access

---

## Database Queries

### Check Device Status

```sql
SELECT id, hwid, platform, device_model, disabled, created_at, updated_at
FROM user_devices
WHERE user_id = ? AND hwid = ?;
```

### Block a Device (via Dashboard)

```sql
UPDATE user_devices
SET disabled = TRUE, updated_at = CURRENT_TIMESTAMP
WHERE id = ?;
```

### Find Blocked Devices

```sql
SELECT u.username, d.hwid, d.device_model, d.updated_at
FROM user_devices d
JOIN users u ON d.user_id = u.id
WHERE d.disabled = 1;
```

---

## API Response Comparison

| Scenario | HTTP Status | Content | Headers | User Experience |
|----------|-------------|---------|---------|-----------------|
| **Active Device** | 200 OK | Proxy configs | All present | Works normally |
| **Blocked Device** | 200 OK | Empty | All present | No configs shown |
| **Limit Reached** | 429 | Empty | `x-hwid-limit: true` | Error message |
| **No HWID** | 429 | Empty | `x-hwid-limit: true` | Error message |

---

## Configuration

### Enable/Disable Feature

This feature is controlled by `HWID_ENABLED` in `.env`:

```bash
# Enable HWID features (including empty subscription for blocked devices)
HWID_ENABLED=true

# Disable all HWID features
HWID_ENABLED=false
```

When `HWID_ENABLED=false`:
- All devices get normal subscriptions
- Blocking has no effect on subscription content
- Device management UI still works

---

## Troubleshooting

### Issue: Blocked device still gets configs

**Solution:**
1. Verify device is actually blocked in database:
   ```sql
   SELECT disabled FROM user_devices WHERE hwid = 'your-hwid';
   ```
2. Check `HWID_ENABLED=true` in `.env`
3. Restart Marzban server
4. Force subscription update on device

### Issue: All devices getting empty subscriptions

**Solution:**
1. Check if all devices are accidentally marked as disabled:
   ```sql
   SELECT COUNT(*) FROM user_devices WHERE disabled = 1;
   ```
2. Re-enable active devices:
   ```sql
   UPDATE user_devices SET disabled = 0 WHERE hwid IN ('hwid-1', 'hwid-2');
   ```

### Issue: Logs not showing blocked device messages

**Solution:**
1. Check log level in config
2. Ensure logger is properly configured
3. Verify `_enforce_hwid()` is being called

---

## Future Enhancements

Possible improvements:

1. **Custom Message** - Return a message explaining why configs are empty
2. **Partial Blocking** - Block specific protocols instead of all
3. **Time-based Blocking** - Automatically unblock after X hours
4. **Notification** - Notify admin when blocked device tries to update
5. **Unblock Endpoint** - API endpoint to re-enable devices

---

## Related Documentation

- `HWID_IMPLEMENTATION_SUMMARY.md` - Complete HWID feature documentation
- `tests/HWID_TEST_RESULTS.md` - Test scenarios and results
- `tests/FINAL_TEST_RESULTS.md` - Verification results

---

**Last Updated:** March 2, 2026  
**Version:** 1.1.0  
**Status:** ✅ Implemented
