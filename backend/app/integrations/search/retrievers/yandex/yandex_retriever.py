"""
YandexRetriever — интеграция с Yandex Search API v2 через gRPC (асинхронно).
"""
# pyright: reportUnknownMemberType=false, reportAttributeAccessIssue=false
import asyncio
import re

import grpc
import xml.etree.ElementTree as ET
from charset_normalizer import from_bytes

from app.integrations.search.ports import LinkRetrieverPort, RetrieverContext
from app.integrations.search.schemas import LinkCandidate, QueryStep
from app.integrations.search.retrievers.yandex.grpc.yandex.cloud.searchapi.v2 import (
    search_query_pb2,
    search_service_pb2,
    search_service_pb2_grpc,
)
from app.integrations.search.retrievers.yandex.grpc.yandex.cloud.operation import (
    operation_service_pb2,
    operation_service_pb2_grpc,
)


def _strip_hlword(text: str) -> str:
    """Убрать теги <hlword> из текста."""
    return re.sub(r"</?hlword>", "", text).strip()


class YandexRetriever:
    """Retriever для Yandex Search API v2 (gRPC)."""

    @property
    def name(self) -> str:
        return "yandex"

    async def retrieve(self, step: QueryStep, ctx: RetrieverContext) -> list[LinkCandidate]:
        settings = ctx.settings
        api_key = settings.YANDEX_API_KEY
        folder_id = settings.YANDEX_FOLDER_ID

        if not api_key or api_key == "changeme" or not folder_id or folder_id == "changeme":
            return self._stub_retrieve(step)

        # Только первое ключевое слово для запроса
        query_text = (
            step.query.keywords[0]
            if step.query.keywords
            else (step.query.text or " ")
        )
        query_text = (query_text or " ").strip()
        if not query_text:
            return []

        groups_on_page = min(step.max_results, 100)
        timeout_s = settings.YANDEX_SEARCH_TIMEOUT_SECONDS
        poll_attempts = settings.YANDEX_OPERATION_POLL_ATTEMPTS
        poll_interval = settings.YANDEX_OPERATION_POLL_INTERVAL_SECONDS
        search_endpoint = settings.YANDEX_SEARCH_ENDPOINT
        operation_endpoint = settings.YANDEX_OPERATION_ENDPOINT
        region = settings.YANDEX_SEARCH_REGION

        try:
            creds = grpc.ssl_channel_credentials()
            metadata = [("authorization", f"Api-Key {api_key}")]

            async with grpc.aio.secure_channel(search_endpoint, creds) as search_channel, grpc.aio.secure_channel(
                operation_endpoint, creds
            ) as op_channel:
                search_stub = search_service_pb2_grpc.WebSearchAsyncServiceStub(search_channel)
                op_stub = operation_service_pb2_grpc.OperationServiceStub(op_channel)

                request = search_service_pb2.WebSearchRequest(
                    folder_id=folder_id,
                    response_format=search_service_pb2.WebSearchRequest.FORMAT_XML,
                    query=search_query_pb2.SearchQuery(
                        search_type=search_query_pb2.SearchQuery.SEARCH_TYPE_RU,
                        query_text=query_text,
                        family_mode=search_query_pb2.SearchQuery.FAMILY_MODE_MODERATE,
                        page=0,
                        fix_typo_mode=search_query_pb2.SearchQuery.FIX_TYPO_MODE_ON,
                    ),
                    sort_spec=search_service_pb2.SortSpec(
                        sort_mode=search_service_pb2.SortSpec.SORT_MODE_BY_RELEVANCE,
                        sort_order=search_service_pb2.SortSpec.SORT_ORDER_DESC,
                    ),
                    group_spec=search_service_pb2.GroupSpec(
                        group_mode=search_service_pb2.GroupSpec.GROUP_MODE_DEEP,
                        groups_on_page=groups_on_page,
                        docs_in_group=1,
                    ),
                    max_passages=2,
                    region=region,
                    l10n=search_service_pb2.WebSearchRequest.LOCALIZATION_RU,
                    user_agent="grpc-search-provider",
                )

                operation = await search_stub.Search(request, metadata=metadata, timeout=timeout_s)

                for attempt in range(poll_attempts):
                    op_result = await op_stub.Get(
                        operation_service_pb2.GetOperationRequest(operation_id=operation.id),
                        metadata=metadata,
                        timeout=timeout_s,
                    )
                    if op_result.done:
                        break
                    await asyncio.sleep(poll_interval)
                else:
                    raise TimeoutError("Операция Yandex Search не завершилась вовремя")

                response = search_service_pb2.WebSearchResponse()
                op_result.response.Unpack(response)
                raw_data = response.raw_data

        except grpc.RpcError as e:
            msg = str(e)
            if "api_key" in msg.lower() or "key" in msg.lower():
                msg = "Ошибка аутентификации Yandex Search API. Проверьте YANDEX_API_KEY."
            raise RuntimeError(msg) from e
        except Exception as e:
            if "api_key" in str(e).lower() or "key" in str(e).lower():
                raise RuntimeError("Ошибка аутентификации Yandex Search API.") from e
            raise

        normalized = from_bytes(raw_data).best()
        if not normalized:
            raise RuntimeError("Не удалось определить кодировку XML ответа Yandex")

        root = ET.fromstring(str(normalized))
        items: list[LinkCandidate] = []
        rank = 1

        for doc in root.findall(".//doc"):
            url = doc.findtext("url")
            if not url:
                continue

            title_text = ""
            if (title_node := doc.find("title")) is not None:
                raw_title = ET.tostring(title_node, encoding="unicode", method="xml")
                match_t = re.search(r"<title>(.*?)</title>", raw_title, re.DOTALL)
                if match_t:
                    title_text = _strip_hlword(match_t.group(1))

            passage_text = ""
            if (passage_node := doc.find("passages/passage")) is not None:
                raw_passage = ET.tostring(passage_node, encoding="unicode", method="xml")
                match = re.search(r"<passage>(.*?)</passage>", raw_passage, re.DOTALL)
                if match:
                    passage_text = _strip_hlword(match.group(1))

            items.append(
                LinkCandidate(
                    url=url,
                    title=title_text or None,
                    snippet=passage_text or None,
                    published_at=None,
                    provider="yandex",
                    rank=rank,
                    provider_meta={},
                )
            )
            rank += 1

        return items

    def _stub_retrieve(self, step: QueryStep) -> list[LinkCandidate]:
        """Заглушка при отсутствии настроек (для тестов и локальной разработки)."""
        import hashlib

        query = step.query
        seed = (
            step.query.keywords[0]
            if step.query.keywords
            else (query.text or " ".join(query.must_have) or "empty")
        )
        seed_hash = hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:8]
        count = min(20 + (int(seed_hash, 16) % 41), step.max_results)
        domains = ["example.com", "news.example", "blog.example"]
        items: list[LinkCandidate] = []
        for i in range(1, count + 1):
            domain = domains[(i - 1) % len(domains)]
            url = f"https://{domain}/article/{seed_hash}-{i}"
            items.append(
                LinkCandidate(
                    url=url,
                    title=f"[stub] Result {i} for {seed}",
                    snippet=f"[stub] Snippet {i} ...",
                    published_at=None,
                    provider="yandex",
                    rank=i,
                    provider_meta={"stub": True, "seed": str(seed)},
                )
            )
        return items
