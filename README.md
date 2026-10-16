# Codex Glass — Plasma 6

A native desktop/panel plasmoid for Codex account usage. It uses your existing CodexBar login; it does not read, store, or ask for credentials. No paid API is needed.

## Installation

### Requirements

- KDE Plasma 6 on Linux (tested with Plasma 6.7.5 on Fedora KDE Wayland).
- Python 3 and KDE's Plasma5Support executable data engine.
- A working [CodexBar Linux CLI](https://github.com/steipete/CodexBar/blob/main/docs/cli.md), authenticated with your existing Codex account.

On Fedora, install the widget dependencies if needed:

```sh
sudo dnf install git python3 plasma-workspace plasma5support
```

Download the appropriate Linux CLI tarball from [CodexBar releases](https://github.com/steipete/CodexBar/releases) and follow its [CLI installation guide](https://github.com/steipete/CodexBar/blob/main/docs/cli.md). Keep the extracted resource bundle beside the executable. Put `codexbar` in PATH or symlink it to `~/.local/bin/codexbar`. The widget does not install CodexBar or manage your login.

Verify your existing login works before installing:

```sh
codexbar --provider codex --format json
```

This diagnostic can contain your account email; do not share its raw output publicly.

### Install from source

```sh
git clone https://github.com/justinnguyen1073-creator/codex-glass.git
cd codex-glass
./install.sh
```

The installer registers only `org.local.codexglass` in your personal Plasma widget directory. It does not edit panels, change desktop configuration, modify other widgets, or restart Plasma.

### Add to your desktop or panel

 Right-click the desktop or enter panel edit mode, choose **Add Widgets**, search **Codex Glass**, and drag it into place. In a panel, click the compact usage indicator to open the full view.

Right-click → **Configure Codex Glass** to choose a refresh interval (default 60 seconds), automatic/dark/light appearance, glass or solid background, and used or remaining bar values. Both percentages remain explicitly labeled. The panel percentage follows this setting and represents the 5-hour window.

## Update, package, or remove

To update an existing source installation:

```sh
git pull --ff-only
./install.sh
```

Remove and re-add an existing widget instance if Plasma still displays its previous code; the installer does not restart your session.

To build an installable archive:

```sh
python3 build-package.py
```

In Plasma, use Add Widgets → Get New Widgets → Install Widget From Local File and select `dist/codex-glass.plasmoid`. The build uses only Python's standard library.

Remove instances using Plasma's normal edit mode. Uninstall the package with `kpackagetool6 --type Plasma/Applet --remove org.local.codexglass`. No Plasma restart or panel configuration edit is needed.

## Data and privacy

The small Python 3 helper calls the installed `codexbar --provider codex --format json`, with a 40-second timeout. It searches PATH and `~/.local/bin/codexbar`. The command and actual live JSON were verified with the locally installed CodexBar. It reads the provider array's `usage.primary`, `secondary`, and `tertiary`, selecting `windowMinutes: 300` and `10080`, with `usedPercent` and ISO `resetsAt`. It never assumes the primary window is always the 5-hour window. Missing or invalid limits are **Unavailable**.

Only sanitized limits and the source timestamp reach QML; account email, identity, credits, credentials, and raw diagnostic output are discarded. No usage data is written to disk. Failed refreshes preserve the last successful values in memory and mark them stale. Reset dates use the desktop's local timezone, including its timezone label.

## Troubleshooting

- **Missing CodexBar:** place the CLI in PATH or `~/.local/bin`.
- **Authentication expired:** sign in through your existing Codex/CodexBar workflow, then click refresh. The widget never requests passwords or tokens.
- **Offline / timeout / stale:** check connectivity and run `codexbar --provider codex --format json` yourself. This command may print account details, so do not post its raw output publicly.
- **Unavailable:** CodexBar did not report a valid matching window. This is distinct from 0% used.
- **No desktop frost:** the wallpaper shader requires Plasma's wallpaper containment. Panels and standalone viewers use the translucent fallback; panel popups also benefit from the Plasma theme/compositor background. Unsupported wallpaper renderers may also fall back. Solid mode improves contrast independently of the wallpaper.
- Requires Plasma 6, Python 3, CodexBar, and KDE's Plasma5Support executable data engine. The latter is shipped on this Fedora installation; this uses the KDE Plasma 6 compatibility API documented at https://develop.kde.org/docs/plasma/widget/porting_kf6/.

## Verification

Live CodexBar retrieval and sanitized helper output passed. Parser tests cover window selection, missing windows, invalid percentages, authentication/network errors, timeout, missing tools, and privacy. Run `python3 tests/test_usage.py` from this directory. QML components compile with the installed Qt 6 engine. A standalone rendering harness is used for layout/data connection validation; actual desktop wallpaper refraction must be checked after adding the widget to a containment.

## Attribution and license

GPL-3.0-or-later; see LICENSE. The unmodified `contents/ui/components/LiquidGlass.qml` and shader sources/binaries are from Jaxparrow07's locally installed **liquidglass-kde-widgets** project, https://github.com/jaxparrow07/liquidglass-kde-widgets. They are vendored copies for this separate package, with no changes to the original project or installed widgets. All corresponding shader sources are included.

This is an independent community widget, unaffiliated with OpenAI or KDE.
