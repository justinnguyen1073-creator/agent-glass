import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami
import "components"

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    readonly property bool panel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal || Plasmoid.formFactor === PlasmaCore.Types.Vertical
    preferredRepresentation: panel ? compactRepresentation : fullRepresentation
    property var usage: ({})
    property bool busy: false
    property string error: ""
    property double now: Date.now()
    readonly property bool light: Plasmoid.configuration.appearance === 2 || (Plasmoid.configuration.appearance === 0 && Kirigami.Theme.backgroundColor.hslLightness > 0.5)
    readonly property color ink: light ? "#182431" : "#f0f5fa"
    readonly property color accent: light ? "#097e6d" : "#79e6cf"
    function shellQuote(value) { return "'" + value.replace(/'/g, "'\\''") + "'" }
    readonly property string command: "/usr/bin/python3 " + shellQuote(decodeURIComponent(Qt.resolvedUrl("../code/usage.py").toString().replace("file://", ""))) + (Plasmoid.configuration.codexPath ? " --codex " + shellQuote(Plasmoid.configuration.codexPath) : "")
    function refresh() {
        if (busy) return
        busy = true
        runner.connectSource(command)
    }
    function resetText(limit) {
        if (!limit || !limit.resetsAt) return i18n("Reset time unavailable")
        const date = new Date(limit.resetsAt)
        return isNaN(date.getTime()) ? i18n("Reset time unavailable") : i18n("Resets %1", date.toLocaleString(Qt.locale(), "ddd, MMM d · h:mm AP t"))
    }
    function ageText() {
        const stamp = new Date(usage.updatedAt).getTime()
        if (!isFinite(stamp)) return i18n("Not updated yet")
        const age = Math.max(0, Math.floor((now - stamp) / 60000))
        return age === 0 ? i18n("Updated just now") : i18n("Updated %1 min ago", age)
    }
    Plasma5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: function(sourceName, data) {
            disconnectSource(sourceName)
            root.busy = false
            try {
                const result = JSON.parse(data.stdout)
                if (result.ok) { root.usage = result; root.error = "" }
                else root.error = result.message || i18n("Refresh failed")
            } catch (e) { root.error = i18n("Could not start the usage helper") }
            root.now = Date.now()
        }
    }
    Timer { interval: Math.max(15, Plasmoid.configuration.refreshInterval) * 1000; repeat: true; running: true; onTriggered: root.refresh() }
    Timer { interval: 15000; repeat: true; running: true; onTriggered: root.now = Date.now() }
    Component.onCompleted: refresh()
    toolTipMainText: "Codex"
    toolTipSubText: error || ageText()
    compactRepresentation: Item {
        implicitWidth: 74; implicitHeight: 32
        Layout.minimumWidth: 40
        Controls.Label {
            anchors.centerIn: parent
            text: root.usage.fiveHour ? "›_ " + Math.round(Plasmoid.configuration.remaining ? root.usage.fiveHour.remaining : root.usage.fiveHour.used) + "%" : "›_ —"
            color: Kirigami.Theme.textColor
        }
        MouseArea { anchors.fill: parent; onClicked: root.expanded = !root.expanded }
        Accessible.name: i18n("Codex usage. %1", root.error || root.ageText())
    }
    fullRepresentation: Item {
        implicitWidth: 340; implicitHeight: 318
        Layout.minimumWidth: 300; Layout.minimumHeight: 310
        LiquidGlass {
            anchors.fill: parent
            radius: 24; roundness: 4; blurRadius: 8
            refractThickness: 18; refractScale: 32; chromaStrength: 0.12
            tint: root.light ? "#ecf5fc" : "#152a38"
            tintAlpha: root.light ? 0.66 : 0.72
            fallbackOpacity: 0.94
            solidMode: !Plasmoid.configuration.glass
            solidColor: root.light ? "#edf3f7" : "#18232f"
        }
        Rectangle {
            anchors.fill: parent; radius: 24; color: "transparent"
            border.color: root.light ? "#50ffffff" : "#35ffffff"
        }
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 22; spacing: 13
            RowLayout {
                spacing: 10
                Rectangle {
                    width: 32; height: 32; radius: 10; color: root.light ? "#152a38" : "#e5f5f1"
                    Text { anchors.centerIn: parent; text: "›_"; color: root.light ? "white" : "#152a38"; font.pixelSize: 19; font.bold: true }
                }
                ColumnLayout {
                    spacing: 0
                    Text { text: "Codex"; color: root.ink; font.pixelSize: 19; font.weight: Font.DemiBold }
                    Text { text: Plasmoid.configuration.remaining ? i18n("ALLOWANCE REMAINING") : i18n("USAGE CONSUMED"); color: root.ink; opacity: 0.6; font.pixelSize: 9; font.letterSpacing: 1 }
                }
                Item { Layout.fillWidth: true }
                Controls.ToolButton {
                    icon.name: "view-refresh"; icon.color: root.ink; enabled: !root.busy
                    onClicked: root.refresh()
                    Controls.ToolTip.visible: hovered
                    Controls.ToolTip.text: i18n("Refresh usage")
                    Accessible.name: i18n("Refresh usage")
                }
            }
            Repeater {
                model: [{label: i18n("5-hour limit"), limit: root.usage.fiveHour}, {label: i18n("Weekly limit"), limit: root.usage.weekly}]
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true; spacing: 6
                    RowLayout {
                        Text { text: modelData.label; color: root.ink; font.pixelSize: 13; font.weight: Font.Medium }
                        Item { Layout.fillWidth: true }
                        Text { text: modelData.limit ? Math.round(Plasmoid.configuration.remaining ? modelData.limit.remaining : modelData.limit.used) + "%" : i18n("Unavailable"); color: root.ink; font.pixelSize: 13; font.bold: true }
                    }
                    Rectangle {
                        Layout.fillWidth: true; height: 7; radius: 4
                        color: root.light ? "#18182431" : "#20ffffff"
                        Rectangle {
                            height: parent.height; radius: 4
                            width: parent.width * (modelData.limit ? (Plasmoid.configuration.remaining ? modelData.limit.remaining : modelData.limit.used) / 100 : 0)
                            color: root.accent
                            Behavior on width { NumberAnimation { duration: 300 } }
                        }
                    }
                    Text { text: modelData.limit ? i18n("%1% used · %2% remaining", modelData.limit.used, modelData.limit.remaining) : i18n("Not reported by your account"); color: root.ink; opacity: 0.75; font.pixelSize: 11 }
                    Text { text: root.resetText(modelData.limit); color: root.ink; opacity: 0.6; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                }
            }
            Item { Layout.fillHeight: true }
            Text {
                Layout.fillWidth: true
                text: root.busy ? i18n("Refreshing…") : root.error ? i18n("Stale · %1", root.ageText()) : root.ageText()
                color: root.ink; opacity: 0.6; font.pixelSize: 10
            }
            Text { Layout.fillWidth: true; visible: root.error !== ""; text: root.error; color: root.ink; font.pixelSize: 10; wrapMode: Text.WordWrap }
        }
    }
}
