"""
lz77.py — Compression LZ77 (Lempel & Ziv, 1977) par fenêtre glissante.

        tampon de recherche (déjà codé)  │ tampon de lecture (à coder)
        … C A B R A C A                  │ D A B R A R  R A R R A D
                                         ▲ position courante

À chaque étape, on cherche dans le tampon de recherche la plus longue chaîne
qui commence comme le tampon de lecture, et on émet un TRIPLET :

    (décalage, longueur, caractère suivant)

  - décalage  : de combien de positions on recule pour trouver la copie
                (0 s'il n'y a aucune correspondance)
  - longueur  : nombre de symboles copiés
  - caractère : le symbole qui suit la copie, écrit en clair

puis on avance de longueur + 1 positions.

Exemple du document (tampon de recherche = 7, tampon de lecture = 6) :
    CABRACADABRARRARRAD → (0,0,C) (0,0,A) (0,0,B) (0,0,R)
                           (3,1,C) (2,1,D) (7,4,R) (3,5,D)

Lancer `python lz77.py` affiche cet exemple pas à pas.
"""

from collections import namedtuple

Triplet = namedtuple("Triplet", "decalage longueur caractere")

# Paramètres utilisés pour les fichiers :
#   décalage ≤ 4095 (12 bits)  et  longueur ≤ 255 (1 octet)
TAILLE_RECHERCHE = 4095
TAILLE_ANTICIPATION = 256

# Paramètres et message de l'exemple du document
EXEMPLE_MESSAGE = "CABRACADABRARRARRAD"
EXEMPLE_RECHERCHE = 7
EXEMPLE_ANTICIPATION = 6


def compresser_lz77(donnees, taille_recherche=TAILLE_RECHERCHE,
                    taille_anticipation=TAILLE_ANTICIPATION, trace=None):
    """Découpe `donnees` (str ou bytes) en une liste de triplets.

    Si `trace` est une liste, on y ajoute (tampon de recherche, tampon de lecture,
    triplet) à chaque étape.
    """
    triplets = []
    n = len(donnees)
    # Le triplet complet (copie + caractère suivant) doit tenir dans le tampon de lecture.
    longueur_max = taille_anticipation - 1
    pos = 0
    while pos < n:
        debut_fenetre = max(0, pos - taille_recherche)
        meilleur_debut, longueur = -1, 0

        # On allonge le motif tant qu'on le retrouve dans le tampon de recherche.
        # (pos + longueur + 1 < n : il faut toujours garder un « caractère suivant ».)
        while longueur < longueur_max and pos + longueur + 1 < n:
            motif = donnees[pos:pos + longueur + 1]
            # rfind cherche la DERNIÈRE occurrence, donc la plus proche (plus petit
            # décalage). La borne de fin pos + longueur oblige la copie à COMMENCER
            # dans le tampon de recherche, mais l'autorise à déborder dans le tampon
            # de lecture : c'est le chevauchement de (3,5,D) dans l'exemple.
            trouve = donnees.rfind(motif, debut_fenetre, pos + longueur)
            if trouve == -1:
                break
            meilleur_debut, longueur = trouve, longueur + 1

        decalage = pos - meilleur_debut if longueur > 0 else 0
        triplet = Triplet(decalage, longueur, donnees[pos + longueur])
        if trace is not None:
            trace.append((donnees[debut_fenetre:pos],
                          donnees[pos:pos + taille_anticipation], triplet))
        triplets.append(triplet)
        pos += longueur + 1
    return triplets


def decompresser_lz77(triplets):
    """Reconstruit les données à partir des triplets (str si les caractères sont
    des str, bytes sinon)."""
    sortie = []
    for decalage, longueur, caractere in triplets:
        if longueur and not 0 < decalage <= len(sortie):
            raise ValueError(f"triplet invalide : ({decalage}, {longueur}, …)")
        debut = len(sortie) - decalage
        # Copie symbole par symbole : si la copie chevauche ce qu'on est en train
        # d'écrire (longueur > décalage), les symboles copiés viennent d'être ajoutés.
        for i in range(longueur):
            sortie.append(sortie[debut + i])
        sortie.append(caractere)
    if triplets and isinstance(triplets[0].caractere, str):
        return "".join(sortie)
    return bytes(sortie)


def demo():
    message = EXEMPLE_MESSAGE
    R, A = EXEMPLE_RECHERCHE, EXEMPLE_ANTICIPATION
    print(f"=== LZ77 : exemple « {message} » ===")
    print(f"Tampon de recherche = {R} symboles, tampon de lecture = {A} symboles\n")
    print(" Étape   Tampon de recherche   Tampon de lecture   Triplet")
    trace = []
    triplets = compresser_lz77(message, R, A, trace)
    for etape, (recherche, lecture, (d, l, c)) in enumerate(trace, start=1):
        print(f"   {etape}     {recherche.rjust(R, '.'):<20}  {lecture:<18}  ({d}, {l}, {c})")
    resultat = decompresser_lz77(triplets)
    print(f"\n{len(triplets)} triplets pour {len(message)} symboles.")
    print(f"Décodage : {resultat}  ({'identique ✓' if resultat == message else 'ERREUR ✗'})")


if __name__ == "__main__":
    demo()
