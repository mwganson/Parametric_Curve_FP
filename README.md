# Parametric_Curve_FP
Create a parametric curve feature python object in FreeCAD

![fp object](fp.jpg)

## Installation
Place both .py files into your macros directory.  Run the Make_Parametric_Curve.py in FreeCAD to create the parametric curve object.  It cannot be installed via the AddonManager at this time.  You can download the files as a zip file by clicking the Code link and selecting download as zip option.  Extract them to a temporary folder and move the 2 .py files into your macros folder.

## History
This macro is based on the FreeCAD macro 3D Parametric Curve by Lucio Gomez and Laurent Despeyroux.  https://wiki.freecadweb.org/Macro_3D_Parametric_Curve
The difference is this macro creates a feature python object that also has spreadsheet and JSON integration capabilities.

## Usage
Run the Make_Parametric_Curve.py file as a macro to create the feature python object.  Then modify the properties to setup the formula to use.  It comes with a default formula to create a curve pictured above

You can also, in addition to modifying the properties directly, elect to use a spreadsheet to hold the formulas.  A spreadsheet needs to have the following aliases defined:

* a_cell -- String that contains the a formula.
* b_cell -- String that contains the b formula.
* c_cell -- String that contains the c formula.
* X -- String that contains the X formula.
* Y -- String that contains the Y formula.
* Z -- String that contains the Z formula.
* min_t -- Floating point that contains the starting value of t.
* max_t -- Floating point that contains the ending value of t.
* interval -- Floating point that contains the step value for t as it goes from min_t to max_t.

The feature python object can add these aliases for you to an existing spreadsheet or a new spreadsheet that it can also create.  If there is no spreadsheet linked in the Spreadsheet property and you set the Update Spreadsheet property to True, the fp object will create the new spreadsheet, link it to itself, and add the aliases to the spreadsheet.  It also sets the Use Spreadsheet property to True.  If you manually select a spreadsheet by editing the Spreadsheet property to link to an existing spreadsheet, and that spreadsheet does not contain the required aliases you will be asked whether to create them or not.  Doing this will clobber any existing data in cells A1 through B9.

As of version 2021.08.28.rev3 there is also support for JSON files.  You can save the fp object's state (the Equation Group and JSON group properties) to the JSON file, and then later load them back from the JSON file in this or in another Parametric Curve object.  With JSON files you are able to have more than one formula per file, unlike spreadsheets, which are limited to one formula per spreadsheet.  If you have many formulas you like to use you can save them all to a single JSON file.

Sample JSON file:
{"formula37": {"a": "37", "b": "4", "c": "(a+cos(a*t)*2)*b", "X": "cos(t)*c", "Y": "sin(t)*c", "Z": "0", "min_t": "0.0", "max_t": "6.283185307179586", "interval": "0.01"}, "formula13": {"a": "13", "b": "13", "c": "(a+cos(a*t)*2)*b", "X": "cos(t)*c", "Y": "sin(t)*c", "Z": "0", "min_t": "0.0", "max_t": "6.283185307179586", "interval": "0.1"}, "formula7": {"a": "7", "b": "18", "c": "(a+cos(a*t)*2)*b", "X": "cos(t)*c", "Y": "sin(t)*c", "Z": "0", "min_t": "0.0", "max_t": "6.283185307179586", "interval": "0.1"}, "formula_clover": {"a": "3", "b": "7", "c": "(a+cos(a*t)*2)*b", "X": "cos(t)*c", "Y": "sin(t)*c", "Z": "0", "min_t": "0.0", "max_t": "6.283185307179586", "interval": "0.1"}}

It holds 4 formulas: "small wire", "biggest wire", "medium wire", and "highest wire".

You can manually edit the JSON files in a text editor, but there are a few things to keep in mind.
* Make sure to follow the formatting properly or else the fp object will not be able to read the file
* Values for min_t, max_t, and interval must evaluate directly to float.  For example, "3.14159" works, but "pi" does not.
* Values with decimal points must not lead with the decimal, but rather should have a leading 0.  Example: "0.5" instead of ".5"
* All values must be strings (in quotes)

## Properties

