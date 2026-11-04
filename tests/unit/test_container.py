import app.container as container

class Proc:
    def __init__(self, name, exit_code=None):
        self.name, self.exit_code, self.terminated = name, exit_code, False
    def poll(self): return self.exit_code
    def terminate(self): self.terminated = True
    def wait(self, timeout=None): return self.exit_code
    def kill(self): self.terminated = True

def test_launcher_starts_api_before_console_and_stops_children(monkeypatch):
    made = []
    def popen(command):
        is_api = "s3_server" in " ".join(command)
        p = Proc("api" if is_api else "console", 1 if is_api else None)
        made.append((command, p)); return p
    monkeypatch.setattr(container.subprocess, "Popen", popen)
    monkeypatch.setattr(container, "_wait_for", lambda url, process: True)
    monkeypatch.setattr(container.signal, "signal", lambda *args: None)
    assert container.main() == 1
    assert "app.s3_server:app" in made[0][0]
    assert "app.console_server:app" in made[1][0]
    assert made[1][1].terminated

def test_launcher_returns_failure_when_api_never_ready(monkeypatch):
    api = Proc("api")
    monkeypatch.setattr(container.subprocess, "Popen", lambda command: api)
    monkeypatch.setattr(container, "_wait_for", lambda url, process: False)
    monkeypatch.setattr(container.signal, "signal", lambda *args: None)
    assert container.main() == 1
    assert api.terminated

def test_launcher_has_no_shell_processes():
    assert all(isinstance(command, list) for command in (container.API, container.CONSOLE))
