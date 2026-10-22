"""
arithmetique.py — Codage arithmétique (version pédagogique, fractions exactes).

Idée : un message entier est représenté par UN SEUL nombre de l'intervalle [0, 1).
On part de [L₀, R₀) = [0, 1) et, à chaque symbole, on « zoome » dans la
partie de l'intervalle courant qui correspond à ce symbole.

Notations (document « codage-arithmétique-2-SUITE ») :
    P(sᵢ)   probabilité du symbole sᵢ
    C(sᵢ)   probabilité cumulée : C(sᵢ) = P(s₁) + … + P(sᵢ), avec C(s₀) = 0
            → le symbole sᵢ possède l'intervalle [C(sᵢ₋₁), C(sᵢ))

Codage (étape j, on lit le symbole sᵢ) :
    Lⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁) · C(sᵢ₋₁)
    Rⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁) · C(sᵢ)

Décodage (D₀ = le nombre reçu) :
    on cherche sᵢ tel que C(sᵢ₋₁) ≤ Dⱼ₋₁ < C(sᵢ)
    Dⱼ = (Dⱼ₋₁ − C(sᵢ₋₁)) / P(sᵢ)

Tous les calculs utilisent fractions.Fraction : AUCUNE erreur d'arrondi.
Le prix à payer : les fractions grossissent à chaque symbole (il n'y a pas de
renormalisation). Pour les fichiers, on découpe donc la suite de symboles en
BLOCS de 256 : chaque bloc est codé comme un petit message indépendant,
exactement comme « CALCU ».

Lancer `python arithmetique.py` affiche l'exemple CALCU pas à pas.
"""

from bisect import bisect_right
from fractions import Fraction

from utils import (bits_vers_fraction, bits_vers_octets, ecrire_varint,
                   fraction_en_texte, fraction_vers_bits, fraction_vers_decimal,
                   lire_varint, octets_vers_bits)

TAILLE_BLOC = 256   # nombre de symboles codés par un seul nombre (fichiers)

# Exemple du document : message « CALCU » et sa table de probabilités,
# dans l'ordre des intervalles : A [0 ; 0.1)  C [0.1 ; 0.6)  U [0.6 ; 0.8)  L [0.8 ; 1)
EXEMPLE_MESSAGE = "CALCU"
EXEMPLE_PROBABILITES = {"A": "0.1", "C": "0.5", "U": "0.2", "L": "0.2"}


class Modele:
    """Table des probabilités P(s) et des intervalles [C(sᵢ₋₁), C(sᵢ)).

    `poids` est un dictionnaire ORDONNÉ {symbole: poids}. Les poids peuvent être
    des effectifs (2, 1, 1…) ou des probabilités ("0.1", Fraction(1, 2)…) :
    ils sont divisés par leur somme. L'ordre du dictionnaire fixe l'ordre des
    intervalles sur [0, 1).
    """

    def __init__(self, poids):
        poids = {s: Fraction(p) for s, p in poids.items()}
        self.symboles = [s for s, p in poids.items() if p > 0]
        if not self.symboles:
            raise ValueError("un modèle doit contenir au moins un symbole")
        total = sum(poids[s] for s in self.symboles)

        self.P = {}        # P(sᵢ)
        self.C_bas = {}    # C(sᵢ₋₁) : début de l'intervalle du symbole
        self.C_haut = {}   # C(sᵢ)   : fin de l'intervalle du symbole
        cumul = Fraction(0)
        for s in self.symboles:
            self.P[s] = poids[s] / total
            self.C_bas[s] = cumul
            cumul += self.P[s]
            self.C_haut[s] = cumul
        self._debuts = [self.C_bas[s] for s in self.symboles]   # pour la recherche

    @classmethod
    def depuis_message(cls, message):
        """Modèle obtenu en comptant les symboles du message (ordre croissant)."""
        effectifs = {}
        for s in message:
            effectifs[s] = effectifs.get(s, 0) + 1
        return cls(dict(sorted(effectifs.items())))

    def intervalle(self, s):
        """Retourne (C(sᵢ₋₁), C(sᵢ)) pour le symbole s."""
        return self.C_bas[s], self.C_haut[s]

    def symbole_pour(self, D):
        """Le symbole sᵢ tel que C(sᵢ₋₁) ≤ D < C(sᵢ) (recherche dichotomique)."""
        return self.symboles[bisect_right(self._debuts, D) - 1]


# ---------------------------------------------------------------------------
# Codage et décodage d'un message (les formules du document)
# ---------------------------------------------------------------------------

def coder(message, modele, trace=None):
    """Code `message` et retourne l'intervalle final [L, R) (deux Fractions).

    Si `trace` est une liste, on y ajoute (symbole, Lⱼ, Rⱼ) à chaque étape.
    """
    L, R = Fraction(0), Fraction(1)                       # [L₀, R₀) = [0, 1)
    for s in message:
        C_prec, C_s = modele.intervalle(s)                # C(sᵢ₋₁) et C(sᵢ)
        largeur = R - L                                   # Rⱼ₋₁ − Lⱼ₋₁
        # Affectation simultanée : Lⱼ et Rⱼ sont tous deux calculés avec Lⱼ₋₁.
        L, R = L + largeur * C_prec, L + largeur * C_s    # Lⱼ, Rⱼ
        if trace is not None:
            trace.append((s, L, R))
    return L, R


