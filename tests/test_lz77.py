"""Tests de LZ77 : exemple CABRACADABRARRARRAD du document + allers-retours."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lz77 import Triplet, compresser_lz77, decompresser_lz77

MESSAGE = "CABRACADABRARRARRAD"
TRIPLETS_DOCUMENT = [
    (0, 0, "C"), (0, 0, "A"), (0, 0, "B"), (0, 0, "R"),
    (3, 1, "C"), (2, 1, "D"), (7, 4, "R"), (3, 5, "D"),
]


class TestExempleDocument(unittest.TestCase):
    def test_huit_triplets_du_document(self):
        triplets = compresser_lz77(MESSAGE, taille_recherche=7, taille_anticipation=6)
        self.assertEqual(len(triplets), 8)
        self.assertEqual(triplets, TRIPLETS_DOCUMENT)

    def test_decodage_du_document(self):
        self.assertEqual(decompresser_lz77([Triplet(*t) for t in TRIPLETS_DOCUMENT]), MESSAGE)

    def test_tampons_affiches(self):
        trace = []
        compresser_lz77(MESSAGE, 7, 6, trace)
        recherche, lecture, triplet = trace[6]          # 7ᵉ étape : (7, 4, R)
        self.assertEqual((recherche, lecture), ("ABRACAD", "ABRARR"))
        self.assertEqual(triplet, (7, 4, "R"))


class TestCasParticuliers(unittest.TestCase):
    def test_vide(self):
        self.assertEqual(compresser_lz77(b""), [])
        self.assertEqual(decompresser_lz77([]), b"")

    def test_un_seul_octet(self):
        self.assertEqual(compresser_lz77(b"x"), [(0, 0, ord("x"))])

    def test_chevauchement(self):
        """Une copie peut être plus longue que le décalage : (1, 8, A) recopie A huit fois."""
        triplets = compresser_lz77("AAAAAAAAAA")
        self.assertEqual(triplets, [(0, 0, "A"), (1, 8, "A")])
        self.assertEqual(decompresser_lz77(triplets), "AAAAAAAAAA")

    def test_triplet_invalide(self):
        with self.assertRaises(ValueError):
            decompresser_lz77([Triplet(3, 2, 65)])   # rien à copier


class TestAllerRetour(unittest.TestCase):
    def test_donnees_variees(self):
        rng = random.Random(1)
        echantillons = [
            b"ABRACADABRA" * 50,
            bytes(range(256)) * 3,
            bytes(rng.randrange(256) for _ in range(3000)),
            bytes(rng.choice(b"ab") for _ in range(3000)),
            b"\x00" * 5000,
            "Le chat mange. Le chien mange. Le chat dort.".encode("utf-8"),
        ]
        for donnees in echantillons:
            for recherche, anticipation in ((7, 6), (255, 16), (4095, 256)):
                with self.subTest(taille=len(donnees), recherche=recherche):
                    triplets = compresser_lz77(donnees, recherche, anticipation)
                    for d, l, _ in triplets:
                        self.assertLessEqual(d, recherche)
                        self.assertLessEqual(l, anticipation - 1)
                    self.assertEqual(decompresser_lz77(triplets), donnees)


if __name__ == "__main__":
    unittest.main()
