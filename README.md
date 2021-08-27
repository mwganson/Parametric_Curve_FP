# Parametric_Curve_FP
Create a parametric curve feature python object in FreeCAD

## Installation
Place both .py files into your macros directory.  Run the Make_Parametric_Curve.py in FreeCAD to create the parametric curve object.

## History
This macro is based on the FreeCAD macro 3D Parametric Curve by Lucio Gomez and Laurent Despeyroux.  https://wiki.freecadweb.org/Macro_3D_Parametric_Curve
The difference is this macro creates a feature python object that also has spreadsheet integration capabilities.

## Warning
This macro, like the original 3D Parametric Curve macro, uses eval(), which is a security vulnerability.  But this one is even more so because the formulas get saved with the document object.

## Usage
Run the Make_Parametric_Curve.py file as a macro to create the feature python object.  Then modify the properties to setup the formula to use.  It comes with a default formula to create a curve pictured here:


