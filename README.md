# MiniZip — compresseur pédagogique LZ77 + codage arithmétique

MiniZip compresse n'importe quel fichier (texte ou binaire) dans une archive `.mz`, puis le restaure **à l'identique**.
Il suit le même principe que WinRAR et 7-Zip, en version simple et lisible :

1. **LZ77** supprime les répétitions (compression par dictionnaire) ;
2. le **codage arithmétique** code les triplets obtenus au plus près de l'entropie (compression par intervalles).

Le projet est écrit en Python, sans aucune dépendance. Chaque fonction est reliée aux formules des deux documents
de cours, et les deux exemples des documents (CALCU → 0.144, CABRACADABRARRARRAD → 8 triplets) sont reproduits
exactement et vérifiés par les tests.

---

## Sommaire

1. [Démarrage rapide](#1-démarrage-rapide)
2. [Arborescence](#2-arborescence)
3. [Architecture](#3-architecture)
4. [Rôle de chaque module](#4-rôle-de-chaque-module)
5. [Les exemples des documents](#5-les-exemples-des-documents)
6. [Le format .mz](#6-le-format-mz)
7. [Utilisation](#7-utilisation)
8. [Tests](#8-tests)
9. [Exemple de session console](#9-exemple-de-session-console)
10. [Taux de compression obtenu et explication](#10-taux-de-compression-obtenu-et-explication)
11. [Limites et pistes d'amélioration](#11-limites-et-pistes-damélioration)
12. [Feuille de route](#12-feuille-de-route)

---

## 1. Démarrage rapide

Il faut **Python 3.8 ou plus récent** (testé avec 3.12 et 3.14), et rien d'autre (aucun `pip install`). Les commandes se lancent depuis le dossier `MiniZip/` :

```bash
python main.py                                  # menu interactif
python main.py demo                             # les deux exemples du cours, pas à pas
python exemples/generer_images.py               # crée exemples/image.bmp et exemples/image.png
python main.py compresser exemples/texte.txt    # → exemples/texte.txt.mz
python main.py decompresser exemples/texte.txt.mz   # → exemples/extrait/texte.txt
python -m unittest discover -s tests -v         # 52 tests unitaires
```

> Sous Linux et macOS, remplacez `python` par `python3` si nécessaire.

---

## 2. Arborescence

```
MiniZip/
├── main.py              Interface console : menu interactif + ligne de commande
├── pipeline.py          Enchaînement LZ77 → arithmétique, fichiers, statistiques
├── lz77.py              Encodeur + décodeur LZ77 (fenêtre glissante, triplets)
├── arithmetique.py      Encodeur + décodeur arithmétique (fractions exactes)
├── format_fichier.py    En-tête .mz (Magic « MZIP », version, nom, taille, CRC),
│                        tables de fréquences, flux
├── utils.py             Conversions Fraction ↔ bits ↔ octets, entiers « varint »
├── tests/
│   ├── test_arithmetique.py   Exemple CALCU + allers-retours
│   ├── test_lz77.py           Exemple CABRACADABRARRARRAD + allers-retours
│   ├── test_utils.py          Nombre le plus court, bits/octets, varints
│   ├── test_format.py         En-tête, tables, flux, fichiers invalides
│   └── test_pipeline.py       decompresser(compresser(f)) == f, corruption
├── exemples/
│   ├── texte.txt              Texte français (6,2 Ko)
│   └── generer_images.py      Crée image.bmp (non compressée) et image.png
├── README.md
└── FEUILLE_DE_ROUTE.md  Planning sur 4 semaines
```

Un module **`pipeline.py`** s'ajoute à ceux du cahier des charges. Il contient l'enchaînement
« LZ77 → codage arithmétique → fichier ». Sans lui, cet enchaînement serait mélangé soit à
l'interface (`main.py`), soit au format (`format_fichier.py`). Avec lui, chaque module garde un seul rôle.

---

## 3. Architecture

```
                               COMPRESSION
  fichier ──► lz77.py ──► triplets (décalage, longueur, caractère)
                                │
                     pipeline.py : séparation en 4 flux d'octets
          ┌──────────────┬──────┴─────────┬──────────────┐
   décalage // 256  décalage % 256     longueur      caractère
          │              │                │              │
          └──── arithmetique.py : 1 table de fréquences par flux,
                         codage par blocs de 256 symboles ────┐
                                                              ▼
              format_fichier.py : en-tête + 4 × (table + données) ──► fichier .mz

                               DÉCOMPRESSION
  fichier .mz ──► lecture de l'en-tête et des tables ──► décodage arithmétique
              ──► triplets ──► décodage LZ77 ──► vérification taille + CRC-32 ──► fichier
```

Dépendances entre modules (aucune boucle) :

```
main.py ──► pipeline.py ──┬──► lz77.py
                          ├──► arithmetique.py ──► utils.py
                          └──► format_fichier.py ──► utils.py
```

**Pourquoi 4 flux ?** Les champs d'un triplet n'ont pas la même statistique : les longueurs sont
surtout 1 à 5, l'octet fort du décalage est presque toujours petit, les caractères suivent la langue.
Avec une table de fréquences par champ, les probabilités sont plus « pointues » et le code est plus court
qu'avec une table unique qui mélangerait tout.

**Pourquoi des blocs de 256 symboles ?** Sans renormalisation, l'intervalle [L, R) rétrécit à chaque
symbole et ses fractions grossissent sans fin. Le coût de chaque opération augmente avec elles. On découpe donc la suite de
symboles en blocs. Chaque bloc est codé comme un petit message indépendant, **exactement comme CALCU** :
un intervalle, puis le nombre le plus court de cet intervalle. Le surcoût est d'environ 2 % (voir § 10).

---

## 4. Rôle de chaque module

| Module | Rôle | Fonctions principales |
|---|---|---|
| `utils.py` | Conversions **Fraction ↔ bits ↔ octets** : choisir dans [L, R) le nombre qui s'écrit avec le moins de chiffres (base 10 pour l'affichage, base 2 pour le fichier) ; entiers de taille variable (varint) | `nombre_le_plus_court`, `fraction_vers_decimal`, `fraction_vers_bits`, `bits_vers_fraction`, `bits_vers_octets`, `ecrire_varint`, `lire_varint` |
| `arithmetique.py` | **Codage arithmétique** exact avec `fractions.Fraction`. `Modele` = table P(s) et intervalles [C(sᵢ₋₁), C(sᵢ)) ; `coder` applique Lⱼ et Rⱼ ; `decoder` applique Dⱼ | `Modele`, `coder`, `decoder`, `compresser_symboles`, `decompresser_symboles`, `demo` |
| `lz77.py` | **LZ77** : fenêtre glissante (tampon de recherche + tampon de lecture), triplets (décalage, longueur, caractère suivant), copie avec chevauchement | `compresser_lz77`, `decompresser_lz77`, `Triplet`, `demo` |
| `format_fichier.py` | **Format .mz** : Magic `MZIP`, version, méthode, nom, taille originale, CRC-32, paramètres, tables de fréquences, flux | `EnTete`, `ecrire_entete`, `lire_entete`, `ecrire_table_frequences`, `lire_flux`, `FormatInvalide` |
| `pipeline.py` | **Enchaînement** LZ77 → 4 flux → arithmétique, mode « stocké » si aucun gain, contrôle d'intégrité, statistiques (entropie, limite de Shannon) | `compresser_octets`, `decompresser_octets`, `compresser_fichier`, `decompresser_fichier`, `lire_infos` |
| `main.py` | **Interface** : menu console et commandes `compresser`, `decompresser`, `info`, `demo` | `menu`, `main` |

Correspondance entre le code et les formules du document :

| Formule du document | Ligne de code (`arithmetique.py`) |
|---|---|
| Lⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ₋₁) | `L, R = L + largeur * C_prec, L + largeur * C_s` avec `largeur = R - L` |
| Rⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ) | (même ligne : l'affectation simultanée utilise Lⱼ₋₁ pour les deux) |
| trouver sᵢ tel que C(sᵢ₋₁) ≤ Dⱼ₋₁ < C(sᵢ) | `s = modele.symbole_pour(D)` |
| Dⱼ = (Dⱼ₋₁ − C(sᵢ₋₁)) / P(sᵢ) | `D_suivant = (D - modele.C_bas[s]) / modele.P[s]` |

---

## 5. Les exemples des documents

### 5.1 Codage arithmétique : « CALCU » → 0.144

`python arithmetique.py` (ou l'option 4 du menu) affiche :

```
Table des probabilités
  Symbole   P(s)    Intervalle [C(sᵢ₋₁) ; C(sᵢ))
     A      0.1     [0 ; 0.1)
     C      0.5     [0.1 ; 0.6)
     U      0.2     [0.6 ; 0.8)
     L      0.2     [0.8 ; 1)

Codage :  Lⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ₋₁)    Rⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ)
   j   symbole   Lⱼ          Rⱼ
   0      -      0           1
   1      C      0.1         0.6
   2      A      0.1         0.15
   3      L      0.14        0.15
   4      C      0.141       0.146
   5      U      0.144       0.145

Intervalle final      : [0.144 ; 0.145)
Code (base 10)        : 0.144
Code (base 2, fichier): 0,00100101 = 0.14453125  → 8 bits au lieu de 40 bits en ASCII

Décodage :  on cherche sᵢ tel que C(sᵢ₋₁) ≤ Dⱼ₋₁ < C(sᵢ),  puis Dⱼ = (Dⱼ₋₁ − C(sᵢ₋₁)) / P(sᵢ)
   j   Dⱼ₋₁        symbole   Dⱼ
   1   0.144          C      0.088
   2   0.088          A      0.88
   3   0.88           L      0.4
   4   0.4            C      0.6
   5   0.6            U      0

Message décodé : CALCU  (identique ✓)
```

### 5.2 LZ77 : « CABRACADABRARRARRAD » → 8 triplets

`python lz77.py` (ou l'option 5 du menu), avec un tampon de recherche de 7 et un tampon de lecture de 6 :

```
 Étape   Tampon de recherche   Tampon de lecture   Triplet
   1     .......               CABRAC              (0, 0, C)
   2     ......C               ABRACA              (0, 0, A)
   3     .....CA               BRACAD              (0, 0, B)
   4     ....CAB               RACADA              (0, 0, R)
   5     ...CABR               ACADAB              (3, 1, C)
   6     .CABRAC               ADABRA              (2, 1, D)
   7     ABRACAD               ABRARR              (7, 4, R)
   8     ADABRAR               RARRAD              (3, 5, D)

8 triplets pour 19 symboles.
Décodage : CABRACADABRARRARRAD  (identique ✓)
```

Le dernier triplet `(3, 5, D)` montre le **chevauchement** : la copie commence 3 positions en arrière
mais dure 5 symboles. Elle déborde donc sur ce qu'elle est en train d'écrire (`RAR` + `RA`).

### 5.3 Conventions retenues (à vérifier avec vos documents)

Les deux fichiers `.docx` n'étaient pas joints au moment du développement. Les exemples ont donc été reconstruits
à partir des résultats annoncés :

- **CALCU** : la table `A = 0.1, C = 0.5, U = 0.2, L = 0.2`, dans cet ordre sur [0, 1), est la seule table
  « ronde » qui donne exactement l'intervalle [0.144 ; 0.145). Elle donne aussi un décodage aux valeurs
  rondes (0.144 → 0.088 → 0.88 → 0.4 → 0.6), ce qui est typique d'un exemple de cours.
  Si votre document utilise une autre table, il suffit de modifier `EXEMPLE_PROBABILITES` dans
  `arithmetique.py` et `TABLE_CALCU` dans `tests/test_arithmetique.py`.
- **LZ77** : tampon de recherche = 7, tampon de lecture = 6 (les paramètres classiques de cet exemple).
  Le décalage se compte **en reculant depuis la position courante**. En cas d'égalité de longueur, on prend
  l'occurrence **la plus proche**, d'où `(2, 1, D)` plutôt que `(5, 1, D)`. Ces paramètres sont modifiables
  via `EXEMPLE_RECHERCHE` et `EXEMPLE_ANTICIPATION` dans `lz77.py`.

---

## 6. Le format .mz

Tous les entiers de taille fixe sont en big-endian.

| Taille | Champ | Contenu |
|---|---|---|
| 4 o | Magic number | `MZIP` (identifie le format) |
| 1 o | Version | `1` |
| 1 o | Méthode | `0` = stocké, `1` = LZ77 + codage arithmétique |
| 2 o | Longueur du nom | n |
| n o | Nom d'origine | UTF-8 |
| 8 o | Taille originale | en octets |
| 4 o | CRC-32 | empreinte du fichier original (contrôle d'intégrité) |
| 2 o | Fenêtre LZ77 | taille du tampon de recherche (4095) |
| 2 o | Anticipation LZ77 | taille du tampon de lecture (256) |
| 2 o | Taille de bloc | symboles par nombre arithmétique (256) |
| 4 o | Nombre de triplets | |

**Corps (méthode 1)** : 4 flux à la suite (décalage octet fort, décalage octet faible, longueur, caractère).
Chaque flux contient :

| Taille | Champ |
|---|---|
| varint | nombre de symboles distincts *d* |
| *d* × (1 o + varint) | **table de fréquences** : (symbole, effectif) |
| varint | taille *t* des données codées |
| *t* o | blocs arithmétiques : pour chaque bloc, `k` (varint) puis les `k` bits du nombre le plus court, complétés à l'octet |

**Corps (méthode 0)** : les octets originaux, tels quels (utilisé quand la compression ne fait rien gagner).

Avec un nom de fichier de 9 caractères (`texte.txt`), l'en-tête fait 39 octets.

---

## 7. Utilisation

### Menu interactif

```bash
python main.py
```

```
==================================================
  MiniZip — compression LZ77 + codage arithmétique
==================================================
  1. Compresser un fichier
  2. Décompresser un fichier .mz
  3. Afficher les informations d'un fichier .mz
  4. Exemple du cours : codage arithmétique (CALCU)
  5. Exemple du cours : LZ77 (CABRACADABRARRARRAD)
  0. Quitter
```

### Ligne de commande

```bash
python main.py
python main.py compresser FICHIER [-o SORTIE.mz]
python main.py decompresser ARCHIVE.mz [-o DOSSIER]
python main.py info ARCHIVE.mz
python main.py demo
```

Par défaut, la décompression écrit le fichier dans un dossier `extrait/` à côté de l'archive. Ainsi, l'original
n'est jamais écrasé et on peut comparer les deux fichiers. Par sécurité, seul le **nom** stocké dans l'en-tête est utilisé :
un nom piégé comme `../../x` ne peut pas écrire en dehors du dossier de sortie.

---

## 8. Tests

```bash
python -m unittest discover -s tests -v
```

52 tests, exécutés en environ 1 seconde (Python 3.12 et 3.14) :

| Fichier | Ce qui est vérifié |
|---|---|
| `test_arithmetique.py` | Les intervalles de chaque symbole, les **5 intervalles intermédiaires** de CALCU, le résultat **[0.144 ; 0.145)** et le code « 0.144 », le **décodage** 0.144 → 0.088 → 0.88 → 0.4 → 0.6, le code binaire `00100101`, des allers-retours aléatoires, le découpage en blocs (0, 1, 255, 256, 257 et 1000 symboles) |
| `test_lz77.py` | Les **8 triplets** exacts du document et leur décodage, le contenu des tampons à l'étape 7, le chevauchement, le fichier vide, les triplets invalides, des allers-retours avec plusieurs tailles de fenêtre |
| `test_utils.py` | Le nombre le plus court (comparé à une recherche exhaustive), les bits ↔ octets, les varints |
| `test_format.py` | L'aller-retour de l'en-tête, le Magic number, une mauvaise version, les en-têtes et flux tronqués |
| `test_pipeline.py` | **decompresser(compresser(f)) == f** pour un fichier vide, 1 octet, du texte, des octets aléatoires (→ stocké) et les fichiers de `exemples/`, la détection de corruption (CRC-32), une archive tronquée, la neutralisation d'un nom piégé |

---

## 9. Exemple de session console

Session réelle (le menu, réaffiché après chaque action, est abrégé ici) :

```
==================================================
  MiniZip — compression LZ77 + codage arithmétique
==================================================
  1. Compresser un fichier
  2. Décompresser un fichier .mz
  3. Afficher les informations d'un fichier .mz
  4. Exemple du cours : codage arithmétique (CALCU)
  5. Exemple du cours : LZ77 (CABRACADABRARRARRAD)
  0. Quitter
Votre choix : 1

Fichier à compresser : exemples/texte.txt
Compression de « exemples/texte.txt »…
  … LZ77 : 1329 triplets
  … codage arithmétique du flux « décalage (octet fort) »
  … codage arithmétique du flux « décalage (octet faible) »
  … codage arithmétique du flux « longueur »
  … codage arithmétique du flux « caractère »

  Flux                       Symboles  Distincts  Entropie   Shannon    Table     Codé
  décalage (octet fort)          1329         16  2.74 b/s     455 o     35 o    469 o
  décalage (octet faible)        1329        252  7.72 b/s    1282 o    506 o   1297 o
  longueur                       1329         26  3.20 b/s     531 o     57 o    544 o
  caractère                      1329         82  5.19 b/s     862 o    165 o    875 o

  Taille originale      : 6 372 octets
  Après LZ77 (brut)     : 1329 triplets × 4 octets = 5 316 octets (83.4 %)
  Méthode retenue       : LZ77 + codage arithmétique
  Fichier .mz           : 3 995 octets (dont en-tête : 39 o)
  Taux de compression   : 62.7 %  → gain de 37.3 %
  Durée                 : 0.23 s
  Archive créée         : exemples/texte.txt.mz

[… menu réaffiché …]
Votre choix : 2

Fichier .mz à décompresser : exemples/texte.txt.mz
Dossier de sortie (Entrée = « extrait » à côté de l'archive) :
Décompression de « exemples/texte.txt.mz »…
  Fichier restauré      : exemples/extrait/texte.txt (6 372 octets)
  Contrôle d'intégrité  : taille et CRC-32 (4C4E8791) conformes ✓
  Durée                 : 0.04 s

[… menu réaffiché …]
Votre choix : 1

Fichier à compresser : exemples/image.bmp
Compression de « exemples/image.bmp »…
  … LZ77 : 443 triplets
  … codage arithmétique du flux « décalage (octet fort) »
  … codage arithmétique du flux « décalage (octet faible) »
  … codage arithmétique du flux « longueur »
  … codage arithmétique du flux « caractère »

  Flux                       Symboles  Distincts  Entropie   Shannon    Table     Codé
  décalage (octet fort)           443          3  1.11 b/s      61 o      8 o     66 o
  décalage (octet faible)         443         37  2.78 b/s     154 o     76 o    158 o
  longueur                        443        110  4.31 b/s     239 o    222 o    243 o
  caractère                       443         92  5.03 b/s     279 o    185 o    283 o

  Taille originale      : 73 782 octets
  Après LZ77 (brut)     : 443 triplets × 4 octets = 1 772 octets (2.4 %)
  Méthode retenue       : LZ77 + codage arithmétique
  Fichier .mz           : 1 287 octets (dont en-tête : 39 o)
  Taux de compression   : 1.7 %  → gain de 98.3 %
  Durée                 : 0.10 s
  Archive créée         : exemples/image.bmp.mz

[… menu réaffiché …]
Votre choix : 2

Fichier .mz à décompresser : exemples/image.bmp.mz
Dossier de sortie (Entrée = « extrait » à côté de l'archive) :
Décompression de « exemples/image.bmp.mz »…
  Fichier restauré      : exemples/extrait/image.bmp (73 782 octets)
  Contrôle d'intégrité  : taille et CRC-32 (4FFD10D3) conformes ✓
  Durée                 : 0.02 s

[… menu réaffiché …]
Votre choix : 3

Fichier .mz : exemples/image.bmp.mz
Fichier « exemples/image.bmp.mz »
  Format             : MZIP version 1
  Nom d'origine      : image.bmp
  Taille originale   : 73 782 octets
  Taille .mz         : 1 287 octets (1.7 %)
  CRC-32             : 4FFD10D3
  Méthode            : LZ77 + codage arithmétique
  LZ77               : fenêtre 4095, anticipation 256, 443 triplets
  Arithmétique       : blocs de 256 symboles
  Tables de fréquences :
    décalage (octet fort)      3 symboles,     66 o codés  | plus fréquents : 0×296, 2×127, 1×20
    décalage (octet faible)   37 symboles,    158 o codés  | plus fréquents : 3×218, 64×69, 0×44, 61×30, 67×15
    longueur                 110 symboles,    243 o codés  | plus fréquents : 255×194, 0×44, 41×13, 3×6, 69×6
    caractère                 92 symboles,    283 o codés  | plus fréquents : 40 '('×81, 250×71, 180×28, 60 '<'×24, 120 'x'×24

[… menu réaffiché …]
Votre choix : 1

Fichier à compresser : exemples/image.png
Compression de « exemples/image.png »…
  … LZ77 : 491 triplets
  … codage arithmétique du flux « décalage (octet fort) »
  … codage arithmétique du flux « décalage (octet faible) »
  … codage arithmétique du flux « longueur »
  … codage arithmétique du flux « caractère »
  … aucun gain : le fichier est stocké sans compression

  Flux                       Symboles  Distincts  Entropie   Shannon    Table     Codé
  décalage (octet fort)           491          3  0.57 b/s      35 o      8 o     38 o
  décalage (octet faible)         491        171  5.80 b/s     356 o    345 o    361 o
  longueur                        491         11  1.40 b/s      86 o     25 o     90 o
  caractère                       491        233  7.56 b/s     464 o    468 o    469 o

  Taille originale      : 957 octets
  Après LZ77 (brut)     : 491 triplets × 4 octets = 1 964 octets (205.2 %)
  Méthode retenue       : stocké (aucune compression)
  Fichier .mz           : 996 octets (dont en-tête : 39 o)
  Taux de compression   : 104.1 %  → le fichier grossit de 39 octets (en-tête)
  Durée                 : 0.06 s
  Archive créée         : exemples/image.png.mz

[… menu réaffiché …]
Votre choix : 0
Au revoir !
```

Vérification indépendante avec l'outil système `cmp` : `exemples/texte.txt` et `exemples/image.bmp` sont
identiques octet pour octet à leurs versions restaurées dans `exemples/extrait/`.

---

## 10. Taux de compression obtenu et explication

**Taux de compression** = taille du `.mz` ÷ taille originale (plus il est petit, mieux c'est).
**Gain** = 1 − taux.

### Résultats mesurés

| Fichier | Original | MiniZip | Taux | Deflate (ZIP) | LZMA (7-Zip) |
|---|---:|---:|---:|---:|---:|
| `texte.txt` (français) | 6 372 o | 3 995 o | **62.7 %** | 44.2 % | 44.1 % |
| `GPL-3` (anglais, `/usr/share/common-licenses`) | 35 149 o | 15 757 o | **44.8 %** | 34.4 % | 32.3 % |
| `image.bmp` (192×128, 24 bits) | 73 782 o | 1 287 o | **1.7 %** | 1.0 % | 0.9 % |
| `image.png` (même image) | 957 o | 996 o | **104.1 %** (stocké) | 93.6 % | 92.0 % |

Les colonnes Deflate et LZMA donnent la taille du flux compressé brut, sans en-tête d'archive. Elles sont calculées
avec les modules `zlib` (niveau 9) et `lzma` (preset 9) de Python, qui utilisent les mêmes algorithmes que ZIP et 7-Zip.

### Où passent les octets ? (`texte.txt`)

```
  3 995 o = 39 o d'en-tête + 763 o de tables de fréquences + 3 185 o de données codées + 8 o de longueurs de flux
```

**Étage 1, LZ77.** Les 6 372 octets deviennent 1 329 triplets : chaque triplet remplace en moyenne 4,8 octets.
Écrits naïvement sur 4 octets, ces triplets feraient déjà 5 316 o (83 %). LZ77 seul gagne donc peu sur un texte court,
car la fenêtre de 4 Ko contient encore peu de répétitions longues.

**Étage 2, codage arithmétique.** Il code chaque flux presque exactement à la **limite de Shannon**
(colonne « Shannon » du rapport) : 3 185 o codés pour une limite théorique de 3 130 o, soit 1,8 % de plus.
Ces 1,8 % viennent du découpage en blocs (un nombre de bits par bloc, plus l'arrondi à l'octet).
Les formules du document atteignent donc leur objectif : on ne peut pas faire mieux **avec ce modèle**.

**Ce qui coûte encore cher :**

- **L'octet faible du décalage** (1 297 o, le plus gros poste) : il est presque uniforme (7,72 bits sur 8 possibles).
  Une position de copie est imprévisible, donc il n'y a presque rien à gagner sur ce flux.
- **Les tables de fréquences** (763 o, soit 19 % de l'archive) : c'est un coût fixe. Sur un texte de 35 Ko (GPL-3),
  il ne pèse plus que 5 % de l'archive, et le taux descend à 44.8 %. Plus le fichier est grand, meilleur est le taux.
- **Le caractère explicite de chaque triplet** : LZ77 écrit un caractère en clair même après une longue copie.

### Pourquoi l'image BMP se compresse à 1.7 %

Un BMP stocke chaque pixel sur 3 octets, sans aucune compression. L'image contient de grandes zones de couleur
unie (chaque ligne de ciel a une seule couleur). LZ77 les remplace par des copies de 255 octets : 194 triplets sur 443
ont la longueur maximale 255, dont 141 avec le décalage 3 (« recopier le pixel précédent »). Ces 194 copies
couvrent à elles seules 49 664 octets sur 73 782. Les 443 triplets sont ensuite codés en 750 o par le codage arithmétique,
plus 491 o de tables.
Une **photographie** se compresserait beaucoup moins bien, car ses pixels voisins ne sont presque jamais identiques.

### Pourquoi le PNG n'est pas compressé (méthode « stocké »)

Un PNG est **déjà compressé** (Deflate, c'est-à-dire LZ77 + Huffman). Ses octets ressemblent à du hasard :
l'entropie des caractères atteint 7,56 bits sur 8. LZ77 ne trouve presque rien : 491 triplets pour 957 octets,
soit 205 % en brut. Le corps compressé (tables + données ≈ 1,8 Ko) dépasse alors l'original, et MiniZip
**stocke le fichier tel quel**, comme le font WinRAR et 7-Zip. Le seul surcoût est l'en-tête de 39 octets.
Deflate et LZMA gagnent encore 6 à 8 % sur ce petit fichier, car leurs modèles n'ont pas de table à stocker.
Chez MiniZip, la seule table des caractères (468 o) pèse presque la moitié du fichier.
Aucun algorithme sans perte ne peut compresser tous les fichiers : il y a moins de fichiers courts que de fichiers longs.

### Pourquoi ZIP et 7-Zip font mieux

MiniZip applique la même idée (dictionnaire puis codage entropique), mais en version simplifiée :

| Technique | MiniZip | ZIP / 7-Zip |
|---|---|---|
| Fenêtre du dictionnaire | 4 Ko | 32 Ko (ZIP), jusqu'à plusieurs Mo/Go (7-Zip) |
| Caractère après chaque copie | toujours | non : chaque élément est soit un littéral, soit une copie (principe de LZSS) |
| Modèle de probabilités | statique, tables stockées dans le fichier | adaptatif (7-Zip) : rien à stocker, et il apprend le contexte |
| Codage des décalages | 2 octets indépendants | codes par classes de distance, contexte de la copie précédente |
| Recherche des correspondances | gloutonne (la plus longue tout de suite) | paresseuse ou optimale |

---

## 11. Limites et pistes d'amélioration

- **Vitesse** : les fractions exactes coûtent environ 35 à 40 µs par octet à la compression
  (35 Ko → 1,2 s, 137 Ko → 5,4 s). MiniZip vise des fichiers de quelques centaines de Ko au plus.
  La décompression est environ 6 fois plus rapide.
  Une amélioration naturelle est le codage arithmétique **en entiers avec renormalisation**
  (Witten, Neal & Cleary, 1987). Il est plusieurs dizaines de fois plus rapide, sans découpage en blocs.
- **LZSS** : remplacer le caractère systématique par un drapeau littéral/copie.
- **Modèle adaptatif** : mettre à jour les fréquences au fil du codage, ce qui supprime les tables de l'en-tête.
- **Recherche plus rapide** : table de hachage des préfixes de 3 octets, plutôt que `rfind`.
- **Archives multi-fichiers** et dossiers, comme WinRAR et 7-Zip.

---

## 12. Feuille de route

Le planning détaillé (tâches, livrables, critères de validation) est dans [FEUILLE_DE_ROUTE.md](FEUILLE_DE_ROUTE.md).

| Semaine | Objectif | Fichiers | Validation |
|---|---|---|---|
| S1 | Codage arithmétique seul | `utils.py`, `arithmetique.py` | `python arithmetique.py` affiche CALCU → 0.144 ; `test_arithmetique`, `test_utils` passent |
| S2 | LZ77 seul | `lz77.py` | `python lz77.py` affiche les 8 triplets ; `test_lz77` passe |
| S3 | Format .mz + pipeline | `format_fichier.py`, `pipeline.py` | aller-retour exact sur texte et image ; `test_format`, `test_pipeline` passent |
| S4 | Interface, tests, rapport | `main.py`, `tests/`, rapport | session console complète, 52 tests verts, rapport rendu |
