#--------------------------------------------------------------------------------------------
# Initial Copyright(c) 2018 Ultimaker B.V.
# Copyright (c) 2022 5axes
#--------------------------------------------------------------------------------------------
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.
#
#  https://github.com/Ultimaker/Cura/tree/master/plugins/SupportEraser
#
# All modification 5@xes
# First release 05-22-2020  First proof of concept
#------------------------------------------------------------------------------------------------------------------
# V1.0.1 11-11-2020 Change the default height _layer_h = _layer_h * 1.2
# V1.1.0 19-02-2021 Add Capsule option on Reality4DEvolution idea   Change supported release from API 7 (Cura 4.4)
# V1.2.0 11-03-2021 Add option Number of layer
# V1.2.1 11-06-2021 Check Cura version
# V1.2.2 04-11-2021 Update Cura 4.12
#
# V1.3.0 03-05-2022 Update for Cura 5.0
#------------------------------------------------------------------------------------------------------------------

VERSION_QT5 = False
try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import QApplication
    VERSION_QT5 = True

from cura.CuraApplication import CuraApplication

from UM.Logger import Logger
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Tool import Tool
from UM.Event import Event, MouseEvent
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Scene.Selection import Selection

from cura.PickingPass import PickingPass

from cura.CuraVersion import CuraVersion  # type: ignore
from UM.Version import Version

from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from cura.Operations.SetParentOperation import SetParentOperation

from UM.Settings.SettingInstance import SettingInstance

from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from UM.Scene.ToolHandle import ToolHandle
from UM.Tool import Tool

from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")


import math
import numpy

