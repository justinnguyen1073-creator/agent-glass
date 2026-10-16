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
    readonly property bool light: !Plasmoid.configuration.glass && (Plasmoid.configuration.appearance === 2 || (Plasmoid.configuration.appearance === 0 && Kirigami.Theme.backgroundColor.hslLightness > 0.5))
    readonly property color ink: light ? "#182431" : "#f0f5fa"
    readonly property color accent: Plasmoid.configuration.glass ? "#ffffff" : light ? "#097e6d" : "#79e6cf"
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
        return isNaN(date.getTime()) ? i18n("Reset time unavailable") : i18n("Resets %1", date.toLocaleString(Qt.locale(), date.toDateString() === new Date(root.now).toDateString() ? "h:mm AP t" : "ddd · h:mm AP t"))
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
        id: full
        implicitWidth: 360; implicitHeight: 320
        Layout.minimumWidth: 300; Layout.minimumHeight: 290
        readonly property real contentScale: Math.max(0.88, Math.min(1.45, Math.min(width / 360, height / 320)))
        readonly property real padding: 24 * contentScale
        LiquidGlass {
            id: glassBackground
            anchors.fill: parent
            radius: Math.min(Plasmoid.configuration.cornerRadius, Math.min(width, height) / 3)
            roundness: Plasmoid.configuration.roundnessX10 / 10
            blurRadius: Plasmoid.configuration.blurRadiusPx
            refractThickness: Plasmoid.configuration.refractThickness
            refractIOR: Plasmoid.configuration.refractIORx100 / 100
            refractScale: Plasmoid.configuration.refractScale
            chromaStrength: Plasmoid.configuration.chromaStrengthPct / 100
            specStrength: Plasmoid.configuration.specStrengthPct / 100
            realtimeRefraction: Plasmoid.configuration.realtimeRefraction
            tint: "#000000"
            tintAlpha: Plasmoid.configuration.tintAlphaPct / 100
            fallbackOpacity: 0.40
            solidMode: !Plasmoid.configuration.glass
            solidColor: root.light ? "#edf3f7" : "#18232f"
        }
        Rectangle {
            anchors.fill: parent
            visible: !glassBackground.active || !Plasmoid.configuration.glass
            radius: glassBackground.radius
            color: "transparent"
            border.color: root.light ? "#30000000" : "#38ffffff"
            border.width: 1
        }
        ColumnLayout {
            anchors.fill: parent; anchors.margins: full.padding
            spacing: 14 * full.contentScale
            RowLayout {
                spacing: 10 * full.contentScale
                Text {
                    text: "›_"; color: root.ink
                    font.pixelSize: 27 * full.contentScale; font.weight: Font.Medium
                    Accessible.ignored: true
                }
                Text { text: "Codex"; color: root.ink; font.pixelSize: 20 * full.contentScale; font.weight: Font.DemiBold }
                Item { Layout.fillWidth: true }
                Controls.ToolButton {
                    icon.name: "view-refresh"; icon.color: root.ink
                    icon.width: 16 * full.contentScale; icon.height: 16 * full.contentScale
                    opacity: hovered ? 1 : 0.65
                    enabled: !root.busy
                    onClicked: root.refresh()
                    Controls.ToolTip.visible: hovered
                    Controls.ToolTip.text: i18n("Refresh usage")
                    Accessible.name: i18n("Refresh usage")
                    background: Rectangle { radius: width / 2; color: root.ink; opacity: parent.hovered ? 0.10 : 0 }
                }
            }
            Repeater {
                model: [{label: i18n("5-hour usage"), limit: root.usage.fiveHour}, {label: i18n("Weekly usage"), limit: root.usage.weekly}]
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 6 * full.contentScale
                    RowLayout {
                        spacing: 8
                        ColumnLayout {
                            spacing: 3 * full.contentScale
                            Text { text: modelData.label; color: root.ink; font.pixelSize: 15 * full.contentScale; font.weight: Font.Medium }
                            Text {
                                text: modelData.limit ? root.resetText(modelData.limit) : i18n("Not reported by your account")
                                color: root.ink; opacity: 0.65; font.pixelSize: 11 * full.contentScale
                                Layout.maximumWidth: full.width - 2 * full.padding - valueLabel.implicitWidth - 8
                                elide: Text.ElideRight
                            }
                        }
                        Item { Layout.fillWidth: true }
                        ColumnLayout {
                            spacing: 0
                            Text {
                                id: valueLabel
                                Layout.alignment: Qt.AlignRight
                                text: modelData.limit ? Math.round(Plasmoid.configuration.remaining ? modelData.limit.remaining : modelData.limit.used) + "%" : "—"
                                color: root.ink; font.pixelSize: 30 * full.contentScale; font.weight: Font.Light
                            }
                            Text {
                                Layout.alignment: Qt.AlignRight
                                text: !modelData.limit ? i18n("Unavailable") : Plasmoid.configuration.remaining ? i18n("remaining") : i18n("used")
                                color: root.ink; opacity: 0.65; font.pixelSize: 10 * full.contentScale
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true; height: 5 * full.contentScale; radius: height / 2
                        color: root.light ? "#18182431" : "#28ffffff"
                        Rectangle {
                            height: parent.height; radius: height / 2
                            width: parent.width * (modelData.limit ? (Plasmoid.configuration.remaining ? modelData.limit.remaining : modelData.limit.used) / 100 : 0)
                            color: root.accent
                            Behavior on width { NumberAnimation { duration: 300 } }
                        }
                    }
                    Text {
                        text: modelData.limit ? i18n("%1% used · %2% remaining", modelData.limit.used, modelData.limit.remaining) : root.resetText(modelData.limit)
                        color: root.ink; opacity: 0.65; font.pixelSize: 11 * full.contentScale
                    }
                }
            }
            RowLayout {
                spacing: 6
                Rectangle { width: 4; height: 4; radius: 2; color: root.ink; opacity: root.error ? 0.4 : 0.8 }
                Text {
                    Layout.fillWidth: true
                    text: root.busy ? i18n("Refreshing…") : root.error ? i18n("Stale · %1", root.ageText()) : root.ageText()
                    color: root.ink; opacity: 0.55; font.pixelSize: 10 * full.contentScale
                    elide: Text.ElideRight
                }
            }
            Text { Layout.fillWidth: true; visible: root.error !== ""; text: root.error; color: root.ink; font.pixelSize: 11 * full.contentScale; wrapMode: Text.WordWrap }
        }
    }
}
