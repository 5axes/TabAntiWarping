# Copyright (c) 2019 5axes
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.

from . import PastilleAntiWrapping

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("cura")

def getMetaData():
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Pastille Anti Wrapping"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Pastille Anti Wrapping"),
            "icon": "tool_icon.svg",
            "tool_panel": "CustomPastille.qml",
            "weight": 9
        }
    }

def register(app):
    return { "tool": PastilleAntiWrapping.PastilleAntiWrapping() }
