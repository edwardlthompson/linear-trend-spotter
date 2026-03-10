import json
import os
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request


def env(name: str, required: bool = True, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def api_request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Token {token}",
    }
    data = None

    if payload is not None:
        encoded = urllib.parse.urlencode(payload)
        data = encoded.encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8").strip()
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API request failed ({error.code}): {details}") from error


def get_or_create_bash_console(base_url: str, username: str, token: str) -> int:
    list_url = f"{base_url}/api/v0/user/{username}/consoles/"
    consoles = api_request("GET", list_url, token)

    for console in consoles:
        if console.get("executable") == "bash":
            return int(console["id"])

    create_url = f"{base_url}/api/v0/user/{username}/consoles/"
    created = api_request("POST", create_url, token, payload={"executable": "bash"})
    return int(created["id"])


def build_sync_command() -> str:
    project_path = env("PA_PROJECT_PATH")
    branch = env("PA_BRANCH", required=False, default="main")
    install_requirements = env("PA_INSTALL_REQUIREMENTS", required=False, default="false").lower() == "true"
    venv_python = env("PA_VENV_PYTHON", required=False, default="")
    post_sync_command = env("PA_POST_SYNC_COMMAND", required=False, default="")

    safe_path = shlex.quote(project_path)
    safe_branch = shlex.quote(branch)

    commands = [
        "set -e",
        f"cd {safe_path}",
        f"git fetch origin {safe_branch}",
        f"git reset --hard origin/{safe_branch}",
        "git clean -fd",
    ]

    if install_requirements:
        python_cmd = shlex.quote(venv_python) if venv_python else "python3"
        commands.append(f"{python_cmd} -m pip install -r requirements.txt")

    if post_sync_command:
        commands.append(post_sync_command)

    return " && ".join(commands) + "\n"


def main() -> int:
    try:
        username = env("PA_USERNAME")
        token = env("PA_API_TOKEN")
        base_url = env("PA_API_BASE_URL", required=False, default="https://www.pythonanywhere.com")

        console_id = get_or_create_bash_console(base_url, username, token)
        sync_command = build_sync_command()

        send_url = f"{base_url}/api/v0/user/{username}/consoles/{console_id}/send_input/"
        api_request("POST", send_url, token, payload={"input": sync_command})

        print(f"Sync command queued on PythonAnywhere console #{console_id}")
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
