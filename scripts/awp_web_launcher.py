"""One-command launcher for the local Novel Coding browser workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT.parent))

from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog


class LauncherError(RuntimeError):
    pass


@dataclass(frozen=True)
class LauncherResult:
    url: str
    started_process: bool


class WebLauncher:
    def __init__(
        self,
        repository_root: Path = _PROJECT_ROOT,
        *,
        health_probe: Callable[[], bool] | None = None,
        browser_open: Callable[[str], object] = webbrowser.open,
        process_start: Callable[[], object] | None = None,
    ):
        self.repository_root = Path(repository_root).resolve()
        self.health_probe = health_probe or self._probe
        self.browser_open = browser_open
        self.process_start = process_start or self._start_process

    def preflight(self) -> None:
        if shutil.which("node") is None:
            raise LauncherError("需要 Node.js >=22.19。")
        try:
            result = subprocess.run(
                ["node", "-v"],
                capture_output=True, text=True, timeout=5,
            )
            version_str = result.stdout.strip().lstrip("v")
            major = int(version_str.split(".")[0])
            if major < 22:
                raise LauncherError(
                    f"Node.js >=22.19 is required, found v{version_str}"
                )
        except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
            pass
        harness = self.repository_root / "agent_harness" / "node_modules" / "@earendil-works" / "pi-coding-agent"
        if not harness.exists():
            raise LauncherError("agent_harness 依赖不完整，请运行：cd agent_harness && npm ci")
        if not (self.repository_root / "frontend" / "dist" / "index.html").is_file():
            raise LauncherError("网页尚未构建，请运行：cd web && npm ci && npm run build")

    def start(self, project_name: str = "", *, open_project_list: bool = False) -> LauncherResult:
        self.preflight()
        selected = None
        if not open_project_list:
            workspaces = NovelWorkspaceCatalog(self.repository_root).list()
            if not workspaces:
                raise LauncherError("没有发现 novels/*/.novel_cli.json 小说项目。")
            selected = next(
                (item for item in workspaces if not project_name or item.project_id == project_name or item.root.name == project_name),
                None,
            )
            if selected is None:
                raise LauncherError(f"找不到小说项目：{project_name}")
        started = False
        if not self.health_probe():
            self.process_start()
            started = True
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self.health_probe():
                    break
                time.sleep(0.2)
            else:
                raise LauncherError("本地服务在 15 秒内未就绪，请查看终端错误。")
        url = (
            "http://127.0.0.1:8188/awp/novels"
            if open_project_list
            else f"http://127.0.0.1:8188/awp/novels/{selected.project_id}/workspace/book"
        )
        self.browser_open(url)
        return LauncherResult(url=url, started_process=started)

    @staticmethod
    def _probe() -> bool:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8188/awp/api/v1/health", timeout=0.7) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def _start_process(self) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, str(self.repository_root / "scripts" / "awp_server.py")],
            cwd=self.repository_root,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Novel Coding 写作工作区")
    parser.add_argument("project", nargs="?", default="")
    parser.add_argument("--projects", action="store_true", help="打开小说项目列表")
    args = parser.parse_args()
    try:
        result = WebLauncher().start(args.project, open_project_list=args.projects)
    except LauncherError as exc:
        raise SystemExit(f"启动失败：{exc}") from exc
    print(f"已打开：{result.url}")


if __name__ == "__main__":
    main()
