# checks which urls our server is willing to visit, no internet needed
# run with:  python backend/test_url_safety.py

import sys

import scraper
from scraper import FetchError, check_url_is_safe

failed = 0


def check(name, condition):
    global failed
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    if not condition:
        failed += 1


def blocked(url, reason=None):
    # reason lets a test say WHY it should be blocked, so it can't pass by accident
    try:
        check_url_is_safe(url)
        return False
    except FetchError as e:
        return reason is None or reason in e.message


# pretend every normal website name points at a public address,
# so these tests don't depend on real dns
real_resolve = scraper.resolve_ips
scraper.resolve_ips = lambda host: {"93.184.216.34"}

check("normal https link is allowed", not blocked("https://example.com/some/page"))
check("normal http link is allowed", not blocked("http://example.com/"))
check("explicit port 443 is allowed", not blocked("https://example.com:443/"))

check("ftp is blocked", blocked("ftp://example.com/file"))
check("file:// is blocked", blocked("file:///etc/passwd"))
check("javascript: is blocked", blocked("javascript:alert(1)"))
check("no scheme is blocked", blocked("example.com/page"))
check("username:password in link is blocked", blocked("http://user:pass@example.com/"))
check("port 22 is blocked", blocked("http://example.com:22/"))
check("port 8080 is blocked", blocked("http://example.com:8080/"))
check("garbage port is blocked, doesn't crash", blocked("http://example.com:abc/"))
check("broken ipv6 brackets don't crash", blocked("http://[bad/"))
check("very long link is blocked", blocked("http://example.com/" + "a" * 3000))

# a name with one public and one private address must still be blocked
scraper.resolve_ips = lambda host: {"93.184.216.34", "10.0.0.5"}
check("name pointing at public AND private is blocked", blocked("http://sneaky.example/", "address"))

# from here on use the real lookup (these are all numbers or localhost)
scraper.resolve_ips = real_resolve

check("localhost is blocked", blocked("http://localhost/", "address"))
check("127.0.0.1 is blocked", blocked("http://127.0.0.1/", "address"))
check("127.1 short form is blocked", blocked("http://127.1/", "address"))
check("decimal 2130706433 is blocked", blocked("http://2130706433/", "address"))
check("hex 0x7f000001 is blocked", blocked("http://0x7f000001/", "address"))
check("10.x private range is blocked", blocked("http://10.0.0.5/", "address"))
check("192.168.x private range is blocked", blocked("http://192.168.1.1/", "address"))
check("172.16.x private range is blocked", blocked("http://172.16.0.1/", "address"))
check("cloud metadata address is blocked", blocked("http://169.254.169.254/latest/meta-data", "address"))
check("0.0.0.0 is blocked", blocked("http://0.0.0.0/", "address"))
check("ipv6 loopback is blocked", blocked("http://[::1]/", "address"))
check("ipv4 hidden inside ipv6 is blocked", blocked("http://[::ffff:127.0.0.1]/", "address"))
check("a name that doesn't exist is an error, not a crash",
      blocked("http://this-name-does-not-exist.invalid/", "could not find"))

print()
if failed == 0:
    print("all url safety checks passed")
else:
    print(f"{failed} check(s) failed, look above")
    sys.exit(1)