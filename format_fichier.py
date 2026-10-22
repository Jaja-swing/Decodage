"""
format_fichier.py — Lecture et écriture du format d'archive « .mz ».

Structure d'un fichier .mz (entiers de taille fixe en big-endian) :

  EN-TÊTE
    4 o   Magic number        b"MZIP" : identifie le format
    1 o   Version             1
    1 o   Méthode             0 = stocké (sans compression)
                              1 = LZ77 + codage arithmétique
    2 o   Longueur du nom     n
    n o   Nom d'origine       UTF-8
    8 o   Taille originale    en octets
    4 o   CRC-32              empreinte du fichier original (contrôle d'intégrité)
    2 o   Fenêtre LZ77        taille du tampon de recherche
    2 o   Anticipation LZ77   taille du tampon de lecture
    2 o   Taille de bloc      symboles par nombre arithmétique
    4 o   Nombre de triplets

  CORPS, méthode 1 : 4 flux à la suite, dans l'ordre
        décalage (octet fort), décalage (octet faible), longueur, caractère.
    Pour chaque flux :
      varint                      nombre de symboles distincts (d)
      d × (1 o symbole + varint)  TABLE DE FRÉQUENCES (symbole, effectif)
      varint                      taille des données codées (t)
      t o                         données codées (blocs arithmétiques)

  CORPS, méthode 0 : les octets originaux, tels quels.
"""

import struct
from dataclasses import dataclass

from utils import ecrire_varint, lire_varint

MAGIC = b"MZIP"
VERSION = 1

METHODE_STOCKE = 0
METHODE_LZ77_ARITH = 1
NOMS_METHODES = {
    METHODE_STOCKE: "stocké (aucune compression)",
    METHODE_LZ77_ARITH: "LZ77 + codage arithmétique",
}

_DEBUT = ">BBH"        # version, méthode, longueur du nom
_FIN = ">QIHHHI"       # taille, CRC-32, fenêtre, anticipation, bloc, nb triplets


class FormatInvalide(Exception):
    """Le fichier n'est pas un .mz valide, ou il est corrompu."""


@dataclass
class EnTete:
    nom: str
    taille_originale: int
    crc32: int
    methode: int = METHODE_LZ77_ARITH
    taille_recherche: int = 0
    taille_anticipation: int = 0
    taille_bloc: int = 0
    nb_triplets: int = 0


def ecrire_entete(en_tete):
    """EnTete → octets."""
    nom = en_tete.nom.encode("utf-8")
    return (MAGIC
            + struct.pack(_DEBUT, VERSION, en_tete.methode, len(nom))
            + nom
            + struct.pack(_FIN, en_tete.taille_originale, en_tete.crc32,
                          en_tete.taille_recherche, en_tete.taille_anticipation,
                          en_tete.taille_bloc, en_tete.nb_triplets))


def lire_entete(donnees):
    """Octets → (EnTete, position du début du corps). Lève FormatInvalide."""
    if donnees[:4] != MAGIC:
        raise FormatInvalide("magic number « MZIP » absent : ce n'est pas un fichier .mz")
    try:
        version, methode, longueur_nom = struct.unpack_from(_DEBUT, donnees, 4)
        if version != VERSION:
            raise FormatInvalide(f"version {version} non prise en charge (attendue : {VERSION})")
        if methode not in NOMS_METHODES:
            raise FormatInvalide(f"méthode de compression inconnue : {methode}")
        pos = 4 + struct.calcsize(_DEBUT)
        nom = bytes(donnees[pos:pos + longueur_nom]).decode("utf-8")
        pos += longueur_nom
        taille, crc, recherche, anticipation, bloc, nb_triplets = \
            struct.unpack_from(_FIN, donnees, pos)
        pos += struct.calcsize(_FIN)
    except (struct.error, UnicodeDecodeError) as erreur:
        raise FormatInvalide(f"en-tête illisible : {erreur}") from erreur
    en_tete = EnTete(nom=nom, taille_originale=taille, crc32=crc, methode=methode,
                     taille_recherche=recherche, taille_anticipation=anticipation,
                     taille_bloc=bloc, nb_triplets=nb_triplets)
    return en_tete, pos


def ecrire_table_frequences(frequences):
    """{symbole 0-255: effectif} → octets. Seuls les symboles présents sont écrits."""
    sortie = bytearray(ecrire_varint(len(frequences)))
    for symbole, effectif in sorted(frequences.items()):
        sortie.append(symbole)
        sortie += ecrire_varint(effectif)
    return bytes(sortie)


def lire_table_frequences(donnees, pos):
    """Retourne ({symbole: effectif} trié par symbole, position suivante)."""
    nb_symboles, pos = lire_varint(donnees, pos)
    frequences = {}
    for _ in range(nb_symboles):
        if pos >= len(donnees):
            raise FormatInvalide("table de fréquences tronquée")
        symbole = donnees[pos]
        frequences[symbole], pos = lire_varint(donnees, pos + 1)
    return frequences, pos


def ecrire_flux(frequences, donnees_codees):
    """Un flux = sa table de fréquences + la taille des données + les données."""
    return (ecrire_table_frequences(frequences)
            + ecrire_varint(len(donnees_codees))
            + donnees_codees)


def lire_flux(donnees, pos):
    """Retourne (fréquences, données codées, position suivante)."""
    frequences, pos = lire_table_frequences(donnees, pos)
    taille, pos = lire_varint(donnees, pos)
    if pos + taille > len(donnees):
        raise FormatInvalide("flux tronqué")
    return frequences, bytes(donnees[pos:pos + taille]), pos + taille
