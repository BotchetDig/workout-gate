# Workout Gate 🏋️

> Ton prompt est bloqué tant que tu n'as pas fait tes pompes devant la webcam.

Workout Gate prend tes prompts Claude Code en otage derrière un défi physique :
des pompes, comptées en direct à la webcam. Pas de pompes, pas de prompt. Tu
fermes la session pour esquiver ? La dette t'attend à la suivante.

*English version: [README.md](README.md)*

## Installation (30 secondes)

```bash
git clone <ce-repo> && cd pushup-gate
./install.sh
```

Ouvre une session Claude Code dans ce dossier — le gate est actif. Sur macOS,
accorde l'accès caméra à ton terminal au premier défi.

## Usage

| Dans Claude Code | Effet |
|---|---|
| `/workout` | état du gate (compteur, dette, réglages) |
| `/workout on` / `off` | activer / désactiver |
| `/workout now` | forcer un défi tout de suite (parfait pour filmer) |
| `/workout stats` | total, aujourd'hui, série, record, 7 derniers jours |
| `/workout preset chill\|demo\|hardcore` | voir presets ci-dessous |
| `/workout freq 15` | un défi tous les 15 prompts |
| `/workout reps 5 10` | fourchette de pompes tirée au hasard |
| `/workout time 30` | temporel : au plus un défi toutes les 30 min |
| `/workout chance 10` | roulette : 10 % de chance à chaque prompt |

`/workout` sans argument ouvre un menu interactif aux flèches directement dans
Claude Code. Mêmes commandes depuis n'importe quel terminal :
`.venv/bin/python -m workout_gate <cmd>`.

### Dashboard

```
workout            # après install globale — depuis n'importe quel terminal
./workout          # depuis ce dossier, sans install globale
```

Depuis Claude Code, tape `! workout` : le prompt `!` ne pouvant pas héberger
curses, le dashboard s'ouvre dans une nouvelle fenêtre Terminal (macOS). Un
seul geste, zéro token. `! workout now`, `! workout stats` etc. s'exécutent
directement.

Dashboard plein écran dans le terminal, instantané et zéro token : flèches
pour naviguer dans tous les réglages (gauche/droite pour changer les valeurs),
stats en direct avec sparkline des 7 derniers jours, et un raccourci « forcer
un défi ». `workout <cmd>` lance aussi n'importe quelle commande CLI
(`workout stats`, `workout off`, ...).

### Presets

- **chill** — tous les 25 prompts, 3–6 reps. Usage quotidien.
- **demo** — à chaque prompt, 5–8 reps. Mode tournage.
- **hardcore** — tous les 5 prompts, 15–25 reps. Tu l'as voulu.

## Comment ça marche

- Un hook `UserPromptSubmit` compte tes prompts. Quand un défi tombe, il tire
  un nombre de pompes, **persiste la dette sur disque d'abord**, ouvre la
  fenêtre webcam et gèle ton prompt jusqu'à validation. Puis le prompt part
  tout seul.
- Détection : MediaPipe Pose, **de profil, au sol**. Une rep = descente
  complète (coude < 95°) puis extension (coude > 150°), avec lissage. Un
  garde-fou ignore tout si le corps n'est pas à l'horizontale — pas de triche
  debout.
- Chaque rep est écrite sur disque à l'instant où elle est faite (écriture
  atomique) : tu coupes à 4/8, tu gardes 4 aux stats et il t'en reste 4 dues.
- Données dans `~/.workout-gate/` : `config.json`, `state.json`, `stats.json`,
  `gate.log`.

## Portes de sortie (anti-lockout, par design)

1. `/workout off` — les prompts `/workout` ne sont jamais bloqués.
2. `.venv/bin/python -m workout_gate off` depuis n'importe quel terminal.
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
sessions Claude Code (et avoir `/workout` partout) :

```bash
./install.sh --global        # ou : .venv/bin/python -m workout_gate global on
.venv/bin/python -m workout_gate global off   # pour retirer
```

Ça ajoute chirurgicalement une entrée de hook dans `~/.claude/settings.json`
(une sauvegarde de ton fichier d'origine est gardée à côté) et retire
exactement ça au `off`. Effectif dans les nouvelles sessions.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

## Roadmap (si ça prend)

Squats, abdos, jumping jacks — la structure est prête : un exercice = un
compteur dans `detector.py`, rien d'autre à toucher.
