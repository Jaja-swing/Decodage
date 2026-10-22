# Feuille de route MiniZip : 4 semaines

Chaque semaine produit un module **qui fonctionne seul** et qui est validé par ses tests. On ne passe à la semaine
suivante que lorsque les critères de validation sont remplis.

| Semaine | Thème | Modules | Validation |
|---|---|---|---|
| S1 | Codage arithmétique seul | `utils.py`, `arithmetique.py` | CALCU → [0.144 ; 0.145), décodage de 0.144 |
| S2 | LZ77 seul | `lz77.py` | CABRACADABRARRARRAD → 8 triplets, décodage |
| S3 | Format .mz + pipeline complet | `format_fichier.py`, `pipeline.py` | decompresser(compresser(f)) == f |
| S4 | Interface + tests + rapport | `main.py`, `tests/`, rapport | session console, 52 tests verts, rapport |

---

## Semaine 1 : codage arithmétique seul

**Objectif** : coder et décoder un message court avec des fractions exactes, en suivant les formules du document.

**Notions à maîtriser**
- probabilité P(sᵢ) et probabilité cumulée C(sᵢ) ; intervalle [C(sᵢ₋₁), C(sᵢ)) de chaque symbole ;
- codage : Lⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ₋₁) et Rⱼ = Lⱼ₋₁ + (Rⱼ₋₁ − Lⱼ₋₁)·C(sᵢ) ;
- décodage : trouver sᵢ tel que C(sᵢ₋₁) ≤ Dⱼ₋₁ < C(sᵢ), puis Dⱼ = (Dⱼ₋₁ − C(sᵢ₋₁)) / P(sᵢ) ;
- pourquoi `float` ne convient pas (0.1 + 0.2 ≠ 0.3) et pourquoi `fractions.Fraction` est exact.

**Tâches**
- [ ] Jour 1 : refaire CALCU **à la main** sur papier (table, 5 intervalles, décodage).
- [ ] Jour 2 : classe `Modele` (P, C_bas, C_haut, `intervalle`, `symbole_pour`).
- [ ] Jour 3 : `coder()` et `decoder()`, avec l'option `trace` pour afficher chaque étape.
- [ ] Jour 4 : `utils.py` : `nombre_le_plus_court` (base 10 → « 0.144 », base 2 → `00100101`), bits ↔ octets.
- [ ] Jour 5 : `demo()` qui affiche les tableaux de codage et de décodage ; tests `test_arithmetique.py` et `test_utils.py`.

**Livrable** : `python arithmetique.py` affiche l'exemple CALCU complet.

**Validation**
```bash
python arithmetique.py
python -m unittest tests.test_arithmetique tests.test_utils -v
```

