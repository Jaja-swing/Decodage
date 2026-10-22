"""
utils.py — Petits outils de conversion utilisés par MiniZip.

1) Fraction ↔ bits ↔ octets
   Le codeur arithmétique produit un INTERVALLE [L, R) de nombres rationnels.
   Pour le transmettre, on choisit dans cet intervalle le nombre qui s'écrit
   avec le MOINS de chiffres possible :
     - en base 10 pour l'affichage pédagogique : [0.144 ; 0.145) → « 0.144 »
     - en base 2 pour le fichier .mz         : 0,b₁b₂…bₖ (base 2) → k bits
   Le décodeur relit ces k bits et retrouve le nombre EXACT D = m / 2ᵏ.

2) Entiers de taille variable (« varint », format LEB128)
   Un entier < 128 tient sur 1 octet, un entier < 16 384 sur 2 octets, etc.
   On s'en sert pour les tables de fréquences et les longueurs de blocs.
"""

from fractions import Fraction


# ---------------------------------------------------------------------------
# 1. Le nombre le plus court d'un intervalle [bas, haut)
# ---------------------------------------------------------------------------

def nombre_le_plus_court(bas, haut, base=2):
    """Plus petit nombre de chiffres k (et entier m) tels que

            bas ≤ m / baseᵏ < haut

    Retourne (m, k) : le nombre choisi s'écrit 0,c₁c₂…cₖ en `base`.

    Exemple : nombre_le_plus_court(0.144, 0.145, 10) → (144, 3), soit 0.144
    """
    bas, haut = Fraction(bas), Fraction(haut)
    if not 0 <= bas < haut <= 1:
        raise ValueError("il faut 0 ≤ bas < haut ≤ 1")

    def candidat(k):
        """Plus petit nombre à k chiffres qui soit ≥ bas, ou None s'il est ≥ haut."""
        echelle = base ** k
        m = -((-bas.numerator * echelle) // bas.denominator)      # m = ⌈bas · baseᵏ⌉
        if m * haut.denominator < haut.numerator * echelle:        # m / baseᵏ < haut ?
            return m
        return None

    # Si k chiffres suffisent, k + 1 aussi (on ajoute un 0 à la fin) :
    # on peut donc doubler k jusqu'à réussir, puis affiner par dichotomie.
    k_max = 1
    while candidat(k_max) is None:
        k_max *= 2
    k_min = 0
    while k_min < k_max:
        milieu = (k_min + k_max) // 2
        if candidat(milieu) is None:
            k_min = milieu + 1
        else:
            k_max = milieu
    return candidat(k_min), k_min


def fraction_vers_decimal(bas, haut):
    """Nombre décimal le plus court de [bas, haut), sous forme de texte (« 0.144 »)."""
    m, k = nombre_le_plus_court(bas, haut, 10)
    return "0." + str(m).zfill(k) if k else "0"


def fraction_vers_bits(bas, haut):
    """Nombre binaire le plus court de [bas, haut) : la chaîne des bits après la virgule.

    Exemple : [0.144 ; 0.145) → "00100101", car 0,00100101 (base 2) = 37/256 = 0.14453125
    """
    m, k = nombre_le_plus_court(bas, haut, 2)
    return format(m, "b").zfill(k) if k else ""


def bits_vers_fraction(bits):
    """Inverse de fraction_vers_bits : "00100101" → Fraction(37, 256)."""
    if not bits:
        return Fraction(0)
    return Fraction(int(bits, 2), 2 ** len(bits))


def bits_vers_octets(bits):
    """Regroupe les bits par paquets de 8 (le dernier octet est complété par des 0)."""
    nb_octets = (len(bits) + 7) // 8
    if nb_octets == 0:
        return b""
    return int(bits.ljust(nb_octets * 8, "0"), 2).to_bytes(nb_octets, "big")


def octets_vers_bits(octets, nb_bits):
    """Inverse de bits_vers_octets : ne garde que les `nb_bits` premiers bits."""
    if nb_bits == 0:
        return ""
    tous = format(int.from_bytes(octets, "big"), "b").zfill(len(octets) * 8)
    return tous[:nb_bits]


# ---------------------------------------------------------------------------
# 2. Entiers de taille variable (varint)
# ---------------------------------------------------------------------------

def ecrire_varint(n):
    """Entier ≥ 0 → octets. Chaque octet porte 7 bits ; le bit de poids fort
    vaut 1 s'il reste des octets à lire.   300 → b'\\xac\\x02'"""
    if n < 0:
        raise ValueError("un varint doit être positif")
    sortie = bytearray()
    while True:
        septet, n = n & 0x7F, n >> 7
        if n:
            sortie.append(septet | 0x80)
        else:
            sortie.append(septet)
            return bytes(sortie)


def lire_varint(donnees, pos):
    """Lit un varint à partir de `pos`. Retourne (valeur, position suivante)."""
    valeur, decalage = 0, 0
    while True:
        if pos >= len(donnees):
            raise ValueError("varint tronqué")
        octet = donnees[pos]
        pos += 1
        valeur |= (octet & 0x7F) << decalage
        decalage += 7
        if octet < 0x80:
            return valeur, pos


# ---------------------------------------------------------------------------
# 3. Affichage
# ---------------------------------------------------------------------------

def fraction_en_texte(f, max_decimales=12):
    """Écrit une fraction en décimal : exact si possible, sinon tronqué et suivi de « … »."""
    f = Fraction(f)
    signe = "-" if f < 0 else ""
    f = abs(f)
    entier, reste = divmod(f.numerator, f.denominator)
    chiffres = []
    while reste and len(chiffres) < max_decimales:
        chiffre, reste = divmod(reste * 10, f.denominator)
        chiffres.append(str(chiffre))
    texte = signe + str(entier) + ("." + "".join(chiffres) if chiffres else "")
    return texte + ("…" if reste else "")
