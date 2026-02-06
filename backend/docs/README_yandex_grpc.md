# Генерация gRPC stubs для Yandex Search API v2

## Зависимости

Установлены в `requirements.txt`:

- `protobuf==5.29.4`
- `grpcio==1.71.0`
- `grpcio-tools==1.71.0`
- `googleapis-common-protos==1.70.0`

## Подготовка api-common-protos

Proto-файлы Yandex Search API импортируют `google/api/annotations.proto` и `google/rpc/status.proto`. Эти файлы находятся в репозитории [googleapis/api-common-protos](https://github.com/googleapis/api-common-protos).

Клонируйте репозиторий в `third_party`:

```bash
cd backend
mkdir -p third_party
git clone --depth 1 https://github.com/googleapis/api-common-protos.git third_party/api-common-protos
```

Либо укажите путь через переменную окружения:

```bash
export GRPC_GOOGLEAPIS_PROTO_PATH=/path/to/api-common-protos
```

## Запуск генерации

```bash
cd backend
python scripts/generate_yandex_grpc.py
```

Скрипт:

1. Находит все `.proto` в `app/integrations/search/retrievers/yandex/grpc/`
2. Запускает `grpc_tools.protoc` с корректными `-I`
3. Генерирует `*_pb2.py` и `*_pb2_grpc.py` в те же папки, где лежат proto
4. Создаёт `__init__.py` во всех подпапках `grpc/`

## Проверка

После успешной генерации:

```bash
python -c "
from app.integrations.search.retrievers.yandex.grpc.yandex.cloud.searchapi.v2 import search_service_pb2
print('OK: stubs загружены')
"
```

Бизнес-логика — в `app/integrations/search/retrievers/yandex/yandex_retriever.py`. Импорты stubs — прямые, без re-export через `__init__.py`.
