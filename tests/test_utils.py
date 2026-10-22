"""Tests des conversions Fraction ↔ bits ↔ octets et des varints."""

import os
import random
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import (bits_vers_fraction, bits_vers_octets, ecrire_varint,
                   fraction_en_texte, fraction_vers_bits, fraction_vers_decimal,
                   lire_varint, nombre_le_plus_court, octets_vers_bits)

F = Fraction


class TestNombreLePlusCourt(unittest.TestCase):
    def test_exemple_calcu(self):
        self.assertEqual(nombre_le_plus_court(F("0.144"), F("0.145"), 10), (144, 3))
        self.assertEqual(fraction_vers_decimal(F("0.144"), F("0.145")), "0.144")

    def test_cas_simples(self):
        self.assertEqual(fraction_vers_decimal(F(0), F(1)), "0")
        self.assertEqual(fraction_vers_decimal(F("0.5"), F("0.5001")), "0.5")
        self.assertEqual(fraction_vers_bits(F("0.5"), F("0.75")), "1")
        self.assertEqual(fraction_vers_bits(F(1, 3), F(1, 2)), "011")    # 0.375

    def test_comparaison_avec_force_brute(self):
        """Le résultat doit être le plus court, vérifié en essayant tous les k."""
        rng = random.Random(3)
        for _ in range(200):
            a, b = sorted(rng.sample(range(1, 10_000), 2))
            bas, haut = F(a, 10_000), F(b, 10_000)
            for base in (2, 10):
                m, k = nombre_le_plus_court(bas, haut, base)
                self.assertTrue(bas <= F(m, base ** k) < haut)
                for k_petit in range(k):
                    m_petit = -(-bas * base ** k_petit // 1)          # ⌈bas·baseᵏ⌉
                    self.assertFalse(F(m_petit, base ** k_petit) < haut)

    def test_intervalle_invalide(self):
        with self.assertRaises(ValueError):
            nombre_le_plus_court(F("0.5"), F("0.4"))


class TestBitsOctets(unittest.TestCase):
    def test_bits_vers_fraction(self):
        self.assertEqual(bits_vers_fraction("00100101"), F(37, 256))
        self.assertEqual(bits_vers_fraction(""), 0)

    def test_aller_retour_octets(self):
        for bits in ["", "1", "0", "00100101", "101", "1" * 17, "0000000000001"]:
            with self.subTest(bits=bits):
                octets = bits_vers_octets(bits)
                self.assertEqual(len(octets), (len(bits) + 7) // 8)
                self.assertEqual(octets_vers_bits(octets, len(bits)), bits)

    def test_completion_par_des_zeros(self):
        self.assertEqual(bits_vers_octets("101"), bytes([0b10100000]))


class TestVarint(unittest.TestCase):
    def test_valeurs(self):
        self.assertEqual(ecrire_varint(0), b"\x00")
        self.assertEqual(ecrire_varint(127), b"\x7f")
        self.assertEqual(ecrire_varint(128), b"\x80\x01")
        self.assertEqual(ecrire_varint(300), b"\xac\x02")

    def test_aller_retour(self):
        for n in (0, 1, 127, 128, 255, 16383, 16384, 2 ** 32, 2 ** 64 + 5):
            donnees = b"!" + ecrire_varint(n) + b"?"
            self.assertEqual(lire_varint(donnees, 1), (n, len(donnees) - 1))

    def test_erreurs(self):
        with self.assertRaises(ValueError):
            ecrire_varint(-1)
        with self.assertRaises(ValueError):
            lire_varint(b"\x80\x80", 0)


class TestAffichage(unittest.TestCase):
    def test_fraction_en_texte(self):
        self.assertEqual(fraction_en_texte(F("0.144")), "0.144")
        self.assertEqual(fraction_en_texte(F(1)), "1")
        self.assertEqual(fraction_en_texte(F(1, 3), 4), "0.3333…")


if __name__ == "__main__":
    unittest.main()
