import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
Kirigami.FormLayout {
    property alias cfg_glass: glass.checked
    property alias cfg_appearance: appearance.currentIndex
    property alias cfg_realtimeRefraction: realtime.checked
    property alias cfg_cornerRadius: cornerRadius.value
    property alias cfg_roundnessX10: roundnessX10.value
    property alias cfg_tintAlphaPct: tintAlphaPct.value
    property alias cfg_blurRadiusPx: blurRadiusPx.value
    property alias cfg_refractThickness: refractThickness.value
    property alias cfg_refractIORx100: refractIORx100.value
    property alias cfg_refractScale: refractScale.value
    property alias cfg_chromaStrengthPct: chromaStrengthPct.value
    property alias cfg_specStrengthPct: specStrengthPct.value
    Controls.CheckBox { id: glass; text: i18n("Liquid glass background") }
    Controls.ComboBox { id: appearance; Kirigami.FormData.label: i18n("Solid appearance:"); enabled: !glass.checked; model: [i18n("Follow system"), i18n("Dark"), i18n("Light")] }
    Controls.Label { text: i18n("Glass uses white lettering and the wallpaper behind it."); opacity: 0.7 }
    Controls.SpinBox { id: cornerRadius; Kirigami.FormData.label: i18n("Corner radius (px):"); from: 8; to: 100; editable: true }
    Controls.SpinBox { id: roundnessX10; Kirigami.FormData.label: i18n("Roundness (×10):"); from: 20; to: 100; editable: true }
    Controls.SpinBox { id: tintAlphaPct; Kirigami.FormData.label: i18n("Tint opacity (%):"); from: 0; to: 100; editable: true }
    Controls.SpinBox { id: blurRadiusPx; Kirigami.FormData.label: i18n("Blur radius (px):"); from: 0; to: 12; editable: true }
    Controls.SpinBox { id: refractThickness; Kirigami.FormData.label: i18n("Refraction thickness (px):"); from: 0; to: 80; editable: true }
    Controls.SpinBox { id: refractIORx100; Kirigami.FormData.label: i18n("Index of refraction (×100):"); from: 100; to: 250; editable: true }
    Controls.SpinBox { id: refractScale; Kirigami.FormData.label: i18n("Refraction strength:"); from: 0; to: 100; editable: true }
    Controls.SpinBox { id: chromaStrengthPct; Kirigami.FormData.label: i18n("Chromatic aberration (%):"); from: 0; to: 100; editable: true }
    Controls.SpinBox { id: specStrengthPct; Kirigami.FormData.label: i18n("Reflection strength (%):"); from: 0; to: 100; editable: true }
    Controls.CheckBox { id: realtime; text: i18n("Recapture every frame (animated wallpapers)") }
}
