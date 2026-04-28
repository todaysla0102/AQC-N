from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Request

from ..config import settings


router = APIRouter(tags=["legacy-scaffold"])


# Generated from AQC-O `_/routes/api.php` to keep all old API entries reachable.
LEGACY_ROUTE_SPECS: list[tuple[str, str, str]] = [
    ("GET", "/json", "ApiController@getJson"),
    ("POST", "/upload", "ApiController@uploadFile"),
    ("POST", "/skuImage", "ApiController@uploadSkuFile"),
    ("POST", "/aboutUs", "ApiController@aboutUs"),
    ("POST", "/document", "ApiController@document"),
    ("POST", "/feedback", "ApiController@feedback"),
    ("POST", "/getAddressInfo", "PostController@getOrderTracesByJson"),
    ("POST", "/homepage", "GoodsController@homepage"),
    ("POST", "/goods/getGoodsList", "GoodsController@getGoodsList"),
    ("POST", "/goods/tabsChange", "GoodsController@tabsChange"),
    ("POST", "/goods/getSpecialArea", "GoodsController@getSpecialArea"),
    ("POST", "/goods/getGoodsCateList", "GoodsController@getGoodsCateList"),
    ("POST", "/goods/getGoodsInfo", "GoodsController@getGoodsInfo"),
    ("POST", "/goods/getReviewsList", "GoodsController@getReviewsList"),
    ("POST", "/goods/searchLog", "GoodsController@searchLog"),
    ("POST", "/goods/searchLogDel", "GoodsController@searchLogDel"),
    ("POST", "/goods/getGoodsGroupList", "GoodsController@getGoodsGroupList"),
    ("POST", "/goods/getGoodsDiscountList", "GoodsController@getGoodsDiscountList"),
    ("POST", "/goods/getGoodsSpeckillList", "GoodsController@getGoodsSpeckillList"),
    ("POST", "/goods/getGoodsScoreList", "GoodsController@getGoodsScoreList"),
    ("POST", "/goods/cart_add", "GoodsController@goodsCartAdd"),
    ("POST", "/goods/cart_info", "GoodsController@goodsCartInfo"),
    ("GET", "/goods/cart_del", "GoodsController@goodsCartDel"),
    ("GET", "/goods/collect", "GoodsController@goodsCollect"),
    ("GET", "/goods/collect_del", "GoodsController@goodsCollectDel"),
    ("POST", "/goods/getCollectList", "GoodsController@getCollectList"),
    ("POST", "/goods/getUserCoupons", "GoodsController@getUserCoupons"),
    ("POST", "/goods/getOrderCoupons", "GoodsController@getOrderCoupons"),
    ("POST", "/goods/getCouponsList", "GoodsController@getCouponsList"),
    ("POST", "/goods/getDeductionData", "GoodsController@getDeductionData"),
    ("POST", "/goods/getGoodsReviews", "GoodsController@getGoodsReviews"),
    ("POST", "/goods/getHotGoodsList", "GoodsController@getHotGoodsList"),
    ("POST", "/goods/getGoodsShareCode", "GoodsController@getGoodsShareCode"),
    ("GET", "/goods/search/{key}", "GoodsController@search"),
    ("POST", "/goods/getGoodsSearchList", "GoodsController@getGoodsSearchList"),
    ("POST", "/goods/getShopList", "GoodsController@getShopList"),
    ("POST", "/goods/getShopInfo", "GoodsController@getShopInfo"),
    ("POST", "/goods/getPickupList", "GoodsController@getPickupList"),
    ("POST", "/goods/getPickupInfo", "GoodsController@getPickupInfo"),
    ("POST", "/goods/addGoodsList", "GoodsController@addGoodsList"),
    ("POST", "/goods/getLeadList", "GoodsController@getLeadList"),
    ("POST", "/goods/getGoodsCateNew", "GoodsController@getGoodsCateNew"),
    ("POST", "/goods/getClockCateList", "GoodsController@getClockCateList"),
    ("POST", "/goods/getClockInfo", "GoodsController@getClockInfo"),
    ("POST", "/goods/getGoodsStaticList", "GoodsController@getGoodsStaticList"),
    ("POST", "/goods/getCategoryList", "GoodsController@getCategoryList"),
    ("POST", "/home/release", "PostController@release"),
    ("POST", "/home/discount", "PostController@discount"),
    ("GET", "/home/goodsCate", "HomeController@getGoodsCategory"),
    ("GET", "/home/strategyCate", "HomeController@getStrategyCategory"),
    ("GET", "/home/goodsDassler", "HomeController@goodsDassler"),
    ("GET", "/home/goodsItemList", "HomeController@goodsItemList"),
    ("GET", "/home/goodsSpecList", "HomeController@goodsSpecList"),
    ("GET", "/home/getAgencyList", "HomeController@getAgencyList"),
    ("GET", "/home/goodsBrokerage", "HomeController@goodsBrokerage"),
    ("GET", "/home/goodsSku", "HomeController@goodsSku"),
    ("GET", "/home/goodsTags", "HomeController@goodsTags"),
    ("GET", "/home/goodsItem", "HomeController@goodsItem"),
    ("GET", "/home/homeCate", "HomeController@homeCategory"),
    ("GET", "/home/homeClock", "HomeController@clockCategory"),
    ("GET", "/home/groupTime", "HomeController@groupTime"),
    ("GET", "/home/taskType", "HomeController@taskType"),
    ("GET", "/home/getAjaxCity", "HomeController@getAjaxCity"),
    ("GET", "/home/getAllCity", "HomeController@getAllCity"),
    ("GET", "/home/getAjaxRegion", "HomeController@getAjaxRegion"),
    ("GET", "/home/getAllProvince", "HomeController@getAllProvince"),
    ("GET", "/home/getUserRule", "HomeController@getUserRule"),
    ("GET", "/home/getAdminList", "HomeController@getAdminList"),
    ("GET", "/home/getCouponsList", "HomeController@getCouponsList"),
    ("POST", "/home/checkIsOrderPay", "HomeController@checkIsOrderPay"),
    ("GET", "/home/getAjaxCategory", "HomeController@getAjaxCategory"),
    ("GET", "/home/getAllCategory", "HomeController@getAllCategory"),
    ("POST", "/home/searchGoods", "HomeController@searchGoods"),
    ("POST", "/home/searchUser", "HomeController@searchUser"),
    ("POST", "/home/addClockOrder", "HomeController@addClockOrder"),
    ("POST", "/home/searchCoupons", "HomeController@searchCoupons"),
    ("GET", "/home/exportClockOrder", "HomeController@exportClockOrder"),
    ("GET", "/home/exportHomepage", "HomeController@exportHomepage"),
    ("ANY", "/home/getClockList", "HomeController@getClockList"),
    ("GET", "/home/exportStatisticsMember", "HomeController@exportStatisticsMember"),
    ("GET", "/home/exportStatisticsRepair", "HomeController@exportStatisticsRepair"),
    ("POST", "/post/getPostList", "PostController@getPostList"),
    ("POST", "/post/getPostDetail", "PostController@getPostDetail"),
    ("POST", "/post/getNewsList", "PostController@getNewsList"),
    ("POST", "/post/getImageList", "PostController@getImageList"),
    ("POST", "/post/getThumbList", "PostController@getThumbList"),
    ("POST", "/post/getCategoryList", "PostController@getCategoryList"),
    ("POST", "/post/getNoticeList", "PostController@getNoticeList"),
    ("POST", "/post/getGoodsLimitedList", "PostController@getGoodsLimitedList"),
    ("POST", "/post/getGoodsGroupList", "PostController@getGoodsGroupList"),
    ("POST", "/post/getGoodsDayList", "PostController@getGoodsDayList"),
    ("POST", "/post/getGoodsHelpList", "PostController@getGoodsHelpList"),
    ("POST", "/post/getPrizeList", "PostController@getPrizeList"),
    ("POST", "/post/startPrize", "PostController@startPrize"),
    ("POST", "/post/getNoticeInfo", "PostController@getNoticeInfo"),
    ("POST", "/post/editUser", "PostController@editUser"),
    ("POST", "/order/buy_now", "OrderController@buyNow"),
    ("POST", "/order/buy_cart", "OrderController@buyCart"),
    ("POST", "/order/choice_address", "OrderController@choiceAddress"),
    ("POST", "/order/getOrderList", "OrderController@orderItem"),
    ("POST", "/order/cancel", "OrderController@orderCancel"),
    ("POST", "/order/gerOrderReviewsList", "OrderController@gerOrderReviewsList"),
    ("POST", "/order/logistics", "OrderController@logistics"),
    ("POST", "/order/getGoodsFreight", "OrderController@getGoodsFreight"),
    ("POST", "/order/getOrderInfo", "OrderController@getOrderInfo"),
    ("POST", "/order/buying", "OrderController@buying"),
    ("POST", "/order/writeOffUserOrder", "OrderController@writeOffUserOrder"),
    ("POST", "/order/getUserWriteOffOrderList", "OrderController@getUserWriteOffOrderList"),
    ("POST", "/order/applyOrderStatus", "OrderController@applyOrderStatus"),
    ("POST", "/wechat/getUserInfo", "WechatController@wxLogin"),
    ("POST", "/wechat/getUserPhone", "WechatController@wxCheck"),
    ("POST", "/wechat/updateUserInfo", "WechatController@updateUserInfo"),
    ("ANY", "/wechat/wechatPay", "WechatController@wechatPay"),
    ("ANY", "/wechat/walletPay", "WechatController@walletPay"),
    ("ANY", "/wechat/walletRecharge", "WechatController@walletRecharge"),
    ("POST", "/wechat/refund", "WechatController@wechatRefund"),
    ("POST", "/wechat/service", "WechatController@wechatService"),
    ("POST", "/wechat/getRefundList", "WechatController@getRefundList"),
    ("POST", "/wechat/push", "WechatController@push"),
    ("POST", "/wxpay/callback", "WxpayController@notify"),
    ("ANY", "/wxpay/refund", "WxpayController@refund"),
    ("ANY", "/wxpay/refundFreight", "WxpayController@refundFreight"),
    ("POST", "/questionnaire/getQuestionnaireData", "QuestionnaireController@getQuestionnaireData"),
    ("POST", "/questionnaire/addQuestionnaireData", "QuestionnaireController@addQuestionnaireData"),
    ("POST", "/show/getShowTags", "ShowController@getShowTags"),
    ("POST", "/show/addShowData", "ShowController@addShowData"),
    ("POST", "/show/getShowList", "ShowController@getShowList"),
    ("POST", "/show/getShowInfo", "ShowController@getShowInfo"),
    ("POST", "/show/getReviewsList", "ShowController@getReviewsList"),
    ("POST", "/show/addReview", "ShowController@addReview"),
    ("POST", "/show/delReview", "ShowController@delReview"),
    ("POST", "/show/getShowLike", "ShowController@getShowLike"),
    ("POST", "/show/getMyShowList", "ShowController@getMyShowList"),
    ("POST", "/show/delShow", "ShowController@delShow"),
    ("POST", "/activity/getActivityList", "ActivityController@getActivityList"),
    ("POST", "/activity/getActivityInfo", "ActivityController@getActivityInfo"),
    ("POST", "/activity/userSignActivity", "ActivityController@userSignActivity"),
    ("POST", "/activity/getOwnerActivityList", "ActivityController@getOwnerActivityList"),
    ("POST", "/user/sign", "UserController@sign"),
    ("POST", "/user/sign_info", "UserController@signInfo"),
    ("POST", "/user/address_info", "UserController@userAddressInfo"),
    ("POST", "/user/address_add", "UserController@userAddressAdd"),
    ("GET", "/user/address_del", "UserController@userAddressDel"),
    ("POST", "/user/couponsExchange", "UserController@couponsExchange"),
    ("POST", "/user/setUserSafePassword", "UserController@setUserSafePassword"),
    ("POST", "/user/editUserSafePassword", "UserController@editUserSafePassword"),
    ("POST", "/user/checkUserSafePassword", "UserController@checkUserSafePassword"),
    ("POST", "/user/setUserBank", "UserController@setUserBank"),
    ("POST", "/user/getBanklList", "UserController@getBanklList"),
    ("POST", "/user/getUserBanklData", "UserController@getUserBanklData"),
    ("POST", "/user/getOneBanklData", "UserController@getOneBanklData"),
    ("POST", "/user/delUserBanklData", "UserController@delUserBanklData"),
    ("POST", "/user/reviewsGoods", "UserController@reviewsGoods"),
    ("POST", "/user/confirmUserGoods", "UserController@confirmUserGoods"),
    ("POST", "/user/reapply", "UserController@reapply"),
    ("POST", "/user/certification", "UserController@certification"),
    ("POST", "/user/getUserDasslerList", "UserController@getUserDasslerList"),
    ("POST", "/user/checkUserApproce", "UserController@checkUserApproce"),
    ("POST", "/user/getRefundOrderList", "UserController@getRefundOrderList"),
    ("POST", "/user/getRefundOrderInfo", "UserController@getRefundOrderInfo"),
    ("POST", "/user/refundApply", "UserController@refundApply"),
    ("POST", "/user/refundLogistics", "UserController@refundLogistics"),
    ("POST", "/user/withdrawApply", "UserController@withdrawApply"),
    ("POST", "/user/memberCenter", "UserController@memberCenter"),
    ("POST", "/user/invitationCode", "UserController@invitationCode"),
    ("POST", "/user/myUser", "UserController@myUser"),
    ("POST", "/user/addUserPhone", "UserController@addUserPhone"),
    ("POST", "/user/getUserCheckList", "UserController@getUserCheckList"),
    ("POST", "/user/getUserCheckInfo", "UserController@getUserCheckInfo"),
    ("POST", "/user/getUserApplyList", "UserController@getUserApplyList"),
    ("POST", "/user/choiceUserCheck", "UserController@choiceUserCheck"),
    ("POST", "/user/getTagList", "UserController@getTagList"),
    ("POST", "/user/getRefundReason", "UserController@getRefundReason"),
    ("POST", "/user/getUserCouponsList", "UserController@getUserCouponsList"),
    ("POST", "/user/getUserWallet", "UserController@getUserWallet"),
    ("POST", "/user/getUserFansList", "UserController@getUserFansList"),
    ("POST", "/user/perform", "UserController@perform"),
    ("POST", "/user/joinActivity", "UserController@joinActivity"),
    ("POST", "/user/getActivityMoney", "UserController@getActivityMoney"),
    ("POST", "/user/getUserMonthCoupons", "UserController@getUserMonthCoupons"),
    ("POST", "/user/getCouponsMealList", "UserController@getCouponsMealList"),
    ("POST", "/user/getMonthCardMsg", "UserController@getMonthCardMsg"),
    ("POST", "/user/getUserId", "UserController@getUserId"),
    ("POST", "/user/applyShop", "UserController@applyShop"),
    ("POST", "/user/applyBusiness", "UserController@applyBusiness"),
    ("POST", "/user/getMyData", "UserController@getMyData"),
    ("POST", "/user/editUser", "UserController@editUser"),
    ("POST", "/user/getUserLevel", "UserController@getUserLevel"),
    ("POST", "/user/adminLogin", "UserController@adminLogin"),
    ("POST", "/user/cancelAfterVerification", "UserController@cancelAfterVerification"),
    ("POST", "/user/checkUserOrder", "UserController@checkUserOrder"),
    ("POST", "/user/checkUserHelpGoods", "UserController@checkUserHelpGoods"),
    ("POST", "/user/getSystemConfig", "UserController@getSystemConfig"),
    ("POST", "/user/refundOrder", "UserController@refundOrder"),
    ("GET", "/user/addUserShareCode", "UserController@addUserShareCode"),
    ("POST", "/user/getIdentityArr", "UserController@getIdentityArr"),
    ("POST", "/user/getUserVipLevelList", "UserController@getUserVipLevelList"),
    ("POST", "/user/userSignClock", "UserController@userSignClock"),
    ("POST", "/user/getUserCodeList", "UserController@getUserCodeList"),
    ("POST", "/user/getUserPayList", "UserController@getUserPayList"),
    ("POST", "/user/getQueryConditionsList", "UserController@getQueryConditionsList"),
    ("POST", "/user/yicode", "UserController@yicode"),
    ("POST", "/user/getUserScoreList", "UserController@getUserScoreList"),
    ("POST", "/check/checkUserPayPwd", "CheckController@checkUserPayPwd"),
    ("POST", "/check/checkBankPic", "CheckController@checkBankPic"),
    ("POST", "/check/checkIsPayPwd", "CheckController@checkIsPayPwd"),
    ("POST", "/check/fanlitest", "CheckController@fanlitest"),
    ("POST", "/check/send_sms", "CheckController@send_sms"),
    ("POST", "/check/isUserHasPhone", "CheckController@isUserHasPhone"),
    ("POST", "/check/checkUserIsApply", "CheckController@checkUserIsApply"),
    ("GET", "/check/delUnpaidOrder", "CheckController@delUnpaidOrder"),
    ("GET", "/check/delUnconfirmedOrder", "CheckController@delUnconfirmedOrder"),
    ("POST", "/check/isUserCode", "CheckController@isUserCode"),
    ("POST", "/check/distributionRule", "CheckController@distributionRule"),
    ("POST", "/check/checkUserCoordinate", "CheckController@checkUserCoordinate"),
    ("POST", "/check/monthSettlement", "CheckController@monthSettlement"),
    ("POST", "/check/updateTask", "CheckController@updateTask"),
    ("POST", "/check/changeUserVip", "CheckController@changeUserVip"),
    ("POST", "/check/checkUserCode", "CheckController@checkUserCode"),
    ("POST", "/check/checkUserRelation", "CheckController@checkUserRelation"),
    ("POST", "/check/addUserRelation", "CheckController@addUserRelation"),
    ("POST", "/check/getUserMonthPrice", "CheckController@getUserMonthPrice"),
    ("POST", "/check/checkAreaCoordinate", "CheckController@checkAreaCoordinate"),
    ("POST", "/check/choiceAreaCoordinate", "CheckController@choiceAreaCoordinate"),
    ("POST", "/check/getProvinceCityAreaMsg", "CheckController@getProvinceCityAreaMsg"),
    ("POST", "/check/uploadUserCheck", "CheckController@uploadUserCheck"),
    ("POST", "/check/checkUserIsUpload", "CheckController@checkUserIsUpload"),
    ("POST", "/check/checkUserPickup", "CheckController@checkUserPickup"),
    ("POST", "/check/checkUserMealOrder", "CheckController@checkUserMealOrder"),
    ("POST", "/check/checkUserVip", "CheckController@checkUserVip"),
    ("POST", "/check/checkAppletStopBusiness", "CheckController@checkAppletStopBusiness"),
    ("POST", "/check/checkGoodsCoupon", "CheckController@checkGoodsCoupon"),
    ("POST", "/logs/logCommission", "LogController@logCommission"),
    ("POST", "/logs/logWallet", "LogController@logWallet"),
    ("POST", "/logs/logWithdraw", "LogController@logWithdraw"),
    ("POST", "/logs/getLogCommissionList", "LogController@getLogCommissionList"),
    ("POST", "/logs/isWithdraw", "LogController@isWithdraw"),
    ("POST", "/logs/getUserSaleLog", "LogController@getUserSaleLog"),
    ("POST", "/logs/getUserSaveLog", "LogController@getUserSaveLog"),
    ("POST", "/logs/getUserMonthRanking", "LogController@getUserMonthRanking"),
    ("POST", "/logs/getTotalMonthRanking", "LogController@getTotalMonthRanking"),
    ("POST", "/logs/getUserActivityList", "LogController@getUserActivityList"),
    ("POST", "/logs/getHelpDocList", "LogController@getHelpDocList"),
    ("POST", "/logistics/getLogisticsData", "LogisticsController@getLogisticsData"),
    ("POST", "/logistics/addLogistics", "LogisticsController@addLogistics"),
    ("POST", "/logistics/cancelLogisticsOrder", "LogisticsController@cancelLogisticsOrder"),
    ("POST", "/logistics/checkLogisticsTrack", "LogisticsController@checkLogisticsTrack"),
    ("POST", "/logistics/getLogistics100Data", "LogisticsController@getLogistics100Data"),
    ("POST", "/logistics/back_url", "LogisticsController@back_url"),
    ("POST", "/logistics/obtainLogisticsTrajectory", "LogisticsController@obtainLogisticsTrajectory"),
    ("POST", "/center/getUserSale", "CenterController@getUserSale"),
    ("POST", "/center/getUserMsg", "CenterController@getUserMsg"),
    ("POST", "/center/getIdentityMsg", "CenterController@getIdentityMsg"),
    ("ANY", "/center/sendSms", "CenterController@sendSms"),
    ("POST", "/center/userPhoneEdit", "CenterController@userPhoneEdit"),
    ("POST", "/center/userDescEdit", "CenterController@userDescEdit"),
    ("POST", "/center/userNameEdit", "CenterController@userNameEdit"),
    ("POST", "/center/userAvatarEdit", "CenterController@userAvatarEdit"),
    ("POST", "/center/scorePay", "CenterController@scorePay"),
    ("POST", "/center/sendUserScore", "CenterController@sendUserScore"),
    ("POST", "/center/userScoreLog", "CenterController@userScoreLog"),
    ("POST", "/center/getActivityList", "CenterController@getActivityList"),
    ("POST", "/center/getUserGrow", "CenterController@getUserGrow"),
    ("GET", "/official/login", "OfficialAccountsController@login"),
    ("GET", "/official/oauth_callback", "OfficialAccountsController@oauth_callback"),
    ("GET", "/official/verify", "OfficialAccountsController@verifyToken"),
    ("GET", "/official/serve", "OfficialAccountsController@serve"),
    ("POST", "/work/checkUserLevel", "WorkController@checkUserLevel"),
    ("POST", "/work/getWorkData", "WorkController@getWorkData"),
    ("POST", "/work/getActivityList", "WorkController@getActivityList"),
    ("POST", "/work/getActivityInfo", "WorkController@getActivityInfo"),
    ("POST", "/work/writeOffActivity", "WorkController@writeOffActivity"),
    ("POST", "/work/getShopBaseData", "WorkController@getShopBaseData"),
    ("POST", "/work/getShopClockList", "WorkController@getShopClockList"),
    ("POST", "/work/userLogin", "WorkController@userLogin"),
    ("POST", "/work/userEdit", "WorkController@userEdit"),
    ("POST", "/work/getCode", "WorkController@getCode"),
    ("GET", "/external/getUserMsg", "ExternalController@getUserMsg"),
]