**Pièges fréquents**
- Calculer Rⱼ avec le **nouveau** Lⱼ au lieu de Lⱼ₋₁ : utilisez une affectation simultanée `L, R = …, …`.
- Oublier que l'intervalle est **fermé à gauche, ouvert à droite** : D = 0.6 appartient à U, pas à C.
- Le décodeur doit connaître le **nombre de symboles** à décoder (il est stocké dans l'en-tête en S3).

---

## Semaine 2 : LZ77 seul

**Objectif** : découper une chaîne en triplets (décalage, longueur, caractère suivant) et la reconstruire.

**Notions à maîtriser**
- tampon de recherche (déjà codé) et tampon de lecture (à coder), fenêtre glissante ;
- recherche de la plus longue correspondance ; égalité → occurrence la plus proche ;
- le **chevauchement** : une copie peut être plus longue que son décalage, comme `(3, 5, D)` ou `(1, 8, A)` ;
- pourquoi on garde toujours un « caractère suivant », y compris à la fin du fichier.

**Tâches**
- [ ] Jour 1 : refaire CABRACADABRARRARRAD **à la main** (fenêtre 7, lecture 6) et retrouver les 8 triplets.
- [ ] Jour 2 : `compresser_lz77()` : boucle principale, recherche avec `rfind`, limites des tampons.
- [ ] Jour 3 : `decompresser_lz77()` : copie symbole par symbole (gère le chevauchement), contrôle des triplets invalides.
- [ ] Jour 4 : faire marcher les mêmes fonctions sur des `bytes` (fichiers binaires) et des `str` (exemple du cours).
- [ ] Jour 5 : `demo()` (tableau des tampons) et `test_lz77.py` (exemple, cas limites, allers-retours aléatoires).

**Livrable** : `python lz77.py` affiche les 8 triplets et le décodage.

**Validation**
```bash
python lz77.py
python -m unittest tests.test_lz77 -v
```

**Pièges fréquents**
- Interdire le chevauchement : on rate alors `(3, 5, D)` et on obtient un triplet de plus.
- Une correspondance qui va jusqu'au dernier symbole ne laisse pas de « caractère suivant ». Il faut la raccourcir d'un symbole.
- Avec une grande fenêtre (4 Ko), une recherche naïve en Python pur est lente. `rfind`, écrit en C, résout le problème.

---

## Semaine 3 : format .mz et pipeline complet

**Objectif** : enchaîner LZ77 → codage arithmétique, écrire un vrai fichier `.mz` et retrouver l'original à l'octet près.

**Notions à maîtriser**
- format binaire : Magic number, version, champs de taille fixe (`struct`, big-endian), varints ;
- table de fréquences : ce que le décodeur doit connaître pour reconstruire **exactement** le même modèle ;
- séparation des triplets en 4 flux, chacun avec son modèle ;
- découpage en blocs de 256 symboles (les fractions restent de taille raisonnable) ;
- intégrité : taille + CRC-32 ; méthode « stocké » quand on ne gagne rien.

**Tâches**
- [ ] Jour 1 : dessiner le format `.mz` sur papier (voir README § 6), puis `ecrire_entete` / `lire_entete` et l'exception `FormatInvalide`.
- [ ] Jour 2 : tables de fréquences et flux (`ecrire_flux` / `lire_flux`), avec les varints.
- [ ] Jour 3 : `compresser_symboles` / `decompresser_symboles` (blocs) dans `arithmetique.py`.
- [ ] Jour 4 : `pipeline.py` : `compresser_octets` (LZ77 → 4 flux → arithmétique → méthode stockée si aucun gain) et `decompresser_octets` (+ CRC-32).
- [ ] Jour 5 : `compresser_fichier` / `decompresser_fichier`, tests `test_format.py` et `test_pipeline.py` (fichier vide, aléatoire, texte, image, corruption).

**Livrable** : un `.mz` créé à partir de `texte.txt` et de `image.bmp`, puis restauré à l'identique.

**Validation**
```bash
python exemples/generer_images.py
python -m unittest tests.test_format tests.test_pipeline -v
```

**Pièges fréquents**
- Construire le modèle dans un ordre différent au codage et au décodage : les tables doivent être **triées** des deux côtés.
- Oublier le cas du fichier vide (0 triplet) et celui d'un flux qui ne contient qu'un seul symbole (0 bit par bloc).
- Faire confiance au nom stocké dans l'archive : n'en garder que le nom de fichier, sans le chemin (`../`).

---

## Semaine 4 : interface, tests et rapport

**Objectif** : rendre le logiciel utilisable, mesurer ses performances et les expliquer.

**Tâches**
- [ ] Jour 1 : `main.py` : menu (compresser, décompresser, infos, deux démonstrations) et ligne de commande (`argparse`).
- [ ] Jour 2 : rapport de compression (entropie et limite de Shannon par flux, tables, taux), messages d'erreur clairs.
- [ ] Jour 3 : compléter les tests, lancer toute la suite, enregistrer une session console (texte + image).
- [ ] Jour 4 : mesures : taux sur texte, BMP et PNG, comparaison avec ZIP et 7-Zip, temps de calcul.
- [ ] Jour 5 : rédiger le rapport et préparer la soutenance (démonstration en direct de CALCU et de CABRACADABRA).

**Livrables** : logiciel complet, README, 52 tests verts, rapport.

**Validation**
```bash
python -m unittest discover -s tests -v
python main.py
```

### Plan de rapport proposé (10 à 15 pages)

1. **Introduction** : compression sans perte, WinRAR et 7-Zip, objectifs de MiniZip.
2. **Rappels théoriques** : entropie de Shannon, LZ77, codage arithmétique (avec les formules du cours).
3. **Exemples du cours** : CALCU (tableaux de codage et de décodage) et CABRACADABRARRARRAD (tableau des tampons).
4. **Conception** : architecture, rôle des modules, format `.mz` (schéma des octets), choix des 4 flux et des blocs.
5. **Réalisation** : extraits de code commentés, lien entre chaque formule et sa ligne de code.
6. **Tests** : stratégie (exemples du cours, allers-retours, cas limites, corruption), résultats.
7. **Résultats** : tableau des taux (README § 10), analyse : pourquoi le BMP se compresse bien, le texte moyennement, le PNG pas du tout.
8. **Limites et perspectives** : vitesse des fractions, renormalisation, LZSS, modèle adaptatif.
9. **Conclusion**.
