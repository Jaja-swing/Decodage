"""Tests du pipeline complet : decompresser(compresser(f)) == f."""

import os
import random
import shutil
import sys
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

import format_fichier as ff
import pipeline


class TestAllerRetourOctets(unittest.TestCase):
    def verifier(self, donnees):
        archive, rapport = pipeline.compresser_octets(donnees, "essai.bin")
        self.assertEqual(archive[:4], b"MZIP")
        en_tete, resultat = pipeline.decompresser_octets(archive)
        self.assertEqual(resultat, donnees)
        self.assertEqual(en_tete.nom, "essai.bin")
        return rapport

    def test_cas_limites(self):
        for donnees in (b"", b"a", b"ab", b"\x00" * 1000, bytes(range(256))):
            with self.subTest(taille=len(donnees)):
                self.verifier(donnees)

    def test_texte_compressible(self):
        texte = ("Le codage arithmétique et LZ77 forment le pipeline de MiniZip. " * 40).encode()
        rapport = self.verifier(texte)
        self.assertEqual(rapport.methode, ff.METHODE_LZ77_ARITH)
        self.assertLess(rapport.taux, 0.2)

    def test_donnees_aleatoires_stockees(self):
        rng = random.Random(5)
        donnees = bytes(rng.randrange(256) for _ in range(5000))
        rapport = self.verifier(donnees)
        self.assertEqual(rapport.methode, ff.METHODE_STOCKE)

    def test_petits_parametres(self):
        donnees = b"CABRACADABRARRARRAD" * 20
        archive, _ = pipeline.compresser_octets(donnees, "x", taille_recherche=7,
                                                taille_anticipation=6, taille_bloc=16)
        self.assertEqual(pipeline.decompresser_octets(archive)[1], donnees)

    def test_triplets_flux_triplets(self):
        triplets = [(0, 0, 65), (4095, 255, 0), (256, 3, 255)]
        self.assertEqual(pipeline.flux_vers_triplets(pipeline.triplets_vers_flux(triplets)),
                         triplets)


class TestCorruption(unittest.TestCase):
    def test_corruption_detectee(self):
        donnees = ("Bonjour MiniZip ! " * 100).encode()
        archive, _ = pipeline.compresser_octets(donnees, "a.txt")
        for position in range(60, len(archive), 7):          # on abîme le corps
            abimee = bytearray(archive)
            abimee[position] ^= 0x55
            with self.subTest(position=position):
                try:
                    _, resultat = pipeline.decompresser_octets(bytes(abimee))
                except ff.FormatInvalide:
                    continue
                self.assertEqual(resultat, donnees)          # sinon : résultat exact

    def test_archive_tronquee(self):
        archive, _ = pipeline.compresser_octets(b"abcabcabc" * 100, "a.txt")
        with self.assertRaises(ff.FormatInvalide):
            pipeline.decompresser_octets(archive[:-5])


class TestFichiers(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dossier)

    def test_aller_retour_sur_disque(self):
        chemin = os.path.join(self.dossier, "notes.txt")
        with open(chemin, "wb") as f:
            f.write("Compression sans perte : le fichier revient à l'identique.\n".encode() * 30)
        rapport = pipeline.compresser_fichier(chemin)
        self.assertTrue(os.path.exists(chemin + ".mz"))
        restaure, _ = pipeline.decompresser_fichier(rapport.chemin_sortie)
        self.assertEqual(restaure, os.path.join(self.dossier, "extrait", "notes.txt"))
        with open(chemin, "rb") as a, open(restaure, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_nom_dangereux_neutralise(self):
        archive, _ = pipeline.compresser_octets(b"pirate", "../../evil.txt")
        chemin_mz = os.path.join(self.dossier, "a.mz")
        with open(chemin_mz, "wb") as f:
            f.write(archive)
        restaure, _ = pipeline.decompresser_fichier(chemin_mz)
        self.assertEqual(restaure, os.path.join(self.dossier, "extrait", "evil.txt"))

    def test_fichiers_exemples(self):
        """Les fichiers du dossier exemples/ (texte et image) reviennent à l'identique."""
        dossier_exemples = os.path.join(RACINE, "exemples")
        for nom in ("texte.txt", "image.bmp", "image.png"):
            chemin = os.path.join(dossier_exemples, nom)
            if not os.path.exists(chemin):
                continue
            with self.subTest(fichier=nom), open(chemin, "rb") as f:
                donnees = f.read()
                archive, _ = pipeline.compresser_octets(donnees, nom)
                self.assertEqual(pipeline.decompresser_octets(archive)[1], donnees)


if __name__ == "__main__":
    unittest.main()
