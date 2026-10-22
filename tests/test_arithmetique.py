"""Tests du codage arithmétique : exemple CALCU du document + allers-retours."""

import os
import random
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arithmetique import (Modele, coder, compresser_symboles, decoder,
                          decompresser_symboles)
from utils import bits_vers_fraction, fraction_vers_bits, fraction_vers_decimal

# Table du document, dans l'ordre des intervalles sur [0, 1)
TABLE_CALCU = {"A": "0.1", "C": "0.5", "U": "0.2", "L": "0.2"}
F = Fraction


class TestExempleCALCU(unittest.TestCase):
    def setUp(self):
        self.modele = Modele(TABLE_CALCU)

    def test_intervalles_des_symboles(self):
        attendu = {"A": ("0", "0.1"), "C": ("0.1", "0.6"),
                   "U": ("0.6", "0.8"), "L": ("0.8", "1")}
        for s, (bas, haut) in attendu.items():
            self.assertEqual(self.modele.intervalle(s), (F(bas), F(haut)), s)

    def test_intervalles_a_chaque_etape(self):
        """Lⱼ et Rⱼ après chaque lettre de CALCU."""
        trace = []
        coder("CALCU", self.modele, trace)
        attendu = [("C", "0.1", "0.6"), ("A", "0.1", "0.15"), ("L", "0.14", "0.15"),
                   ("C", "0.141", "0.146"), ("U", "0.144", "0.145")]
        self.assertEqual(trace, [(s, F(L), F(R)) for s, L, R in attendu])

    def test_calcu_donne_0_144(self):
        L, R = coder("CALCU", self.modele)
        self.assertEqual((L, R), (F("0.144"), F("0.145")))
        self.assertEqual(fraction_vers_decimal(L, R), "0.144")

    def test_decodage_de_0_144(self):
        """Dⱼ = (Dⱼ₋₁ − C(sᵢ₋₁)) / P(sᵢ) : 0.144 → 0.088 → 0.88 → 0.4 → 0.6 → 0."""
        trace = []
        message = decoder(F("0.144"), 5, self.modele, trace)
        self.assertEqual("".join(message), "CALCU")
        self.assertEqual([D for D, _, _ in trace],
                         [F("0.144"), F("0.088"), F("0.88"), F("0.4"), F("0.6")])
        self.assertEqual(trace[-1][2], 0)

    def test_code_binaire(self):
        L, R = coder("CALCU", self.modele)
        bits = fraction_vers_bits(L, R)
        self.assertEqual(bits, "00100101")                 # 37/256 = 0.14453125
        self.assertEqual("".join(decoder(bits_vers_fraction(bits), 5, self.modele)), "CALCU")


class TestModele(unittest.TestCase):
    def test_effectifs_et_probabilites_equivalents(self):
        m1 = Modele({"A": 1, "C": 5, "U": 2, "L": 2})
        m2 = Modele(TABLE_CALCU)
        self.assertEqual(m1.P, m2.P)
        self.assertEqual(m1.C_bas, m2.C_bas)

    def test_cumul_final_vaut_1(self):
        m = Modele.depuis_message(b"une phrase quelconque")
        self.assertEqual(m.C_haut[m.symboles[-1]], 1)
        self.assertEqual(sum(m.P.values()), 1)

    def test_symbole_pour(self):
        m = Modele(TABLE_CALCU)
        self.assertEqual(m.symbole_pour(F(0)), "A")
        self.assertEqual(m.symbole_pour(F("0.1")), "C")        # borne basse incluse
        self.assertEqual(m.symbole_pour(F("0.5999")), "C")
        self.assertEqual(m.symbole_pour(F("0.6")), "U")        # borne haute exclue
        self.assertEqual(m.symbole_pour(F("0.99")), "L")

    def test_modele_vide_refuse(self):
        with self.assertRaises(ValueError):
            Modele({})


class TestAllerRetour(unittest.TestCase):
    def verifier(self, message):
        modele = Modele.depuis_message(message)
        L, R = coder(message, modele)
        D = bits_vers_fraction(fraction_vers_bits(L, R))
        self.assertTrue(L <= D < R)
        self.assertEqual(decoder(D, len(message), modele), list(message))

    def test_messages_divers(self):
        for message in ["CALCU", "A", "ABRACADABRA", "aaaaaaaaab", "0123456789" * 5]:
            with self.subTest(message=message):
                self.verifier(message)

    def test_un_seul_symbole_coute_zero_bit(self):
        modele = Modele.depuis_message("zzzzzz")
        L, R = coder("zzzzzz", modele)
        self.assertEqual(fraction_vers_bits(L, R), "")
        self.assertEqual(decoder(F(0), 6, modele), list("zzzzzz"))

    def test_octets_aleatoires(self):
        rng = random.Random(42)
        for longueur in (1, 10, 100):
            self.verifier(bytes(rng.randrange(256) for _ in range(longueur)))


class TestBlocs(unittest.TestCase):
    def test_limites_de_blocs(self):
        rng = random.Random(7)
        for n in (0, 1, 255, 256, 257, 1000):
            symboles = [rng.choice([0, 0, 0, 1, 2, 3, 200]) for _ in range(n)]
            with self.subTest(n=n):
                modele = Modele(dict.fromkeys([0, 1, 2, 3, 200], 1)) if n == 0 \
                    else Modele.depuis_message(symboles)
                donnees = compresser_symboles(symboles, modele, taille_bloc=256)
                self.assertEqual(decompresser_symboles(donnees, n, modele, 256), symboles)

    def test_donnees_tronquees(self):
        symboles = list(range(256)) * 2
        modele = Modele.depuis_message(symboles)
        donnees = compresser_symboles(symboles, modele)
        with self.assertRaises(ValueError):
            decompresser_symboles(donnees[:-10], len(symboles), modele)


if __name__ == "__main__":
    unittest.main()
