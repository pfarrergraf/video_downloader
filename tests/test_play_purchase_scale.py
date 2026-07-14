from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_play_mapping_remains_idempotent_at_100k_rows() -> None:
    db = sqlite3.connect(":memory:")
    db.executescript((ROOT / "pro/website/schema.sql").read_text(encoding="utf-8"))
    now = 1_784_000_000
    licenses = []
    purchases = []
    for index in range(100_000):
        token_hash = hashlib.sha256(f"test-token-{index}".encode()).hexdigest()
        key = f"DLT-{token_hash[:8]}-{token_hash[8:16]}-{token_hash[16:24]}".upper()
        licenses.append((key, f"play-{index}@local.invalid", now, now))
        purchases.append((token_hash, "cipher", "iv", f"ORDER-{index}", key, now, now, now))
    with db:
        db.executemany(
            "INSERT INTO licenses (license_key,tier,email,status,created_at,updated_at) VALUES (?,'lifetime',?,'active',?,?)",
            licenses,
        )
        db.executemany(
            """INSERT INTO play_purchases
               (token_hash,purchase_token_ciphertext,purchase_token_iv,order_id,package_name,product_id,
                purchase_state,license_key,verified_at,created_at,updated_at)
               VALUES (?,?,?,?,'de.classydl.app','pro','purchased',?,?,?,?)
               ON CONFLICT(token_hash) DO UPDATE SET verified_at=excluded.verified_at""",
            purchases,
        )
        db.executemany(
            """INSERT INTO play_purchases
               (token_hash,purchase_token_ciphertext,purchase_token_iv,order_id,package_name,product_id,
                purchase_state,license_key,verified_at,created_at,updated_at)
               VALUES (?,?,?,?,'de.classydl.app','pro','purchased',?,?,?,?)
               ON CONFLICT(token_hash) DO UPDATE SET verified_at=excluded.verified_at""",
            purchases[:1000],
        )
    assert db.execute("SELECT COUNT(*) FROM play_purchases").fetchone()[0] == 100_000
    assert db.execute("SELECT COUNT(DISTINCT license_key) FROM play_purchases").fetchone()[0] == 100_000