class TabAntiWarping(Tool):
    def __init__(self):
        super().__init__()
        
        # variable for menu dialog        
        self._UseSize = 0.0
        self._UseOffset = 0.0
        self._AsCapsule = False
        self._Nb_Layer = 1


        # Shortcut
        if not VERSION_QT5:
            self._shortcut_key = Qt.Key.Key_I
        else:
            self._shortcut_key = Qt.Key_I
            
        self._controller = self.getController()

        self._selection_pass = None

        # self._i18n_catalog = None
        
        self.Major=1
        self.Minor=0

        # Logger.log('d', "Info Version CuraVersion --> " + str(Version(CuraVersion)))
        Logger.log('d', "Info CuraVersion --> " + str(CuraVersion))
        
        # Test version for Cura Master
        # https://github.com/smartavionics/Cura
        if "master" in CuraVersion :
            self.Major=4
            self.Minor=20
        else:
            try:
                self.Major = int(CuraVersion.split(".")[0])
                self.Minor = int(CuraVersion.split(".")[1])
            except:
                pass
        
        self.setExposedProperties("SSize", "SOffset", "SCapsule", "NLayer")
        
        CuraApplication.getInstance().globalContainerStackChanged.connect(self._updateEnabled)
        
         
        # Note: if the selection is cleared with this tool active, there is no way to switch to
        # another tool than to reselect an object (by clicking it) because the tool buttons in the
        # toolbar will have been disabled. That is why we need to ignore the first press event
        # after the selection has been cleared.
        Selection.selectionChanged.connect(self._onSelectionChanged)
        self._had_selection = False
        self._skip_press = False

        self._had_selection_timer = QTimer()
        self._had_selection_timer.setInterval(0)
        self._had_selection_timer.setSingleShot(True)
        self._had_selection_timer.timeout.connect(self._selectionChangeDelay)
        
        # set the preferences to store the default value
        self._preferences = CuraApplication.getInstance().getPreferences()
        self._preferences.addPreference("customsupportcylinder/p_size", 10)
        # convert as float to avoid further issue
        self._UseSize = float(self._preferences.getValue("customsupportcylinder/p_size"))
 
        self._preferences.addPreference("customsupportcylinder/p_offset", 0.16)
        # convert as float to avoid further issue
        self._UseOffset = float(self._preferences.getValue("customsupportcylinder/p_offset"))

        self._preferences.addPreference("customsupportcylinder/as_capsule", False)
        # convert as float to avoid further issue
        self._AsCapsule = bool(self._preferences.getValue("customsupportcylinder/as_capsule"))   

        self._preferences.addPreference("customsupportcylinder/nb_layer", 1)
        # convert as float to avoid further issue
        self._Nb_Layer = int(self._preferences.getValue("customsupportcylinder/nb_layer"))        
                
    def event(self, event):
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        if not VERSION_QT5:
            ctrl_is_active = modifiers & Qt.KeyboardModifier.ControlModifier
        else:
            ctrl_is_active = modifiers & Qt.ControlModifier

        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons and self._controller.getToolsEnabled():
            if ctrl_is_active:
                self._controller.setActiveTool("TranslateTool")
                return

            if self._skip_press:
                # The selection was previously cleared, do not add/remove an support mesh but
                # use this click for selection and reactivating this tool only.
                self._skip_press = False
                return

            if self._selection_pass is None:
                # The selection renderpass is used to identify objects in the current view
                self._selection_pass = CuraApplication.getInstance().getRenderer().getRenderPass("selection")
            picked_node = self._controller.getScene().findObject(self._selection_pass.getIdAtPosition(event.x, event.y))
            if not picked_node:
                # There is no slicable object at the picked location
                return

            node_stack = picked_node.callDecoration("getStack")

            
            if node_stack:
            
                if node_stack.getProperty("support_mesh", "value"):
                    self._removeSupportMesh(picked_node)
                    return

                elif node_stack.getProperty("anti_overhang_mesh", "value") or node_stack.getProperty("infill_mesh", "value") or node_stack.getProperty("support_mesh", "value"):
                    # Only "normal" meshes can have support_mesh added to them
                    return

            # Create a pass for picking a world-space location from the mouse location
            active_camera = self._controller.getScene().getActiveCamera()
            picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
            picking_pass.render()

            picked_position = picking_pass.getPickedPosition(event.x, event.y)

            # Add the support_mesh cube at the picked location
            self._createSupportMesh(picked_node, picked_position)

    def _createSupportMesh(self, parent: CuraSceneNode, position: Vector):
        node = CuraSceneNode()

        node.setName("RoundTab")
            
        node.setSelectable(True)
        
        # long=Support Height
        _long=position.y

        # get layer_height_0 used to define pastille height
        _id_ex=0
        
        # This function can be triggered in the middle of a machine change, so do not proceed if the machine change
        # has not done yet.
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        #extruder = global_container_stack.extruderList[int(_id_ex)] 
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]        
        _layer_h_i = extruder_stack.getProperty("layer_height_0", "value")
        _layer_height = extruder_stack.getProperty("layer_height", "value")
        _line_w = extruder_stack.getProperty("line_width", "value")
        # Logger.log('d', 'layer_height_0 : ' + str(_layer_h_i))
        _layer_h = (_layer_h_i * 1.2) + (_layer_height * (self._Nb_Layer -1) )
        _line_w = _line_w * 1.2 
        
        if self._AsCapsule:
             # Capsule creation Diameter , Increment angle 4°, length, layer_height_0*1.2 , line_width
            mesh = self._createCapsule(self._UseSize,4,_long,_layer_h,_line_w)       
        else:
            # Cylinder creation Diameter , Increment angle 4°, length, layer_height_0*1.2
            mesh = self._createPastille(self._UseSize,4,_long,_layer_h)
        
        node.setMeshData(mesh.build())

        active_build_plate = CuraApplication.getInstance().getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(active_build_plate))
        node.addDecorator(SliceableObjectDecorator())

        stack = node.callDecoration("getStack") # created by SettingOverrideDecorator that is automatically added to CuraSceneNode
        settings = stack.getTop()

        # support_mesh type
        definition = stack.getSettingDefinition("support_mesh")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", True)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        definition = stack.getSettingDefinition("support_mesh_drop_down")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", False)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)
 
        if self._AsCapsule:
            s_p = global_container_stack.getProperty("support_type", "value")
            if s_p ==  'buildplate' :
                Message(text = "Info modification current profile support_type parameter\nNew value : everywhere", title = catalog.i18nc("@info:title", "Warning ! Tab Anti Warping")).show()
                Logger.log('d', 'support_type different : ' + str(s_p))
                # Define support_type=everywhere
                global_container_stack.setProperty("support_type", "value", 'everywhere')
                
            
        # Define support_xy_distance
        definition = stack.getSettingDefinition("support_xy_distance")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", self._UseOffset)
        # new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        # Fix some settings in Cura to get a better result
        id_ex=0
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]
        #extruder = global_container_stack.extruderList[int(id_ex)]    
        
        # hop to fix it in a futur release
        # https://github.com/Ultimaker/Cura/issues/9882
        # if self.Major < 5 or ( self.Major == 5 and self.Minor < 1 ) :
        _xy_distance = extruder_stack.getProperty("support_xy_distance", "value")
        if self._UseOffset !=  _xy_distance :
            _msg = "New value : %8.3f" % (self._UseOffset) 
            Message(text = "Info modification current profile support_xy_distance parameter\nNew value : %8.3f" % (self._UseOffset), title = catalog.i18nc("@info:title", "Warning ! Tab Anti Warping")).show()
            Logger.log('d', 'support_xy_distance different : ' + str(_xy_distance))
            # Define support_xy_distance
            extruder_stack.setProperty("support_xy_distance", "value", self._UseOffset)
 
        if self._Nb_Layer >1 :
            s_p = int(extruder_stack.getProperty("support_infill_rate", "value"))
            Logger.log('d', 'support_infill_rate actual : ' + str(s_p))
            if s_p < 99 :
                Message(text = "Info modification current profile support_infill_rate parameter\nNew value : 100%", title = catalog.i18nc("@info:title", "Warning ! Tab Anti Warping")).show()
                Logger.log('d', 'support_infill_rate different : ' + str(s_p))
                # Define support_infill_rate=100%
                extruder_stack.setProperty("support_infill_rate", "value", 100)
                
        
        
        op = GroupedOperation()
        # First add node to the scene at the correct position/scale, before parenting, so the support mesh does not get scaled with the parent
        op.addOperation(AddSceneNodeOperation(node, self._controller.getScene().getRoot()))
        op.addOperation(SetParentOperation(node, parent))
        op.push()
        node.setPosition(position, CuraSceneNode.TransformSpace.World)

        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _removeSupportMesh(self, node: CuraSceneNode):
        parent = node.getParent()
        if parent == self._controller.getScene().getRoot():
            parent = None

        op = RemoveSceneNodeOperation(node)
        op.push()

        if parent and not Selection.isSelected(parent):
            Selection.add(parent)

        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _updateEnabled(self):
        plugin_enabled = False

        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        if global_container_stack:
            plugin_enabled = global_container_stack.getProperty("support_mesh", "enabled")

        CuraApplication.getInstance().getController().toolEnabledChanged.emit(self._plugin_id, plugin_enabled)
    
    def _onSelectionChanged(self):
        # When selection is passed from one object to another object, first the selection is cleared
        # and then it is set to the new object. We are only interested in the change from no selection
        # to a selection or vice-versa, not in a change from one object to another. A timer is used to
        # "merge" a possible clear/select action in a single frame
        if Selection.hasSelection() != self._had_selection:
            self._had_selection_timer.start()

    def _selectionChangeDelay(self):
        has_selection = Selection.hasSelection()
        if not has_selection and self._had_selection:
            self._skip_press = True
        else:
            self._skip_press = False

        self._had_selection = has_selection
 
    # Capsule creation
    def _createCapsule(self, size, nb , lg, He, lw):
        mesh = MeshBuilder()
        # Per-vertex normals require duplication of vertices
        r = size / 2
        # First layer length
        sup = -lg + He
        if self._Nb_Layer >1 :
            sup_c = -lg + (He * 2)
        else:
            sup_c = -lg + (He * 3)
        l = -lg
        rng = int(360 / nb)
        ang = math.radians(nb)

        r_sup=math.tan(math.radians(45))*(He * 3)+r
        # Top inside radius 
        ri=r_sup-(1.8*lw)
        # Top radius 
        rit=r-(1.8*lw)
            
        verts = []
        for i in range(0, rng):
            # Top
            verts.append([ri*math.cos(i*ang), sup_c, ri*math.sin(i*ang)])
            verts.append([r_sup*math.cos((i+1)*ang), sup_c, r_sup*math.sin((i+1)*ang)])
            verts.append([r_sup*math.cos(i*ang), sup_c, r_sup*math.sin(i*ang)])
            
            verts.append([ri*math.cos((i+1)*ang), sup_c, ri*math.sin((i+1)*ang)])
            verts.append([r_sup*math.cos((i+1)*ang), sup_c, r_sup*math.sin((i+1)*ang)])
            verts.append([ri*math.cos(i*ang), sup_c, ri*math.sin(i*ang)])

            #Side 1a
            verts.append([r_sup*math.cos(i*ang), sup_c, r_sup*math.sin(i*ang)])
            verts.append([r_sup*math.cos((i+1)*ang), sup_c, r_sup*math.sin((i+1)*ang)])
            verts.append([r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)])
            
            #Side 1b
            verts.append([r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)])
            verts.append([r*math.cos(i*ang), l, r*math.sin(i*ang)])
            verts.append([r_sup*math.cos(i*ang), sup_c, r_sup*math.sin(i*ang)])
 
            #Side 2a
            verts.append([rit*math.cos((i+1)*ang), sup, rit*math.sin((i+1)*ang)])
            verts.append([ri*math.cos((i+1)*ang), sup_c, ri*math.sin((i+1)*ang)])
            verts.append([ri*math.cos(i*ang), sup_c, ri*math.sin(i*ang)])
            
            #Side 2b
            verts.append([ri*math.cos(i*ang), sup_c, ri*math.sin(i*ang)])
            verts.append([rit*math.cos(i*ang), sup, rit*math.sin(i*ang)])
            verts.append([rit*math.cos((i+1)*ang), sup, rit*math.sin((i+1)*ang)])
                
            #Bottom Top
            verts.append([0, sup, 0])
            verts.append([rit*math.cos((i+1)*ang), sup, rit*math.sin((i+1)*ang)])
            verts.append([rit*math.cos(i*ang), sup, rit*math.sin(i*ang)])
            
            #Bottom 
            verts.append([0, l, 0])
            verts.append([r*math.cos(i*ang), l, r*math.sin(i*ang)])
            verts.append([r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)]) 
            
            
        mesh.setVertices(numpy.asarray(verts, dtype=numpy.float32))

        indices = []
        # for every angle increment 24 Vertices
        tot = rng * 24
        for i in range(0, tot, 3): # 
            indices.append([i, i+1, i+2])
        mesh.setIndices(numpy.asarray(indices, dtype=numpy.int32))

        mesh.calculateNormals()
        return mesh
        
    # Cylinder creation
    def _createPastille(self, size, nb , lg, He):
        mesh = MeshBuilder()
        # Per-vertex normals require duplication of vertices
        r = size / 2
        # First layer length
        sup = -lg + He
        l = -lg
        rng = int(360 / nb)
        ang = math.radians(nb)
        
        verts = []
        for i in range(0, rng):
            # Top
            verts.append([0, sup, 0])
            verts.append([r*math.cos((i+1)*ang), sup, r*math.sin((i+1)*ang)])
            verts.append([r*math.cos(i*ang), sup, r*math.sin(i*ang)])
            #Side 1a
            verts.append([r*math.cos(i*ang), sup, r*math.sin(i*ang)])
            verts.append([r*math.cos((i+1)*ang), sup, r*math.sin((i+1)*ang)])
            verts.append([r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)])
            #Side 1b
            verts.append([r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)])
            verts.append([r*math.cos(i*ang), l, r*math.sin(i*ang)])
            verts.append([r*math.cos(i*ang), sup, r*math.sin(i*ang)])
            #Bottom 
            verts.append([0, l, 0])
            verts.append([r*math.cos(i*ang), l, r*math.sin(i*ang)])
            verts.append([r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)]) 
            
            
        mesh.setVertices(numpy.asarray(verts, dtype=numpy.float32))

        indices = []
        # for every angle increment 12 Vertices
        tot = rng * 12
        for i in range(0, tot, 3): # 
            indices.append([i, i+1, i+2])
        mesh.setIndices(numpy.asarray(indices, dtype=numpy.int32))

        mesh.calculateNormals()
        return mesh
    
    def getSSize(self) -> float:
        """ 
            return: golabl _UseSize  in mm.
        """           
        return self._UseSize
  
    def setSSize(self, SSize: str) -> None:
        """
        param SSize: Size in mm.
        """
 
        try:
            s_value = float(SSize)
        except ValueError:
            return

        if s_value <= 0:
            return
        
        #Logger.log('d', 's_value : ' + str(s_value))        
        self._UseSize = s_value
        self._preferences.setValue("customsupportcylinder/p_size", s_value)
 
    def getNLayer(self) -> int:
        """ 
            return: golabl _Nb_Layer
        """           
        return self._Nb_Layer
  
    def setNLayer(self, NLayer: str) -> None:
        """
        param NLayer: NLayer as integer >1
        """
 
        try:
            i_value = int(NLayer)
            
        except ValueError:
            return
 
        if i_value < 1:
            return
            
        Logger.log('d', 'i_value : ' + str(i_value))        
        self._Nb_Layer = i_value
        self._preferences.setValue("customsupportcylinder/nb_layer", i_value)
        
    def getSOffset(self) -> float:
        """ 
            return: golabl _UseOffset  in mm.
        """           
        return self._UseOffset
  
    def setSOffset(self, SOffset: str) -> None:
        """
        param SOffset: SOffset in mm.
        """
 
        try:
            s_value = float(SOffset)
        except ValueError:
            return
        
        #Logger.log('d', 's_value : ' + str(s_value))        
        self._UseOffset = s_value
        self._preferences.setValue("customsupportcylinder/p_offset", s_value)

    def getSCapsule(self) -> bool:
        """ 
            return: golabl _AsCapsule  as boolean
        """           
        return self._AsCapsule
  
    def setSCapsule(self, SCapsule: bool) -> None:
        """
        param SCapsule: as boolean.
        """
        self._AsCapsule = SCapsule
        self._preferences.setValue("customsupportcylinder/as_capsule", SCapsule)
        