def decoder(D, nb_symboles, modele, trace=None):
    """Retrouve `nb_symboles` symboles à partir du nombre D (une Fraction).

    Si `trace` est une liste, on y ajoute (Dⱼ₋₁, symbole, Dⱼ) à chaque étape.
    """
    message = []
    for _ in range(nb_symboles):
        s = modele.symbole_pour(D)                        # C(sᵢ₋₁) ≤ Dⱼ₋₁ < C(sᵢ)
        D_suivant = (D - modele.C_bas[s]) / modele.P[s]   # Dⱼ = (Dⱼ₋₁ − C(sᵢ₋₁)) / P(sᵢ)
        if trace is not None:
            trace.append((D, s, D_suivant))
        message.append(s)
        D = D_suivant
    return message


# ---------------------------------------------------------------------------
# Longues suites de symboles (fichiers) : découpage en blocs
# ---------------------------------------------------------------------------

def compresser_symboles(symboles, modele, taille_bloc=TAILLE_BLOC):
    """Code une suite de symboles bloc par bloc et retourne des octets.

    Chaque bloc devient :  [k = nombre de bits (varint)] [k bits, complétés à l'octet]
    où les k bits sont le nombre binaire le plus court de l'intervalle du bloc.
    """
    sortie = bytearray()
    for debut in range(0, len(symboles), taille_bloc):
        L, R = coder(symboles[debut:debut + taille_bloc], modele)
        bits = fraction_vers_bits(L, R)
        sortie += ecrire_varint(len(bits))
        sortie += bits_vers_octets(bits)
    return bytes(sortie)


def decompresser_symboles(donnees, nb_symboles, modele, taille_bloc=TAILLE_BLOC):
    """Inverse de compresser_symboles : retourne la liste des `nb_symboles` symboles."""
    if taille_bloc <= 0:
        raise ValueError("taille de bloc invalide")
    symboles, pos = [], 0
    while len(symboles) < nb_symboles:
        nb_bits, pos = lire_varint(donnees, pos)
        nb_octets = (nb_bits + 7) // 8
        if pos + nb_octets > len(donnees):
            raise ValueError("bloc arithmétique tronqué")
        D = bits_vers_fraction(octets_vers_bits(donnees[pos:pos + nb_octets], nb_bits))
        pos += nb_octets
        symboles.extend(decoder(D, min(taille_bloc, nb_symboles - len(symboles)), modele))
    return symboles


# ---------------------------------------------------------------------------
# Démonstration : l'exemple CALCU du document
# ---------------------------------------------------------------------------

def demo():
    t = fraction_en_texte
    modele = Modele(EXEMPLE_PROBABILITES)
    message = EXEMPLE_MESSAGE

    print(f"=== Codage arithmétique : exemple « {message} » ===\n")
    print("Table des probabilités")
    print("  Symbole   P(s)    Intervalle [C(sᵢ₋₁) ; C(sᵢ))")
    for s in modele.symboles:
        bas, haut = modele.intervalle(s)
        print(f"     {s}      {t(modele.P[s]):<6}  [{t(bas)} ; {t(haut)})")

    print("\nCodage :  Lⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ₋₁)    Rⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ)")
    print("   j   symbole   Lⱼ          Rⱼ")
    print("   0      -      0           1")
    trace = []
    L, R = coder(message, modele, trace)
    for j, (s, Lj, Rj) in enumerate(trace, start=1):
        print(f"   {j}      {s}      {t(Lj):<11} {t(Rj)}")

    code = fraction_vers_decimal(L, R)
    bits = fraction_vers_bits(L, R)
    print(f"\nIntervalle final      : [{t(L)} ; {t(R)})")
    print(f"Code (base 10)        : {code}")
    print(f"Code (base 2, fichier): 0,{bits} = {t(bits_vers_fraction(bits))}"
          f"  → {len(bits)} bits au lieu de {8 * len(message)} bits en ASCII")

    print("\nDécodage :  on cherche sᵢ tel que C(sᵢ₋₁) ≤ Dⱼ₋₁ < C(sᵢ),"
          "  puis Dⱼ = (Dⱼ₋₁ − C(sᵢ₋₁)) / P(sᵢ)")
    print("   j   Dⱼ₋₁        symbole   Dⱼ")
    trace = []
    resultat = "".join(decoder(Fraction(code), len(message), modele, trace))
    for j, (D, s, D_suivant) in enumerate(trace, start=1):
        print(f"   {j}   {t(D):<11}    {s}      {t(D_suivant)}")
    print(f"\nMessage décodé : {resultat}  ({'identique ✓' if resultat == message else 'ERREUR ✗'})")


if __name__ == "__main__":
    demo()
