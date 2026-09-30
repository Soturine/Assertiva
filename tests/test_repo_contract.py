import subprocess
import sys

def test_repo_contract():
    result = subprocess.run([sys.executable, 'scripts/validate_repo.py'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
