import csv
import hashlib
import os
import socket
import struct


def load_env(path):
    env = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def read_exact(sock, n):
    chunks = []
    left = n
    while left:
        chunk = sock.recv(left)
        if not chunk:
            raise RuntimeError("socket closed")
        chunks.append(chunk)
        left -= len(chunk)
    return b"".join(chunks)


def read_packet(sock):
    header = read_exact(sock, 4)
    length = header[0] | (header[1] << 8) | (header[2] << 16)
    return read_exact(sock, length)


def send_packet(sock, seq, payload):
    header = bytes([
        len(payload) & 0xFF,
        (len(payload) >> 8) & 0xFF,
        (len(payload) >> 16) & 0xFF,
        seq & 0xFF,
    ])
    sock.sendall(header + payload)


def read_null(buf, pos):
    end = buf.index(0, pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def lenenc_int(buf, pos):
    first = buf[pos]
    pos += 1
    if first < 0xFB:
        return first, pos
    if first == 0xFC:
        return struct.unpack_from("<H", buf, pos)[0], pos + 2
    if first == 0xFD:
        return buf[pos] | (buf[pos + 1] << 8) | (buf[pos + 2] << 16), pos + 3
    if first == 0xFE:
        return struct.unpack_from("<Q", buf, pos)[0], pos + 8
    return None, pos


def lenenc_str(buf, pos):
    length, pos = lenenc_int(buf, pos)
    if length is None:
        return None, pos
    value = buf[pos:pos + length].decode("utf-8", "replace")
    return value, pos + length


def mysql_error(packet):
    if packet and packet[0] == 0xFF:
        code = packet[1] | (packet[2] << 8)
        msg = packet[3:].decode("utf-8", "replace")
        if msg.startswith("#"):
            msg = msg[6:]
        return f"MySQL error {code}: {msg}"
    return None


def native_token(password, seed):
    p = password.encode("utf-8")
    s1 = hashlib.sha1(p).digest()
    s2 = hashlib.sha1(s1).digest()
    s3 = hashlib.sha1(seed + s2).digest()
    return bytes(a ^ b for a, b in zip(s1, s3))


def query_mysql(env, sql):
    host = env["DB_HOST"]
    port = int(env.get("DB_PORT", "3306"))
    user = env["DB_USERNAME"]
    password = env["DB_PASSWORD"]
    database = env["DB_DATABASE"]
    prefix = env.get("DB_PREFIX", "")
    sql = sql.replace("{prefix}", prefix)

    sock = socket.create_connection((host, port), timeout=20)
    sock.settimeout(30)
    try:
        hs = read_packet(sock)
        pos = 1
        _, pos = read_null(hs, pos)
        pos += 4
        seed1 = hs[pos:pos + 8]
        pos += 9
        pos += 2
        pos += 1 + 2
        pos += 2
        auth_len = hs[pos]
        pos += 1 + 10
        seed2 = hs[pos:pos + max(13, auth_len - 8)]
        pos += max(13, auth_len - 8)
        plugin = "mysql_native_password"
        if pos < len(hs):
            try:
                plugin, _ = read_null(hs, pos)
            except ValueError:
                pass
        if plugin != "mysql_native_password":
            raise RuntimeError(f"Unsupported auth plugin: {plugin}")

        seed = (seed1 + seed2)[:20]
        token = native_token(password, seed)
        flags = (
            1
            | 4
            | 8
            | 512
            | 32768
            | 0x00080000
            | 0x00020000
        )
        payload = bytearray()
        payload += struct.pack("<I", flags)
        payload += struct.pack("<I", 16 * 1024 * 1024)
        payload += bytes([33])
        payload += bytes(23)
        payload += user.encode("utf-8") + b"\0"
        payload += bytes([len(token)]) + token
        payload += database.encode("utf-8") + b"\0"
        payload += plugin.encode("ascii") + b"\0"
        send_packet(sock, 1, bytes(payload))

        auth = read_packet(sock)
        err = mysql_error(auth)
        if err:
            raise RuntimeError(err)
        if not auth or auth[0] != 0:
            raise RuntimeError(f"unexpected auth response: {auth[:8].hex()}")

        send_packet(sock, 0, b"\x03" + sql.encode("utf-8"))
        first = read_packet(sock)
        err = mysql_error(first)
        if err:
            raise RuntimeError(err)
        col_count, _ = lenenc_int(first, 0)
        for _ in range(col_count):
            read_packet(sock)
        read_packet(sock)

        rows = []
        while True:
            packet = read_packet(sock)
            if packet[0] == 0xFE and len(packet) < 9:
                break
            pos = 0
            row = []
            for _ in range(col_count):
                value, pos = lenenc_str(packet, pos)
                row.append(value)
            rows.append(row)
        return rows
    finally:
        sock.close()


SQL = """
SELECT
  COALESCE(NULLIF(p.sku, ''), p.model) AS sku,
  pd.name AS product_name_uk,
  COALESCE(GROUP_CONCAT(DISTINCT cd.name ORDER BY cd.name SEPARATOR ' | '), '') AS category_name
FROM {prefix}product p
JOIN {prefix}product_description pd
  ON pd.product_id = p.product_id
 AND pd.language_id = 1
LEFT JOIN {prefix}manufacturer m
  ON m.manufacturer_id = p.manufacturer_id
LEFT JOIN {prefix}product_to_category p2c
  ON p2c.product_id = p.product_id
LEFT JOIN {prefix}category_description cd
  ON cd.category_id = p2c.category_id
 AND cd.language_id = 1
WHERE p.manufacturer_id = 0
   OR m.manufacturer_id IS NULL
GROUP BY p.product_id, sku, product_name_uk
ORDER BY pd.name
"""


def main():
    env = load_env(".env_open")
    rows = query_mysql(env, SQL)
    out = os.path.abspath("open_products_without_brand.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sku", "назва товару укр", "назва категорії"])
        writer.writerows(rows)
    print(f"ok file={out} count={len(rows)}")


if __name__ == "__main__":
    main()
