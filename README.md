# Parametric_Curve_FP
Create a parametric curve feature python object in FreeCAD

![fp object](fp.jpg)

## Installation
Place both .py files into your macros directory.  Run the Make_Parametric_Curve.py in FreeCAD to create the parametric curve object.  It cannot be installed via the AddonManager at this time.  You can download the files as a zip file by clicking the Code link and selecting download as zip option.  Extract them to a temporary folder and move the 2 .py files into your macros folder.

## History
This macro is based on the FreeCAD macro 3D Parametric Curve by Lucio Gomez and Laurent Despeyroux.  https://wiki.freecadweb.org/Macro_3D_Parametric_Curve
The difference is this macro creates a feature python object that also has spreadsheet integration capabilities.

## Usage
Run the Make_Parametric_Curve.py file as a macro to create the feature python object.  Then modify the properties to setup the formula to use.  It comes with a default formula to create a curve pictured here:

![curve.jpg](curve.jpg)

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

## Properties

The Feature Python object (ParametricCurve) has a number of properties separated into different groupings.

### Curve Group
#### Closed (Default: True)
The property sets the curve to either closed or not closed.  If it's set to True the wire will close itself (connect the first vertex to the last vertex).  This is required if you are to use the curve to create a solid with a Pad, Extrude, etc.
#### Make BSpline (Default: True)
If set to True a BSpline object is created for the curve.  If False, a polygon is created instead.
#### Version
This gives the version used to create this object (not necessarily the same as currently installed.)  It is in the form of the date of last modification, e.g. 2021.08.27.
### Data Group
#### Spreadsheet (Default: None)
This is a link property, linking the fp object to a spreadsheet.  By default, it is empty, but if you select a spreadsheet in the tree view, and then run the macro to create the fp object, it will link that spreadsheet automatically and import the data into the properties.  See Usage section above for more details on required format of spreadsheet.
#### Update Spreadsheet (Default: False)
This property serves as a command button.  When you set it to True it triggers the fp object to save the properties to the connected spreadsheet, overwriting any existing values.  If no spreadsheet is connected it will create a new spreadsheet for you, link it in the Spreadsheet property, add the required aliases, and set their values.  It's a way of saving the current properties to a new spreadsheet for later use.  In all other cases the fp object pulls values from the connected spreadsheet (if Use Spreadsheet = True, see below), but in this case it is pushing those values to the spreadsheet.  After it pushes the data to the spreadsheet it resets itself back to False.
#### Use Spreadsheet (Default: False)
When this is True, the formula properties (a,b,c,X,Y,Z,t,t_max, and interval) are all set to readonly.  You won't be able to modify the properties in the fp object's property view when this is True.  Instead, you must modify the appropriate cells in the spreadsheet.  The fp object automatically updates its properties from the spreadsheet when they change.  Set this to False if you would prefer to modify the properties in the fp object rather than in the spreadsheet.  But if you set it to True again your property changes will be overwritten with the values from the spreadsheet.  Use the Update Spreadsheet property/command trigger to push the data to the spreadsheet first if you don't want the property values to be clobbered.
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

### T Parameters Group
#### t,t_max,interval.
The way the macro works is it creates points in a loop, and then at the end of the loop it uses those points to create the BSpline / Polygon.  The t is the looping index.  It starts the loop initialized at t (min_t in the spreadsheet) and at the end of the loop t = t_max (max_t in the spreadsheet).  The interval is the amount by which t is increased each time through the loop.  The lower the interval the more points get produced.  The properties in this group are type Float, whereas the other properties are type String.  The others have to be Strings in order for you to be able to use variables in the formulas.  These string formulas get evaluated by some code using the pyparsing module.  It's slower, but more secure than using eval().
### Changelog
* 2021.08.28<br/>
** Generalize parser for more general use.  To use:<br/>
from Parametric_Curve_FP import evaluate<br/>
evaluate("1+2") -> 3<br/>
evaluate("a+2",{"a":5}) -> 7<br/>
The dictionary object can contain any number of variables and their values.
* 2021.08.27<br/>
** Initial upload.
