#!/bin/sh
set -eu
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
package_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["KPlugin"]["Id"])' "$package_dir/metadata.json")
python3 "$package_dir/build-package.py"
archive="$package_dir/dist/codex-glass.plasmoid"
if [ -d "${XDG_DATA_HOME:-$HOME/.local/share}/plasma/plasmoids/$package_id" ]; then
    kpackagetool6 --type Plasma/Applet --upgrade "$archive"
else
    kpackagetool6 --type Plasma/Applet --install "$archive"
fi
