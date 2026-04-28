from __future__ import annotations

import base64

from fastapi import APIRouter, Depends

from ..deps import CurrentAuth, get_current_auth_optional, sex_name
from ..schemas import LegacyGetUserIdRequest


router = APIRouter(prefix="/legacy/user", tags=["legacy"])


def _legacy_success(data, message: str = "请求成功", code: int = 200):
    return {
        "code": code,
        "token": "SUCCESS",
        "data": data,
        "msg": message,
    }


def _legacy_error(data, message: str, code: int = 201):
    return {
        "code": code,
        "token": "FAILED",
        "data": data,
        "msg": message,
    }


@router.post("/getUserId")
def get_user_id(
    payload: LegacyGetUserIdRequest,
    auth: CurrentAuth | None = Depends(get_current_auth_optional),
):
    if payload.token:
        try:
            decoded = base64.b64decode(payload.token).decode("utf-8")
            user_id_raw = decoded.split(",", 1)[0].strip()
            return _legacy_success(int(user_id_raw))
        except Exception:
            pass

    if auth is not None:
        return _legacy_success(auth.user.id)
    return _legacy_success(0)


@router.post("/getIdentityArr")
def get_identity_arr(auth: CurrentAuth | None = Depends(get_current_auth_optional)):
    if auth is None:
        return _legacy_error({}, "登陆信息不匹配", 288)

    user = auth.user
    identity = user.identity
    sex = identity.sex if identity else 0
    sex_value = sex_name(sex)

    user_payload = {
        "id": user.id,
        "name": (identity.name if identity else "") or user.display_name,
        "avatar": (identity.avatar if identity else "") or user.avatar_url,
        "mobile": (identity.mobile if identity else None) or user.phone,
        "sex": sex,
        "sex_name": sex_value,
        "vip": user.vip,
        "vip_level": user.vip_level,
        "user_rule_id": user.user_rule_id,
    }

    data = {
        "user": user_payload,
        "sexList": {
            "select": [
                {"id": 1, "name": "男"},
                {"id": 2, "name": "女"},
            ],
            "value": sex_value,
        },
    }
    return _legacy_success(data)

