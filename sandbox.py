"""Run generated code only inside a networkless bubblewrap namespace."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile


class IsolationError(RuntimeError):
    pass


def evaluate(request, *, wall_seconds=None, cpu_seconds=None):
    executable = shutil.which("bwrap")
    if sys.platform != "linux" or not executable:
        raise IsolationError("Linux and bubblewrap are required; no unrestricted fallback")
    mode = request.get("mode")
    default_cpu = 120 if mode == "unit" else 12
    payload = dict(request, cpu_seconds=cpu_seconds or default_cpu)
    encoded = json.dumps(payload, allow_nan=False).encode()
    if len(encoded) > 2 * 1024 * 1024:
        raise ValueError("Sandbox request exceeds 2 MiB")
    prefix = Path(sys.prefix).resolve()
    command = [executable, "--die-with-parent", "--new-session", "--unshare-all", "--clearenv"]
    for location in [Path("/usr"), Path("/lib"), Path("/lib64")]:
        if location.exists():
            command += ["--ro-bind", str(location), str(location)]
    for location in {prefix, Path(sys.base_prefix).resolve()}:
        if str(location) not in ("/usr",) and not str(location).startswith("/usr/"):
            command += ["--ro-bind", str(location), str(location)]
        elif str(location).startswith("/usr/local"):
            continue
    command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/work",
                "--ro-bind", str(Path(__file__).resolve()), "/work/sandbox.py",
                "--chdir", "/work"]
    for key, value in {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                       "MKL_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1",
                       "LD_LIBRARY_PATH": str(prefix / "lib")}.items():
        command += ["--setenv", key, value]
    command += [str(Path(sys.executable).resolve()), "-I", "/work/sandbox.py", "--worker"]
    # File-backed output plus the worker's file limit also bounds direct os.write calls.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                   start_new_session=True, env={"PATH": "/usr/bin:/bin"})
        try:
            process.communicate(encoded, timeout=wall_seconds or default_cpu + 15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return {"status": "timeout"}
        stdout.seek(0)
        raw = stdout.read(1024 * 1024 + 1)
        stderr.seek(0)
        error = stderr.read(4000).decode(errors="replace")
    if "bwrap:" in error:
        raise IsolationError("bubblewrap could not establish isolation: " + error.splitlines()[0])
    if process.returncode:
        return {"status": "process_error", "returncode": process.returncode}
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        return {"status": "invalid_worker_output"}
    if not isinstance(result, dict) or "status" not in result:
        return {"status": "invalid_worker_output"}
    if result["status"] == "dependency_error":
        raise IsolationError("Sandbox dependency unavailable: " + result.get("module", "unknown"))
    return result


def preflight():
    result = evaluate({"mode": "probe"})
    if result.get("status") != "ok":
        raise IsolationError("Sandbox self-check failed: " + str(result.get("status")))
    return result


# The following functions run only in the isolated child process.

import ast
import contextlib
import inspect
import io
import json
import math
import re
import resource
import sys
import types
import unittest


class BoundedText(io.StringIO):
    def write(self, value):
        available = max(0, 16000 - self.tell())
        super().write(value[:available])
        return len(value)


def numeric(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numerical reference")
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError("Empty numerical list")
        return [numeric(x) for x in value]
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("Nonfinite number")
        return value
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Unsupported numerical value")
    text = value.strip().strip("$").strip()
    text = text.replace(r"\left", "").replace(r"\right", "")
    if re.search(r"\\(?:text|mathrm|operatorname)\s*\{", text):
        raise ValueError("Units or text in boxed answer")
    if re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
        return numeric(float(text.replace(",", "")))
    try:
        item = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        item = None
    if isinstance(item, (list, tuple, int, float, bool)):
        return numeric(item)
    if text[:1] in ("[", "(") and text[-1:] == {"[": "]", "(": ")"}.get(text[:1]):
        depth, start, parts = 0, 1, []
        for i, char in enumerate(text[1:-1], 1):
            if char in "[{(":
                depth += 1
            elif char in "]})":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(text[start:i]); start = i + 1
        if parts:
            parts.append(text[start:-1])
            return [numeric(part) for part in parts]
    plain = text.replace(r"\,", "").replace(" ", "")
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", plain):
        return numeric(float(plain))
    scientific = re.fullmatch(r"([+-]?[\d.]+)\\(?:times|cdot)10\^\{?([+-]?\d+)\}?", plain)
    if scientific:
        return numeric(float(scientific[1]) * 10 ** int(scientific[2]))
    if plain.lower() in {"nan", "inf", "infinity", "+inf", "-inf"}:
        raise ValueError("Nonfinite number")
    syntax = re.sub(r"\\(?:frac|dfrac|tfrac|sqrt|pi|times|cdot|displaystyle|textstyle)\b", "", text)
    syntax = syntax.replace(r"\,", "").replace(r"\!", "")
    if not re.fullmatch(r"[\d\s{}()\[\].,+*/^eE-]*", syntax):
        raise ValueError("Only complete unit-free numerical expressions are accepted")
    from math_verify import parse
    parsed = parse("$" + text + "$", fallback_mode="no_fallback")
    if len(parsed) != 1:
        raise ValueError("Cannot parse numerical expression")
    item = parsed[0]
    if isinstance(item, (tuple, list)):
        return numeric(item)
    if getattr(item, "free_symbols", None) or getattr(item, "is_real", None) is not True:
        raise ValueError("Not a real numerical expression")
    return numeric(float(item.evalf()))


def close(actual, expected, relative, zero_absolute):
    if isinstance(actual, list) or isinstance(expected, list):
        return (isinstance(actual, list) and isinstance(expected, list)
                and len(actual) == len(expected)
                and all(close(a, b, relative, zero_absolute) for a, b in zip(actual, expected)))
    if expected == 0:
        return abs(actual) <= zero_absolute
    error, allowed = abs(actual - expected), relative * abs(expected)
    return error <= allowed or math.isclose(error, allowed, rel_tol=1e-12, abs_tol=0.0)


def work(request):
    mode = request["mode"]
    if mode == "probe":
        return {"status": "ok"}
    if mode == "compare":
        actual, expected = numeric(request["actual"]), numeric(request["expected"])
        return {"status": "ok", "match": close(actual, expected, request.get("rtol", .05),
                                                 request.get("zero_atol", 1e-12)),
                "actual": actual, "expected": expected}
    module = types.ModuleType("tire_generated_program")
    sys.modules[module.__name__] = module
    code = request["code"]
    exec(compile(code, "<formula-program>", "exec"), module.__dict__)
    if mode == "unit":
        exec(compile(request["tests"], "<formula-tests>", "exec"), module.__dict__)
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(stream=BoundedText()).run(suite)
        return {"status": "passed" if result.wasSuccessful() and result.testsRun else "failed",
                "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)}
    if mode != "execute":
        raise ValueError("Unknown worker mode")
    names = [n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)]
    name = request.get("function") or (names[0] if len(names) == 1 else None)
    if name not in names:
        raise ValueError("Explicit top-level function required")
    function = getattr(module, name)
    params = request["parameters"]
    inspect.signature(function).bind(**params)
    value = numeric(function(**params))
    return {"status": "ok", "value": value, "function": name}


def worker_main():
    request = json.load(sys.stdin)
    cpu = max(1, min(120, int(request.get("cpu_seconds", 12))))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    with contextlib.redirect_stdout(BoundedText()), contextlib.redirect_stderr(BoundedText()):
        try:
            result = work(request)
        except ModuleNotFoundError as error:
            result = {"status": "dependency_error", "module": error.name}
        except BaseException as error:
            result = {"status": "failed", "error_type": type(error).__name__}
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use pipeline.py")
    worker_main()

