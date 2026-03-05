import base64
import json
import re
from distutils.version import LooseVersion
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Path, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError

from app import logger
from app.db import Session, crud, get_db
from app.dependencies import get_validated_sub, validate_dates
from app.models.user import SubscriptionUserResponse, UserResponse
from app.subscription.share import encode_title, generate_subscription
from app.templates import render_template
from config import (
    HWID_ENABLED,
    SUB_PROFILE_TITLE,
    SUB_SUPPORT_URL,
    SUB_UPDATE_INTERVAL,
    SUBSCRIPTION_PAGE_TEMPLATE,
    USE_CUSTOM_JSON_DEFAULT,
    USE_CUSTOM_JSON_FOR_HAPP,
    USE_CUSTOM_JSON_FOR_STREISAND,
    USE_CUSTOM_JSON_FOR_NPVTUNNEL,
    USE_CUSTOM_JSON_FOR_V2RAYN,
    USE_CUSTOM_JSON_FOR_V2RAYNG,
    XRAY_SUBSCRIPTION_PATH,
)

client_config = {
    "clash-meta": {"config_format": "clash-meta", "media_type": "text/yaml", "as_base64": False, "reverse": False},
    "sing-box": {"config_format": "sing-box", "media_type": "application/json", "as_base64": False, "reverse": False},
    "clash": {"config_format": "clash", "media_type": "text/yaml", "as_base64": False, "reverse": False},
    "v2ray": {"config_format": "v2ray", "media_type": "text/plain", "as_base64": True, "reverse": False},
    "outline": {"config_format": "outline", "media_type": "application/json", "as_base64": False, "reverse": False},
    "v2ray-json": {"config_format": "v2ray-json", "media_type": "application/json", "as_base64": False,
                   "reverse": False}
}

router = APIRouter(tags=['Subscription'], prefix=f'/{XRAY_SUBSCRIPTION_PATH}')


def get_subscription_user_info(user: UserResponse) -> dict:
    """Retrieve user subscription information including upload, download, total data, and expiry."""
    return {
        "upload": 0,
        "download": user.used_traffic,
        "total": user.data_limit if user.data_limit is not None else 0,
        "expire": user.expire if user.expire is not None else 0,
    }


def _enforce_hwid(request: Request, db: Session, dbuser, user_agent: str) -> tuple[Optional[Response], bool, bool]:
    """
    Enforce HWID-based device limiting.

    Returns:
        tuple: (response, is_blocked, is_limit_reached)
            - response: Response object if request should be blocked/limited, None otherwise
            - is_blocked: True if device is disabled/blocked (should return empty inbounds)
            - is_limit_reached: True if device limit is exceeded (should return warning subscription)
    """
    if not HWID_ENABLED:
        return (None, False, False)

    hwid = request.headers.get("x-hwid", "").strip() or None
    platform = request.headers.get("x-device-os", "").strip() or None
    os_version = request.headers.get("x-ver-os", "").strip() or None
    device_model = request.headers.get("x-device-model", "").strip() or None

    # Refresh dbuser to ensure we have the latest device_limit
    db.refresh(dbuser)

    allowed, reason = crud.check_hwid_limit(db, dbuser, hwid)
    if not allowed:
        logger.warning(f"HWID limit check failed for user {dbuser.username}: hwid={hwid}, reason={reason}, device_limit={dbuser.device_limit}")
        return (None, False, True)

    # Check if this HWID is disabled/blocked
    if hwid:
        existing = crud.get_user_device_by_hwid(db, dbuser.id, hwid)
        if existing:
            if existing.disabled:
                # Device is blocked - return is_blocked=True to generate empty inbounds
                logger.info(f"Blocked device {hwid} updating subscription for user {dbuser.username} - returning empty inbounds")
                return (None, True, False)

            # Update existing device info
            crud.update_user_device(db, existing, platform=platform, os_version=os_version,
                                    device_model=device_model, user_agent=user_agent or None)
        else:
            # New device - register it
            try:
                crud.register_user_device(db, dbuser.id, hwid, platform=platform, os_version=os_version,
                                          device_model=device_model, user_agent=user_agent or None)
                logger.info(f"New device registered for user {dbuser.username}: hwid={hwid}")
            except IntegrityError:
                db.rollback()
                logger.warning(f"Device registration race condition for user {dbuser.username}: hwid={hwid}")

    return (None, False, False)


