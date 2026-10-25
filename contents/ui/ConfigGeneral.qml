import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
Kirigami.FormLayout {
    property alias cfg_codexPath: codexPath.text
    property alias cfg_refreshInterval: interval.value
    property alias cfg_remaining: remaining.checked
    property alias cfg_showCodex: showCodex.checked
    property alias cfg_showClaude: showClaude.checked
    // At least one agent stays selected.
    Controls.CheckBox { id: showCodex; Kirigami.FormData.label: i18n("Show usage for:"); text: i18n("Codex"); enabled: showClaude.checked }
    Controls.CheckBox { id: showClaude; text: i18n("Claude"); enabled: showCodex.checked }
    Controls.TextField { id: codexPath; Kirigami.FormData.label: i18n("Codex executable:"); placeholderText: i18n("Auto-detect existing installation"); Layout.preferredWidth: 300 }
    Controls.SpinBox { id: interval; Kirigami.FormData.label: i18n("Refresh (seconds):"); from: 15; to: 3600; editable: true }
    Controls.CheckBox { id: remaining; text: i18n("Bars show remaining allowance") }
}
