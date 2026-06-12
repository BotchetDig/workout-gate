# Workout Gate 🏋️

> Ton prompt est bloqué tant que tu n'as pas fait ton exercice devant la webcam.

Workout Gate prend tes prompts Claude Code en otage derrière un défi physique :
pompes ou squats, comptés en direct à la webcam. Quand un défi tombe, tu
choisis ta douleur (genre 6 pompes *ou* 9 squats). Pas d'effort, pas de prompt.
Tu fermes la session pour esquiver ? La dette t'attend à la suivante.

*English version: [README.md](README.md)*

## Installation

### En plugin Claude Code (recommandé)

```
/plugin marketplace add BotchetDig/workout-gate
/plugin install workout-gate@workout-gate
```

Puis **démarre une nouvelle session** (ou lance `/reload-plugins`) — rien ne
se passe avant ça. L'onboarding s'ouvre tout seul dans une fenêtre
Terminal — installation des dépendances, puis l'assistant de 30 secondes (ton
max, choix du déclencheur, test caméra de 2 pompes). Tant que le setup n'est
pas fait, les prompts passent librement. Le gate et `/workout-gate:workout`
marchent ensuite dans toutes tes sessions, et les mises à jour du plugin ne
cassent jamais l'installation (le runtime vit dans `~/.workout-gate/`).

### Une ligne, sans le plugin

```bash
curl -fsSL https://raw.githubusercontent.com/BotchetDig/workout-gate/main/get.sh | bash
```

Relancer la même ligne met à jour. Tu préfères inspecter d'abord ?

```bash
git clone https://github.com/BotchetDig/workout-gate.git && cd workout-gate
./install.sh
```

L'installeur prépare tout (venv, dépendances, modèle de pose) puis te guide
dans un assistant de 30 secondes : il demande ton max en une série pour
calibrer les défis sur toi (25–50 % du max), te fait choisir le déclencheur,
propose l'installation globale, et lance un test caméra de 2 pompes pour que
le dialogue de permission macOS arrive maintenant — pas au milieu de ton
premier prompt bloqué.

Relance l'assistant quand tu veux avec `workout setup`. `./install.sh
--no-setup` pour une installation non interactive avec les défauts (tous les
15 prompts, 5–10 reps).

## Usage

Pilote-le avec `! workout` depuis Claude Code (le préfixe `!` lance une
commande shell — instantané, **zéro token**), ou juste `workout` depuis
n'importe quel terminal.

| Commande | Effet |
|---|---|
| `! workout` | ouvre le dashboard (flèches, stats live) dans une fenêtre Terminal |
| `! workout now` | forcer un défi tout de suite (parfait pour filmer) |
| `! workout stats` | total, aujourd'hui, série, record, 7 derniers jours |
| `! workout status` | état du gate (compteur, dette, réglages) |
| `! workout on` / `off` | activer / désactiver |
| `! workout stop` | fermer un défi en cours |
| `! workout preset chill\|demo\|hardcore` | voir presets ci-dessous |
| `! workout enable\|disable squats` | activer/désactiver un exercice |
| `! workout set reps squats 8 15` | fourchette d'un exercice |
| `! workout set mode choice\|random` | choisir l'exo soi-même, ou au hasard |
| `! workout set freq 15` | un défi tous les 15 prompts |
| `! workout set time 30` | temporel : au plus un défi toutes les 30 min |
| `! workout set chance 10` | roulette : 10 % de chance à chaque prompt |

> Une slash command `/workout-gate:workout` existe aussi, mais elle passe par
> Claude et consomme des tokens — préfère `! workout` pour tout ce qui précède.

### Dashboard

`! workout` (ou `workout` dans un terminal) ouvre un dashboard plein écran :
flèches pour naviguer dans tous les réglages, gauche/droite pour changer les
valeurs, stats en direct avec sparkline des 7 derniers jours, et un raccourci
« forcer un défi ». Le prompt `!` ne pouvant pas héberger curses, il s'ouvre
dans une nouvelle fenêtre Terminal (macOS) qui se ferme toute seule à la
sortie.

### Presets

- **chill** — tous les 25 prompts, 3–6 reps. Usage quotidien.
- **demo** — à chaque prompt, 5–8 reps. Mode tournage.
- **hardcore** — tous les 5 prompts, 15–25 reps. Tu l'as voulu.

## Comment ça marche

- Un hook `UserPromptSubmit` compte tes prompts. Quand un défi tombe, il tire
  un nombre de pompes, **persiste la dette sur disque d'abord**, ouvre la
  fenêtre webcam et gèle ton prompt jusqu'à validation. Puis le prompt part
  tout seul.
- Détection : MediaPipe Pose. Pompes via l'angle du coude (**de profil, au
  sol**, corps horizontal) ; squats via l'angle du genou (**debout, plein
  cadre, de côté**, corps vertical). Une rep = descente complète puis
  extension, avec lissage et garde-fou anti-triche.
- Quand plusieurs exercices sont actifs, le défi propose un choix (« choisis
  ta douleur ») — ou tire au hasard en `mode random`.
- Chaque rep est écrite sur disque à l'instant où elle est faite (écriture
  atomique) : tu coupes à 4/8, tu gardes 4 aux stats et il t'en reste 4 dues.
- Données dans `~/.workout-gate/` : `config.json`, `state.json`, `stats.json`,
  `gate.log`.

## Portes de sortie (anti-lockout, par design)

1. `! workout off` depuis Claude Code — les prompts commençant par `!` ou
   `/workout` ne sont jamais bloqués, tu peux donc toujours y accéder.
2. `workout off` depuis n'importe quel terminal.
3. `WORKOUT_GATE_OFF=1` dans l'environnement court-circuite tout.
4. **Fail-open** : pas de webcam, dépendance cassée, crash → le prompt passe et
   l'erreur va dans `~/.workout-gate/gate.log`. Jamais enfermé hors de ton
   propre outil.

## Modes

`config.json → "mode"` :
- `"sync"` (défaut) : le hook attend la fin du défi, puis le prompt part tout
  seul. Le plus satisfaisant en vidéo. Timeout 5 min.
- `"detached"` : la fenêtre s'ouvre en arrière-plan, le prompt est bloqué avec
  un message ; fais tes pompes puis renvoie-le (↑ + Entrée).

## Installation globale

Par défaut le gate ne s'applique que dans ce dossier. Pour gater **toutes** tes
sessions Claude Code (l'install plugin le fait pour toi) :

```bash
./install.sh --global        # ou : workout global on
workout global off           # pour retirer
```

Ça ajoute chirurgicalement une entrée de hook dans `~/.claude/settings.json`
(une sauvegarde de ton fichier d'origine est gardée à côté) et retire
exactement ça au `off`. Effectif dans les nouvelles sessions.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

## Roadmap (si ça prend)

Abdos, jumping jacks — la structure est prête : un exercice = une entrée dans
`detector.EXERCISES` (un compteur + un message à l'écran), rien d'autre à
toucher.
