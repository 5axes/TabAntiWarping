# Copyright (c) 2020 5axes
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.

from . import TabAntiWraping

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("cura")

def getMetaData():
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Tab Anti Warping"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Add Tab Anti Warping"),
            "icon": "tool_icon.svg",
            "tool_panel": "CustomTap.qml",
            "weight": 10
        }
    }

def register(app):
    return { "tool": TabAntiWraping.TabAntiWraping() }
