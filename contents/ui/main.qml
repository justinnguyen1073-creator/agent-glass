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
    property var spending: ({})
    property bool busy: false
    property string error: ""
    property double now: Date.now()
    readonly property bool light: !Plasmoid.configuration.glass && (Plasmoid.configuration.appearance === 2 || (Plasmoid.configuration.appearance === 0 && Kirigami.Theme.backgroundColor.hslLightness > 0.5))
    readonly property color ink: light ? "#182431" : "#f0f5fa"
    readonly property color accent: Plasmoid.configuration.glass ? "#ffffff" : light ? "#097e6d" : "#79e6cf"
    function shellQuote(value) { return "'" + value.replace(/'/g, "'\\''") + "'" }
    readonly property string command: "/usr/bin/python3 " + shellQuote(decodeURIComponent(Qt.resolvedUrl("../code/usage.py").toString().replace("file://", ""))) + (Plasmoid.configuration.codexPath ? " --codex " + shellQuote(Plasmoid.configuration.codexPath) : "")
    function money(value) {
        return value === null || value === undefined ? "—" : "$" + Number(value).toLocaleString(Qt.locale(), "f", 2)
    }
    function compactCount(value) {
        const n = Number(value || 0)
        return n >= 1000000000 ? (n / 1000000000).toLocaleString(Qt.locale(), "f", 1) + "B" : n >= 1000000 ? (n / 1000000).toLocaleString(Qt.locale(), "f", 1) + "M" : count(n)
    }
    function count(value) {
        const locale = Qt.locale()
        return Number(value || 0).toLocaleString(locale.name === "C" ? Qt.locale("en_US") : locale, "f", 0)
    }
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
                if (result.spending) root.spending = result.spending
                if (result.ok) { root.usage = result; root.error = "" }
                else root.error = result.message || i18n("Refresh failed")
            } catch (e) { root.error = i18n("Could not start the usage helper") }
            root.now = Date.now()
        }
    }
    Timer { interval: Math.max(15, Plasmoid.configuration.refreshInterval) * 1000; repeat: true; running: true; onTriggered: root.refresh() }
    Timer { interval: 15000; repeat: true; running: true; onTriggered: root.now = Date.now() }
    Component.onCompleted: refresh()
    toolTipMainText: "Codex Glass"
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
        objectName: "usageFullView"
        implicitWidth: 360; implicitHeight: 320
        Layout.minimumWidth: 300; Layout.minimumHeight: 290
        readonly property real contentScale: Math.max(0.88, Math.min(1.45, Math.min(width / 360, height / 320)))
        readonly property real padding: 24 * contentScale
        readonly property bool exactTokens: width >= 440
        readonly property bool showDetails: (width >= 440 && height >= 480) || (width >= 700 && height >= 400)
        function tokenText(value) { return exactTokens ? root.count(value) : root.compactCount(value) }
        focus: true
        Accessible.role: Accessible.Button
        Accessible.name: card.flipped ? i18n("Spending. Activate to show usage.") : i18n("Usage. Activate to show spending.")
        Accessible.onPressAction: card.flipped = !card.flipped
        Keys.onSpacePressed: card.flipped = !card.flipped
        Keys.onReturnPressed: card.flipped = !card.flipped
        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: function(eventPoint) {
                // Leave the refresh/return button independent of the card tap.
                if (eventPoint.position.x > full.width - full.padding - 40 && eventPoint.position.y < full.padding + 44) return
                card.flipped = !card.flipped
                full.forceActiveFocus()
            }
        }
        Component {
            id: material
            Item {
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
            // The shader owns the solid/glass silhouette; only border the rectangle fallback.
            visible: Plasmoid.configuration.glass && !glassBackground.active
            radius: glassBackground.radius
            color: "transparent"
            border.color: root.light ? "#30000000" : "#38ffffff"
            border.width: 1
        }
            }
        }
        Flipable {
            id: card
            objectName: "usageCard"
            anchors.fill: parent
            property bool flipped: false
            transform: Rotation {
                origin.x: card.width / 2; origin.y: card.height / 2
                axis.x: 0; axis.y: 1; axis.z: 0
                angle: card.flipped ? 180 : 0
                Behavior on angle { NumberAnimation { duration: 420; easing.type: Easing.InOutCubic } }
            }
            front: Item {
                anchors.fill: parent
                Loader { anchors.fill: parent; sourceComponent: material }
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
                    objectName: "refreshButton"
                    icon.name: "view-refresh"; icon.color: root.ink
                    icon.width: 16 * full.contentScale; icon.height: 16 * full.contentScale
                    opacity: hovered ? 1 : 0.65
                    enabled: !root.busy
                    onClicked: { root.refresh(); full.forceActiveFocus() }
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
                Text { text: i18n("Tap for spending ↻"); color: root.ink; opacity: 0.55; font.pixelSize: 10 * full.contentScale }
            }
            Text { Layout.fillWidth: true; visible: root.error !== ""; text: root.error; color: root.ink; font.pixelSize: 11 * full.contentScale; wrapMode: Text.WordWrap }
        }
            }
            back: Item {
                id: spendingFace
                readonly property real textScale: Math.min(full.contentScale, 1.15)
                anchors.fill: parent
                Loader { anchors.fill: parent; sourceComponent: material }
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: full.padding
                    spacing: 6 * spendingFace.textScale
                    RowLayout {
                        Text { text: i18n("Spending"); color: root.ink; font.pixelSize: 20 * spendingFace.textScale; font.weight: Font.DemiBold }
                        Item { Layout.fillWidth: true }
                        Controls.ToolButton {
                            objectName: "returnButton"
                            icon.name: "go-previous"; icon.color: root.ink; opacity: hovered ? 1 : 0.65
                            onClicked: { card.flipped = false; full.forceActiveFocus() }
                            Accessible.name: i18n("Back to usage")
                            background: Rectangle { radius: width / 2; color: root.ink; opacity: parent.hovered ? 0.1 : 0 }
                        }
                    }
                    Text { text: i18n("List-price estimate · USD"); color: root.ink; opacity: 0.65; font.pixelSize: 11 * spendingFace.textScale
                        HoverHandler { id: basisHover }
                        Controls.ToolTip.visible: basisHover.hovered
                        Controls.ToolTip.text: root.spending.basis || "" }
                    Row {
                        id: spendingTotals
                        Layout.fillWidth: true
                        spacing: 16
                        Repeater {
                            model: [{label: i18n("Today"), value: root.spending.todayUsd}, {label: i18n("Last 30 days"), value: root.spending.monthUsd}]
                            delegate: Column {
                                required property var modelData
                                width: (spendingTotals.width - spendingTotals.spacing) / 2
                                spacing: 2
                                Text { text: modelData.label; color: root.ink; opacity: 0.65; font.pixelSize: 12 * spendingFace.textScale }
                                Text { text: root.money(modelData.value); color: root.ink; font.pixelSize: 26 * spendingFace.textScale; font.weight: Font.Light }
                            }
                        }
                    }
                    Text { objectName: "tokenSummary"; text: i18n("%1 tokens · local history", full.tokenText(root.spending.tokens)); color: root.ink; opacity: 0.65; font.pixelSize: 11 * spendingFace.textScale
                        HoverHandler { id: tokensHover }
                        Controls.ToolTip.visible: tokensHover.hovered
                        Controls.ToolTip.text: i18n("Input %1 · cached %2 · output %3", root.count(root.spending.input), root.count(root.spending.cached), root.count(root.spending.output))
                    }
                    GridLayout {
                        id: spendingGrid
                        objectName: "spendingDetails"
                        visible: full.showDetails
                        Layout.fillWidth: true
                        columns: full.width >= 700 ? 4 : 2
                        columnSpacing: 14 * spendingFace.textScale
                        rowSpacing: 10 * spendingFace.textScale
                        Repeater {
                            model: [{label: i18n("Input · includes cache"), value: root.spending.input},
                                    {label: i18n("Cached input"), value: root.spending.cached},
                                    {label: i18n("Output"), value: root.spending.output},
                                    {label: i18n("Unpriced tokens"), value: root.spending.unpricedTokens}]
                            delegate: Column {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: (spendingGrid.width - spendingGrid.columnSpacing * (spendingGrid.columns-1)) / spendingGrid.columns
                                spacing: 3
                                Text { text: modelData.label; color: root.ink; opacity: 0.55; font.pixelSize: 10 * spendingFace.textScale }
                                Text { text: root.count(modelData.value); color: root.ink; font.pixelSize: 13 * spendingFace.textScale; font.weight: Font.Medium }
                            }
                        }
                    }
                    RowLayout {
                        visible: full.showDetails
                        Layout.fillWidth: true
                        Text { text: i18n("Daily estimated cost · USD"); color: root.ink; opacity: 0.6; font.pixelSize: 10 * spendingFace.textScale }
                        Item { Layout.fillWidth: true }
                        Text { text: root.money(Math.max(0, ...chart.days.map(day => day.usd))); color: root.ink; opacity: 0.6; font.pixelSize: 10 * spendingFace.textScale }
                    }
                    Row {
                        id: chart
                        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 40 * spendingFace.textScale
                        spacing: 3
                        readonly property var days: root.spending.days || []
                        readonly property real maximum: Math.max(0.01, ...days.map(day => day.usd))
                        Repeater {
                            model: chart.days
                            delegate: Item {
                                required property var modelData
                                width: Math.max(1, (chart.width - (chart.days.length - 1) * chart.spacing) / Math.max(1, chart.days.length))
                                height: chart.height
                                Rectangle {
                                    anchors.bottom: parent.bottom; width: parent.width; radius: Math.min(2, width / 2)
                                    height: modelData.usd > 0 ? Math.max(2, parent.height * modelData.usd / chart.maximum) : 1
                                    color: root.accent; opacity: modelData.usd > 0 ? 0.85 : 0.15
                                }
                                HoverHandler { id: barHover }
                                Controls.ToolTip.visible: barHover.hovered
                                Controls.ToolTip.text: modelData.date + " · " + root.money(modelData.usd)
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: chart.days.length ? (full.showDetails ? chart.days[0].date : chart.days[0].date.slice(5)) : ""; color: root.ink; opacity: 0.5; font.pixelSize: 9 * spendingFace.textScale }
                        Item { Layout.fillWidth: true }
                        Text { text: chart.days.length ? (full.showDetails ? chart.days[chart.days.length-1].date : chart.days[chart.days.length-1].date.slice(5)) : ""; color: root.ink; opacity: 0.5; font.pixelSize: 9 * spendingFace.textScale }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: !root.spending.ok ? i18n("Local spending history unavailable") : !root.spending.tokens ? i18n("No recorded token history") : root.spending.incomplete ? i18n("Priced portion only · %1 unpriced tokens", full.tokenText(root.spending.unpricedTokens)) : i18n("API-equivalent estimate · not your bill")
                        color: root.ink; opacity: 0.65; font.pixelSize: 10 * spendingFace.textScale; wrapMode: Text.WordWrap
                    }
                    Text {
                        visible: full.showDetails && full.height >= 520
                        Layout.fillWidth: true
                        text: i18n("Hypothetical API token cost · pricing snapshot %1", root.spending.pricingDate || "—") + "\n" + (root.spending.basis || "")
                        color: root.ink; opacity: 0.5; font.pixelSize: 10 * spendingFace.textScale; wrapMode: Text.WordWrap
                    }
                    Text { objectName: "spendingHint"; text: i18n("Tap to return to usage ↻"); color: root.ink; opacity: 0.5; font.pixelSize: 10 * spendingFace.textScale }
                }
            }
        }
    }
}
