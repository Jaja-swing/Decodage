"""
pipeline.py — Le cœur de MiniZip : LZ77 puis codage arithmétique.

COMPRESSION
    octets ──LZ77──► triplets (décalage, longueur, caractère)
           ──séparation──► 4 flux d'octets :
                 décalage // 256 │ décalage % 256 │ longueur │ caractère
           ──codage arithmétique (une table de fréquences par flux)──► .mz

DÉCOMPRESSION : le chemin inverse, puis vérification de la taille et du CRC-32.

Pourquoi 4 flux séparés ? Chaque champ du triplet a sa propre statistique
(les longueurs sont souvent petites, les caractères suivent la langue…).
Un modèle par champ donne des probabilités plus « pointues », donc un code
plus court qu'un modèle unique pour tout mélanger.

Si la compression ne fait rien gagner (fichier déjà compressé : PNG, JPEG,
ZIP…), le fichier est simplement STOCKÉ, comme le font WinRAR et 7-Zip.
"""

import binascii
import math
import os
import struct
import time
from collections import Counter
from dataclasses import dataclass, field

import arithmetique
import format_fichier as ff
import lz77

NOMS_FLUX = ("décalage (octet fort)", "décalage (octet faible)", "longueur", "caractère")


# ---------------------------------------------------------------------------
# Triplets ↔ flux
# ---------------------------------------------------------------------------