def _safe_json(data: Any) -> Any:
    if data is None:
        return None
    if isinstance(data, (str, int, float, bool, list, dict)):
        return data
    return str(data)


def _proxy_legacy_request(
    method: str,
    sub_path: str,
    query: dict[str, str],
    raw_body: bytes | None,
    content_type: str,
) -> tuple[Any | None, str | None]:
    if not settings.aqco_legacy_bridge_enabled:
        return None, "legacy bridge 未启用"

    base_url = settings.aqco_legacy_bridge_base.strip().rstrip("/")
    if not base_url:
        return None, "legacy bridge 地址未配置"

    query_string = urlencode(query)
    full_url = f"{base_url}{sub_path}"
    if query_string:
        full_url = f"{full_url}?{query_string}"

    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "AQC-N-LegacyBridge/1.0",
    }
    body = None
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        body = raw_body or b""
        headers["Content-Type"] = content_type or "application/json"

    req = UrlRequest(url=full_url, data=body, method=method, headers=headers)
    timeout = max(3, int(settings.aqco_legacy_bridge_timeout or 20))
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            resp_text = raw.decode("utf-8", errors="ignore")
            try:
                return json.loads(resp_text), None
            except Exception:
                return {"success": True, "legacyProxy": True, "raw": resp_text}, None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw)
            return parsed, None
        except Exception:
            return None, f"legacy 请求失败（HTTP {exc.code}）"
    except URLError:
        return None, "legacy 服务不可达"
    except Exception:
        return None, "legacy 响应异常"


