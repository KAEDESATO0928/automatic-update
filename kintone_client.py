"""kintone REST API クライアント (urllib のみ、外部依存なし)"""

import json
import urllib.parse
import urllib.request


class KintoneError(Exception):
    pass


class KintoneClient:
    def __init__(self, subdomain: str, api_token: str):
        self.base_url = f"https://{subdomain}.cybozu.com/k/v1"
        self.api_token = api_token

    def get_record(self, app_id: int, record_id: int) -> dict:
        qs = urllib.parse.urlencode({"app": app_id, "id": record_id})
        url = f"{self.base_url}/record.json?{qs}"
        req = urllib.request.Request(
            url,
            headers={"X-Cybozu-API-Token": self.api_token},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise KintoneError(
                f"kintone API HTTPエラー: {e.code} {e.reason}\n{body[:300]}"
            ) from e
        except urllib.error.URLError as e:
            raise KintoneError(f"kintone API 接続失敗: {e.reason}") from e
        return data.get("record", {})
