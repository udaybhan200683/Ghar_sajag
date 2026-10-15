#!/usr/bin/env python3
from __future__ import annotations
import errno, fcntl, os, stat, subprocess, time, urllib.request, signal, socket
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LAB_HOST = "127.0.0.1"
LAB_PORT = int(os.environ.get("PLAYWRIGHT_PORT", "8766"))
DEFAULT_BASE = f"http://{LAB_HOST}:{LAB_PORT}"
BASE = os.environ.get("PWA_BASE_URL", DEFAULT_BASE)
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(exist_ok=True)
LAB_LOG = EVIDENCE / "playwright-lab.log"
PORT_START_LOCK = Path(f"/tmp/ghar_sajag_playwright_gate_port_{os.getuid()}.lock")


class LabPortOccupiedError(RuntimeError):
    """The requested browser-gate port is already owned by another process."""


@contextmanager
def port_start_lock():
    """Serialize lab port selection and startup across worktrees on this host."""
    flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(PORT_START_LOCK, flags, 0o600)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        os.close(descriptor)
        raise RuntimeError(f"ENVIRONMENT_BLOCKED: unsafe port-lock file {PORT_START_LOCK}")
    with os.fdopen(descriptor, "a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

def _bind_probe(host: str, port: int) -> None:
    """Probe with the same reuse policy as the owned ThreadingWSGIServer."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        # Browser connections can leave TCP entries in TIME_WAIT after the lab
        # exits. Those are not listeners and must not fail owned-lab cleanup.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))


def assert_lab_port_available(host: str = LAB_HOST, port: int = LAB_PORT) -> None:
    """Fail before the build if another lab owns the fixed browser-gate port."""
    try:
        _bind_probe(host, port)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise LabPortOccupiedError(
                f"ENVIRONMENT_BLOCKED: {host}:{port} is already occupied. "
                "Choose another validation port or let the browser gate select one."
            ) from exc
        if exc.errno in (errno.EPERM, errno.EACCES):
            raise RuntimeError(
                f"ENVIRONMENT_BLOCKED: sandbox cannot bind {host}:{port}; "
                "run make release-gate-final in the normal local terminal."
            ) from exc
        raise RuntimeError(f"ENVIRONMENT_BLOCKED: cannot bind {host}:{port}: {exc}") from exc


def ephemeral_lab_port(host: str = LAB_HOST) -> int:
    """Ask the OS for a currently unused loopback port for an owned lab."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, 0))
            return int(probe.getsockname()[1])
    except OSError as exc:
        if exc.errno in (errno.EPERM, errno.EACCES):
            raise RuntimeError(
                "ENVIRONMENT_BLOCKED: sandbox cannot allocate a loopback port; "
                "run make release-gate-final in the normal local terminal."
            ) from exc
        raise RuntimeError(f"ENVIRONMENT_BLOCKED: cannot allocate loopback port: {exc}") from exc


def select_lab_port(preferred: int = LAB_PORT, allow_alternate: bool = False) -> int:
    """Use the preferred port, optionally falling back only on address-in-use."""
    try:
        assert_lab_port_available(LAB_HOST, preferred)
        return preferred
    except LabPortOccupiedError:
        if not allow_alternate:
            raise
        for _ in range(8):
            port = ephemeral_lab_port(LAB_HOST)
            try:
                assert_lab_port_available(LAB_HOST, port)
            except LabPortOccupiedError:
                continue
            print(f"Preferred Playwright port {preferred} is occupied; selected {port}.", flush=True)
            return port
        raise RuntimeError("ENVIRONMENT_BLOCKED: could not reserve a free alternate Playwright port")


def validate_base_url(base_url: str = BASE, port: int = LAB_PORT) -> None:
    """Reject a Playwright URL that does not target this runner's lab port."""
    parsed = urlparse(base_url)
    if parsed.hostname != LAB_HOST or parsed.port != port:
        raise RuntimeError(
            f"ENVIRONMENT_BLOCKED: PWA_BASE_URL must target {LAB_HOST}:{port}; got {base_url}"
        )


def lab_command(port: int = LAB_PORT) -> list[str]:
    """Build the lab command using the same dedicated port as the URL."""
    return ["python3", "tools/sim/local_lab.py", "--port", str(port)]


def playwright_environment(base_url: str = BASE, port: int = LAB_PORT) -> dict[str, str]:
    """Return the browser environment after validating its lab endpoint."""
    validate_base_url(base_url, port)
    env = os.environ.copy()
    env["PWA_BASE_URL"] = base_url
    package_modules = str(ROOT / "frontend" / "node_modules")
    existing_modules = env.get("NODE_PATH")
    env["NODE_PATH"] = os.pathsep.join(
        [package_modules, *([existing_modules] if existing_modules else [])]
    )
    return env


def wait_for_port_available(host: str = LAB_HOST, port: int = LAB_PORT,
                            timeout: float = 5.0, interval: float = 0.05,
                            owner: subprocess.Popen | None = None) -> None:
    """Wait until a gate-owned listener has actually released its port.

    This is deliberately a reuse-aware bind probe rather than a fixed sleep.
    It distinguishes a listener from harmless TCP TIME_WAIT state left by the
    owned server's completed browser requests. EADDRINUSE is retried for a
    short bounded period; permission errors remain immediate setup errors.
    Callers use this only after terminating their own lab process.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            _bind_probe(host, port)
            return
        except OSError as exc:
            if exc.errno in (errno.EPERM, errno.EACCES):
                raise RuntimeError(
                    f"VALIDATION_HARNESS_ERROR: cannot verify release of {host}:{port}: {exc}"
                ) from exc
            if exc.errno != errno.EADDRINUSE:
                raise RuntimeError(
                    f"VALIDATION_HARNESS_ERROR: cannot verify release of {host}:{port}: {exc}"
                ) from exc
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                owner_detail = ""
                if owner is not None:
                    owner_detail = f"; owned lab pid={owner.pid}, returncode={owner.poll()}"
                raise RuntimeError(
                    f"VALIDATION_HARNESS_ERROR: listener still holds {host}:{port} "
                    f"after owned-lab cleanup within {timeout:g}s{owner_detail}"
                ) from exc
            time.sleep(min(interval, remaining))


def terminate_process_group(proc: subprocess.Popen, timeout: float = 5.0) -> str:
    """Terminate and reap a lab process and all children in its private group."""
    # Signal the private group even if the parent has already exited: an early
    # parent failure must not leave its simulator child orphaned.  A missing
    # group is harmless; the fallback is only used for a live non-session child.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError:
        if proc.poll() is None:
            proc.terminate()
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            proc.kill()
        try:
            output, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"VALIDATION_HARNESS_ERROR: owned lab process group {proc.pid} "
                f"did not terminate within {timeout:g}s after SIGKILL"
            ) from exc
    return output or ""

def wait_http(url: str, proc: subprocess.Popen, timeout: int = 60) -> None:
    """Wait for HTTP readiness, but fail immediately if the server process exits."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        rc = proc.poll()
        if rc is not None:
            output = ""
            try:
                output = proc.stdout.read() if proc.stdout else ""
            except Exception:
                pass
            LAB_LOG.write_text(output or "", encoding="utf-8")
            raise RuntimeError(
                f"lab server exited before becoming ready (exit={rc}). "
                f"See {LAB_LOG}\n{output[-4000:]}"
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return
        except Exception as e:
            last = e
        time.sleep(0.5)
    raise RuntimeError(
        f"server not ready after {timeout}s: {url}: {last}. "
        f"See {LAB_LOG}"
    )

def main() -> int:
    automatic_port = "PLAYWRIGHT_PORT" not in os.environ and "PWA_BASE_URL" not in os.environ
    validate_base_url()
    if not automatic_port:
        # Explicit port/base configuration remains a strict ownership contract.
        assert_lab_port_available(LAB_HOST, LAB_PORT)
    # release-gate sanitizer/trace stages may clean the build. Build before
    # starting the HTTP-readiness timer; WSL builds can take ~40-60 seconds.
    print("Preparing Playwright lab build...", flush=True)
    subprocess.run(["make", "lab-build"], cwd=ROOT, check=True)
    port = LAB_PORT
    base = BASE
    lab = None
    result = 1
    cleanup_errors = []
    try:
        # Keep selection and startup under a host-wide lock so concurrent gate
        # runs in separate worktrees cannot choose the same ephemeral port.
        with port_start_lock():
            port = select_lab_port(LAB_PORT, allow_alternate=automatic_port)
            if automatic_port:
                base = f"http://{LAB_HOST}:{port}"
            validate_base_url(base, port)
            assert_lab_port_available(LAB_HOST, port)
            print("Starting Parivar Saathi / Ghar Sajag local lab...", flush=True)
            lab = subprocess.Popen(
                lab_command(port), cwd=ROOT,
                env={**os.environ, "GS_APP_DB": ":memory:"},
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1, start_new_session=True,
            )
            try:
                wait_http(base, lab, timeout=60)
            except BaseException:
                # Do not release the startup lock while an unsuccessful owned
                # server could still hold its selected port.
                out = terminate_process_group(lab)
                LAB_LOG.write_text(out or "", encoding="utf-8")
                wait_for_port_available(port=port, owner=lab)
                lab = None
                raise
        print(f"Lab ready: {base}", flush=True)
        result = subprocess.call(["npx", "playwright", "test"], cwd=ROOT / "frontend",
                                 env=playwright_environment(base, port))
        if result == 0:
            print("Running Engineering Dashboard PREVIEW_ONLY review suite...", flush=True)
            result = subprocess.call(
                ["node", "tests/support/engineering_dashboard_review/review_browser.mjs"],
                cwd=ROOT, env=os.environ.copy(),
            )
    finally:
        if lab is not None:
            out = ""
            try:
                out = terminate_process_group(lab)
            except RuntimeError as exc:
                cleanup_errors.append(str(exc))
            LAB_LOG.write_text(out or "", encoding="utf-8")
            try:
                wait_for_port_available(port=port, owner=lab)
            except RuntimeError as exc:
                cleanup_errors.append(str(exc))
    if cleanup_errors:
        print("\n".join(cleanup_errors), flush=True)
        return 1
    return result

if __name__ == "__main__":
    raise SystemExit(main())
