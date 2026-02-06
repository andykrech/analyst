#!/usr/bin/env python3
"""
Генерация gRPC stubs из .proto для Yandex Search API v2.

Запуск: python scripts/generate_yandex_grpc.py

Требует GRPC_GOOGLEAPIS_PROTO_PATH для proto-файлов google/api (api-common-protos).
См. docs/README_yandex_grpc.md
"""
import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    """Корень проекта (backend/)."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def _grpc_root() -> Path:
    """Папка grpc с proto-файлами."""
    return _project_root() / "app" / "integrations" / "search" / "retrievers" / "yandex" / "grpc"


def _grpc_tools_proto_include() -> Path:
    """Include для google/protobuf из grpc_tools."""
    import grpc_tools

    return Path(grpc_tools.__file__).parent / "_proto"


def _ensure_init_py(dir_path: Path) -> None:
    """Создать __init__.py в папке, если нет."""
    init_file = dir_path / "__init__.py"
    if not init_file.exists():
        init_file.touch()


def _ensure_all_init_py(grpc_root: Path) -> None:
    """Создать __init__.py во всех подпапках grpc/."""
    for d in grpc_root.rglob("*"):
        if d.is_dir() and not d.name.startswith("."):
            _ensure_init_py(d)


# Префикс для прямых импортов (без extraPaths / sys.path)
_GRPC_IMPORT_PREFIX = "app.integrations.search.retrievers.yandex.grpc.yandex"


def _fix_imports_in_generated(grpc_root: Path) -> None:
    """Заменить импорты yandex.* на полные пути для работы без extraPaths."""
    for pb_file in grpc_root.rglob("*_pb2*.py"):
        text = pb_file.read_text(encoding="utf-8")
        if "from yandex." in text or "import yandex." in text:
            new_text = text.replace("from yandex.", f"from {_GRPC_IMPORT_PREFIX}.")
            new_text = new_text.replace("import yandex.", f"import {_GRPC_IMPORT_PREFIX}.")
            if new_text != text:
                pb_file.write_text(new_text, encoding="utf-8")


def main() -> int:
    project_root = _project_root()
    grpc_root = _grpc_root()

    if not grpc_root.exists():
        print(f"Ошибка: папка {grpc_root} не найдена.", file=sys.stderr)
        return 1

    proto_files = sorted(grpc_root.rglob("*.proto"))
    if not proto_files:
        print(f"Ошибка: .proto файлы не найдены в {grpc_root}", file=sys.stderr)
        return 1

    # Include paths
    include_paths = [
        str(grpc_root),
        str(_grpc_tools_proto_include()),
    ]

    googleapis_path = project_root / "third_party" / "api-common-protos"
    for candidate in [
        googleapis_path,
    ]:
        if candidate.exists() and (candidate / "google" / "api").exists():
            include_paths.append(str(candidate))
            break
    else:
        import os

        env_path = os.environ.get("GRPC_GOOGLEAPIS_PROTO_PATH")
        if env_path:
            p = Path(env_path)
            if p.exists():
                include_paths.append(str(p))
            else:
                print(f"Предупреждение: GRPC_GOOGLEAPIS_PROTO_PATH={env_path} не существует.")
        else:
            print(
                "Предупреждение: для google/api/annotations.proto нужен api-common-protos. "
                "Установите GRPC_GOOGLEAPIS_PROTO_PATH или положите third_party/api-common-protos. "
                "См. docs/README_yandex_grpc.md",
                file=sys.stderr,
            )

    grpc_root_str = str(grpc_root)
    proto_rel = [str(p.relative_to(grpc_root)).replace("\\", "/") for p in proto_files]

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        *[arg for inc in include_paths for arg in ("-I", inc)],
        f"--python_out={grpc_root_str}",
        f"--grpc_python_out={grpc_root_str}",
        *proto_rel,
    ]

    result = subprocess.run(cmd, cwd=str(grpc_root))
    if result.returncode != 0:
        return result.returncode

    _ensure_all_init_py(grpc_root)
    _fix_imports_in_generated(grpc_root)
    print("Генерация gRPC stubs завершена.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
