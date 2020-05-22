# Copyright (c) 2019 5axes
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.

from . import TabAntiWarping

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("cura")

def getMetaData():
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Tab Anti Warping"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Tab Anti Warping"),
            "icon": "tool_icon.svg",
            "tool_panel": "CustomTab.qml",
            "weight": 9
        }
    }

def register(app):
    return { "tool": TabAntiWarping.TabAntiWarping() }
