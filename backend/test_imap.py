"""
163.com IMAP 诊断脚本
用法: python test_imap.py <email> <授权码>
示例: python test_imap.py catfishliu@163.com ABCDEFGHIJKLMNO

诊断内容:
  1. SSL 连接 + 登录
  2. 发送 IMAP ID 命令（原始字节），显示服务器原始响应
  3. SELECT INBOX，显示是否成功及邮件数
  4. SEARCH ALL，显示 UID 列表（最多显示前 10 个）
"""
import imaplib
import sys


def run(email: str, password: str, host: str = "imap.163.com", port: int = 993):
    print(f"\n=== 连接 {host}:{port} ===")
    imap = imaplib.IMAP4_SSL(host, port)

    # 登录
    print(f"登录 {email} ...")
    try:
        typ, data = imap.login(email, password)
        print(f"  login: {typ} {data}")
    except Exception as e:
        print(f"  login 失败: {e}")
        return

    # --- ID 命令（原始字节，绕过 _checkquote）---
    print("\n=== 发送 ID 命令（原始字节格式）===")
    try:
        imap.send(b'ZIDCMD1 ID ("name" "MailSage" "version" "1.0")\r\n')
        id_lines = []
        while True:
            line = imap.readline()
            id_lines.append(line)
            if line.startswith(b'ZIDCMD1'):
                break
        for l in id_lines:
            print(f"  S: {l.rstrip()}")
    except Exception as e:
        print(f"  ID 命令失败: {e}")

    # --- SELECT INBOX ---
    print("\n=== SELECT INBOX ===")
    try:
        typ, data = imap.select("INBOX")
        print(f"  typ: {typ}")
        for d in data:
            print(f"  data: {d}")
        if typ != "OK":
            print("  !! SELECT 失败，无法继续")
            imap.logout()
            return
        print(f"  邮箱中共 {data[0].decode()} 封邮件")
    except Exception as e:
        print(f"  SELECT 失败: {e}")
        imap.logout()
        return

    # --- SEARCH ALL（显示 UID）---
    print("\n=== SEARCH ALL (UID) ===")
    try:
        typ, data = imap.uid("search", None, "ALL")
        uids = data[0].decode().split() if data[0] else []
        print(f"  找到 {len(uids)} 封邮件")
        if uids:
            preview = uids[-10:] if len(uids) > 10 else uids
            print(f"  最新 UID（最多10个）: {preview}")
    except Exception as e:
        print(f"  SEARCH 失败: {e}")

    imap.logout()
    print("\n=== 完成，连接已关闭 ===\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python test_imap.py <email> <授权码> [imap_host] [imap_port]")
        sys.exit(1)

    _email = sys.argv[1]
    _password = sys.argv[2]
    _host = sys.argv[3] if len(sys.argv) > 3 else "imap.163.com"
    _port = int(sys.argv[4]) if len(sys.argv) > 4 else 993

    run(_email, _password, _host, _port)
