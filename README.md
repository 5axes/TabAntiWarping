# Tab Anti Warping
Add element as rounded Tab to limit warping effect in print corner.

![Pastille](./images/pastille_anti_wrapping.JPG)

Using Helper Disks, which act on the corners of your model to help keep everything pinned down. Once the print is finished, the disks can be cut away pretty easily.

Test with a diameter of 20mm and Support X/Y Distance=0.2mm. To keep a support with a full pattern don't goes over 20/25mm.

![Pastille](./images/test.jpg)

**Actual solution limited by the possibility to use just a global : Support X/Y Distance**



## Installation
First, make sure your Cura version is 3.6 or newer.

Manual Install Download & extract the repository as ZIP or clone it. Copy the files/plugins/TabAntiWarping directory to:

on Windows: [Cura installation folder]/plugins/TabAntiWarping
on Linux: ~/.local/share/cura/[YOUR CURA VERSION]/plugins/TabAntiWarping (e.g. ~/.local/share/cura/4.6/plugins/TabAntiWarping)
on Mac: ~/Library/Application Support/cura/[YOUR CURA VERSION]/plugins/TabAntiWarping


## How to use

- Load a model in Cura and select it
- Click on the "Tab Anti Warping" button on the left toolbar  (Shortcut I)
- Change de value for the tab *Size* in numeric input field in the tool panel if necessary


- Click anywhere on the model to place support cylinder there

- **Clicking existing support cylinder deletes it**

- **Clicking existing support cylinder + Ctrl** switch automaticaly to the Translate Tool to modify the position of the support.

* The length of the support is automaticaly set to the Initial Layer Height .


>Note: it's easier to add/remove tabs when you are in "Solid View" mode