The Feature Python object (ParametricCurve) has a number of properties separated into different groupings.

### Curve Group
#### Closed (Default: True)
The property sets the curve to either closed or not closed.  If it's set to True the wire will close itself (connect the first vertex to the last vertex).  This is required if you are to use the curve to create a solid with a Pad, Extrude, etc.
#### Make BSpline (Default: True)
If set to True a BSpline object is created for the curve.  If False, a polygon is created instead.
#### Version
This gives the version used to create this object (not necessarily the same as currently installed.)  It is in the form of the date of last modification, e.g. 2021.08.27.
### Spreadsheet Group
#### Spreadsheet (Default: None)
This is a link property, linking the fp object to a spreadsheet.  By default, it is empty, but if you select a spreadsheet in the tree view, and then run the macro to create the fp object, it will link that spreadsheet automatically and import the data into the properties.  See Usage section above for more details on required format of spreadsheet.
#### Update Spreadsheet (Default: False)
This property serves as a command button.  When you set it to True it triggers the fp object to save the properties to the connected spreadsheet, overwriting any existing values.  If no spreadsheet is connected it will create a new spreadsheet for you, link it in the Spreadsheet property, add the required aliases, and set their values.  It's a way of saving the current properties to a new spreadsheet for later use.  In all other cases the fp object pulls values from the connected spreadsheet (if Use Spreadsheet = True, see below), but in this case it is pushing those values to the spreadsheet.  After it pushes the data to the spreadsheet it resets itself back to False.
#### Use Spreadsheet (Default: False)
When this is True, the formula properties (a,b,c,X,Y,Z,t,t_max, and interval) are all set to readonly.  You won't be able to modify the properties in the fp object's property view when this is True.  Instead, you must modify the appropriate cells in the spreadsheet.  The fp object automatically updates its properties from the spreadsheet when they change.  Set this to False if you would prefer to modify the properties in the fp object rather than in the spreadsheet.  But if you set it to True again your property changes will be overwritten with the values from the spreadsheet.  Use the Update Spreadsheet property/command trigger to push the data to the spreadsheet first if you don't want the property values to be clobbered.
### JSON Group
#### Change Preset Name
[Trigger]  This property serves as a trigger to trigger a command.  The command triggered is to change the name of the current preset (as currently selected in the Presets property) to the string currently in the Preset_Name property field.  By default, when a new formula is created (or when a new JSON file is initiated) the default name given to it is "formula" or sometimes "formula1", "formula2", etc.  If you want to change the name to something more meaningful, such as "Spiral", enter "Spiral" into the Preset_Name property and trigger the Change Preset Name property form False to True.  Note: You must connect a JSON file to the feature python object using the File property, discussed below, before you can use most of the features in the JSON group.
#### File
This is the JSON file connected to the fp object.  By default, it is empty.  You can click the "[...]" button to open the file open dialog to select a file or create a new one by entering the name into the File property field.  Make sure you have write access to the folder you choose.  In Linux something like ~/Documents/myjsonfile.txt would work.  In Windows, maybe use c:\users\YOURUSERNAME\Documents\myjsonfile.txt.  When you connect the file, if it is one that already exists and has previously saved data in it, the data in the file will be read in and the Equation properties will be populated with this data.

A JSON file may have more than one formula stored in it.  Each formula is given a name, e.g. formula, formula1, etc.  Or you can assign your own custom name if you prefer.  All of the formulas get populated into the Presets property, which presents as a drop down list from which you can select the desired formula.
#### New Formula
[Trigger]  This property serves as a trigger to trigger a command.  The command triggered is to create a new formula and add it to the Presets property.  It is given a default name, such as "formula", "formula1", "formula2", etc., whichever one is first available.  You can change this name to a more meaningful one as described above im the Change Preset Name documentation.  All of the Trigger properties are boolean properties that are normally False.  You trigger them by setting them to True.  They reset themselves to False after running the command.
#### Open File
[Trigger]  This property serves as a trigger to trigger a command.  The command triggered is to open the JSON file in your default editor.  If you give it a .txt extension this is more likely to be successful.  It has been tested on Windows and Ubuntu, but not as yet on Mac.  The JSON file can be edited as you would any text file.  Just take care to follow the formatting if adding new formulas in this manner.  Once you have edited and saved your changes you can have the fp object reload the file by triggering the Reload File property.
#### Reload File
[Trigger]  This property serves as a trigger to trigger a command.  The command triggered is to reload the JSON file from disk in the event changes have been made to the file outside of the fp object or in the case where you simply want to reset the fp object.
#### Write JSON
[Trigger]  This property serves as a trigger to trigger a command.  The command triggered is to save the current state of the fp object to the JSON file.  Everything in the JSON file will be overwritten.  You must trigger this command in order to save any changes to the JSON file unless you made the changes outside the fp object, such as using Notepad in Windows.

### Equation1 and Equation2 Groups
#### a,b,c,X,Y,Z
These are string properties that hold the formulas for creating the curve.  Math expressions, like cos(), sin(), atan(), etc. can be used in the formulas.  Basically, anything in the math package, such as math.pi can be used (use it as simply pi and not as math.pi).  In all of these you can refer to t.  For property a you cannot refer to b or c (because these variables haven't been created yet).  In b you can refer to a, but not c.  In c you can refer to both a and b.  In X,Y, and Z you can refer to a, b, or c.<br/>
<br/>
a -> only refer to t<br/>
b -> only refer to a and t<br/>
c -> only refer to a, b, and t<br/>
X -> only refer to a, b, c, and t<br/>
Y -> only refer to a, b, c, X, and t<br/>
Z -> only refer to a, b, c, X, Y, and t<br/>
<br/>
Supported math functions:<br/><br/>
    "sin": math.sin<br/>
    "cos": math.cos<br/>
    "tan": math.tan<br/>
    "exp": math.exp<br/>
    "atan": math.atan<br/>
    "acos": math.acos<br/>
    "acosh": math.acosh<br/>
    "asin": math.asin<br/>
    "asinh": math.asinh<br/>
    "sqrt": math.sqrt<br/>
    "ceil": math.ceil<br/>
    "floor": math.floor<br/>
    "sinh": math.sinh<br/>
    "log": math.log<br/>
    "factorial":math.factorial<br/>
    "abs": abs<br/>
    "degrees": math.degrees<br/>
    "degree": math.degrees<br/>
    "deg": math.degrees<br/>
    "lgamma": math.lgamma<br/>
    "gamma": math.gamma<br/>
    "radians": math.radians<br/>
    "rad": math.radians<br/>
    "trunc": int<br/>
    "round": round<br/>
 
 To do basic adding, subtracting, multiplying, dividing, use standard "+-\*/". For exponents instead of 3\*\*7 standard python syntax use 3^7 to do "3 to the power of 7".

### Equation3(T Params) Group
#### t,t_max,interval.
The way the macro works is it creates points in a loop, and then at the end of the loop it uses those points to create the BSpline / Polygon.  The t is the looping index.  It starts the loop initialized at t (min_t in the spreadsheet) and at the end of the loop t = t_max (max_t in the spreadsheet).  The interval is the amount by which t is increased each time through the loop.  The lower the interval the more points get produced.  The properties in this group are type Float, whereas the other properties are type String.  The others have to be Strings in order for you to be able to use variables in the formulas.  These string formulas get evaluated by some code using the pyparsing module.  It's slower, but more secure than using eval().
### Changelog
* 2021.08.29<br/>
** bug fixes
** renamed some internal functions and properties, probably breaks any existing models
* 2021.08.28.rev3<br/>
** Adds JSON support
* 2021.08.28, rev.2<br/>
** Allow for unused variables to be blank, empty string.<br/>
evaluate("") -> 0<br/>
** Add Continuity (read only) property in Curve group
** Remove unused hidden property "d"
* 2021.08.28<br/>
** Generalize parser for more general use.  To use:<br/>
from Parametric_Curve_FP import evaluate<br/>
evaluate("1+2") -> 3<br/>
evaluate("a+2",{"a":5}) -> 7<br/>
The dictionary object can contain any number of variables and their values.
* 2021.08.27<br/>
** Initial upload.
