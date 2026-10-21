"""Tests for the RFC 6962 Merkle transparency log primitives."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.merkle import (
    consistency_proof,
    leaf_hash,
    node_hash,
    path,
    tree_hash,
    verify_consistency,
    verify_inclusion,
)


def dleaves(n: int) -> list[bytes]:
    """Deterministic leaf inputs d0..dn-1 (the RFC example uses d0..d6)."""

    return [f"d{i}".encode() for i in range(n)]


def incremental_tree_hash(leaves: list[bytes]) -> bytes:
    """RFC 9162 §2.1.2 stack algorithm — cross-check of the recursive tree_hash."""

    stack: list[bytes] = []
    for i, leaf in enumerate(leaves):
        stack.append(leaf_hash(leaf))
        merge_count = 0
        while (i >> merge_count) & 1:
            merge_count += 1
        for _ in range(merge_count):
            right = stack.pop()
            left = stack.pop()
            stack.append(node_hash(left, right))
    while len(stack) > 1:
        right = stack.pop()
        left = stack.pop()
        stack.append(node_hash(left, right))
    if not stack:
        return hashlib.sha256(b"").digest()
    return stack[0]


class TestTreeHash(unittest.TestCase):
    def test_empty_tree_hash_is_sha256_of_empty_string(self) -> None:
        self.assertEqual(tree_hash([]), hashlib.sha256(b"").digest())

    def test_leaf_hash_domain_separation(self) -> None:
        for leaf in (b"", b"a", b"\x00", bytes(range(256))):
            self.assertEqual(tree_hash([leaf]), hashlib.sha256(b"\x00" + leaf).digest())

    def test_recursive_matches_incremental_rfc9162_algorithm(self) -> None:
        for n in range(0, 40):
            self.assertEqual(tree_hash(dleaves(n)), incremental_tree_hash(dleaves(n)), msg=n)


class TestRfcWorkedExample(unittest.TestCase):
    """RFC 6962 §2.1.5 / RFC 9162 §2.1.5: the seven-leaf example tree."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.d = dleaves(7)
        cls.a = tree_hash(cls.d)  # root "hash"

    def test_audit_paths_match_rfc_structure(self) -> None:
        d = self.d
        leaf = leaf_hash
        mth = tree_hash
        # PATH(d0) = [b, h, l]; PATH(d3) = [c, g, l]; PATH(d4) = [f, j, k]; PATH(d6) = [i, k]
        self.assertEqual(path(0, d), [leaf(d[1]), mth(d[2:4]), mth(d[4:7])])
        self.assertEqual(path(3, d), [leaf(d[2]), mth(d[0:2]), mth(d[4:7])])
        self.assertEqual(path(4, d), [leaf(d[5]), mth(d[6:7]), mth(d[0:4])])
        self.assertEqual(path(6, d), [mth(d[4:6]), mth(d[0:4])])

    def test_every_audit_path_verifies(self) -> None:
        for index in range(7):
            audit = path(index, self.d)
            self.assertTrue(
                verify_inclusion(self.d[index], index, audit, 7, self.a),
                msg=f"index {index}",
            )

    def test_consistency_proofs_match_rfc_structure(self) -> None:
        d = self.d
        leaf = leaf_hash
        mth = tree_hash
        # PROOF(3, D[7]) = [c, d, g, l]; PROOF(4, D[7]) = [l]; PROOF(6, D[7]) = [i, j, k]
        self.assertEqual(
            consistency_proof(3, d),
            [leaf(d[2]), leaf(d[3]), mth(d[0:2]), mth(d[4:7])],
        )
        self.assertEqual(consistency_proof(4, d), [mth(d[4:7])])
        self.assertEqual(
            consistency_proof(6, d),
            [mth(d[4:6]), leaf(d[6]), mth(d[0:4])],
        )


class TestInclusionProperties(unittest.TestCase):
    def test_all_sizes_all_indices(self) -> None:
        for n in range(1, 41):
            leaves = dleaves(n)
            root = tree_hash(leaves)
            for index in range(n):
                audit = path(index, leaves)
                self.assertTrue(
                    verify_inclusion(leaves[index], index, audit, n, root), msg=(n, index)
                )

    def test_wrong_leaf_fails(self) -> None:
        leaves = dleaves(8)
        root = tree_hash(leaves)
        self.assertFalse(verify_inclusion(b"d0", 1, path(1, leaves), 8, root))
        self.assertFalse(verify_inclusion(b"z", 1, path(1, leaves), 8, root))

    def test_tampered_audit_path_fails(self) -> None:
        leaves = dleaves(13)
        root = tree_hash(leaves)
        for index in range(13):
            for position in range(len(path(index, leaves))):
                audit = [bytes(node) for node in path(index, leaves)]
                audit[position] = bytes([audit[position][0] ^ 1]) + audit[position][1:]
                self.assertFalse(
                    verify_inclusion(leaves[index], index, audit, 13, root),
                    msg=(index, position),
                )

    def test_out_of_bounds_fail(self) -> None:
        leaves = dleaves(4)
        root = tree_hash(leaves)
        self.assertFalse(verify_inclusion(leaves[0], 4, path(0, leaves), 4, root))
        self.assertFalse(verify_inclusion(leaves[0], 0, path(0, leaves), -1, root))
        with self.assertRaises(ValueError):
            path(4, leaves)


class TestConsistencyProperties(unittest.TestCase):
    def test_all_pairs(self) -> None:
        for n in range(2, 41):
            leaves = dleaves(n)
            new_root = tree_hash(leaves)
            for m in range(1, n):
                proof = consistency_proof(m, leaves)
                old_root = tree_hash(leaves[:m])
                self.assertTrue(
                    verify_consistency(m, n, proof, old_root, new_root), msg=(m, n)
                )
                # a proof generated over DIFFERENT underlying leaves must fail
                other = [f"e{i}".encode() for i in range(n)]
                other_proof = consistency_proof(m, other)
                self.assertFalse(
                    verify_consistency(m, n, other_proof, old_root, new_root),
                    msg=(m, n),
                )

    def test_tampered_proof_fails(self) -> None:
        leaves = dleaves(10)
        new_root = tree_hash(leaves)
        for m in range(1, 10):
            proof = [bytes(node) for node in consistency_proof(m, leaves)]
            old_root = tree_hash(leaves[:m])
            for position in range(len(proof)):
                spoiled = list(proof)
                spoiled[position] = bytes([spoiled[position][0] ^ 1]) + spoiled[position][1:]
                self.assertFalse(
                    verify_consistency(m, 10, spoiled, old_root, new_root), msg=(m, position)
                )

    def test_equal_head_requires_empty_proof(self) -> None:
        leaves = dleaves(5)
        root = tree_hash(leaves)
        self.assertTrue(verify_consistency(5, 5, [], root, root))
        self.assertFalse(verify_consistency(5, 5, [], root, tree_hash(dleaves(6))))
        self.assertFalse(verify_consistency(5, 5, [leaf_hash(b"x")], root, root))
        self.assertFalse(verify_consistency(5, 7, [], tree_hash(leaves[:5]), tree_hash(leaves)))

    def test_garbage_structure_fails(self) -> None:
        leaves = dleaves(9)
        old_root, new_root = tree_hash(leaves[:4]), tree_hash(leaves)
        self.assertFalse(verify_consistency(0, 9, consistency_proof(4, leaves), old_root, new_root))
        self.assertFalse(verify_consistency(5, 4, [], old_root, new_root))
        self.assertTrue(verify_consistency(4, 9, consistency_proof(4, leaves), old_root, new_root))


if __name__ == "__main__":
    unittest.main()
