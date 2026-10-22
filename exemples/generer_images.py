"""
generer_images.py — Crée deux images de test identiques, sans bibliothèque externe :

  image.bmp : format BMP 24 bits NON compressé (3 octets par pixel)
  image.png : la même image au format PNG (déjà compressé par zlib)

Le dessin (ciel en dégradé, soleil, collines, maison) contient de grandes zones
de couleur unie, comme un logo ou un dessin, et pas de bruit.

    python exemples/generer_images.py
"""

import os
import struct
import zlib

LARGEUR, HAUTEUR = 192, 128
DOSSIER = os.path.dirname(os.path.abspath(__file__))


def couleur(x, y):
    """Couleur (rouge, vert, bleu) du pixel (x, y), y = 0 en haut de l'image."""
    # Maison : toit triangulaire, murs, porte et fenêtre
    if 30 <= y < 56 and abs(x - 125) <= (y - 30) * 1.2:
        return (150, 40, 30)
    if 56 <= y < 96 and 100 <= x < 150:
        if 72 <= y and 118 <= x < 132:
            return (90, 50, 20)                     # porte
        if 62 <= y < 76 and 104 <= x < 114:
            return (170, 210, 240)                  # fenêtre
        return (235, 220, 180)
    # Soleil
    if (x - 40) ** 2 + (y - 28) ** 2 <= 14 ** 2:
        return (255, 210, 40)
    # Collines, puis herbe
    if y >= 80 + 12 * ((x // 24) % 2):
        return (60, 150, 60) if y < 100 else (40, 120, 40)
    # Ciel : dégradé vertical (chaque ligne a une seule couleur)
    return (100 + y // 2, 160 + y // 4, 250)


def generer_bmp(chemin):
    taille_ligne = (3 * LARGEUR + 3) // 4 * 4             # lignes alignées sur 4 octets
    pixels = bytearray()
    for y in reversed(range(HAUTEUR)):                    # BMP : de bas en haut
        ligne = bytearray()
        for x in range(LARGEUR):
            r, v, b = couleur(x, y)
            ligne += bytes((b, v, r))                     # BMP : ordre bleu, vert, rouge
        pixels += ligne.ljust(taille_ligne, b"\0")
    entete_dib = struct.pack("<IiiHHIIiiII", 40, LARGEUR, HAUTEUR, 1, 24, 0,
                             len(pixels), 2835, 2835, 0, 0)
    entete = b"BM" + struct.pack("<IHHI", 14 + 40 + len(pixels), 0, 0, 14 + 40)
    with open(chemin, "wb") as f:
        f.write(entete + entete_dib + pixels)


def generer_png(chemin):
    def bloc(type_bloc, donnees):
        return (struct.pack(">I", len(donnees)) + type_bloc + donnees
                + struct.pack(">I", zlib.crc32(type_bloc + donnees)))

    brut = bytearray()
    for y in range(HAUTEUR):
        brut.append(0)                                    # filtre PNG « aucun »
        for x in range(LARGEUR):
            brut += bytes(couleur(x, y))
    ihdr = struct.pack(">IIBBBBB", LARGEUR, HAUTEUR, 8, 2, 0, 0, 0)
    with open(chemin, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", ihdr)
                + bloc(b"IDAT", zlib.compress(bytes(brut), 9)) + bloc(b"IEND", b""))


if __name__ == "__main__":
    for nom, fonction in (("image.bmp", generer_bmp), ("image.png", generer_png)):
        chemin = os.path.join(DOSSIER, nom)
        fonction(chemin)
        print(f"{chemin} : {os.path.getsize(chemin)} octets")
