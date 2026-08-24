"""Deterministic synthetic test data.

Seeded from stable story IDs so generated fixtures are reproducible across
runs and machines; no real user data is ever used in factory tests.
"""

import hashlib

FIRST_NAMES = ["Ava", "Ben", "Chloe", "Dev", "Elena", "Farid", "Grace", "Hiro"]
DOMAINS = ["example.com", "test.local", "sample.org"]
CATEGORIES = ["bug", "idea", "praise", "question"]


def _pick(seed: str, salt: str, options: list[str]) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return options[digest[0] % len(options)]


def generate_synthetic_records(seed: str, count: int = 3) -> list[dict]:
    records = []
    for index in range(1, count + 1):
        name = _pick(seed, f"name{index}", FIRST_NAMES)
        domain = _pick(seed, f"domain{index}", DOMAINS)
        records.append(
            {
                "name": name,
                "email": f"{name.lower()}{index}@{domain}",
                "category": _pick(seed, f"cat{index}", CATEGORIES),
                "message": f"Synthetic record {index} for {seed}",
            }
        )
    return records
