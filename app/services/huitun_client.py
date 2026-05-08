from __future__ import annotations

import time
from typing import Any

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from requests.adapters import HTTPAdapter

from app.config import get_settings
from app.services.signer import build_sign_params


settings = get_settings()
if not settings.huitun_verify_ssl:
    urllib3.disable_warnings(InsecureRequestWarning)


class HuitunClient:
    def __init__(self) -> None:
        self.settings = settings
        self.base_url = self.settings.huitun_base_url.rstrip("/")
        self.client_id = self.settings.huitun_client_id
        self.secret_key = self.settings.huitun_secret_key
        self.platform = getattr(self.settings, "huitun_platform", "xhs")
        self.timeout = 60
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=30, max_retries=0)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        include_platform: bool = True,
        retry_read: bool = False,
    ) -> dict[str, Any]:
        payload = dict(params or {})

        if include_platform:
            payload.setdefault("platform", self.platform)

        signed = build_sign_params(
            client_id=self.client_id,
            secret_key=self.secret_key,
            params=payload,
            with_timestamp=True,
            with_nonce=True,
        )

        url = f"{self.base_url}{path}"
        attempts = 3 if retry_read else 1
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                # 文档里的业务接口以 GET + Query 为主
                if method.upper() == "GET":
                    resp = self.session.get(
                        url,
                        params=signed,
                        timeout=self.timeout,
                        verify=self.settings.huitun_verify_ssl,
                    )
                else:
                    resp = self.session.post(
                        url,
                        params=signed,
                        timeout=self.timeout,
                        verify=self.settings.huitun_verify_ssl,
                    )

                if retry_read and resp.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                    time.sleep(0.4 * (attempt + 1))
                    continue

                resp.raise_for_status()
                data = resp.json()

                status = data.get("status")
                if status not in (200, "200", None):
                    raise RuntimeError(f"huitun error: {data}")

                return data
            except requests.RequestException as exc:
                last_exc = exc
                if not retry_read or attempt >= attempts - 1:
                    raise
                time.sleep(0.4 * (attempt + 1))

        if last_exc:
            raise last_exc
        raise RuntimeError("huitun request failed")

    # 4. 获取笔记分类
    # noteTag 实测不接受 platform，所以这里关闭 include_platform
    def get_note_categories(self) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="/api/v1/cg/noteTag",
            params={},
            include_platform=False,
            retry_read=True,
        )

    # 5. 笔记搜索
    def search_notes(
        self,
        *,
        keyword: str | None = None,
        tag_list: list[int] | list[str] | None = None,
        sort: int = 1,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"sort": sort}
        if keyword:
            params["keyword"] = keyword
        if tag_list:
            params["tagList"] = tag_list
        return self._request(
            method="GET",
            path="/api/v1/cg/note/search",
            params=params,
            include_platform=True,
            retry_read=True,
        )

    # 6. 达人搜索
    def search_anchors(
        self,
        *,
        keyword: str | None = None,
        tag_list: list[int] | list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if keyword:
            params["keyword"] = keyword
        if tag_list:
            params["tagList"] = tag_list
        return self._request(
            method="GET",
            path="/api/v1/cg/anchor/search",
            params=params,
            include_platform=True,
            retry_read=True,
        )

    # 3. 获取笔记信息（异步）
    def create_note_info(self, *, note_link: str, back_url: str) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="/api/v1/cg/create/noteInfo",
            params={
                "noteLink": note_link,
                "backUrl": back_url,
            },
            include_platform=True,
        )

    # 12. 获取笔记评论（异步）
    # 如果你文档里的实际 path 不是 noteComment，请只改这里
    def create_note_comments(self, *, note_link: str, back_url: str) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="/api/v1/cg/create/noteComment",
            params={
                "noteLink": note_link,
                "backUrl": back_url,
            },
            include_platform=True,
        )

    # 2. 获取达人信息（异步）
    def create_anchor_info(self, *, anchor_link: str, back_url: str) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="/api/v1/cg/create/anchorInfo",
            params={
                "anchorLink": anchor_link,
                "backUrl": back_url,
            },
            include_platform=True,
        )

    # 1. 获取达人画像（异步）
    def create_fans_portrait(self, *, anchor_link: str, back_url: str) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="/api/v1/cg/create/fansPortrait",
            params={
                "anchorLink": anchor_link,
                "backUrl": back_url,
            },
            include_platform=True,
        )

    # 7. 创建关键词分析任务（异步）
    def create_keyword_analysis(
        self,
        *,
        keyword: str,
        last_days: int,
        back_url: str,
        priority: int = 3,
        note_type: int | None = None,
        business: int | None = None,
        goods: int | None = None,
        max_note_num: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "keyword": keyword,
            "lastDays": last_days,
            "priority": priority,
            "backUrl": back_url,
        }
        if note_type is not None:
            params["noteType"] = note_type
        if business is not None:
            params["business"] = business
        if goods is not None:
            params["goods"] = goods
        if max_note_num is not None:
            params["maxNoteNum"] = max_note_num

        return self._request(
            method="GET",
            path="/api/v1/cg/create/keywordAnalysis",
            params=params,
            include_platform=True,
        )

    # 8. 创建品牌分析任务（异步）
    def create_brand_analysis(
        self,
        *,
        brand_id: str,
        back_url: str,
        last_days: int = 30,
        priority: int = 3,
        ent_id: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "brandId": brand_id,
            "lastDays": last_days,
            "priority": priority,
            "backUrl": back_url,
        }
        if ent_id:
            params["entId"] = ent_id
        return self._request(
            method="GET",
            path="/api/v1/cg/create/brandAnalysis",
            params=params,
            include_platform=True,
        )

    # 9. 获取品牌简易信息
    # 如果你文档里的实际 path 不是这个，只改 path
    def get_brand_simple_info(self, *, keyword: str) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="/api/v1/cg/brand/search",
            params={"keyword": keyword},
            include_platform=True,
            retry_read=True,
        )

    # 10. 获取品牌关联账号信息
    def get_brand_accounts(self, *, keyword: str) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="/api/v1/cg/brandEnt/search",
            params={"keyword": keyword},
            include_platform=True,
            retry_read=True,
        )

    # 11. 接口剩余次数
    def get_quota(self) -> dict[str, Any]:
        # Current API doc path: /api/v1/cg/task/surplus
        # Keep a legacy fallback for backward compatibility.
        paths = ("/api/v1/cg/task/surplus", "/api/v1/cg/quota")
        last_exc: Exception | None = None
        for path in paths:
            try:
                return self._request(
                    method="GET",
                    path=path,
                    params={},
                    include_platform=True,
                    retry_read=True,
                )
            except requests.HTTPError as exc:
                last_exc = exc
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code == 404:
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("huitun quota request failed")
