# Codex Glass — Plasma 6

A native KDE Plasma widget for your Codex account's 5-hour and weekly usage, with Liquid Glass styling and desktop/panel support.

**No CodexBar required.** The widget uses your existing Codex installation and ChatGPT sign-in. It does not ask for credentials or require a paid API key.

## Installation

### Requirements

- KDE Plasma 6 on Linux (tested with Plasma 6.7.5 on Fedora KDE Wayland).
- Python 3 and KDE's Plasma5Support executable data engine.
- An existing Codex installation that supports `codex app-server`, signed in with your ChatGPT account. API-key-only authentication does not provide these subscription usage limits.

On Fedora, install the desktop dependencies if needed:

```sh
sudo dnf install git python3 plasma-workspace plasma5support
```

If you already use Codex, keep your existing installation and sign-in. No separate usage tracker or additional login is needed. If Codex itself is missing, follow [OpenAI's Codex CLI instructions](https://developers.openai.com/codex/cli).

### Install the widget

```sh
git clone https://github.com/justinnguyen1073-creator/codex-glass.git
cd codex-glass
./install.sh
```

The installer registers only `org.local.codexglass` in your personal Plasma widget directory. It does not edit panels, change desktop configuration, modify other widgets, or restart Plasma.

Right-click the desktop or enter panel edit mode, choose **Add Widgets**, search **Codex Glass**, and drag it into place. In a panel, click the compact indicator to open the full view.

### Configure

Right-click → **Configure Codex Glass** to choose:

- Refresh interval: default 60 seconds, configurable from 15 to 3600 seconds.
- Appearance: glass or solid background. Glass matches the Liquid Glass widgets with white lettering, wallpaper-driven color, and a default 10% tint. Solid mode supports follow-system, dark, or light appearance.
- Glass controls: corner radius, roundness, tint opacity, blur, refraction thickness/index/strength, chromatic aberration, reflections, and optional animated-wallpaper capture.
- Bar values: usage consumed or allowance remaining. Both percentages remain explicitly labeled in the full view; the panel percentage follows this setting and represents the 5-hour window.
- Codex executable: leave blank for auto-detection, or provide the absolute path to your existing Codex CLI/app-server executable.

Auto-detection checks PATH, common user installation locations, and nvm installations. For npm/nvm installs it uses the matching Node executable when available, so Plasma does not need to load your shell configuration. A Codex desktop installation with a bundled CLI can use that executable through the path setting; the graphical desktop launcher itself is not an app-server executable.

## Update, package, or remove

To update an existing source installation:

```sh
git pull --ff-only
./install.sh
```

Remove and re-add an existing widget instance if Plasma still displays its previous code; the installer does not restart your session.

To build an installable archive using Python's standard library:

```sh
python3 build-package.py
```

In Plasma, use Add Widgets → Get New Widgets → Install Widget From Local File and select `dist/codex-glass.plasmoid`.

Remove instances using Plasma's edit mode. To uninstall the package:

```sh
kpackagetool6 --type Plasma/Applet --remove org.local.codexglass
```

## Data and privacy

The small Python helper opens a private stdio connection to `codex app-server --listen stdio://`. After the initialization handshake, it calls only `account/rateLimits/read`, then terminates its own server process group. It never starts a conversation, sends a model prompt, or redeems reset credits. The entire request has a 40-second deadline.

This uses the [documented Codex app-server interface](https://developers.openai.com/codex/app-server). The verified response contains `rateLimitsByLimitId.codex` (preferred) or the legacy `rateLimits`. The helper selects `primary`/`secondary` windows by `windowDurationMins: 300` and `10080`, reads `usedPercent`, and converts Unix `resetsAt` timestamps to ISO dates. It never assumes primary always means five hours or substitutes another model's limit bucket. A missing or invalid matching window is **Unavailable**, distinct from 0% used.

Codex manages its existing authentication; the helper never reads token files or asks for passwords. Only sanitized usage values and a successful retrieval timestamp reach QML. Account IDs, identity, credits, credentials, and raw diagnostics are discarded. The widget does not persist usage data; Codex retains control of its own normal caches/logs. Failed refreshes preserve the last successful values in memory and mark them stale. Reset dates use the desktop's local timezone, including its timezone label.

## Troubleshooting

- **Codex not found:** select the absolute path to your existing Codex executable in widget settings. A terminal can locate it with `command -v codex`.
- **Sign-in error:** sign in to Codex using your ChatGPT account through your normal Codex workflow, then refresh. API-key-only login cannot provide these account limits.
- **Unsupported usage method:** update your Codex installation to a version supporting `account/rateLimits/read`.
- **Offline / timeout / stale:** check connectivity and retry. For sanitized diagnostics, run `python3 contents/code/usage.py` from this repository; optionally add `--codex /absolute/path/to/codex`.
- **Unavailable:** the account did not report a valid window matching that duration. The widget does not fabricate missing values.
- **No desktop frost:** wallpaper refraction requires Plasma's wallpaper containment. Panels and standalone viewers use a translucent fallback. Unsupported wallpaper renderers may also fall back. Solid mode improves contrast independently of the wallpaper.

The widget uses KDE's [Plasma 6 compatibility DataSource API](https://develop.kde.org/docs/plasma/widget/porting_kf6/) to invoke its fixed local helper.

## Verification

Run the account-independent tests:

```sh
python3 tests/test_usage.py
```

Tests cover parsing, bucket selection, missing windows, invalid percentages/reset dates, authentication/network errors, executable discovery, privacy, and the real stdio transport with a simulated server (handshake, notifications, fragmented messages, unexpected requests, EOF, and timeout cleanup).

Live direct Codex retrieval has been verified with Codex CLI 0.163.0. QML compilation and standalone rendering/data connection checks cover the widget views; actual desktop wallpaper refraction must be checked after adding the widget to a containment.

## Attribution and license

GPL-3.0-or-later; see [LICENSE](LICENSE). The unmodified `contents/ui/components/LiquidGlass.qml` and shader sources/binaries are from Jaxparrow07's [liquidglass-kde-widgets](https://github.com/jaxparrow07/liquidglass-kde-widgets) project. They are vendored copies for this separate package, with no changes to the original project or installed widgets. All corresponding shader sources are included.

This is an independent community widget, unaffiliated with OpenAI or KDE.
