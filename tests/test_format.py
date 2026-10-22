"""Tests du format .mz : en-tête, tables de fréquences, flux."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import format_fichier as ff


def en_tete_exemple():
    return ff.EnTete(nom="vacances été.bmp", taille_originale=123456, crc32=0xDEADBEEF,
                     methode=ff.METHODE_LZ77_ARITH, taille_recherche=4095,
                     taille_anticipation=256, taille_bloc=256, nb_triplets=789)


class TestEnTete(unittest.TestCase):
    def test_aller_retour(self):
        octets = ff.ecrire_entete(en_tete_exemple()) + b"CORPS"
        en_tete, pos = ff.lire_entete(octets)
        self.assertEqual(en_tete, en_tete_exemple())
        self.assertEqual(octets[pos:], b"CORPS")

    def test_magic_number_au_debut(self):
        self.assertEqual(ff.ecrire_entete(en_tete_exemple())[:4], b"MZIP")

    def test_mauvais_magic(self):
        with self.assertRaises(ff.FormatInvalide):
            ff.lire_entete(b"PK\x03\x04 ceci est un zip")

    def test_mauvaise_version(self):
        octets = bytearray(ff.ecrire_entete(en_tete_exemple()))
        octets[4] = 99
        with self.assertRaises(ff.FormatInvalide):
            ff.lire_entete(bytes(octets))

    def test_entete_tronque(self):
        with self.assertRaises(ff.FormatInvalide):
            ff.lire_entete(ff.ecrire_entete(en_tete_exemple())[:20])


class TestTablesEtFlux(unittest.TestCase):
    def test_table_aller_retour(self):
        frequences = {0: 1, 65: 300, 255: 70000}
        octets = ff.ecrire_table_frequences(frequences)
        self.assertEqual(ff.lire_table_frequences(octets, 0), (frequences, len(octets)))

    def test_table_vide(self):
        self.assertEqual(ff.ecrire_table_frequences({}), b"\x00")

    def test_flux_aller_retour(self):
        octets = ff.ecrire_flux({1: 2, 3: 4}, b"donnees") + b"suite"
        frequences, donnees, pos = ff.lire_flux(octets, 0)
        self.assertEqual((frequences, donnees, octets[pos:]), ({1: 2, 3: 4}, b"donnees", b"suite"))

    def test_flux_tronque(self):
        with self.assertRaises(ff.FormatInvalide):
            ff.lire_flux(ff.ecrire_flux({1: 2}, b"donnees")[:-2], 0)


if __name__ == "__main__":
    unittest.main()
