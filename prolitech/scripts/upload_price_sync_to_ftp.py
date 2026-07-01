import ftplib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/cli/price-sync"


def load_env(path):
    env = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def ensure_dir(ftp, path):
    current = ftp.pwd()
    try:
        ftp.cwd("/")
        for part in path.strip("/").split("/"):
            if not part:
                continue
            try:
                ftp.cwd(part)
            except ftplib.error_perm:
                ftp.mkd(part)
                ftp.cwd(part)
    finally:
        ftp.cwd(current)


def upload_file(ftp, local_path, remote_path):
    remote_dir = str(Path(remote_path).parent).replace("\\", "/")
    remote_name = Path(remote_path).name
    ensure_dir(ftp, remote_dir)
    ftp.cwd(remote_dir)
    with local_path.open("rb") as f:
        ftp.storbinary(f"STOR {remote_name}", f)


def main():
    env = load_env(ROOT / ".env_open")
    ftp = ftplib.FTP()
    ftp.connect(env["FTP_HOST"], int(env.get("FTP_PORT", "21")), timeout=30)
    ftp.login(env["FTP_USERNAME"], env["FTP_PASSWORD"])
    ftp.set_pasv(False)
    try:
        for directory in [
            REMOTE_ROOT,
            f"{REMOTE_ROOT}/scripts",
            f"{REMOTE_ROOT}/exports",
            f"{REMOTE_ROOT}/logs",
        ]:
            ensure_dir(ftp, directory)

        upload_file(
            ftp,
            ROOT / "scripts" / "export_open_prices_csv.py",
            f"{REMOTE_ROOT}/scripts/export_open_prices_csv.py",
        )
        upload_file(
            ftp,
            ROOT / ".env_open.example",
            f"{REMOTE_ROOT}/.env_open.example",
        )
        current_csv = ROOT / "exports" / "prolitech_prices_current.csv"
        if current_csv.exists():
            upload_file(
                ftp,
                current_csv,
                f"{REMOTE_ROOT}/exports/prolitech_prices_current.csv",
            )

        print(f"ok uploaded_to={REMOTE_ROOT}")
    finally:
        ftp.quit()


if __name__ == "__main__":
    main()