def _generate_device_limit_warning_response(config_format: str) -> Response:
    """Generate a subscription response with a single warning entry for device limit exceeded."""
    WARNING_NAME = "⚠️ Лимит устройств достигнут"
    headers = {"x-hwid-limit": "true"}

    if config_format in ("clash", "clash-meta"):
        content = (
            'proxies:\n'
            f'  - name: "{WARNING_NAME}"\n'
            '    type: socks5\n'
            '    server: 0.0.0.0\n'
            '    port: 1\n'
            'proxy-groups:\n'
            f'  - name: "{WARNING_NAME}"\n'
            '    type: select\n'
            '    proxies:\n'
            f'      - "{WARNING_NAME}"\n'
            'rules:\n'
            f'  - MATCH,{WARNING_NAME}\n'
        )
        return Response(content=content, media_type="text/yaml", headers=headers)

    elif config_format == "sing-box":
        content = json.dumps({
            "outbounds": [
                {"type": "socks", "tag": WARNING_NAME, "server": "0.0.0.0", "server_port": 1}
            ]
        })
        return Response(content=content, media_type="application/json", headers=headers)

    else:
        # V2Ray base64 format (default for v2ray, v2ray-json, outline, unknown)
        link = f"vless://00000000-0000-0000-0000-000000000001@0.0.0.0:0?type=tcp#{quote(WARNING_NAME)}"
        content = base64.b64encode(link.encode()).decode()
        return Response(content=content, media_type="text/plain", headers=headers)


@router.get("/{token}/")
@router.get("/{token}", include_in_schema=False)
def user_subscription(
    request: Request,
    db: Session = Depends(get_db),
    dbuser: UserResponse = Depends(get_validated_sub),
    user_agent: str = Header(default="")
):
    """Provides a subscription link based on the user agent (Clash, V2Ray, etc.)."""
    user: UserResponse = UserResponse.model_validate(dbuser)

    accept_header = request.headers.get("Accept", "")
    if "text/html" in accept_header:
        return HTMLResponse(
            render_template(
                SUBSCRIPTION_PAGE_TEMPLATE,
                {"user": user}
            )
        )

    hwid_response, is_blocked, is_limit_reached = _enforce_hwid(request, db, dbuser, user_agent)
    if hwid_response is not None:
        return hwid_response

    if is_limit_reached:
        if re.match(r'^([Cc]lash-verge|[Cc]lash[-\.]?[Mm]eta|[Ff][Ll][Cc]lash|[Mm]ihomo)', user_agent):
            return _generate_device_limit_warning_response("clash-meta")
        elif re.match(r'^([Cc]lash|[Ss]tash)', user_agent):
            return _generate_device_limit_warning_response("clash")
        elif re.match(r'^(SFA|SFI|SFM|SFT|[Kk]aring|[Hh]iddify[Nn]ext)|.*sing[-b]?ox.*', user_agent, re.IGNORECASE):
            return _generate_device_limit_warning_response("sing-box")
        else:
            return _generate_device_limit_warning_response("v2ray")

    crud.update_user_sub(db, dbuser, user_agent)
    response_headers = {
        "content-disposition": f'attachment; filename="{user.username}"',
        "profile-web-page-url": str(request.url),
        "support-url": SUB_SUPPORT_URL,
        "profile-title": encode_title(SUB_PROFILE_TITLE),
        "profile-update-interval": SUB_UPDATE_INTERVAL,
        "subscription-userinfo": "; ".join(
            f"{key}={val}"
            for key, val in get_subscription_user_info(user).items()
        )
    }

    # If device is blocked, return empty subscription (no inbounds)
    if is_blocked:
        logger.info(f"Returning empty subscription for blocked device of user {user.username}")
        return Response(content="", media_type="text/plain", headers=response_headers)

    if re.match(r'^([Cc]lash-verge|[Cc]lash[-\.]?[Mm]eta|[Ff][Ll][Cc]lash|[Mm]ihomo)', user_agent):
        conf = generate_subscription(user=user, config_format="clash-meta", as_base64=False, reverse=False)
        return Response(content=conf, media_type="text/yaml", headers=response_headers)

    elif re.match(r'^([Cc]lash|[Ss]tash)', user_agent):
        conf = generate_subscription(user=user, config_format="clash", as_base64=False, reverse=False)
        return Response(content=conf, media_type="text/yaml", headers=response_headers)

    elif re.match(r'^(SFA|SFI|SFM|SFT|[Kk]aring|[Hh]iddify[Nn]ext)|.*sing[-b]?ox.*', user_agent, re.IGNORECASE):
        conf = generate_subscription(user=user, config_format="sing-box", as_base64=False, reverse=False)
        return Response(content=conf, media_type="application/json", headers=response_headers)

    elif re.match(r'^(SS|SSR|SSD|SSS|Outline|Shadowsocks|SSconf)', user_agent):
        conf = generate_subscription(user=user, config_format="outline", as_base64=False, reverse=False)
        return Response(content=conf, media_type="application/json", headers=response_headers)

    elif (USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_V2RAYN) and re.match(r'^v2rayN/(\d+\.\d+)', user_agent):
        version_str = re.match(r'^v2rayN/(\d+\.\d+)', user_agent).group(1)
        if LooseVersion(version_str) >= LooseVersion("6.40"):
            conf = generate_subscription(user=user, config_format="v2ray-json", as_base64=False, reverse=False)
            return Response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True, reverse=False)
            return Response(content=conf, media_type="text/plain", headers=response_headers)

    elif (USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_V2RAYNG) and re.match(r'^v2rayNG/(\d+\.\d+\.\d+)', user_agent):
        version_str = re.match(r'^v2rayNG/(\d+\.\d+\.\d+)', user_agent).group(1)
        if LooseVersion(version_str) >= LooseVersion("1.8.29"):
            conf = generate_subscription(user=user, config_format="v2ray-json", as_base64=False, reverse=False)
            return Response(content=conf, media_type="application/json", headers=response_headers)
        elif LooseVersion(version_str) >= LooseVersion("1.8.18"):
            conf = generate_subscription(user=user, config_format="v2ray-json", as_base64=False, reverse=True)
            return Response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True, reverse=False)
            return Response(content=conf, media_type="text/plain", headers=response_headers)

    elif re.match(r'^[Ss]treisand', user_agent):
        if USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_STREISAND:
            conf = generate_subscription(user=user, config_format="v2ray-json", as_base64=False, reverse=False)
            return Response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True, reverse=False)
            return Response(content=conf, media_type="text/plain", headers=response_headers)

    elif (USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_HAPP) and re.match(r'^Happ/(\d+\.\d+\.\d+)', user_agent):
        version_str = re.match(r'^Happ/(\d+\.\d+\.\d+)', user_agent).group(1)
        if LooseVersion(version_str) >= LooseVersion("1.11.0"):
            conf = generate_subscription(user=user, config_format="v2ray-json", as_base64=False, reverse=False)
            return Response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True, reverse=False)
            return Response(content=conf, media_type="text/plain", headers=response_headers)

    elif USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_NPVTUNNEL:
        if "ktor-client" in user_agent:
            conf = generate_subscription(user=user, config_format="v2ray-json", as_base64=False, reverse=False)
            return Response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True, reverse=False)
            return Response(content=conf, media_type="text/plain", headers=response_headers)

    else:
        conf = generate_subscription(user=user, config_format="v2ray", as_base64=True, reverse=False)
        return Response(content=conf, media_type="text/plain", headers=response_headers)


