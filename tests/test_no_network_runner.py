from pathlib import Path


def test_egress_denied_runner_uses_local_image_and_docker_network_isolation():
    script = Path("scripts/run_egress_denied_tests.ps1").read_text(encoding="utf-8")
    assert "docker image inspect $Image" in script
    assert "--network', 'none'" in script
    assert '--volume\', "${repoRoot}:/workspace:ro"' in script
    assert "--read-only" in script and "--cap-drop', 'ALL'" in script
    assert "docker run" not in script.replace("$dockerArgs = @(", "")
    assert "docker pull" not in script.lower()
    assert "docker build" not in script.lower()


def test_egress_guidance_distinguishes_container_and_host_controls():
    docs = Path("docs/container-security.md").read_text(encoding="utf-8").lower()
    assert "--network none" in docs
    assert "host-level deny-by-default" in docs
    assert "python socket guards alone" in docs
    assert "has not applied or independently verified a host firewall policy" in docs
