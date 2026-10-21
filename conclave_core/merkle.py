"""RFC 6962 Merkle transparency log over conclave artifacts (pure stdlib).

The transparency log is an append-only Merkle tree whose leaves are the
binary CID bytes of published verdicts (and, via M5, appeal outcomes).
Tree math follows RFC 6962 §2.1 exactly (same as RFC 9162 §2.1.1):

- leaves:      SHA-256(0x00 || leaf_bytes); empty tree root: SHA-256()
- interior:    SHA-256(0x01 || left || right)
- split rule:  k = largest power of two strictly smaller than n

Proof *generation* is transcribed from RFC 6962 §2.1.1/§2.1.2; proof
*verification* is transcribed verbatim (in iterative form) from RFC 9162
§2.1.3.2 (inclusion) and §2.1.4.2 (consistency). The RFC's worked example
(§2.1.5) is reproduced concretely in tests/test_merkle.py.

Signed tree heads carry (treeSize, root, publishedAt) and are published as
SignedTreeHead artifacts signed by the conclave identity key.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

__all__ = [
    "leaf_hash",
    "tree_hash",
    "node_hash",
    "path",
    "verify_inclusion",
    "consistency_proof",
    "verify_consistency",
]


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(leaf: bytes) -> bytes:
    """RFC 6962 §2.1: MTH({d0}) = SHA-256(0x00 || d0)."""

    return _h(b"\x00" + leaf)


def node_hash(left: bytes, right: bytes) -> bytes:
    """Interior node: SHA-256(0x01 || left || right)."""

    return _h(b"\x01" + left + right)


def _largest_power_of_two_below(n: int) -> int:
    """RFC 6962: k with k < n <= 2k (for n > 1)."""

    k = 1
    while k * 2 < n:
        k *= 2
    return k


def tree_hash(leaves: Sequence[bytes]) -> bytes:
    """RFC 6962 §2.1 Merkle Tree Hash over an ordered leaf list."""

    n = len(leaves)
    if n == 0:
        return _h(b"")
    if n == 1:
        return leaf_hash(leaves[0])
    k = _largest_power_of_two_below(n)
    return node_hash(tree_hash(leaves[:k]), tree_hash(leaves[k:]))


def path(index: int, leaves: Sequence[bytes]) -> list[bytes]:
    """RFC 6962 §2.1.1: inclusion audit path PATH(m, D[n])."""

    n = len(leaves)
    if not 0 <= index < n:
        raise ValueError(f"leaf index {index} outside tree of size {n}")
    if n == 1:
        return []
    k = _largest_power_of_two_below(n)
    if index < k:
        return path(index, leaves[:k]) + [tree_hash(leaves[k:])]
    return path(index - k, leaves[k:]) + [tree_hash(leaves[:k])]


def verify_inclusion(
    leaf: bytes, index: int, audit_path: Sequence[bytes], tree_size: int, root: bytes
) -> bool:
    """Inclusion-proof verifier (RFC 9162 §2.1.3.2, verbatim structure)."""

    if not 0 <= index < tree_size:
        return False
    fn, sn = index, tree_size - 1
    r = leaf_hash(leaf)
    for p in audit_path:
        if sn == 0:
            return False
        if (fn & 1) == 1 or fn == sn:
            r = node_hash(p, r)
            if (fn & 1) == 0:
                while (fn & 1) == 0 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


def consistency_proof(m: int, leaves: Sequence[bytes]) -> list[bytes]:
    """RFC 6962 §2.1.2: minimal consistency proof PROOF(m, D[n]); 1 <= m <= n."""

    n = len(leaves)
    if m > n or m < 1:
        raise ValueError("consistency proofs need 1 <= m <= len(leaves)")
    return _subproof(m, leaves, n, True)


def _subproof(m: int, leaves: Sequence[bytes], n: int, subtree: bool) -> list[bytes]:
    if m == n:
        if subtree:
            return []
        return [tree_hash(leaves[:n])]
    k = _largest_power_of_two_below(n)
    if m <= k:
        return _subproof(m, leaves, k, subtree) + [tree_hash(leaves[k:n])]
    return _subproof(m - k, leaves[k:], n - k, False) + [tree_hash(leaves[:k])]


def verify_consistency(
    first: int,
    second: int,
    consistency_path: Sequence[bytes],
    first_hash: bytes,
    second_hash: bytes,
) -> bool:
    """Consistency verifier (RFC 9162 §2.1.4.2, verbatim structure)."""

    if first < 1 or first > second:
        return False
    if first == second:
        return len(consistency_path) == 0 and first_hash == second_hash
    consistency_path = list(consistency_path)
    if not consistency_path:
        return False
    if first & (first - 1) == 0:  # first is an exact power of two
        consistency_path.insert(0, first_hash)
    fn, sn = first - 1, second - 1
    while (fn & 1) == 1:
        fn >>= 1
        sn >>= 1
    if not consistency_path:
        return False
    fr = sr = consistency_path[0]
    for c in consistency_path[1:]:
        if sn == 0:
            return False
        if (fn & 1) == 1 or fn == sn:
            fr = node_hash(c, fr)
            sr = node_hash(c, sr)
            if (fn & 1) == 0:
                while (fn & 1) == 0 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            sr = node_hash(sr, c)
        fn >>= 1
        sn >>= 1
    return sn == 0 and fr == first_hash and sr == second_hash
