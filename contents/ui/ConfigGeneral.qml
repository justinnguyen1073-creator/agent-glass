import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
Kirigami.FormLayout {
    property alias cfg_refreshInterval: interval.value
    property alias cfg_appearance: appearance.currentIndex
    property alias cfg_remaining: remaining.checked
    property alias cfg_glass: glass.checked
    Controls.SpinBox { id: interval; Kirigami.FormData.label: i18n("Refresh (seconds):"); from: 15; to: 3600; editable: true }
    Controls.ComboBox { id: appearance; Kirigami.FormData.label: i18n("Appearance:"); model: [i18n("Follow system"), i18n("Dark"), i18n("Light")] }
    Controls.CheckBox { id: glass; text: i18n("Liquid glass background") }
    Controls.CheckBox { id: remaining; text: i18n("Bars show remaining allowance") }
}