def _build_handler(method: str, path: str, target: str):
    async def _handler(request: Request):
        request_method = request.method.upper()
        if method != "ANY":
            request_method = method

        raw_body = await request.body()
        content_type = request.headers.get("content-type", "")
        payload = None
        if raw_body:
            if "application/json" in content_type:
                try:
                    payload = _safe_json(json.loads(raw_body.decode("utf-8", errors="ignore")))
                except Exception:
                    payload = raw_body.decode("utf-8", errors="ignore")
            else:
                payload = raw_body.decode("utf-8", errors="ignore")

        query = {k: v for k, v in request.query_params.items()}
        path_params = dict(request.path_params)
        request_path = str(request.url.path)
        sub_path = request_path
        if request_path.startswith(settings.api_prefix):
            sub_path = request_path[len(settings.api_prefix) :]
        if not sub_path.startswith("/"):
            sub_path = f"/{sub_path}"

        proxy_payload, proxy_error = _proxy_legacy_request(
            method=request_method,
            sub_path=sub_path,
            query=query,
            raw_body=raw_body if raw_body else None,
            content_type=content_type,
        )
        if proxy_error is None and proxy_payload is not None:
            if isinstance(proxy_payload, dict):
                proxy_payload.setdefault("legacyProxy", True)
                proxy_payload.setdefault("legacyAction", target)
            return proxy_payload

        return {
            "success": False,
            "message": "legacy 接口暂不可用，已保留迁移占位",
            "legacyProxyError": proxy_error or "unknown",
            "legacy": {
                "method": method,
                "path": path,
                "controllerAction": target,
            },
            "request": {
                "pathParams": path_params,
                "query": query,
                "payload": payload,
            },
        }

    return _handler


for index, (method, path, target) in enumerate(LEGACY_ROUTE_SPECS):
    methods = [method]
    if method == "ANY":
        methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    router.add_api_route(
        path=path,
        endpoint=_build_handler(method, path, target),
        methods=methods,
        name=f"legacy_scaffold_{index}",
        include_in_schema=False,
    )
