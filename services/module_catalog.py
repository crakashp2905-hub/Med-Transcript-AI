"""Classify service modules and list API routes from repository source."""

import ast
from collections import Counter, deque
from importlib.util import resolve_name
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOTS = ("services.api.main", "services.worker_loop")
LABELS = (
    "integrated-in-production-flow",
    "candidate-only",
    "test-only",
    "documentation-only",
)


def _module_name(path, root):
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    name = ".".join(parts)
    return (
        f"services.{name}"
        if root.name == "services" and name
        else ("services" if root.name == "services" else name)
    )


def _package_name(module, path):
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _local_imports(tree, module, path, modules):
    package = _package_name(module, path)
    edges = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
                    edges.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative = "." * node.level + (node.module or "")
                base = resolve_name(relative, package)
            else:
                base = node.module or ""
            if base in modules:
                edges.add(base)
            for alias in node.names:
                candidate = f"{base}.{alias.name}" if base else alias.name
                if candidate in modules:
                    edges.add(candidate)
        elif (
            isinstance(node, ast.Call)
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "import_module"
                and isinstance(node.args[0].value, str)
            ):
                candidate = node.args[0].value
                if candidate.startswith("."):
                    candidate = resolve_name(candidate, package)
                if candidate in modules:
                    edges.add(candidate)
    return edges


def _closure(roots, graph):
    seen, pending = set(), deque(roots)
    while pending:
        module = pending.popleft()
        if module in seen or module not in graph:
            continue
        seen.add(module)
        parts = module.split(".")
        for length in range(1, len(parts)):
            parent = ".".join(parts[:length])
            if parent in graph:
                pending.append(parent)
        pending.extend(graph[module] - seen)
    return seen


def _endpoints(tree, module):
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(
                decorator.func, ast.Attribute
            ):
                continue
            method = decorator.func.attr.upper()
            if method not in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "OPTIONS",
                "HEAD",
                "API_ROUTE",
            }:
                continue
            route = next(
                (
                    arg.value
                    for arg in decorator.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ),
                None,
            )
            if route:
                rows.append(
                    {
                        "method": method,
                        "path": route,
                        "handler": node.name,
                        "module": module,
                    }
                )
    return rows


def build_catalog(root=ROOT):
    root = Path(root).resolve()
    paths = sorted((root / "services").rglob("*.py"))
    modules = {_module_name(path, root / "services"): path for path in paths}
    trees = {
        module: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module, path in modules.items()
    }
    graph = {
        module: _local_imports(trees[module], module, path, modules)
        for module, path in modules.items()
    }
    runtime = _closure(RUNTIME_ROOTS, graph)

    tests_root = root / "tests"
    test_roots = set()
    for path in tests_root.rglob("*.py") if tests_root.is_dir() else ():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (UnicodeDecodeError, SyntaxError):
            continue
        test_roots.update(_local_imports(tree, _module_name(path, root), path, modules))
    test_reachable = _closure(test_roots, graph)
    docs = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (root / "docs").rglob("*.md")
        if path.name != "service-catalog.md"
    )

    entries = []
    endpoints = []
    for module, path in sorted(modules.items()):
        if module in runtime:
            label = "integrated-in-production-flow"
            reason = "statically reachable from configured API or worker entry point"
        elif module in test_reachable:
            label = "test-only"
            reason = "imported by tests but not reachable from configured runtime roots"
        elif (
            f"services/{path.relative_to(root / 'services').as_posix()}" in docs
            or module in docs
        ):
            label = "documentation-only"
            reason = "referenced by documentation but absent from runtime and test import graphs"
        else:
            label = "candidate-only"
            reason = "not reachable from configured runtime roots or test imports"
        entries.append(
            {
                "module": module,
                "path": path.relative_to(root).as_posix(),
                "classification": label,
                "classification_basis": reason,
            }
        )
        endpoints.extend(_endpoints(trees[module], module))
    return {
        "modules": entries,
        "classification_counts": dict(
            Counter(row["classification"] for row in entries)
        ),
        "endpoints": sorted(
            endpoints, key=lambda row: (row["path"], row["method"], row["handler"])
        ),
        "runtime_roots": list(RUNTIME_ROOTS),
        "limitations": [
            "Reachability is inferred from static imports, including function-local imports; it does not prove a helper was executed in production.",
            "Dynamic imports built from non-literal values may be missed; human confirmation is required before treating a module as deployed.",
            "Endpoint discovery reads FastAPI-style decorators and may omit routes registered by runtime-generated code.",
        ],
    }


def render(catalog):
    lines = [
        "# Service and endpoint catalog",
        "",
        "Generated from the Python source tree. Runtime reachability is a static import analysis, not proof of actual invocation.",
        "",
        "## Module classification counts",
        "",
        "| Classification | Modules |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {label} | {catalog['classification_counts'].get(label, 0)} |"
        for label in LABELS
    )
    lines += [
        "",
        "## Service modules",
        "",
        "| Module | Classification | Basis |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{row['path']}` | `{row['classification']}` | {row['classification_basis']} |"
        for row in catalog["modules"]
    )
    lines += [
        "",
        "## Discovered HTTP endpoints",
        "",
        "| Method | Path | Handler | Module |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{row['method']}` | `{row['path']}` | `{row['handler']}` | `{row['module']}` |"
        for row in catalog["endpoints"]
    )
    lines += ["", "## Runtime roots", ""]
    lines.extend(f"- `{module}`" for module in catalog["runtime_roots"])
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in catalog["limitations"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    output = ROOT / "docs/service-catalog.md"
    output.write_text(render(build_catalog()), encoding="utf-8")
    print(f"catalog written: {output.relative_to(ROOT)}")
