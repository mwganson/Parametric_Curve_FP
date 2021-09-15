# -*- coding: utf-8 -*-
########
my_code = """
########
__title__ = "Parametric_Curve_FP"
__author__ = "<TheMarkster> 2021, based on macro 3D Parametric Curve by Gomez Lucio,  Modified by Laurent Despeyroux on 9th feb 2015"
__license__ = "LGPL 2.1"
__doc__ = "Parametric curve from formula"
__usage__ = '''Activate the tool and modify properties as desired'''
__version__ = "2021.09.15.rev3"
__Files__='Parametric_Curve_FP.py'


import FreeCAD, FreeCADGui
from pivy import coin
from math import *
import Part
import json
import os, sys
import subprocess, os 
import platform
import re


# Albert Einstein once remarked how he "stood on the shoulders of giants" in giving credit to those
# great thinkers who came before him and who helped pave the way for his Theory of Relativity.
# I'm certainly no Einstein, but in making this macro, I, too, have built upon the work of others
# who came before.  Thanks, in particular, to Gomez Lucio, author of the original parametric curve
# macro, and to Laurent Despeyroux, who extended it, and Paul McGuire for his work on FourFn parser.
# Also thanks to users openBrain and edwilliams16 of the FreeCAD forum for their help with regular
# expression parsing.

# In order to avoid using eval() and the security implications therefrom, I have borrowed and modified
# some code for using pyparsing.  I added the ability to include a dictionary of constants to evaluate().
# For example, evaluate("a+b*3", {"a":1,"b":2}) evalutes to 7.  I also added some additional math functions
# to the fn dictionary.  And user edwilliams16 at the FreeCAD forum has fixed a bug in the fnumber
# regular expression, which was failing in cases of ".5" instead of "0.5". --Mark

# <begin imported code from FourFN.py>

# https://github.com/pyparsing/pyparsing/blob/master/examples/fourFn.py
#

# fourFn.py
#
# Demonstration of the pyparsing module, implementing a simple 4-function expression parser,
# with support for scientific notation, and symbols for e and pi.
# Extended to add exponentiation and simple built-in functions.
# Extended test cases, simplified pushFirst method.
# Removed unnecessary expr.suppress() call (thanks Nathaniel Peterson!), and added Group
# Changed fnumber to use a Regex, which is now the preferred method
# Reformatted to latest pypyparsing features, support multiple and variable args to functions
#
# Copyright 2003-2019 by Paul McGuire
#
from pyparsing import (
    Literal,
    Word,
    Group,
    Forward,
    alphas,
    alphanums,
    Regex,
    ParseException,
    CaselessKeyword,
    Suppress,
    delimitedList,
#    ParserElement,
)
import math
import operator

#ParserElement.enablePackrat()
exprStack = []


def push_first(toks):
    exprStack.append(toks[0])


def push_unary_minus(toks):
    for t in toks:
        if t == "-":
            exprStack.append("unary -")
        else:
            break


bnf = None


def BNF():
    '''
    expop   :: '^'
    multop  :: '*' | '/'
    addop   :: '+' | '-'
    integer :: ['+' | '-'] '0'..'9'+
    atom    :: PI | E | real | fn '(' expr ')' | '(' expr ')'
    factor  :: atom [ expop factor ]*
    term    :: factor [ multop factor ]*
    expr    :: term [ addop term ]*
    '''
    global bnf
    if not bnf:
        # use CaselessKeyword for e and pi, to avoid accidentally matching
        # functions that start with 'e' or 'pi' (such as 'exp'); Keyword
        # and CaselessKeyword only match whole words
        e = CaselessKeyword("E")
        pi = CaselessKeyword("PI")
        # fnumber = Combine(Word("+-"+nums, nums) +
        #                    Optional("." + Optional(Word(nums))) +
        #                    Optional(e + Word("+-"+nums, nums)))
        # or use provided pyparsing_common.number, but convert back to str:
        # fnumber = ppc.number().addParseAction(lambda t: str(t[0]))
        #fnumber = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
        fnumber = Regex(r'[-+]?(?:(?:\d*\.\d+)|(?:\d+\.?))(?:[Ee][+-]?\d+)?')
        ident = Word(alphas, alphanums + "_$")

        plus, minus, mult, div = map(Literal, "+-*/")
        lpar, rpar = map(Suppress, "()")
        addop = plus | minus
        multop = mult | div
        expop = Literal("^")

        expr = Forward()
        expr_list = delimitedList(Group(expr))
        # add parse action that replaces the function identifier with a (name, number of args) tuple
        def insert_fn_argcount_tuple(t):
            fn = t.pop(0)
            num_args = len(t[0])
            t.insert(0, (fn, num_args))

        fn_call = (ident + lpar - Group(expr_list) + rpar).setParseAction(
            insert_fn_argcount_tuple
        )
        atom = (
            addop[...]
            + (
                (fn_call | pi | e | fnumber | ident).setParseAction(push_first)
                | Group(lpar + expr + rpar)
            )
        ).setParseAction(push_unary_minus)

        # by defining exponentiation as "atom [ ^ factor ]..." instead of "atom [ ^ atom ]...", we get right-to-left
        # exponents, instead of left-to-right that is, 2^3^2 = 2^(3^2), not (2^3)^2.
        factor = Forward()
        factor <<= atom + (expop + factor).setParseAction(push_first)[...]
        term = factor + (multop + factor).setParseAction(push_first)[...]
        expr <<= term + (addop + term).setParseAction(push_first)[...]
        bnf = expr
    return bnf


# map operator symbols to corresponding arithmetic operations
epsilon = 1e-12
opn = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": operator.pow,
}

fn = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "atan": math.atan,
    "acos": math.acos,
    "acosh": math.acosh,
    "asin": math.asin,
    "asinh": math.asinh,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "sinh": math.sinh,
    "log": math.log,
    "factorial":math.factorial,
    "abs": abs,
    "degrees": math.degrees,
    "degree": math.degrees,
    "deg": math.degrees,
    "lgamma": math.lgamma,
    "gamma": math.gamma,
    "radians": math.radians,
    "rad": math.radians,
    "trunc": int,
    "round": round,
    "sgn": lambda a: -1 if a < -epsilon else 1 if a > epsilon else 0,
    # functionsl with multiple arguments
    "multiply": lambda a, b: a * b,
    "hypot": math.hypot,
    # functions with a variable number of arguments
    "all": lambda *a: all(a),
}


def evaluate_stack(s,vars):
    op, num_args = s.pop(), 0
    if isinstance(op, tuple):
        op, num_args = op
    if op == "unary -":
        return -evaluate_stack(s,vars)
    if op in "+-*/^":
        # note: operands are pushed onto the stack in reverse order
        op2 = evaluate_stack(s,vars)
        op1 = evaluate_stack(s,vars)
        return opn[op](op1, op2)
    elif op == "PI":
        return math.pi  # 3.1415926535
    elif op == "E":
        return math.e  # 2.718281828
    elif op in vars:
        return vars[op]
    elif op in fn:
        # note: args are pushed onto the stack in reverse order
        args = reversed([evaluate_stack(s,vars) for _ in range(num_args)])
        return fn[op](*args)
    elif op[0].isalpha():
        raise Exception("invalid identifier '%s'" % op)
    else:
        # try to evaluate as int first, then as float if int fails
        try:
            return int(op)
        except ValueError:
            return float(op)
#vars is a dictionary of variable names
#example:
#vars = {"a":1,"b":2}
# then where "a" or "b" is found a value is substituted
# evaluate("a+b",vars) thus returns 3 --Mark
def evaluate(s, vars={}):
    if s == "": #return 0 in case the user has left the field blank --Mark
        return 0

    exprStack[:] = []
    try:
        results = BNF().parseString(s, parseAll=True)
        val = evaluate_stack(exprStack[:],vars)
    except ParseException as pe:
        raise Exception(s, "failed parse:", str(pe))
    except Exception as e:
        raise Exception (s, "failed eval:", str(e), exprStack)
    else:
        return val

# <end imported code from FourFn.py>


class Curve:
    def __init__(self, obj):
        obj.addExtension("Part::AttachExtensionPython")
        obj.addProperty("App::PropertyString","a","Equation1(a,b,c)","a(t)").a = "37"
        obj.addProperty("App::PropertyString","b","Equation1(a,b,c)","b(a,t)").b = "1"
        obj.addProperty("App::PropertyString","c","Equation1(a,b,c)","c(a,b,t)").c = "(a+cos(a*t)*2)*b"
        obj.addProperty("App::PropertyStringList","d","Equation1(a,b,c)","d1(a,b,c,t)"+chr(10)+"d2(a,b,c,t,d1)"+chr(10)+"d3(a,b,c,t,d1,d2)"+chr(10)+"d4(a,b,c,t,d1,d2,d3)"+chr(10)+"..."+chr(10))
        obj.addProperty("App::PropertyString","X","Equation2(X,Y,Z)","X(a,b,c,t)").X = "cos(t)*c"
        obj.addProperty("App::PropertyString","Y","Equation2(X,Y,Z)","Y(a,b,c,t)").Y = "sin(t)*c"
        obj.addProperty("App::PropertyString","Z","Equation2(X,Y,Z)","Z(a,b,c,t)").Z = "0"
        obj.addProperty("App::PropertyFloat","t","Equation3(T Params)","start value for t").t = 0.0
        obj.addProperty("App::PropertyFloat","t_max","Equation3(T Params)","Max t").t_max = 2*pi
        obj.addProperty("App::PropertyFloat","Interval","Equation3(T Params)","Interval").Interval = 0.1
        obj.addProperty("App::PropertyBool","Closed","Curve","Whether curve is closed").Closed=True
        obj.addProperty("App::PropertyVectorList","Points","Curve","Points used to make the curve. Regenerated each recompute.").Points =[]
        obj.addProperty("App::PropertyString","Version", "Base", "Version this object was created with").Version = __version__
        obj.addProperty("App::PropertyEnumeration","ShapeType","Curve","Options: BSpline, Polygon, Points").ShapeType=["BSpline","Polygon","Points"]
        obj.ShapeType = "BSpline" #default
        obj.addProperty("App::PropertyLink","Spreadsheet","Spreadsheet","Link a spreadsheet")
        obj.addProperty("App::PropertyBool","UpdateSpreadsheet","Spreadsheet","[Trigger] Push current formula to linked spreadsheet, creates one and links it if necessary.").UpdateSpreadsheet=False
        obj.addProperty("App::PropertyBool","UseSpreadsheet","Spreadsheet","If True, poperties are readonly and must come from spreadsheet.  If false, spreadsheet is ignored and properties are set to read/write.").UseSpreadsheet=False
        obj.addProperty("App::PropertyString","Continuity","Curve","Continuity of Curve")
        obj.setEditorMode('Continuity',1)
        obj.addProperty("App::PropertyFile","File","JSON","JSON format file to contain data")
        obj.addProperty("App::PropertyEnumeration","Formulas","JSON","Formulas in JSON data").Formulas=["formula"]
        obj.addProperty("App::PropertyBool","WriteFile","JSON","[Trigger] Updates JSON file with current data.  WARNING: will overwrite all current data, use AppendFile to add current formula to file.").WriteFile = False
        obj.addProperty("App::PropertyBool","RenameFormula","JSON","[Trigger] Changes current Formula name to string in FormulaName").RenameFormula = False
        obj.addProperty("App::PropertyString","FormulaName","JSON","Modify this for changing formula name, and then toggle Rename Formula to True")
        obj.addProperty("App::PropertyBool","NewFormula","JSON","[Trigger] Creates new formula adds to Formulas").NewFormula = False
        obj.addProperty("App::PropertyBool","OpenFile","JSON","[Trigger] Opens JSON file in default system editor for text files.").OpenFile = False
        obj.addProperty("App::PropertyBool","ReadFile","JSON","[Trigger] Reads JSON file.  WARNING: will clobber current formula, use AppendFile to save current formula to file before reading if you want to save it").OpenFile = False
        obj.addProperty("App::PropertyBool","AppendFile","JSON","[Trigger] Appends current formula to JSON file.").AppendFile = False
        obj.addProperty("App::PropertyBool","DeleteFormula","JSON","[Trigger] Removes current formula from internal data, does not modify JSON file").DeleteFormula=False
        obj.Proxy = self
        self.JSON_Data = {}
        self.previousFormula = ""
        self.bInihibitUpdates = False;
        self.bInhibitRecompute = False;
        self.newFormula(obj) #initialize with a new formula

    def setReadOnly(self,fp,bReadOnly):
        '''if bReadOnly = True, we set the properties linked to the spreadsheet readonly, else set them normal mode'''
        if bReadOnly:
            mode = 1
        else:
            mode = 0
        if not hasattr(fp,"a"):
            return
        fp.setEditorMode('a',mode)
        fp.setEditorMode('b',mode)
        fp.setEditorMode('c',mode)
        fp.setEditorMode('d',mode)
        fp.setEditorMode('X',mode)
        fp.setEditorMode('Y',mode)
        fp.setEditorMode('Z',mode)
        fp.setEditorMode('t',mode)
        fp.setEditorMode('t_max',mode)
        fp.setEditorMode('Interval',mode)

    def readJSONFile(self,fp):
        if not self.checkFile(fp):
            return
        try:
            f = open(fp.File)
        except:
            #could not open file
            #assume user entered name for new file
            f = open(fp.File,"w")
            f.close()
            FreeCAD.Console.PrintMessage("New JSON file created: "+str(os.path.realpath(f.name))+chr(10))
            self.writeJSONFile(fp)
            fp.File = os.path.realpath(f.name)
            return
        self.JSON_Data = json.load(f)
        f.close()
        formula_names = []
        for pn in self.JSON_Data:
            formula_names.append(pn)
        fp.Formulas = formula_names
        #Formulas, when the left hand operand, accepts a list
        #but when the right hand operand, it gives a string, the current formula
        self.bInihibitUpdates=True
        self.updateJSONFormula(fp,fp.Formulas)
        self.bInihibitUpdates=False
    def deleteFormula(self,fp):
        if not fp.FormulaName:
            FreeCAD.Console.PrintError("No formula selected."+chr(10))
            return
        self.JSON_Data.pop(fp.FormulaName,None)
        if len(self.JSON_Data.keys()) == 0:
            FreeCAD.Console.PrintMessage("Must have at least one formula, new one created using existing equations."+chr(10))
            self.newFormula(fp) #must have at least one formula
            FreeCAD.ActiveDocument.recompute()
        fp.Formulas = list(self.JSON_Data.keys())


    def appendFile(self,fp):
        if not self.checkFile(fp):
            return
        try:
            f = open(fp.File)
        except:
            #could not open file
            #assume user entered name for new file
            f = open(fp.File,"w")
            f.close()
            FreeCAD.Console.PrintMessage("New JSON file created: "+str(os.path.realpath(f.name))+""+chr(10))
            self.writeJSONFile(fp)
            fp.File = os.path.realpath(f.name)
            return
        data = json.load(f) #load current data first
        f.close()
        for formula in self.JSON_Data.keys():
            if formula in data: #find a new unique name for this formula and append it
                FreeCAD.Console.PrintWarning("Skipping: "+formula+" (already in file).  Rename "+formula+" and try again, if desired."+chr(10))
            else: #formula not already in data file
                FreeCAD.Console.PrintMessage("Appending: "+formula+" to file."+chr(10))
                data[formula] = self.JSON_Data[formula]

        with open(fp.File,"w") as outfile:
            json.dump(data,outfile)

    def checkFile(self,fp):
        if not fp.File: #checks to see if there is filename in File property
            FreeCAD.Console.PrintError("No linked JSON file.  Create a new JSON file or link one via the File property.  You can also just enter a name in the File property to create a new file."+chr(10))
            return False
        return True
    def writeJSONFile(self,fp):
        if not self.checkFile(fp):
            return
        if self.JSON_Data == {}:
            self.JSON_Data = { #new file, so we just get the one formula
                "formula":{
                "a":fp.a,
                "b":fp.b,
                "c":fp.c,
                "d":fp.d,
                "X":fp.X,
                "Y":fp.Y,
                "Z":fp.Z,
                "t":str(fp.t),
                "t_max":str(fp.t_max),
                "interval":str(fp.Interval)
                }}
        with open(fp.File,"w") as outfile:
            json.dump(self.JSON_Data,outfile)

    def renameFormula(self,fp):
        newName = fp.FormulaName
        if fp.Formulas in self.JSON_Data.keys():
            self.JSON_Data[fp.FormulaName] = self.JSON_Data.pop(fp.Formulas)
            fp.Formulas = list(self.JSON_Data.keys())
            fp.Formulas = newName


    def newFormula(self,fp):

        ii = 1
        trialName = "formula"
        while (trialName in self.JSON_Data):
            ii += 1
            trialName = "formula"+str(ii)

        self.JSON_Data[trialName] ={
                "a":fp.a,
                "b":fp.b,
                "c":fp.c,
                "d":fp.d,
                "X":fp.X,
                "Y":fp.Y,
                "Z":fp.Z,
                "t":str(fp.t),
                "t_max":str(fp.t_max),
                "interval":str(fp.Interval)
                }
        fp.Formulas = list(self.JSON_Data.keys())
        fp.Formulas = trialName
        fp.FormulaName = trialName

    def updateJSON_Data(self,fp,formulaName): #update json data from current fp settings
        if hasattr(fp,"a"):
            self.JSON_Data[formulaName]["a"] = fp.a
        if hasattr(fp,"b"):
            self.JSON_Data[formulaName]["b"] = fp.b
        if hasattr(fp,"c"):        
            self.JSON_Data[formulaName]["c"] = fp.c
        if hasattr(fp,"d"):
            self.JSON_Data[formulaName]["d"] = fp.d
        if hasattr(fp,"X"):
            self.JSON_Data[formulaName]["X"] = fp.X
        if hasattr(fp,"Y"):
            self.JSON_Data[formulaName]["Y"] = fp.Y
        if hasattr(fp,"Z"):
            self.JSON_Data[formulaName]["Z"] = fp.Z
        if hasattr(fp,"t"):
            self.JSON_Data[formulaName]["t"] = str(fp.t)
        if hasattr(fp,"t_max"):
            self.JSON_Data[formulaName]["t_max"] = str(fp.t_max)
        if hasattr(fp,"Interval"):
            self.JSON_Data[formulaName]["interval"] = str(fp.Interval)

    def updateJSONFormula(self,fp,formulaName):
        #FreeCAD.Console.PrintMessage("updateJSONFormula"+chr(10))
        fp.a = self.JSON_Data[formulaName]["a"]
        fp.b = self.JSON_Data[formulaName]["b"]
        fp.c = self.JSON_Data[formulaName]["c"]
        fp.d = self.JSON_Data[formulaName]["d"]
        fp.X = self.JSON_Data[formulaName]["X"]
        fp.Y = self.JSON_Data[formulaName]["Y"]
        fp.Z = self.JSON_Data[formulaName]["Z"]
        fp.t = float(self.JSON_Data[formulaName]["t"])
        fp.t_max = float(self.JSON_Data[formulaName]["t_max"])
        fp.Interval = float(self.JSON_Data[formulaName]["interval"])


    def updateToSpreadsheet(self,fp):
        sheet = None
        if fp.Spreadsheet == None:
            sheet = FreeCAD.ActiveDocument.addObject("Spreadsheet::Sheet","PC_Sheet")
            fp.Spreadsheet = sheet
            FreeCAD.Console.PrintMessage("Spreadsheet linked.\\nSet Use Spreadsheet to True to use those aliases."+chr(10))

        if not hasattr(fp.Spreadsheet,"a_cell"):
            if not sheet and fp.UseSpreadsheet: #not a new spreadsheet, but one already that exists
                from PySide import QtGui
                mw = QtGui.QApplication.activeWindow()
                items = ["Add aliases to spreadsheet","Cancel"]
                item,ok = QtGui.QInputDialog.getItem(mw,"Set aliases","Warning: setting aliases will clobber any existing data in cells A1 - B9.  Set aliases anyway?",items,0)
                if ok and item == items[0]:
                    sheet = fp.Spreadsheet
                else:
                    return

            if sheet:
                fp.Spreadsheet.set('A1',"a_cell")
                fp.Spreadsheet.setAlias('B1',"a_cell")
                fp.Spreadsheet.set('A2',"b_cell")
                fp.Spreadsheet.setAlias('B2',"b_cell")
                fp.Spreadsheet.set('A3',"c_cell")
                fp.Spreadsheet.setAlias('B3',"c_cell")
                fp.Spreadsheet.set('A4',"X")
                fp.Spreadsheet.setAlias('B4',"X")
                fp.Spreadsheet.set('A5',"Y")
                fp.Spreadsheet.setAlias('B5',"Y")
                fp.Spreadsheet.set('A6',"Z")
                fp.Spreadsheet.setAlias('B6',"Z")
                fp.Spreadsheet.set('A7',"t_min")
                fp.Spreadsheet.setAlias('B7',"t_min")
                fp.Spreadsheet.set('A8',"t_max")
                fp.Spreadsheet.setAlias('B8',"t_max")
                fp.Spreadsheet.set('A9',"interval")
                fp.Spreadsheet.setAlias('B9',"interval")
                for dd in range(0,len(fp.d)):
                    fp.Spreadsheet.set('A'+str(dd+10),'d'+str(dd+1))
                    fp.Spreadsheet.setAlias('B'+str(dd+10),'d'+str(dd+1))
        fp.Spreadsheet.set('a_cell',fp.a)
        fp.Spreadsheet.set('b_cell',fp.b)
        fp.Spreadsheet.set('c_cell',fp.c)
        for dd in range(0,len(fp.d)):
            fp.Spreadsheet.set('A'+str(dd+10),'d'+str(dd+1))
            fp.Spreadsheet.setAlias('B'+str(dd+10),'d'+str(dd+1))
            fp.Spreadsheet.set('d'+str(dd+1),fp.d[dd])
        fp.Spreadsheet.set('X',fp.X)
        fp.Spreadsheet.set('Y',fp.Y)
        fp.Spreadsheet.set('Z',fp.Z)
        fp.Spreadsheet.set('t_min',str(fp.t))
        fp.Spreadsheet.set('t_max',str(fp.t_max))
        fp.Spreadsheet.set('interval',str(fp.Interval))


    def updateFromSpreadsheet(self,fp):
        if not fp.Spreadsheet or not hasattr(fp.Spreadsheet,"a_cell"):
            return
        if fp.UseSpreadsheet == False:
            self.setReadOnly(fp,False)
            return
        else:
            self.setReadOnly(fp,True)
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Update from Spreadsheet")

        fp.a=str(fp.Spreadsheet.a_cell)
        fp.b=str(fp.Spreadsheet.b_cell)
        fp.c=str(fp.Spreadsheet.c_cell)
        dd=0
        k = "d"+str(dd+1)
        new_d = []
        while hasattr(fp.Spreadsheet,k):
            new_d.append(str(getattr(fp.Spreadsheet,k)))
            k = "d"+str(dd+1)
            dd += 1
        fp.d = new_d
        fp.X=str(fp.Spreadsheet.X)
        fp.Y=str(fp.Spreadsheet.Y)
        fp.Z=str(fp.Spreadsheet.Z)
        fp.t=fp.Spreadsheet.t_min 
        fp.t_max=fp.Spreadsheet.t_max
        fp.Interval=fp.Spreadsheet.interval

        if fp.FormulaName:
            self.bInihibitUpdates=True
            self.updateJSONFormula(fp,fp.FormulaName)
            self.bInihibitUpdates=False
        doc.commitTransaction()
    def onChanged(self, fp, prop):
        '''Do something when a property has changed'''
        doc = FreeCAD.ActiveDocument
        #FreeCAD.Console.PrintMessage("Change property: " + str(prop) + ""+chr(10))
        if prop == "Spreadsheet" and fp.Spreadsheet != None:
            self.updateFromSpreadsheet(fp)

        elif prop == "UseSpreadsheet" and fp.UseSpreadsheet == True:
            if not fp.Spreadsheet:
                FreeCAD.Console.PrintError("No spreadsheet linked.\\n  Create one with Update Spreadsheet or link existing one first."+chr(10))
            self.setReadOnly(fp, True)
        elif prop == "UseSpreadsheet" and fp.UseSpreadsheet == False:
            self.setReadOnly(fp,False)
        elif prop == "Spreadsheet" and fp.Spreadsheet == None: #user removed link to Spreadsheet
            self.setReadOnly(fp,False)

        elif prop == "UpdateSpreadsheet" and fp.UpdateSpreadsheet == True:
            doc.openTransaction("Update to Spreadsheet")
            self.bInhibitRecompute = True
            self.updateToSpreadsheet(fp)
            fp.UpdateSpreadsheet = False
            doc.commitTransaction()

        elif prop == "File" and fp.File != None:
            #self.readJSONFile(fp)
            FreeCAD.Console.PrintMessage("File linked.\\n\
Use Read File to import into object.\\n\
Use Append File to append formulas to file.\\n\
Use Write File to overwrite all data in file.\\n\
Use Open File to open file in external editor.\\n\
")

        elif prop == "Formulas" and fp.File != None:
            self.bInihibitUpdates = True
            self.updateJSONFormula(fp,fp.Formulas)
            self.bInihibitUpdates = False
            fp.FormulaName = fp.Formulas

        elif prop == "WriteFile" and fp.File != None and fp.WriteFile == True:
            self.bInhibitRecompute = True
            self.writeJSONFile(fp)
            fp.WriteFile = False
        elif prop == "RenameFormula" and fp.RenameFormula == True and fp.File != None:
            doc.openTransaction("Rename formula")
            self.bInhibitRecompute = True
            self.renameFormula(fp)
            fp.RenameFormula = False
            doc.commitTransaction()
        elif prop == "NewFormula" and fp.NewFormula == True:
            doc.openTransaction("Create new formula")
            self.bInhibitRecompute = True
            self.newFormula(fp)
            fp.NewFormula = False
            doc.commitTransaction()
        elif prop == "OpenFile" and fp.OpenFile == True:
            fp.OpenFile = False
            self.bInhibitRecompute = True
            sys = platform.system()
            if fp.File:
                if 'Windows' in sys:
                    import webbrowser
                    webbrowser.open(fp.File)
                elif 'Linux' in sys:
                    os.system("xdg-open '%s'" % fp.File)
                elif 'Darwin' in sys:
                    subprocess.Popen(["open", fp.File])
                else:
                    FreeCAD.Console.PrintError("We were unable to determine your platform, and thus cannot open your file for you."+chr(10))
 
        elif prop == "ReadFile" and fp.ReadFile == True:
            fp.ReadFile = False
            doc.openTransaction("Read file")
            if fp.File:
                self.readJSONFile(fp)
            doc.commitTransaction()
        elif prop == "AppendFile" and fp.AppendFile == True:
            fp.AppendFile = False
            self.bInhibitRecompute = True
            self.appendFile(fp)
        elif prop == "DeleteFormula" and fp.DeleteFormula == True:
            doc.openTransaction("Delete formula")
            fp.DeleteFormula = False
            self.deleteFormula(fp)
            doc.commitTransaction()
        elif prop == "a" or prop == "b" or prop == "c" or prop == "d" or prop == "X" or prop == "Y" or prop == "Z" or prop == "t" or prop == "t_max" or prop == "Interval":
            if fp.FormulaName and not self.bInihibitUpdates:
                self.updateJSON_Data(fp,fp.Formulas) #update self.JSON_Data on every property change

    def makeCurve(self, fp):
        self.updateFromSpreadsheet(fp)
        vars = {"a":0,"b":0,"c":0,"X":0,"Y":0,"Z":0,"t":0}

        fa = fp.a
        fb = fp.b
        fc = fp.c
        fx = fp.X
        fy = fp.Y
        fz = fp.Z
        t = fp.t
        tf = fp.t_max
        intv = fp.Interval
        increment=(tf-t)/intv
        matriz = []
        for i in range(int(increment)):

            try:
                vars["t"] = t
                value="a ->"+str(fa)
                a=evaluate(fa,vars)
                vars["a"]=a
                value="b ->"+str(fb)
                b=evaluate(fb,vars)
                vars["b"] = b
                value="c ->"+str(fc)
                c=evaluate(fc,vars)
                vars["c"]=c
                for dd in range(0,len(fp.d)):#fp.d[0] = d1, fp.d[1] = d2, etc
                    k = "d"+str(dd+1)# where dd = 0, k = "d1"
                    value = k+" ->"+str(fp.d[dd])
                    vars[k] = evaluate(fp.d[dd],vars)
                value="X ->"+str(fx)
                fxx=evaluate(fx,vars)
                vars["X"]=fxx
                value="Y ->"+str(fy)
                fyy=evaluate(fy,vars)
                vars["Y"]=fyy
                value="Z ->"+str(fz)
                fzz=evaluate(fz,vars)
                vars["Z"]=fzz
            except ZeroDivisionError:
                FreeCAD.Console.PrintError("Error division by zero in calculus of "+value+"() for t="+str(t)+" !")
            except:
                FreeCAD.Console.PrintError("Error in the formula of "+value+"() !")

            matriz.append(FreeCAD.Vector(fxx,fyy,fzz))
            t+=intv
        if fp.ShapeType == "Polygon" and fp.Closed == True:
            matriz.append(matriz[0])
        fp.Points = matriz
        curva = Part.makePolygon(matriz)
        if fp.ShapeType == "BSpline":
            curve = Part.BSplineCurve()
            curve.interpolate(matriz, PeriodicFlag=fp.Closed)
            return curve.toShape()
        elif fp.ShapeType == "Polygon":
            return curva
        else: #fp.ShapeType == "Points":
            vertices = [Part.Vertex(p) for p in fp.Points]
            comp = Part.Compound(vertices)
            return comp


    def execute(self, fp):
        '''Do something when doing a recomputation, this method is mandatory'''
        if self.bInhibitRecompute: #some things do not require a recompute, such as saving to JSON file or updating spreadsheet
            self.bInhibitRecompute = False
            return
        fp.Shape = self.makeCurve(fp)
        if hasattr(fp.Shape,"Continuity"):
            fp.Continuity = fp.Shape.Continuity
        else:
            fp.Continuity = "N/A"
        #FreeCAD.Console.PrintMessage("Recompute Python Curve feature"+chr(10))

class CurveVP:
    '''Creates a 3D parametric curve'''
    def __init__(self, obj):
        '''Set this object to the proxy object of the actual view provider'''
        obj.Proxy = self
 
    def attach(self, obj):
        '''Setup the scene sub-graph of the view provider, this method is mandatory'''
        self.Object = obj.Object
 
    def updateData(self, fp, prop):
        '''If a property of the handled feature has changed we have the chance to handle this here'''
        # fp is the handled feature, prop is the name of the property that has changed
        pass
 
    def getDisplayModes(self,obj):
        '''Return a list of display modes.'''
        modes=[]
        modes.append("Flat Lines")
        return modes
 
    def getDefaultDisplayMode(self):
        '''Return the name of the default display mode. It must be defined in getDisplayModes.'''
        return "Flat Lines"
 
    def setDisplayMode(self,mode):
        '''Map the display mode defined in attach with those defined in getDisplayModes.\
                Since they have the same names nothing needs to be done. This method is optional'''
        return mode
 
    def onChanged(self, vp, prop):
        '''Here we can do something when a single property got changed'''
        #FreeCAD.Console.PrintMessage("Change property: " + str(prop) + ""+chr(10))

 
    def getIcon(self):
        '''Return the icon in XPM format which will appear in the tree view. This method is\
                optional and if not defined a default icon is shown.'''
        return '''
/* XPM */
static char *_ce4cf5b663f4b5f9c7b8e8d0afb135esksMX5u0XGPbxtkI[] = {
/* columns rows colors chars-per-pixel */
"64 64 202 2 ",
"   c #EA0004",
".  c #EB030C",
"X  c #EC0C0D",
"o  c #EB0610",
"O  c #EB0B13",
"+  c #EB0D19",
"@  c #EC1214",
"#  c #ED1B17",
"$  c #EC141C",
"%  c #EC1A1F",
"&  c #EC1720",
"*  c #EC1B23",
"=  c #EC1B2C",
"-  c #EB1A30",
";  c #EE2321",
":  c #ED2A38",
">  c #EF3534",
",  c #EF3834",
"<  c #ED2E41",
"1  c #EE3041",
"2  c #EF424A",
"3  c #F1474A",
"4  c #F04D56",
"5  c #F25559",
"6  c #F05463",
"7  c #F15C6A",
"8  c #F3666B",
"9  c #F26674",
"0  c #F36C78",
"q  c #F57B75",
"w  c #1B8939",
"e  c #3AA657",
"r  c #3DAE5A",
"t  c #2DBA52",
"y  c #35B255",
"u  c #34B857",
"i  c #3AB45A",
"p  c #3BBB5D",
"a  c #44A85E",
"s  c #45AE61",
"d  c #4CAF66",
"f  c #54A469",
"g  c #5AA66D",
"h  c #53AF6B",
"j  c #44B462",
"k  c #49B365",
"l  c #44BD63",
"z  c #4BBC69",
"x  c #53B16C",
"c  c #5DAC72",
"v  c #5CB473",
"b  c #58BA72",
"n  c #66A577",
"m  c #63AD76",
"M  c #69A779",
"N  c #65AE79",
"B  c #6BAC7C",
"V  c #62B377",
"C  c #65B179",
"Z  c #65B97C",
"A  c #39C65E",
"S  c #3EC461",
"D  c #3DCB62",
"F  c #3DD464",
"G  c #3FDA67",
"H  c #3BE668",
"J  c #41CA65",
"K  c #4CC56C",
"L  c #45CD69",
"P  c #4BCB6D",
"I  c #50C36F",
"U  c #43D268",
"Y  c #46D36B",
"T  c #43DC6B",
"R  c #48DB6E",
"E  c #57C474",
"W  c #4EDC73",
"Q  c #54DA77",
"!  c #43E36D",
"~  c #42EB6E",
"^  c #4BE473",
"/  c #46EE72",
"(  c #4AEC74",
")  c #4FEF79",
"_  c #51E979",
"`  c #45F473",
"'  c #49F476",
"]  c #43FE75",
"[  c #4DF378",
"{  c #47FE79",
"}  c #4DFD7C",
"|  c #53F57D",
" . c #51FD7F",
".. c #F27080",
"X. c #F47C8B",
"o. c #7B9B83",
"O. c #7CA486",
"+. c #73AC82",
"@. c #79AC86",
"#. c #7CAD89",
"$. c #6EBA82",
"%. c #79B087",
"&. c #55FF84",
"*. c #59FF87",
"=. c #5EFF89",
"-. c #60FF8C",
";. c #85A58D",
":. c #82AC8D",
">. c #80B18D",
",. c #87AC91",
"<. c #8BAD94",
"1. c #93A798",
"2. c #93AD9A",
"3. c #99AE9E",
"4. c #86B392",
"5. c #8CB296",
"6. c #8FB399",
"7. c #92B19A",
"8. c #97B49F",
"9. c #9DAAA0",
"0. c #9DB3A3",
"q. c #9AB9A2",
"w. c #A3ACA5",
"e. c #ABAEAC",
"r. c #B1ABAF",
"t. c #A2B2A6",
"y. c #A5B3A9",
"u. c #ABB3AD",
"i. c #A4BBAA",
"p. c #B3ABB1",
"a. c #BFACBA",
"s. c #AFB3B0",
"d. c #B4B3B4",
"f. c #B9B2B7",
"g. c #BDB5BA",
"h. c #B7BCB8",
"j. c #F68785",
"k. c #F58A8D",
"l. c #F58A93",
"z. c #F69495",
"x. c #F79993",
"c. c #F6939C",
"v. c #F9A69E",
"b. c #F59AA7",
"n. c #C1B5BD",
"m. c #F8A4A6",
"M. c #F7A1AB",
"N. c #F8AAAD",
"B. c #FAB6AD",
"V. c #F9B4B4",
"C. c #FBBCB7",
"Z. c #FABDBC",
"A. c #BAC0BC",
"S. c #B5C8BA",
"D. c #FBC2BA",
"F. c #CEB3C7",
"G. c #CCB5C6",
"H. c #C6BAC3",
"J. c #CABCC6",
"K. c #CEBDCA",
"L. c #F8BAC9",
"P. c #C4C4C4",
"I. c #CDC6CB",
"U. c #D2C3CE",
"Y. c #D0CBCF",
"T. c #C6D0C9",
"R. c #D8C4D3",
"E. c #D4CBD2",
"W. c #DACAD6",
"Q. c #DDCDD9",
"!. c #DAD5D8",
"~. c #FAC6C8",
"^. c #FCD7CD",
"/. c #E2C5DA",
"(. c #E0CDDB",
"). c #FBCED2",
"_. c #E3D1DE",
"`. c #FDDBD3",
"'. c #FEE6DC",
"]. c #E6D2E1",
"[. c #E9D5E4",
"{. c #E6DBE3",
"}. c #ECDCE8",
"|. c #FBDAE4",
" X c #F3DDED",
".X c #FCDFEA",
"XX c #F7DEF0",
"oX c #EEE5EC",
"OX c #FEE8E2",
"+X c #F2E1EE",
"@X c #FEF3EA",
"#X c #F6E3F1",
"$X c #FAE6F4",
"%X c #F3EEF2",
"&X c #FBEAF4",
"*X c #FFEDFC",
"=X c #FEF3F3",
"-X c #FFFDF6",
";X c #FEF3FD",
":X c #FFFAFF",
">X c #FFFEFF",
",X c white",
/* pixels */
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X:X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X5.t q.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xn.{ -./ E.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xi.V E.,X,X,X,X,X,X,Xk =.-.=.c ,X,X,X,X,X,X,XP.m S.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X[.H =.H t.,X,X,X,X,XU.' =.=.-.~ _.,X,X,X,X,X7.` =.A *X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xe.&.-.-.} 3.,X,X,X,X@.*.=.-.=.*.5.,X,X,X,X<.} -.=. .n.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xu.&.=.=.=.' h.,X,X:XS =.=.&.=.=.j ,X,X,X0.{ -.-.=.&.y.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xw.&.=.=.=.=.` h.,Xe.&.-.Q e.W =.&.f.,Xt.{ -.=.=.-.&.t.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xe.&.=.=.&.*.=.' +._ =./ W.,Xn.} -.Q B  .-.&. .-.-. .f.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,XI.J.:X,X,X,X,X,Xu.&.=.E F.B &.=.=.=.=.c ,X,X,Xx =.=.=.-.} @.F.I =.&.g.,X,X,X,X,X,XH.W.,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,Xi.` } p :.].,X,X,Xs.&.*.0.,X,X2.{ -.-.&.e.,X,X,Xy.&.=.=.' 3.,X,X5.&.&.n.,X,X,XW.#.p } H h.,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X%.=.=.=.*.! N K.,X0.&.&.d.,X,X,X;.&.-.i ,X,X,X,X*XD -.} 1.,X,X,Xu.&.&.w.,XJ.c / *.-.-.*.5.,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,Xt.&.=.=.-.=.=.[ r ) =.&.f.,X,X,X,X@.] ;.,X,X,X,X,X@.] 5.,X,X,X,Xu.&.=._ i  .*.-.-.=.=.&.r.,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X+XG =.-.-.*.&.=.-.=.=.&.f.,X,X,X,X,Xf.,X,X,X,X,X,X:Xg.,X,X,X,X,Xu.&.=.=.-.*.&.*.-.=.-.D :X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,XN =.-.&.;.0.c ~ *.-.&.0.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X1.*.-.*.! n t.#.&.-.*.@.,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,Xn.} -.A :X,X,X_.@.D { p.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xe.{ S :._.,X,X.XT -./ W.,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,Xx =.( _.,X,X,X,X#Xp.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xp.*X,X,X,X,XK. .=.c ,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,Xt.&.&.2.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X#.*.&.d.,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,Xa.&.=.l ,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X*XJ -.} K.,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X{.B j j j j j s ^ =.=.&.d.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X0.&.-.-.R j j j j j k B oX,X,X,X",
",X,X,X,Xy =.=.-.=.-.-.-.-.-.=.=.v ,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xk -.=.-.-.-.=.=.-.=.=.*.k ,X,X,X",
",X,X,X,Xx =.-.=.=.=.[ p i i i u n ,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xf u i i i p &.=.=.-.=.*.m ,X,X,X",
",X,X,X,X_.! =.-.=.^ J.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xf.) -.=.=.F  X,X,X,X",
",X,X,X,X,XP.~ =.-.S :X,X,X,X,X,X,X,X,X,X&X5 > : B.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,XXXT -.-.! !.,X,X,X,X",
",X,X,X,X,X,XP.~ -.*.@.,X,X,X,X,X,X,X,X|.  $ $ o x.,X,X,Xl.2 1 @X,X,X,X,X,X,X,X,X,X,X4 2 4 ,X,X,X,X,X,X,X,X,XM =.=.! E.,X,X,X,X,X",
",X,X,X,X,X,X,XA.` =.&.;.,X,X,X,X,X,X,X: $ * %   z.,X,X&X  O 4 ,X,X,X,X,X,X,X,X,X,X,Xb.. . v.,X,X,X,X,X,X,Xo.&.-.~ Y.,X,X,X,X,X,X",
",X,X,X,X,X,X,X,Xd. .=.} 7.,X,X,X,X,X,X  * % > N.Z.,X,X7 $ . ^.,X,X,X,X,X,X,X,X,X,X,X,X+ % @ ,X,X,X,X,X,X@.&.=.( P.,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,Xp -.-.{ q.,X,X,X,X$X. * o ~.,X,X,X,X. $ % ,X,X,X,X,X,X,X,X,X,X,X,X,X9 $ . B.,X,X,X,X:.&.=.=.j ,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X:Xu.z -.-.=.*.e ,X,X,X).c.+ * @ j.m.=X,Xb.O + q ,X|.m.N.m.).,X,XM.N.N.B.,XL.o $ 5 ,X,X,X,Xt *.-.-.=.x f.,X,X,X,X,X,X",
",X,X,X,XQ.#.p &.=.=.&.p ,.$X,X,X,X9 . * * * @   `.,X6 $ O D.,X,X  O O O ,X|.  O   x.,X,X  % X ,X,X,X,X X@.S &.=.=.&.p <.[.,X,X,X",
",X,X*XM / *.-.-.&.h d.,X,X,X,X,X,X0 O * * * %   `.,X= & . @X,X,XX.O * o '.X.@ % ; ,X,X,X- * . @X,X,X,X,X,X:Xw.x &.=.-.*.G +.:X,X",
",X:Xz *.=.=.-.&.<.,X,X,X,X,X,X,X,Xc.2 $ * * 2 2 OX,X. * . ,X,X,X,Xo * $ q : & . D.,X,X,X4 $ o Z.,X,X,X,X,X,X,X,X>.*.-.-.-.*.b ,X",
",X_.H -.=.-.-.[ W.,X,X,X,X,X,X,X,X,X;Xo * o ~.,X,X&X. * @ ,X,X,X,XX.O * * * % > ,X,X,X,X7 $ O V.,X:X,X,X,X,X:X,XK.r k k k z w :X",
",X,Xq.H *.-.=.=.P g.,X,X,X,X,X,X,X,X.X. * o C.,X,X&X. % ; ,X,X,X,X,X+ * * * o `.,X:X,X:X9 + O V.,X,X,X,X,X,X,Xs.W =.-.-.=.H S.,X",
",X,X,XQ.B F &.=.-. .h 9.*X,X,X,X,X,X.X. ; O C.,X,X&X. * # ,X,X,X,X,XO * * * + j.,X,X,X,X8 $ O V.,X,X:X,X$X9.k &.=.=.*.F B }.,X,X",
",X,X,X,X,X#X2.j  .-.=.&.D 8.,X,X,X,X#X. * o C.,X,X:X. % . ,X,X,X,X..O * $ * * . ,X,X:X,X6 + O V.,X,X,X4.F &.=.-.} d 0.#X:X,X,X,X",
",X,X,X,X,X,X,X,Xs.) -.=.=.e ,X,X,X,X.X. * O Z.,X,X,X+ % . -X,X,X,X. * $ j.O * O x.,X,X,X< * . ^.,X,X,Xy =.=.=.^ g.,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X;XJ -.=.Y #X,X,X,X,X#X. * O C.,X,X,X< $ O ^.,X,X9 O *   ,X= * * @ ,X:X,X. *   ,X,X,X,X{.T =.=.l ,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,Xv =.=.K +X,X,X,X,X,X|.  O   V.,X,X,XX.@ O k.,X=X  O . 3 :Xl.  O   x.,X).. & > ,X,X,X,X,X{.J =.*.C ,X,X,X,X,X,X,X",
",X,X,X,X,X,X:Xv *.=.J *X,X,X,X,X,X,X=Xk.z.k.'.,X,X,X|.. % > ,X~.k.z.l.`.,X=Xk.c.l.m.,Xk.+ O j.,X,X,X,X,X,X XU =.&.B ,X,X,X,X,X,X",
",X,X,X,X,X,XZ &.=.| J.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X< % . @X,X,X,X:X,X:X,X,X,X:X,X,X= %   ,X,X,X,X,X,X,X,Xd.&.=.&.C ,X,X,X,X,X",
",X,X,X,X,XV &.=.-.y ,X,X,X:X,X,X,X,X,X,X,X,X,X,X,X,X,X~.  O 8 ,X,X,X,X,X,X,X,X,X,X,XL.. O q ,X,X,X,X,X,X,X,X;XD -.-.*.B ,X,X,X,X",
",X,X,X,X2.&.-.=.-.=.v 0.0.t.0.0.!.,X,X,X,X,X,X,X,X,X,X,X6 * o =X,X,X,X,X,X,X,X,X,X,X: $ * :X,X:XY.0.0.t.t.3.f =.=.-.=.} t.,X,X,X",
",X,X,X,Xu -.=.-.=.-.*.*.&.&.&.&.r ,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X:X,X,X:X:X,X,X:X,X,X,X,X,X,X,X,Xt &.*.&.&.&.=.=.-.=.=.-.j ,X,X,X",
",X,X,X,X+.~ &.&.&.&.&.&.*.=.-.*.:.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X:X,X,X,X,X:X,X,X,X:X,X,X,XB =.=.=.*.&.&.&.*.&.&.~ 5.,X,X,X",
",X,X,X,X,XW.e.t.t.0.s.p.$.=.=.! [.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,XU./ =.=.@.u.y.t.w.0.u.Q.,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,XG. .*.V ,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X:X,X,X,X:X,Xh =.} /.,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X@.*.&.p.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X:X,X,X:X:X,X,X:X,X:X,X,X,X:X,X,X,Xe.&.&.5.,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X*XD -.A ;X,X,X,X XO.s oX,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X!.s <.$X,X,X,X[.! -.S :X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X7.*.-.R  X,XG.+.T *.&.w.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X8.&.*.U #.K.,XR.( -.&.w.,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,Xj -.=.-.L i } *.-.=.&.d.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xw.&.-.-.*.} r Y -.-.=.h ,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,XH. .=.-.=.-.-.=.*.=.=.&.f.,X,X,X,X}.a !.,X,X,X,X:XT.a $X,X,X,X,Xu.&.=.=.*.=.-.=.-.-.=.' U.,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X4.*.=.-.-.*./ c y.Z =.&.f.,X,X,X XU =.f ,X,X,X,X,Xa *.P $X,X,X,Xu.&.=.$.t.h } =.=.=.=.&.0.,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X@.&.*.&.U B W.,X,Xu.&.&.u.,X,X XY =.=.H ].,X,X,XU.' =.=.P *X,X,Xt.&. .g.,X,XJ.m T &.=.&.6.,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X%Xm V 2.+X,X,X,X,Xu.&.*.#.,X[.Y =.=.=.*.6.,X,X,X@.*.=.-.=.K  X,XB *. .n.,X,X,X:X}.2.V c =X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xu.&.-.| c ! =.=.[ =.=.l :X,X*XJ =.*.[ =.-.R g | =. .n.,X:X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xy.&.=.-.=.=.=.E /.Z =.*.,.,X+.*.*.%./.K =.=.=.=.=.&.y.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X6.*.=.=.=.*.I ;X,X(./ -.&.e *.-.G #X,X*XP =.=.-.=.&.t.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xu.&.=.=.=.I *X,X,X,Xh =.=.-.-.=.N ,X,X:X$XP =.=.-.&.d.,X:X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xf.&.=.*.K *X,X,X,X,Xw.*.=.=.=. .d.,X,X,X,X#XL =.-.' R.,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,Xj ` g *X,X,X,X,X,X*XA -.=.=.p :X,X,X,X,X,X+Xh { d ,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X&XU.,X,X,X,X,X,X,X,X#.&.=.&.2.,X,X,X,X,X,X,X,XK.;X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X*XJ *.l :X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X",
",X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,XoX5.*X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X,X"
};

'''
 
    def __getstate__(self):
        '''When saving the document this object gets stored using Python's json module.\
                Since we have some un-serializable parts here -- the Coin stuff -- we must define this method\
                to return a tuple of all serializable objects or None.'''
        return None
 
    def __setstate__(self,state):
        '''When restoring the serialized object from document we have the chance to set some internals here.\
                Since no data were serialized nothing needs to be done here.'''
        return None
#########
"""
#########
#this is a workaround for getting a feature python object created in a macro to be still parametric
#upon reloading the file to which the object was saved after restarting FreeCAD
#the usual way is to create 2 files, one to import the class and instantiate the object, the other the object class
#but with this workaround call can be included in the same file, we just need to "import" the code as a string
#first step is to enclose all the code to be imported inside a triple double quote literal """many lines of code"""
#replace any instances of """ with ''' inside the string literals
#any instances of "\n" must be replaced with chr(10) or, alternatively "\\n" but the later makes it harder to
#debug the code by commenting out the workaround bits and running as normal code for debugging
#copy and modify the code below, replacing instances of Parametric_Curve_FP with the name of your .py file

