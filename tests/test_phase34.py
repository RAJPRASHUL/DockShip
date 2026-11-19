import hashlib
import hmac
import json

from dockship.webhook import verify_signature


def test_webhook_signature_verification():
    body = b'{"ok":true}'
    signature = "sha256=" + hmac.new(
        b"secret", body, hashlib.sha256
    ).hexdigest()
    assert verify_signature(body, signature, "secret")
    assert not verify_signature(body, "sha256=wrong", "secret")
    assert not verify_signature(body, None, "secret")


def test_webhook_signature_uses_raw_body():
    body = json.dumps({"value": 1}, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(
        b"secret", body, hashlib.sha256
    ).hexdigest()
    assert verify_signature(body, signature, "secret")
