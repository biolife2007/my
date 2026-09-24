import os
import subprocess
from pathlib import Path
base=Path(__file__).resolve().parent
old=subprocess.check_output(['crontab','-l'],universal_newlines=True)
backup=base/'crontab-before-orders.txt'
if not backup.exists():
    fd=os.open(str(backup),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(old)
line='*/15 * * * * /usr/bin/python3 '+str(base/'order_notify.py')+' >> '+str(base/'orders.log')+' 2>&1 # telegram-new-orders'
lines=[x for x in old.splitlines() if '# telegram-new-orders' not in x]
subprocess.run(['crontab','-'],input='\n'.join(lines).rstrip()+'\n\n'+line+'\n',universal_newlines=True,check=True)
new=subprocess.check_output(['crontab','-l'],universal_newlines=True)
assert line in new.splitlines()
assert [x for x in new.splitlines() if x.strip() and '# telegram-new-orders' not in x]==[x for x in old.splitlines() if x.strip() and '# telegram-new-orders' not in x]
print(line)
