import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar

import requests
from pydantic import BaseModel
from requests import Response

T = TypeVar("T", bound=BaseModel)


class MorphClientResponse(Response):
    def __init__(self, response: Response):
        super().__init__()
        self.__dict__ = response.__dict__.copy()

    @staticmethod
    def is_api_error(response: Dict[str, Any]) -> bool:
        return "error" in response and "subCode" in response and "message" in response

    def is_error(self, raise_err: Optional[bool] = False) -> bool:
        try:
            self.raise_for_status()
            if MorphClientResponse.is_api_error(self.json()):
                if raise_err:
                    raise SystemError(self.text)
                return True
        except Exception as e:
            if raise_err:
                raise e
            return True
        return False

    def to_model(
        self, model: Type[T], raise_err: Optional[bool] = False
    ) -> Optional[T]:
        if raise_err:
            if self.status_code > 500:
                raise SystemError(self.text)
            try:
                response_json = self.json()
            except Exception as e:
                raise SystemError(e)
            if MorphClientResponse.is_api_error(response_json):
                raise SystemError(response_json["message"])
            return model(**response_json)
        else:
            try:
                response_json = self.json()
            except Exception:  # noqa
                return None
            if MorphClientResponse.is_api_error(response_json):
                return None
            return model(**response_json)


class MorphApiBaseClient(ABC):
    @abstractmethod
    def get_headers(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        pass

    def request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        is_debug: Optional[bool] = False,
    ) -> MorphClientResponse:
        headers = self.get_headers()
        url = urllib.parse.urljoin(f"{self.get_base_url()}/", path)

        if query:
            url_parts = list(urllib.parse.urlparse(url))
            existing_query = dict(urllib.parse.parse_qsl(url_parts[4]))
            updated_query = {
                k: (str(v).lower() if isinstance(v, bool) else v)
                for k, v in query.items()
                if v is not None
            }
            existing_query.update(updated_query)
            url_parts[4] = urllib.parse.urlencode(existing_query)
            url = urllib.parse.urlunparse(url_parts)

        if is_debug:
            print(">> DEBUGGING REQUEST ==============================")
            print(f"URL: {url}")
            print(f"Headers: {headers}")
            print(f"Data: {data}")
            print(f"Query: {query}")

        response = requests.request(
            method=method, url=url, headers=headers, json=data, verify=True
        )

        if is_debug:
            print(">> DEBUGGING RESPONSE =============================")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")

        return MorphClientResponse(response)
