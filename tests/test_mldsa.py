"""Tests for the OpenSSL-backed ML-DSA-65 adapter (conclave_core.mldsa)."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.artifacts import ArtifactError, make_key_publication, validate_artifact
from conclave_core.mldsa import (
    PK_SIZE,
    SEED_SIZE,
    SIG_SIZE,
    keygen,
    keypair_from_seed,
    public_fingerprint,
    public_key_bytes,
    sign,
    verify,
)

# Deterministic test seed; the pinned values below work as a conformance
# anchor for the seed -> public-key derivation (FIPS 204 is a fixed standard,
# so these MUST stay stable across cryptography/OpenSSL upgrades).
TEST_SEED = hashlib.sha256(b"conclave-m2-mldsa-v1").digest()
PINNED_PUBLIC_KEY = bytes.fromhex(
    "b4363ad4330b208c50ea409a2cc5252d549be4863fe9935388586bd4d536765f1805eb33960a6bb"
    "32198afe393eef5edab40ea64073d53a1ac0ccc367fdaca39b60d98c0916d09d449f3364f70dcf0834"
    "b594bb9732edc9562c34a85aab83b2227448dbe7a76cbdf9be83c0ef6f8fd924d045114a4bb882a9c3"
    "07c5230faebb78c36db7efce27da351affb3b6182ccc83639da49ff5806196647f51c39e91a7c25760"
    "46c7fc463360a783d6369925633a22d8da0800d76ffce650fa720322d3d16403b4ffb15c7eb2b3f39e"
    "43148db52df06884acdddf902c85de7351220673ab39cd280d31c63a368a49c5d3cd0baae4035523f2c"
    "4d39e033f8c58eca714e73fe6c53232480c39a0835fabbd4e04816ed7866367488a0daa9f93d1c1505"
    "e78692be53d1e64a630d467bcdc2b458c578e1aadf04473412d34ab7a5575040501790350abd2c2be2"
    "1dae8ce365d84cb28e5d6bd634241fb672cac84703977a48df522a3d41f2f5c20f500e8c2a379f0404"
    "192d49b7f5ae3be34f941f87c54454b375dee05e40fe7593cee0bce4e7a4af43fb0b2dfe4b38c7cb35"
    "9a92d063debeeab02410f3f8262ba5a976d4e21294e4f03b045398b4e3a3ba9419d2a8388058bf9866"
    "09d5eedd4e51d405c9f40ab4342fd94b9699b32d9c76d1c9f6293442b71c00684cefbe2379a059bf5a"
    "34c6b95fdeb81a0a4868114b05996bf3779fb3722ce792736b0a48f86bc7169da0f9599ac3223d88b5"
    "4fddb292a95afba6d5474473cd39b0953743b4febb276b93aea7d73bfd4d5bd276c1433288bf875b64"
    "3f6a17dd751a27a6ed06de7a1b9b8a2d09d897bd76136dcd8fb8092633b832acef0dee2e81b23d43174"
    "abc5ace62a132a1e4ce64b533858c83261769fab79876db553780452a937d16de55e879564c87194a66"
    "95235e6572ecc45e34afcf6a09676ba503f35504e12d853ebcdc27119adcaba14c21619527c4e74da350"
    "58020d6903622cfaf82f23a8c21b704729d833098e00db588f8c8f3aab43f77dc1f60a3d722a7b3af92"
    "847fbc8b1dc6befd8b05bbcc74dc70703f1e38fc8ed78662872c761d30052e17e27158b576cfb6e8977"
    "316f656eedaacf23f92d70ea20c8c82749e6d23a3b1cb867a8442adcaa3fec730a0dd218937176201f0"
    "f3a7b41a2a80a11cf58cba57e5c26c9ae5521f1571b3e773c2f220c0a179b22b51711008563cf78286a"
    "ebcc3476c2bb46ddeab9369d78641bef8fecfa91e69900a539eee8cf9c45a3dd43582b86d0b7e4d9b42"
    "7c26841acb50692ab1b6503676040d14d4784f064dca6f3c04dda74f2c94bd30ac733044563eda4f13c"
    "007d49bbfd0b3930283ec339fa932a831350ffef3aa20e8e2a660500980da2abcae80fabbb3d42f2f10"
    "5f0895a95ed5da078845fad80c5b932efe25e790d6a3f03e0b9eda4ae3471fba04d54c71f0615ca4cb7"
    "d663149a9ba5ebac0a03b185757d79a01a0592d9c1c255bd092ace43f7bf7cfd4e4cee2a2376cd4f912"
    "cb254bd7df5fb8f5a3cb1e441f8558dcf970e19f1c7384eb357e3cf0760eea500b39adcb75609ea9429"
    "704d57151567639e78f0bebfda55512cc2f8f36ddf521590f64ec590cc81f274a3e71b8eea405a8ba62"
    "f24a663640518f367494376cb2cc12b28f7651b55a13c307576e6bdaa0b055e6ac146826e49097a1c83"
    "1495a5792274716f292d42a953468b65c54596745594d18f2ffb9138dc5e58c16a12f59a02de2804a34"
    "284d309017c68020ac25305f3cae0cf149c25475333dc012713905b965ef0c4dd59cffa830338a0d9f3"
    "7e937064da2e70dc5b2292bd648ba41038eff815720258e1a505f4da9c8bd3703cbf37847a22285972d"
    "32ebf4043e9e1e927a768daefadfbc183738c66d9371e5c70b6c6a0a642d6158fe46e2e4777d0321d68"
    "02967094200f22ce7679b0888b75023eaf37ca64e9ef8a9e6c1d7cb799f43e678b545fdde47bcc617d2"
    "e2fa6290a194c43e04844d194f0f23c638b9d28fe48c3182a451df8afa512ec9c5b8ffb56b543d510b4"
    "709c436222d4a324eb1f030ed9691ac80d525e9cf782337b330005829ea485dfb61fe317c7e1a249b64"
    "d13acb96c1c5696d1d90b115c21e37f251d08aff918e3e4e160fc9f2ec2646745c18ddff4805441abf5"
    "f7ac4b540e52adf4de8e75d0937d5d02b29036deff33dfa935a40f6a5c4308bd575bf965a82a3f051b8"
    "385d98ed9db842aceb857a618d59ba73b06139de76e2879792b245f611d34496cc8f838e32cd42e10d1"
    "c2c8105f2b6065dbab7e691c0e39eb38288d16822d494d1d3d6e772445f5e37fd13a2dfb901e69f1e24"
    "92660c6ef2b55a3a937ecc9eb1f0d8037e0c711dc8f92c7591f9eea3c21982f776754dece468ac77d93"
    "221a922bcfc35493239bb8d3d4ca7b94fd5d00527c16271e5f56ebe68a42a1178964836b479167376d8"
    "18bca0361df1e291341511572b491407b55313612dc28668d69c93b4587ddd1a104c6a591d303fc4338"
    "fc6f09b81af2d7d295b581f005c6fb86c33b1ff5a3bafb4d5b0216f76ffa9159fda04862123bd5fabd3"
    "0df3c1b8e58b6678c79f7b64661d2cce757395002c9cee5a44c41f2a69263377be615d61a0001b3d257"
    "043c018d19c3d687ca262e39b93f05dbc90d875ba58a3c13e743642aab9297516b9184f834927e79eba"
    "4fe40ba800fae0877cb19302010034d6184811f68ce722937efde36d872e23eb3342afd0e74b69126fe"
    "b190521c7f0f5b938f"
)
PINNED_FINGERPRINT = "dbd366b8d65cda93c0c073e9392a6acec4335240ae6b600adb2a7fcc0db6f5d0"


class TestPinnedKeypair(unittest.TestCase):
    """Seed -> key derivation must be deterministic and format-stable."""

    def test_seed_derives_pinned_public_key(self) -> None:
        seed, public_key = keypair_from_seed(TEST_SEED)
        self.assertEqual(seed, TEST_SEED)
        self.assertEqual(public_key.hex(), PINNED_PUBLIC_KEY.hex())

    def test_pinned_fingerprint_is_stable(self) -> None:
        self.assertEqual(public_fingerprint(PINNED_PUBLIC_KEY), PINNED_FINGERPRINT)


class TestKeygenProperties(unittest.TestCase):
    def test_sizes_and_determinism(self) -> None:
        self.assertEqual(SEED_SIZE, 32)
        self.assertEqual(PK_SIZE, 1952)
        self.assertEqual(SIG_SIZE, 3309)
        seed_a, pk_a = keygen()
        seed_b, pk_b = keygen()
        self.assertNotEqual(seed_a, seed_b)
        self.assertNotEqual(pk_a, pk_b)
        self.assertEqual(len(seed_a), SEED_SIZE)
        self.assertEqual(len(pk_a), PK_SIZE)
        self.assertEqual(keypair_from_seed(seed_a)[1], pk_a)  # deterministic keys
        self.assertEqual(public_key_bytes(seed_a), pk_a)

    def test_bad_seed_lengths_rejected(self) -> None:
        with self.assertRaises(ValueError):
            keypair_from_seed(b"short")
        with self.assertRaises(ValueError):
            keypair_from_seed(b"x" * 64)


class TestSignVerify(unittest.TestCase):
    def test_sign_verify_roundtrip(self) -> None:
        seed, pk = keygen()
        message = b"verdict artifact CID bytes"
        signature = sign(seed, message)
        self.assertEqual(len(signature), SIG_SIZE)
        self.assertTrue(verify(pk, message, signature))
        self.assertTrue(verify(pk, message, signature, context=b"conclave/v1"))
        self.assertFalse(verify(pk, message + b"!", signature))

    def test_context_separation(self) -> None:
        seed, pk = keygen()
        message = b"same payload"
        default_sig = sign(seed, message)
        audit_sig = sign(seed, message, context=b"conclave/audit/v1")
        self.assertTrue(verify(pk, message, default_sig))
        self.assertTrue(verify(pk, message, audit_sig, context=b"conclave/audit/v1"))
        self.assertFalse(verify(pk, message, audit_sig))  # wrong context rejected
        self.assertFalse(verify(pk, message, default_sig, context=b"conclave/audit/v1"))

    def test_wrong_key_and_malformed_inputs_rejected(self) -> None:
        seed, pk = keygen()
        other_seed, other_pk = keygen()
        signature = sign(seed, b"payload")
        self.assertFalse(verify(other_pk, b"payload", signature))
        self.assertFalse(verify(pk, b"payload", b""))
        self.assertFalse(verify(pk, b"payload", signature[:-1]))
        self.assertFalse(verify(b"x" * PK_SIZE, b"payload", signature))
        self.assertFalse(verify(pk[: PK_SIZE - 1], b"payload", signature))


class TestKeyPublicationIntegration(unittest.TestCase):
    def test_publication_binds_real_key(self) -> None:
        seed, pk = keygen()
        publication = make_key_publication(role="identity", public_key=pk)
        self.assertEqual(publication["keyFingerprint"], public_fingerprint(pk))
        validate_artifact(publication)

        tampered = dict(publication)
        tampered["keyFingerprint"] = "0" * 64
        with self.assertRaises(ArtifactError):
            validate_artifact(tampered)

        # a signature made with the seed verifies under the published key
        seed_bytes, derived_pk = keypair_from_seed(seed)
        self.assertTrue(verify(derived_pk, b"m", sign(seed_bytes, b"m")))


if __name__ == "__main__":
    unittest.main()
