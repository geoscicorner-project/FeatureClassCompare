# -*- coding: utf-8 -*-

def classFactory(iface):
    from .featureclass_compare import FeatureClassComparePlugin
    return FeatureClassComparePlugin(iface)