#credit to Mila Nautikus for his answer to a question on stackoverflow, which I modified here
#in this example the filename is Parametric_Curve_FP.py
#https://stackoverflow.com/questions/5362771/how-to-load-a-module-from-code-in-a-string

##########
import sys, importlib

my_name = 'Parametric_Curve_FP' #filename = Parametric_Curve_FP.py, so this must be 'Parametric_Curve_FP'
my_spec = importlib.util.spec_from_loader(my_name, loader=None)

Parametric_Curve_FP = importlib.util.module_from_spec(my_spec)

exec(my_code, Parametric_Curve_FP.__dict__)
sys.modules['Parametric_Curve_FP'] = Parametric_Curve_FP
##########


def makeCurve():
    sheet = None
    sel = FreeCADGui.Selection.getSelection()
    if sel and "Spreadsheet" in str(type(sel[0])):
        sheet = sel[0]
    if not FreeCAD.ActiveDocument:
        FreeCAD.newDocument()
    pc=FreeCAD.ActiveDocument.addObject("Part::FeaturePython","ParametricCurve")

##########
    Parametric_Curve_FP.Curve(pc)
    Parametric_Curve_FP.CurveVP(pc.ViewObject)
    #Curve(pc)
    #CurveVP(pc.ViewObject)
#########

    FreeCAD.ActiveDocument.recompute()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(FreeCAD.ActiveDocument.Name,pc.Name)
    if sheet:
        pc.Spreadsheet = sheet
    else:
        FreeCADGui.SendMsgToActiveView("ViewSelection")

if __name__ == "__main__":
    makeCurve()