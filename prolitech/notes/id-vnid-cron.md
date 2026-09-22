# CSV to XLSX for id-vnid

Deployed script: `/home/rvbkkxiv/public_html/cli/box/convert_id_vnid.py`.
Requires only Python 3 (verified with the server's Python 3.6.8).

Scheduler command:

```sh
/usr/bin/python3 /home/rvbkkxiv/public_html/cli/box/convert_id_vnid.py >> /home/rvbkkxiv/public_html/cli/box/convert_id_vnid.log 2>&1
```

Example cron schedule, daily at 05:20 server time (before the existing 05:30 price export):

```cron
20 5 * * * /usr/bin/python3 /home/rvbkkxiv/public_html/cli/box/convert_id_vnid.py >> /home/rvbkkxiv/public_html/cli/box/convert_id_vnid.log 2>&1
```

The schedule is an example and has not been installed. The script was uploaded and run once.
It reads adjacent `id-vnid.csv` (UTF-8, semicolon delimiter), preserving both headers,
row order, duplicate IDs, empty values and leading zeros. All IDs are text cells.
The input is left untouched. A temporary XLSX is atomically renamed to `id-vnid.xlsx`
only after successful conversion; errors exit with code 1. A file lock prevents
concurrent converter runs. Upload the source CSV atomically, or schedule conversion
after its upload finishes; the converter lock cannot lock an external FTP uploader.

Verified on 2026-09-22: 3,754 data rows, 122 empty second-column values and 55
second-column IDs starting with zero. Every saved XLSX cell matched the source CSV.
