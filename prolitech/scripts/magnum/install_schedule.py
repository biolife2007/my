"""Install the requested weekly schedule, preserving other cron entries."""
import os
import subprocess
from pathlib import Path

base = Path(__file__).resolve().parent
config = base / 'config.json'
os.chmod(str(config), 0o600)
current = subprocess.run(['crontab', '-l'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
if current.returncode not in (0, 1):
    raise SystemExit('Cannot read cron')
if current.returncode == 1 and 'no crontab' not in current.stderr.lower():
    raise SystemExit('Unexpected cron read error')
old = current.stdout
backup = base / 'crontab-before-magnum.txt'
if not backup.exists():
    fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f: f.write(old)
line = '0 8 * * 2 /usr/bin/python3 ' + str(base / 'monitor.py') + ' >> ' + str(base / 'monitor.log') + ' 2>&1 # magnum-url-monitor'
lines = [x for x in old.splitlines() if '# magnum-url-monitor' not in x]
new = '\n'.join(lines).rstrip() + '\n\n' + line + '\n'
subprocess.run(['crontab', '-'], input=new, universal_newlines=True, check=True)
installed = subprocess.check_output(['crontab', '-l'], universal_newlines=True)
assert line in installed.splitlines()
assert [x for x in installed.splitlines() if x.strip() and '# magnum-url-monitor' not in x] == [x for x in old.splitlines() if x.strip() and '# magnum-url-monitor' not in x]
print('Installed: ' + line)