def triplets_vers_flux(triplets):
    """Sépare les triplets en 4 listes d'octets (une par champ)."""
    flux = ([], [], [], [])
    for decalage, longueur, caractere in triplets:
        flux[0].append(decalage // 256)
        flux[1].append(decalage % 256)
        flux[2].append(longueur)
        flux[3].append(caractere)
    return flux


def flux_vers_triplets(flux):
    """Inverse de triplets_vers_flux."""
    return [lz77.Triplet(fort * 256 + faible, longueur, caractere)
            for fort, faible, longueur, caractere in zip(*flux)]


# ---------------------------------------------------------------------------
# Statistiques (pour expliquer le taux de compression)
# ---------------------------------------------------------------------------

@dataclass
class StatFlux:
    nom: str
    nb_symboles: int
    nb_distincts: int
    entropie: float          # bits par symbole : limite théorique de Shannon
    taille_table: int        # octets occupés par la table de fréquences
    taille_codee: int        # octets occupés par les données codées

    @property
    def limite_shannon(self):
        """Taille minimale théorique des données codées, en octets."""
        return self.nb_symboles * self.entropie / 8


@dataclass
class Rapport:
    nom: str
    taille_originale: int
    taille_compressee: int = 0
    taille_entete: int = 0
    methode: int = ff.METHODE_LZ77_ARITH
    nb_triplets: int = 0
    flux: list = field(default_factory=list)
    duree: float = 0.0
    chemin_sortie: str = ""

    @property
    def taux(self):
        """Taille compressée / taille originale (0.40 = le fichier fait 40 % de l'original)."""
        return self.taille_compressee / self.taille_originale if self.taille_originale else 1.0


def entropie(effectifs):
    """H = −Σ p·log₂(p) = Σ p·log₂(1/p), en bits par symbole."""
    total = sum(effectifs.values())
    return sum(n / total * math.log2(total / n) for n in effectifs.values())


# ---------------------------------------------------------------------------
# Compression / décompression en mémoire
# ---------------------------------------------------------------------------

def compresser_octets(donnees, nom="fichier",
                      taille_recherche=lz77.TAILLE_RECHERCHE,
                      taille_anticipation=lz77.TAILLE_ANTICIPATION,
                      taille_bloc=arithmetique.TAILLE_BLOC,
                      journal=None):
    """Compresse des octets. Retourne (contenu du fichier .mz, Rapport).

    `journal` (facultatif) est une fonction appelée avec un message à chaque étape.
    """
    if taille_recherche > 65535 or taille_anticipation > 256:
        raise ValueError("le format .mz limite la fenêtre à 65535 et l'anticipation à 256")
    debut = time.perf_counter()
    signaler = journal or (lambda message: None)
    en_tete = ff.EnTete(nom=nom, taille_originale=len(donnees),
                        crc32=binascii.crc32(donnees),
                        taille_recherche=taille_recherche,
                        taille_anticipation=taille_anticipation,
                        taille_bloc=taille_bloc)
    rapport = Rapport(nom=nom, taille_originale=len(donnees))

    # Étape 1 : LZ77
    triplets = lz77.compresser_lz77(donnees, taille_recherche, taille_anticipation)
    en_tete.nb_triplets = rapport.nb_triplets = len(triplets)
    signaler(f"LZ77 : {len(triplets)} triplets")

    # Étape 2 : un codage arithmétique par flux
    corps = bytearray()
    for nom_flux, symboles in zip(NOMS_FLUX, triplets_vers_flux(triplets)):
        frequences = dict(sorted(Counter(symboles).items()))
        codees = b""
        if symboles:
            signaler(f"codage arithmétique du flux « {nom_flux} »")
            codees = arithmetique.compresser_symboles(
                symboles, arithmetique.Modele(frequences), taille_bloc)
        corps += ff.ecrire_flux(frequences, codees)
        rapport.flux.append(StatFlux(
            nom=nom_flux, nb_symboles=len(symboles), nb_distincts=len(frequences),
            entropie=entropie(frequences) if symboles else 0.0,
            taille_table=len(ff.ecrire_table_frequences(frequences)),
            taille_codee=len(codees)))

    # Étape 3 : si on n'a rien gagné, on stocke le fichier tel quel
    if len(corps) >= len(donnees):
        signaler("aucun gain : le fichier est stocké sans compression")
        en_tete.methode = rapport.methode = ff.METHODE_STOCKE
        corps = donnees

    entete = ff.ecrire_entete(en_tete)
    archive = entete + bytes(corps)
    rapport.taille_entete = len(entete)
    rapport.taille_compressee = len(archive)
    rapport.duree = time.perf_counter() - debut
    return archive, rapport


def decompresser_octets(archive):
    """Contenu d'un .mz → (EnTete, octets originaux). Lève ff.FormatInvalide."""
    en_tete, pos = ff.lire_entete(archive)
    try:
        if en_tete.methode == ff.METHODE_STOCKE:
            donnees = bytes(archive[pos:pos + en_tete.taille_originale])
        else:
            flux = []
            for _ in NOMS_FLUX:
                frequences, codees, pos = ff.lire_flux(archive, pos)
                if en_tete.nb_triplets == 0:
                    flux.append([])
                    continue
                modele = arithmetique.Modele(frequences)
                flux.append(arithmetique.decompresser_symboles(
                    codees, en_tete.nb_triplets, modele, en_tete.taille_bloc))
            donnees = lz77.decompresser_lz77(flux_vers_triplets(flux))
    except ff.FormatInvalide:
        raise
    except (ValueError, IndexError, KeyError, struct.error) as erreur:
        raise ff.FormatInvalide(f"données corrompues : {erreur}") from erreur

    if len(donnees) != en_tete.taille_originale:
        raise ff.FormatInvalide("taille incorrecte : le fichier .mz est corrompu")
    if binascii.crc32(donnees) != en_tete.crc32:
        raise ff.FormatInvalide("CRC-32 incorrect : le fichier .mz est corrompu")
    return en_tete, donnees


# ---------------------------------------------------------------------------
# Compression / décompression de fichiers
# ---------------------------------------------------------------------------

def compresser_fichier(chemin, chemin_sortie=None, journal=None, **options):
    """Compresse `chemin` vers `chemin_sortie` (par défaut : chemin + ".mz")."""
    with open(chemin, "rb") as f:
        donnees = f.read()
    archive, rapport = compresser_octets(donnees, os.path.basename(chemin),
                                         journal=journal, **options)
    rapport.chemin_sortie = chemin_sortie or chemin + ".mz"
    with open(rapport.chemin_sortie, "wb") as f:
        f.write(archive)
    return rapport


def decompresser_fichier(chemin_mz, dossier_sortie=None):
    """Décompresse `chemin_mz` dans `dossier_sortie` (par défaut : un dossier
    « extrait » à côté de l'archive). Retourne (chemin du fichier restauré, EnTete)."""
    with open(chemin_mz, "rb") as f:
        archive = f.read()
    en_tete, donnees = decompresser_octets(archive)

    if dossier_sortie is None:
        dossier_sortie = os.path.join(os.path.dirname(chemin_mz), "extrait")
    os.makedirs(dossier_sortie, exist_ok=True)
    # Sécurité : on ne garde que le nom, jamais un chemin (« ../../ » interdit).
    nom = os.path.basename(en_tete.nom.replace("\\", "/"))
    if nom in ("", ".", ".."):
        nom = "fichier_extrait"
    chemin = os.path.join(dossier_sortie, nom)
    with open(chemin, "wb") as f:
        f.write(donnees)
    return chemin, en_tete


def lire_infos(chemin_mz):
    """Lit l'en-tête et les tables de fréquences d'un .mz, sans décompresser.
    Retourne (EnTete, liste de (nom du flux, fréquences, taille codée), taille du fichier)."""
    with open(chemin_mz, "rb") as f:
        archive = f.read()
    en_tete, pos = ff.lire_entete(archive)
    flux = []
    if en_tete.methode == ff.METHODE_LZ77_ARITH:
        for nom_flux in NOMS_FLUX:
            frequences, codees, pos = ff.lire_flux(archive, pos)
            flux.append((nom_flux, frequences, len(codees)))
    return en_tete, flux, len(archive)
