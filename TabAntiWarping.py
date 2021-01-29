# Initial Copyright (c) 2018 Aldo Hoeben fieldOfView
# Based on the SupportBlocker plugin by Ultimaker B.V., and licensed under LGPLv3 or higher.
# All modification 5@xes
# First release 05-22-2020  First proof of concept
#--------------------------------------------------------------------------------------------
# V1.0.1 11-11-2020 Change the default height _layer_h = _layer_h * 1.2
#--------------------------------------------------------------------------------------------

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from cura.CuraApplication import CuraApplication

from UM.Logger import Logger
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Tool import Tool
from UM.Event import Event, MouseEvent
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Scene.Selection import Selection

from cura.PickingPass import PickingPass

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
        
        # Shortcut
        self._shortcut_key = Qt.Key_I
        self._controller = self.getController()

        self._selection_pass = None

        # self._i18n_catalog = None
        
        self.setExposedProperties("SSize", "SOffset")
        
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
        
                
    def event(self, event):
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
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
        extruder = global_container_stack.extruderList[int(_id_ex)]    
        _layer_h = extruder.getProperty("layer_height_0", "value")
        # Logger.log('d', 'layer_height_0 : ' + str(_layer_h))
        _layer_h = _layer_h * 1.2   
        
        # Cylinder creation Diameter , Increment angle 4°, length
        mesh = self._createPastille(self._UseSize,4,_long,_layer_h)
        
        node.setMeshData(mesh.build())

        active_build_plate = CuraApplication.getInstance().getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(active_build_plate))
        node.addDecorator(SliceableObjectDecorator())

        stack = node.callDecoration("getStack") # created by SettingOverrideDecorator that is automatically added to CuraSceneNode
        settings = stack.getTop()

        # support_mesh type
        for key in ["support_mesh", "support_mesh_drop_down"]:
            definition = stack.getSettingDefinition(key)
            new_instance = SettingInstance(definition, settings)
            new_instance.setProperty("value", True)
            new_instance.resetState()  # Ensure that the state is not seen as a user state.
            settings.addInstance(new_instance)
            
        # Define support_xy_distance
        definition = stack.getSettingDefinition("support_xy_distance")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", self._UseOffset)
        # new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        # Fix some settings in Cura to get a better result
        id_ex=0
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        extruder = global_container_stack.extruderList[int(id_ex)]    
        
        _xy_distance = extruder.getProperty("support_xy_distance", "value")
        if self._UseOffset !=  _xy_distance :
            _msg = "New value : %8.3f" % (self._UseOffset) 
            Message(text = "Info modification support_xy_distance :\nNew value : %8.3f" % (self._UseOffset), title = catalog.i18nc("@info:title", "tab anti wraping")).show()
            Logger.log('d', 'support_xy_distance different : ' + str(_xy_distance))
            # Define support_xy_distance
            extruder.setProperty("support_xy_distance", "value", self._UseOffset)
        
        
        
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

