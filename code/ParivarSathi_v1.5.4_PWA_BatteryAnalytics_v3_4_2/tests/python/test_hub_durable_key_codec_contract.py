"""Design-only model for the future ESP32 durable BlobStore key mapping."""

import re
import unittest


U64_MAX = (1 << 64) - 1
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
DYNAMIC_FAMILIES = ("ef", "ev")
FIXED = {
    *(f"cp{i}" for i in range(2)),
    *(f"sel{i}" for i in range(2)),
    *(f"tr{i}" for i in range(4)),
    *(f"bm{i}" for i in range(2)),
    *(f"ret{i}" for i in range(3)),
}
LEGACY = {
    *(f"e{i:03d}" for i in range(128)),
    *(f"c{i:03d}" for i in range(128)),
}
VECTORS = {
    0: "0000000000000",
    1: "0000000000001",
    9: "0000000000009",
    10: "000000000000a",
    31: "000000000000v",
    32: "000000000000w",
    255: "0000000000073",
    256: "0000000000074",
    (1 << 32) - 1: "0000001z141z3",
    U64_MAX: "3w5e11264sgsf",
}


def encode_u64(value):
    if not isinstance(value, int) or not 0 <= value <= U64_MAX:
        raise ValueError("out of range")
    chars = ["0"] * 13
    for position in range(12, -1, -1):
        value, digit = divmod(value, 36)
        chars[position] = DIGITS[digit]
    if value:
        raise ValueError("out of range")
    return "".join(chars)


def logical_to_physical(key):
    if key in FIXED or key in LEGACY:
        return key
    family = key[:2]
    digits = key[2:]
    if family not in DYNAMIC_FAMILIES or not re.fullmatch(r"0|[1-9][0-9]*", digits):
        raise ValueError("unknown or noncanonical logical key")
    return family + encode_u64(int(digits))


def physical_to_inventory_record(key):
    if key in FIXED:
        return ("fixed", key)
    if key in LEGACY:
        return ("legacy", key)
    family = key[:2]
    body = key[2:]
    if family not in DYNAMIC_FAMILIES or len(body) != 13 or any(
        character not in DIGITS for character in body
    ):
        raise ValueError("unknown or noncanonical physical key")
    value = int(body, 36)
    if value > U64_MAX or encode_u64(value) != body:
        raise ValueError("overflow or alias")
    return (family, value)


class DurableKeyCodecContract(unittest.TestCase):
    def test_arithmetic_and_vectors(self):
        self.assertLess(36**12, U64_MAX)
        self.assertGreater(36**13, U64_MAX)
        for value, body in VECTORS.items():
            self.assertEqual(encode_u64(value), body)
            for family in DYNAMIC_FAMILIES:
                physical = logical_to_physical(family + str(value))
                self.assertEqual(physical, family + body)
                self.assertEqual(len(physical), 15)
                self.assertEqual(physical_to_inventory_record(physical), (family, value))

    def test_all_current_fixed_and_legacy_keys_fit_without_overlap(self):
        self.assertTrue(FIXED.isdisjoint(LEGACY))
        physical = {logical_to_physical(key) for key in FIXED | LEGACY}
        self.assertEqual(len(physical), len(FIXED | LEGACY))
        self.assertTrue(all(len(key) <= 15 for key in physical))
        for key in physical:
            self.assertIn(physical_to_inventory_record(key)[0], ("fixed", "legacy"))
        for family in DYNAMIC_FAMILIES:
            self.assertTrue(all(not key.startswith(family) for key in physical))

    def test_round_trip_and_lexical_order(self):
        values = sorted(VECTORS)
        for family in DYNAMIC_FAMILIES:
            physical = [logical_to_physical(family + str(value)) for value in values]
            self.assertEqual(physical, sorted(physical))
            self.assertEqual(len(set(physical)), len(values))
            for value, key in zip(values, physical):
                self.assertEqual(physical_to_inventory_record(key), (family, value))

    def test_rejects_malformed_and_unknown_keys(self):
        bad_physical = (
            "ef000000000000", "ef00000000000000", "ef000000000000A",
            "ev000000000000_", "efzzzzzzzzzzzzz", "xy0000000000000",
            "e128", "c999", "tr4", "ret3", "mig0", "ef1",
        )
        for key in bad_physical:
            with self.subTest(key=key), self.assertRaises(ValueError):
                physical_to_inventory_record(key)
        for key in ("ef00", "ef01", "ev+1", "ev-1", "ev", "ef18446744073709551616"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                logical_to_physical(key)


if __name__ == "__main__":
    unittest.main()