@router.get("/{token}/info", response_model=SubscriptionUserResponse)
def user_subscription_info(
    dbuser: UserResponse = Depends(get_validated_sub),
):
    """Retrieves detailed information about the user's subscription."""
    return dbuser


@router.get("/{token}/usage")
def user_get_usage(
    dbuser: UserResponse = Depends(get_validated_sub),
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db)
):
    """Fetches the usage statistics for the user within a specified date range."""
    start, end = validate_dates(start, end)

    usages = crud.get_user_usages(db, dbuser, start, end)

    return {"usages": usages, "username": dbuser.username}


@router.get("/{token}/{client_type}")
def user_subscription_with_client_type(
    request: Request,
    dbuser: UserResponse = Depends(get_validated_sub),
    client_type: str = Path(..., regex="sing-box|clash-meta|clash|outline|v2ray|v2ray-json"),
    db: Session = Depends(get_db),
    user_agent: str = Header(default="")
):
    """Provides a subscription link based on the specified client type (e.g., Clash, V2Ray)."""
    user: UserResponse = UserResponse.model_validate(dbuser)

    hwid_response, is_blocked, is_limit_reached = _enforce_hwid(request, db, dbuser, user_agent)
    if hwid_response is not None:
        return hwid_response

    if is_limit_reached:
        return _generate_device_limit_warning_response(client_type)

    response_headers = {
        "content-disposition": f'attachment; filename="{user.username}"',
        "profile-web-page-url": str(request.url),
        "support-url": SUB_SUPPORT_URL,
        "profile-title": encode_title(SUB_PROFILE_TITLE),
        "profile-update-interval": SUB_UPDATE_INTERVAL,
        "subscription-userinfo": "; ".join(
            f"{key}={val}"
            for key, val in get_subscription_user_info(user).items()
        )
    }

    # If device is blocked, return empty subscription (no inbounds)
    if is_blocked:
        logger.info(f"Returning empty subscription for blocked device of user {user.username} (client_type={client_type})")
        return Response(content="", media_type="text/plain", headers=response_headers)

    config = client_config.get(client_type)
    conf = generate_subscription(user=user,
                                 config_format=config["config_format"],
                                 as_base64=config["as_base64"],
                                 reverse=config["reverse"])

    return Response(content=conf, media_type=config["media_type"], headers=response_headers)
