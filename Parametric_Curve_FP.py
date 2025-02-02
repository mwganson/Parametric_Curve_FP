# -*- coding: utf-8 -*-
__version__ = "2025.01.28b"
__title__ = "Parametric_Curve_FP"
__author__ = "<TheMarkster> 2021, based on macro 3D Parametric Curve by Gomez Lucio,  Modified by Laurent Despeyroux on 9th feb 2015"
__license__ = "LGPL 2.1"
__doc__ = "Parametric curve from formula"
__usage__ = '''Activate the tool and modify properties as desired'''


import FreeCAD, FreeCADGui
from pivy import coin
from math import *
import statistics
import Part
import json
import os, sys
import subprocess, os
import platform
import re
from PySide import QtGui,QtCore


# Albert Einstein once remarked how he "stood on the shoulders of giants" in giving credit to those
# great thinkers who came before him and who helped pave the way for his Theory of Relativity.
# I'm certainly no Einstein, but in making this macro, I, too, have built upon the work of others
# who came before.  Thanks, in particular, to Gomez Lucio, author of the original parametric curve
# macro, and to Laurent Despeyroux, who extended it, and Paul McGuire for his work on FourFn parser.
# Also thanks to users openBrain and edwilliams16 of the FreeCAD forum for their help with regular
# expression parsing and testing / debugging / helping with other coding aspects.

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
# Removed unnecessary expr.suppress() call (thanks Nathaniel Peterson!), and added pyparsing.Group
# Changed fnumber to use a pyparsing.Regex, which is now the preferred method
# Reformatted to latest pypyparsing features, support multiple and variable args to functions
#
# Copyright 2003-2019 by Paul McGuire
#
# ------- added by <TheMarkster> -- to fix conflict with another addon
syspath = sys.path
newsyspath = [sp for sp in sys.path if not "cadquery" in sp]
sys.path = newsyspath
import pyparsing
import importlib
importlib.reload(pyparsing)
#-------------
#from pyparsing import (
#    pyparsing.Literal,
#    pyparsing.Word,
#    pyparsing.Group,
#    pyparsing.Forward,
#    pyparsing.alphas,
#    pyparsing.alphanums,
#    pyparsing.Regex,
#    pyparsing.ParseException,
#    pyparsing.CaselessKeyword,
#    pyparsing.Suppress,
#    pyparsing.delimitedList,
#)
#----------------
sys.path = syspath
# ------- end <TheMarkster> code
import math
import operator

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
        # use pyparsing.CaselessKeyword for e and pi, to avoid accidentally matching
        # functions that start with 'e' or 'pi' (such as 'exp'); Keyword
        # and pyparsing.CaselessKeyword only match whole words
        e = pyparsing.CaselessKeyword("E")
        pi = pyparsing.CaselessKeyword("PI")
        # fnumber = Combine(pyparsing.Word("+-"+nums, nums) +
        #                    Optional("." + Optional(pyparsing.Word(nums))) +
        #                    Optional(e + pyparsing.Word("+-"+nums, nums)))
        # or use provided pyparsing_common.number, but convert back to str:
        # fnumber = ppc.number().addParseAction(lambda t: str(t[0]))
        #fnumber = pyparsing.Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
        fnumber = pyparsing.Regex(r'[-+]?(?:(?:\d*\.\d+)|(?:\d+\.?))(?:[Ee][+-]?\d+)?')
        ident = pyparsing.Word(pyparsing.alphas, pyparsing.alphanums + "_$")

        plus, minus, mult, div = map(pyparsing.Literal, "+-*/")
        lpar, rpar = map(pyparsing.Suppress, "()")
        addop = plus | minus
        multop = mult | div
        expop = pyparsing.Literal("^")

        expr = pyparsing.Forward()
        expr_list = pyparsing.delimitedList(pyparsing.Group(expr))
        # add parse action that replaces the function identifier with a (name, number of args) tuple
        def insert_fn_argcount_tuple(t):
            fn = t.pop(0)
            num_args = len(t[0])
            t.insert(0, (fn, num_args))

        fn_call = (ident + lpar - pyparsing.Group(expr_list) + rpar).setParseAction(
            insert_fn_argcount_tuple
        )
        atom = (
            addop[...]
            + (
                (fn_call | pi | e | fnumber | ident).setParseAction(push_first)
                | pyparsing.Group(lpar + expr + rpar)
            )
        ).setParseAction(push_unary_minus)

        # by defining exponentiation as "atom [ ^ factor ]..." instead of "atom [ ^ atom ]...", we get right-to-left
        # exponents, instead of left-to-right that is, 2^3^2 = 2^(3^2), not (2^3)^2.
        factor = pyparsing.Forward()
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
    "sinh": math.sinh,
    "cos": math.cos,
    "cosh": math.cosh,
    "tan": math.tan,
    "tanh": math.tanh,
    "exp": math.exp,
    "atan": math.atan,
    "atanh": math.atanh,
    "acos": math.acos,
    "acosh": math.acosh,
    "asin": math.asin,
    "asinh": math.asinh,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
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
    "copysign": lambda a, b: 1 * (math.copysign(a,b)),
    "multiply": lambda a, b: a * b,
    "mod": lambda a, b: a % b,
    "interval": lambda a, b, t: 1 * ((t >= a) and (t < b)),
    "lt":lambda a, b: 1 * (a < b),
    "lte": lambda a, b: 1 * (a <= b),
    "gt": lambda a, b: 1 * (a > b),
    "gte": lambda a, b: 1 * (a >= b),
    "isequal": lambda a, b: 1 * (a == b),
    "isclose": lambda a, b: 1 * (math.isclose(a, b, abs_tol = 1e-9)),
    "isclosetol": lambda a, b, tol: 1 * (math.isclose(a, b, abs_tol = tol)),
    "floordiv": lambda a, b: a // b,
    "atan2": lambda a, b: math.atan2(a, b),
    "perm": lambda a, b: math.perm(a, b),
    "hypot": math.hypot,
    "ternary": lambda a, b, c: b if a else c,
    # functions with a variable number of arguments
    "any": lambda *a: 1 * any(a),
    "all": lambda *a: 1 * all(a),
    "sum": lambda *a: sum(a),
    "avg": lambda *a: sum(a)/float(len(a)),
    "mean": lambda *a: sum(a)/float(len(a)),
    "gmean": lambda *a: statistics.geometric_mean(a),
    "hmean": lambda *a: statistics.harmonic_mean(a),
    "mode": lambda *a: statistics.mode(a),
    "median": lambda *a: statistics.median(a),
    "stdev": lambda *a: statistics.stdev(a),
    "prod": lambda *a: math.prod(a),
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

# vars is a dictionary of variable names
# example:
# vars = {"a":1,"b":2}
# then where "a" or "b" is found a value is substituted
# evaluate("a+b",vars) thus returns 3 --Mark

def evaluate(s, vars={}):
    if s == "": #return 0 in case the user has left the field blank --Mark
        return 0
    s= checkForFCEval(s)


    exprStack[:] = []
    try:
        results = BNF().parseString(s, parseAll=True)
        val = evaluate_stack(exprStack[:],vars)
    except pyparsing.ParseException as pe:
        raise Exception(s, "failed parse:", str(pe))
    except Exception as e:
        raise Exception (s, "failed eval:", str(e), exprStack)
    else:
        return val

# implement FreeCAD.DocumentObject.evalExpression(str)
# usage: fc(freecad_expression_string)

def checkForFCEval(s):
    if "fc(" in s:
        idx = s.index("fc(")
        idx2 = s.index(")",idx)+1
        fc_Total = s[idx:idx2] #example fc(dd.ddFloat)
        fc_Eval = fc_Total[3:-1] # example dd.ddFloat
        if "fc(" in fc_Eval:
            FreeCAD.Console.PrintError("ParametricCurve::Unsupported -- Nested fc(expr) functions not supported.\n")
        evaluated = FreeCAD.ActiveDocument.Objects[0].evalExpression(fc_Eval)
        evaluated = evaluated.Value if hasattr(evaluated,"Value") else evaluated
        s = s.replace(fc_Total,str(evaluated))
        return checkForFCEval(s) #in case there are multiple fc(expr) calls in the same string
    else:
        return s

# <end imported code from FourFn.py>


class Curve:
    def __init__(self, obj):
        obj.addExtension("Part::AttachExtensionPython")
        obj.addProperty("App::PropertyLinkList","Dependencies","Curve",
"If using fc(expr) to link to another object, add the object to these links to force parametric recomputes when that object changes")
        obj.addProperty("App::PropertyString","a","Equation1(a,b,c)","a(t)").a="6"
        obj.addProperty("App::PropertyString","b","Equation1(a,b,c)","b(a,t)").b="1"
        obj.addProperty("App::PropertyString","c","Equation1(a,b,c)","c(a,b,t)").c="20"
        obj.addProperty("App::PropertyStringList","d","Equation1(a,b,c)","d1(a,b,c,t)"+chr(10)+"d2(a,b,c,t,d1)"+chr(10)+"d3(a,b,c,t,d1,d2)"+chr(10)+"d4(a,b,c,t,d1,d2,d3)"+chr(10)+"..."+chr(10))
        obj.addProperty("App::PropertyString","X","Equation2(X,Y,Z)","X(a,b,c,d1-dN,t)").X="(a+b*cos(c*t))*cos(t)"
        obj.addProperty("App::PropertyString","Y","Equation2(X,Y,Z)","Y(a,b,c,d1-dN,X,t)").Y="(a+b*cos(c*t))*sin(t)"
        obj.addProperty("App::PropertyString","Z","Equation2(X,Y,Z)","Z(a,b,c,d1-dN,X,Y,t)").Z="b*sin(c*t)"
        obj.addProperty("App::PropertyFloat","F_a","Floats","a as a float if it is a constant (readonly)")
        obj.addProperty("App::PropertyFloat","F_b","Floats","b as a float if it is a constant (readonly)")
        obj.addProperty("App::PropertyFloat","F_c","Floats","c as a float if it is a constant (readonly)")
        obj.addProperty("App::PropertyFloatList","F_d","Floats","di as a float if it is a constant (readonly)\n\
1-indexed, e.g. F_d[1] = d1, F_d[2] = d2, etc.")
        obj.addProperty("App::PropertyFloat","F_X","Floats","X as a float if it is a constant (readonly)")
        obj.addProperty("App::PropertyFloat","F_Y","Floats","Y as a float if it is a constant (readonly)")
        obj.addProperty("App::PropertyFloat","F_Z","Floats","Z as a float if it is a constant (readonly)")
        for prop in ["F_a","F_b","F_c","F_d","F_X","F_Y","F_Z"]:
            obj.setEditorMode(prop,1) #readonly
        obj.addProperty("App::PropertyFloat","t_min","Equation3(T Params)","start value for t").t_min = 0.0
        obj.addProperty("App::PropertyFloat","t_max","Equation3(T Params)","Max t").t_max = 2*pi
        obj.addProperty("App::PropertyFloat","Interval","Equation3(T Params)","Interval").Interval = 0.1
        obj.addProperty("App::PropertyBool","Closed","Curve","Whether curve is closed").Closed=False
        obj.addProperty("App::PropertyBool","PlusOneIteration","Curve","Fixes a bug, but changes existing behavior.  Set to False if it breaks an existing model.").PlusOneIteration = True
        obj.addProperty("App::PropertyVectorList","Points","Curve","Points used to make the curve. Regenerated each recompute.").Points =[]
        obj.addProperty("App::PropertyString","Version", "Base", "Version this object was created with").Version = __version__
        obj.addProperty("App::PropertyEnumeration","ShapeType","Curve","Options: BSpline, Polygon, Points").ShapeType=["BSpline","Polygon","Points"]
        obj.ShapeType = "BSpline" #default
        obj.addProperty("App::PropertyLink","Spreadsheet","Spreadsheet","Link a spreadsheet")
        obj.addProperty("App::PropertyBool","UpdateSpreadsheet","Spreadsheet","[Trigger] Push current formula to linked spreadsheet, creates one and links it if necessary.").UpdateSpreadsheet=False
        obj.addProperty("App::PropertyBool","UseSpreadsheet","Spreadsheet","If True, poperties are readonly and must come from spreadsheet.  If false, spreadsheet is ignored and properties are set to read/write.").UseSpreadsheet=False
        obj.addProperty("App::PropertyString","Continuity","Curve","Continuity of Curve")
        obj.setEditorMode('Continuity',1)
        obj.addProperty("App::PropertyBool","MakeFace","Curve","Make a face from curve object if possible.  Can't be done with points or if shape isn't closed.")
        obj.addProperty("App::PropertyFile","File","JSON","JSON format file to contain data")
        obj.setEditorMode("File",2)#hidden
        obj.addProperty("App::PropertyBool","Sorted","JSON", "Sort formula names")
        obj.addProperty("App::PropertyEnumeration","Formulas","JSON","Formulas in JSON data").Formulas=["formula"]
        obj.addProperty("App::PropertyBool","EditFormulas","JSON","[Trigger] brings up editor dialog")
#        obj.addProperty("App::PropertyBool","WriteFile","JSON","[Trigger] Updates JSON file with current data.  WARNING: will overwrite all current data, use AppendFile to add current formula to file.").WriteFile = False
#        obj.addProperty("App::PropertyBool","RenameFormula","JSON","[Trigger] Changes current Formula name to string in FormulaName").RenameFormula = False
        obj.addProperty("App::PropertyString","FormulaName","JSON","Modify this for changing formula name, and then toggle Rename Formula to True")
        obj.setEditorMode("FormulaName",2) #hidden --renaming now done in editor
#        obj.addProperty("App::PropertyBool","NewFormula","JSON","[Trigger] Creates new formula adds to Formulas").NewFormula = False
#        obj.addProperty("App::PropertyBool","OpenFile","JSON","[Trigger] Opens JSON file in default system editor for text files.").OpenFile = False
#        obj.addProperty("App::PropertyBool","ReadFile","JSON","[Trigger] Reads JSON file.  WARNING: will clobber current formula, use AppendFile to save current formula to file before reading if you want to save it").OpenFile = False
#        obj.addProperty("App::PropertyBool","AppendFile","JSON","[Trigger] Appends current formula to JSON file.").AppendFile = False
#        obj.addProperty("App::PropertyBool","DeleteFormula","JSON","[Trigger] Removes current formula from internal data, does not modify JSON file").DeleteFormula=False
        obj.Proxy = self
        self.JSON_Data = {}
        self.previousFormula = ""
        self.bInihibitUpdates = False
        self.bInhibitRecompute = False
        self.newFormula(obj) #initialize with a new formula
        self.editingMode = False
        self.fpName = obj.Name

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
        fp.setEditorMode('t_min',mode)
        fp.setEditorMode('t_max',mode)
        fp.setEditorMode('Interval',mode)

    def readJSONFile(self,fp,txt=None):
        if txt == None:
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
        else: #txt != None
            self.JSON_Data = json.loads(txt)
        #now rename any "t" to "t_min"
        for k,v in self.JSON_Data.items():
            if "t" in v.keys():
                self.JSON_Data[k]["t_min"] = self.JSON_Data[k]["t"]
                self.JSON_Data[k].pop("t")
                FreeCAD.Console.PrintMessage(f"ParametricCurve: renaming 't' to 't_min' in {k}"+chr(10))
        formula_names = []
        for pn in self.JSON_Data:
            formula_names.append(pn)
        fp.Formulas = sorted(formula_names) if hasattr(fp,"Sorted") and fp.Sorted else formula_names
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
                "t_min":str(fp.t) if hasattr(fp,"t") else str(fp.t_min),
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
                "t_min":str(fp.t) if hasattr(fp,"t") else str(fp.t_min),
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
        if hasattr(fp,"t_min"):
            self.JSON_Data[formulaName]["t_min"] = str(fp.t_min)
        if hasattr(fp,"t_max"):
            self.JSON_Data[formulaName]["t_max"] = str(fp.t_max)
        if hasattr(fp,"Interval"):
            self.JSON_Data[formulaName]["interval"] = str(fp.Interval)

    def updateJSONFormula(self,fp,formulaName):
        #FreeCAD.Console.PrintMessage("updateJSONFormula"+chr(10))
        #when changing formulas if expressions are used the expressions override the new
        #values from the formula, so we try to set them all to None
        if not hasattr(fp,"a"):
            return
        if bool(fp.ExpressionEngine):
            propstrs = ["a","b","c","X","Y","Z","t","t_min","t_max","interval"]
            for propstr in propstrs:
                try:
                    fp.setExpression(propstr,None)
                except Exception:
                    pass
            FreeCAD.Console.PrintWarning("ParameticCurve: clearing expressions\n")
        fp.a = self.JSON_Data[formulaName]["a"]
        fp.b = self.JSON_Data[formulaName]["b"]
        fp.c = self.JSON_Data[formulaName]["c"]
        fp.d = self.JSON_Data[formulaName]["d"]
        fp.X = self.JSON_Data[formulaName]["X"]
        fp.Y = self.JSON_Data[formulaName]["Y"]
        fp.Z = self.JSON_Data[formulaName]["Z"]
        if hasattr(fp,"t"):
            fp.t = evaluate(self.stripComments(self.JSON_Data[formulaName]["t_min"]))
        else:
            fp.t_min = evaluate(self.stripComments(self.JSON_Data[formulaName]["t_min"]))
        fp.t_max = evaluate(self.stripComments(self.JSON_Data[formulaName]["t_max"]))
        fp.Interval = evaluate(self.stripComments(self.JSON_Data[formulaName]["interval"]))


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
        fp.Spreadsheet.set('a_cell',self.stripComments(fp.a))
        fp.Spreadsheet.set('b_cell',self.stripComments(fp.b))
        fp.Spreadsheet.set('c_cell',self.stripComments(fp.c))
        for dd in range(0,len(fp.d)):
            fp.Spreadsheet.set('A'+str(dd+10),'d'+str(dd+1))
            fp.Spreadsheet.setAlias('B'+str(dd+10),'d'+str(dd+1))
            fp.Spreadsheet.set('d'+str(dd+1),self.stripComments(fp.d[dd]))
        fp.Spreadsheet.set('X',self.stripComments(fp.X))
        fp.Spreadsheet.set('Y',self.stripComments(fp.Y))
        fp.Spreadsheet.set('Z',self.stripComments(fp.Z))
        if hasattr(fp,"t"):
            fp.Spreadsheet.set('t_min',str(fp.t))
        else:
            fp.Spreadsheet.set('t_min',str(fp.t_min))
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
            dd += 1
            k = "d"+str(dd+1)
        fp.d = new_d
        fp.X=str(fp.Spreadsheet.X)
        fp.Y=str(fp.Spreadsheet.Y)
        fp.Z=str(fp.Spreadsheet.Z)
        if hasattr(fp,"t"):
            fp.t = fp.Spreadsheet.t_min
        else:
            fp.t_min = fp.Spreadsheet.t_min
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
            FreeCAD.Console.PrintMessage("File linked.\n\
Use Read File to import into object.\n\
Use Append File to append formulas to file.\n\
Use Write File to overwrite all data in file.\n\
Use Open File to open file in external editor.\n\
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
        elif prop == "Sorted":
            formulas = [key for key in self.JSON_Data.keys()]
            fp.Formulas = sorted(formulas) if fp.Sorted else formulas
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
        elif prop == "a" or prop == "b" or prop == "c" or prop == "d" or prop == "X" or prop == "Y" or prop == "Z" or prop == "t" or prop == "t_min" or prop == "t_max" or prop == "Interval":
            if fp.FormulaName and not self.bInihibitUpdates:
                self.updateJSON_Data(fp,fp.Formulas) #update self.JSON_Data on every property change
        elif prop == "MakeFace" and fp.MakeFace == True:
            self.bInhibitRecompute = True
            if fp.MakeFace and fp.Shape.isClosed():
                try:
                    face = Part.makeFace(fp.Shape,"Part::FaceMakerCheese")
                    fp.Shape = face
                except:
                    pass
        elif prop == "EditFormulas" and fp.EditFormulas == True:
            fp.EditFormulas = False
            t = QtCore.QTimer()
            t.singleShot(50, self.showEditor)

    def stripComments(self,string):
        """returns a string with everything after # removed, including #"""
        strip1 = string
        if not "#" in string and not "{" in string and not "}" in string:
            return string
        elif "#" in string:
            idx = string.index("#")
            strip1 = string[:idx]
        if not "{" in strip1 and not "}" in strip1:
            return strip1
        idx2 = strip1.index("{")
        idx3 = strip1.index("}")
        return strip1[:idx2] + strip1[idx3+1:]

    def makeCurve(self, fp):
        self.updateFromSpreadsheet(fp)
        vars = {"a":0,"b":0,"c":0,"X":0,"Y":0,"Z":0,"t":0}

        fa = self.stripComments(fp.a)
        fb = self.stripComments(fp.b)
        fc = self.stripComments(fp.c)
        fx = self.stripComments(fp.X)
        fy = self.stripComments(fp.Y)
        fz = self.stripComments(fp.Z)
        t = fp.t if hasattr(fp,"t") else fp.t_min
        tf = fp.t_max
        intv = fp.Interval
        if not intv:
            FreeCAD.Console.PrintWarning("ParametricCurve: interval must be non-zero, return null shape.\n")
            return Part.Shape()
        if (tf-t)*intv <= 0:
            FreeCAD.Console.PrintWarning(f"Infinite loop avoided.  t_max - t * Interval cannot be less than 0.  Interval used will be {intv * -1}\n")
            intv *= -1
        iterations = int((tf-t)/intv)
        matriz = []
        plus1 = 1
        if hasattr(fp,"PlusOneIteration") and fp.PlusOneIteration:
            lastT = t + iterations * intv
            while lastT < tf and not math.isclose(lastT, tf, abs_tol = 1e-9): #don't add if almost equal
                plus1 += 1
                lastT += intv
        else:
            plus1 = 0  # restore old bug for compatibility
        for i in range(iterations + plus1):
            if hasattr(fp,"PlusOneIteration") and fp.PlusOneIteration:
                if i == int(iterations) + plus1 - 1: #last iteration
                    t = tf
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
                    vars[k] = evaluate(self.stripComments(fp.d[dd]),vars)
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
        if not matriz:
            FreeCAD.Console.PrintWarning("ParametricCurve: --vector list is empty, returning null shape\n")
            return Part.Shape()
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
        if fp.MakeFace and fp.Shape.isClosed():
            try:
                face = Part.makeFace(fp.Shape,"Part::FaceMakerCheese")
                fp.Shape = face
            except:
                pass
        #FreeCAD.Console.PrintMessage("Recompute Python Curve feature"+chr(10))
        self.updateFloats(fp)

    def updateFloat(self, fp, propstr, propfloat):
        try:
            fval = evaluate(self.stripComments(getattr(fp,propstr)))
            setattr(fp,propfloat,fval)
        except Exception:
            setattr(fp,propfloat,0.0)

    def updateFloats(self, fp):
        if not hasattr(fp, "F_a"): #do not break existing objects created with earlier versions
            return
        propstrs = ["a","b","c","X","Y","Z"]
        for propstr in propstrs:
            self.updateFloat(fp,propstr,f"F_{propstr}")
        d_vals = [0.0] #dummy first value so we can 1-index into the array
        for dd,val in enumerate(fp.d):
            try:
                d_vals.append(evaluate(self.stripComments(val)))
            except:
                d_vals.append(0.0)
        d_vals = d_vals if not d_vals == [0.0] else []
        setattr(fp, "F_d",d_vals)

    def showEditor(self):
        '''show the formula editor'''
        if not hasattr(self,"fpName"):
            FreeCAD.Console.PrintError("Formula editor not available for objects created with older versions.\n")
            return #object made with old version
        fp = FreeCADGui.Selection.getSelection()[0]
        if not FreeCADGui.Control.activeDialog():
            editor = TaskEditFormulasPanel(fp)
            FreeCADGui.Control.showDialog(editor)
            self.editingMode = True
        else:
            self.editingMode=False
            FreeCAD.Console.PrintError("Another task dialog is active.  Close that one and try again.\n")
            return


class TaskEditFormulasPanel: #formula editor
    def __init__(self, fp):
        self.blockSignals = True
        self.fp = fp
        self.sorted = fp.Sorted if hasattr(fp,"Sorted") else False
#        self.json = self.shallowCopy(self.fp.Proxy.JSON_Data)
        self.clipboard = QtGui.QApplication.clipboard()
        self.form = QtGui.QWidget()
        self.form.setObjectName("formulaEditor")
        self.form.editor = self #used by context menu handler
        layout=QtGui.QVBoxLayout()
        layout.setObjectName("layout")
        commandBox = QtGui.QHBoxLayout()
        commandBox.setObjectName("commandBox")
        self.formulaList = QtGui.QListWidget()
        commandBox.addWidget(self.formulaList)
        self.formulaList.currentItemChanged.connect(self.formulaListCurrentItemChanged)

        #layout is a vbox, the entire layout of the Edit Formulas panel, beneath the standard buttons
        #commandBox is a hbox containing the formula list and topButtonBox
        #topButtonBox is a vbox containing buttons related to top level commands
        #hBoxBottom is similar to commandBox, hbox containing various line edits and
        #bottomButtonBox, a vbox containing buttons related commands for the line edits

        formulasLabel = QtGui.QLabel("Formulas in editor memory:")
        layout.addWidget(formulasLabel)

        layout.addLayout(commandBox)
        hBoxBottom = QtGui.QHBoxLayout()
        hBoxBottom.setObjectName("hBoxBottom")
        formulaBox = QtGui.QGridLayout()
        formulaBox.setObjectName("formulaBox")
        hBoxBottom.addLayout(formulaBox)
        bottomButtonBox = QtGui.QVBoxLayout()
        bottomButtonBox.setObjectName("bottomButtonBox")
        hBoxBottom.addLayout(bottomButtonBox)
        divider = QtGui.QLabel("Current formula:")
        layout.addWidget(divider)
        layout.addLayout (hBoxBottom)
        topButtonBox = QtGui.QVBoxLayout()
        topButtonBox.setObjectName("topButtonBox")
        commandBox.addLayout(topButtonBox)

        self.form.setLayout(layout)

        self.checkBoxSorted = QtGui.QCheckBox("Sorted")
        self.checkBoxSorted.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.checkBoxSorted.setToolTip ("Sort formulas")
        self.checkBoxSorted.clicked.connect(self.checkBoxSortedClicked)
        self.checkBoxSorted.setChecked(self.sorted)
        topButtonBox.addWidget(self.checkBoxSorted)

        buttonPlus = QtGui.QPushButton("+")
        buttonPlus.setToolTip ("Add new formula, a copy of selected formula")
        topButtonBox.addWidget(buttonPlus)
        buttonPlus.clicked.connect(self.buttonPlusClicked)

        buttonMinus = QtGui.QPushButton("-")
        buttonMinus.setToolTip("Delete formula")
        topButtonBox.addWidget(buttonMinus)
        buttonMinus.clicked.connect(self.buttonMinusClicked)

        buttonImport = QtGui.QPushButton("Import")
        buttonImport.setToolTip ("Import one or more formulas from a JSON file\n\
Does not overwrite existing memory contents\n")
        topButtonBox.addWidget(buttonImport)
        buttonImport.clicked.connect(self.buttonImportClicked)

        buttonCopy = QtGui.QPushButton("Copy")
        buttonCopy.setToolTip ("Copy formula to clipboard")
        bottomButtonBox.addWidget(buttonCopy)
        buttonCopy.clicked.connect(self.buttonCopyClicked)

        buttonPaste = QtGui.QPushButton("Paste")
        buttonPaste.setToolTip("Paste formula from clipboard")
        bottomButtonBox.addWidget(buttonPaste)
        buttonPaste.clicked.connect(self.buttonPasteClicked)

        buttonRename = QtGui.QPushButton("Rename")
        buttonRename.setToolTip ("Rename formula")
        bottomButtonBox.addWidget(buttonRename)
        buttonRename.clicked.connect(self.buttonRenameClicked)

        buttonClear = QtGui.QPushButton("Clear One")
        buttonClear.setToolTip ("Clear current formula")
        bottomButtonBox.addWidget(buttonClear)
        buttonClear.clicked.connect(self.buttonClearClicked)

        buttonClearAll = QtGui.QPushButton("Clear")
        buttonClearAll.setToolTip ("Clear all formulas")
        topButtonBox.addWidget(buttonClearAll)
        buttonClearAll.clicked.connect(self.buttonClearAllClicked)

        buttonOpen = QtGui.QPushButton("Open")
        buttonOpen.setToolTip ("Open JSON file")
        topButtonBox.addWidget(buttonOpen)
        buttonOpen.clicked.connect(self.buttonOpenClicked)

        buttonSave = QtGui.QPushButton("Save")
        buttonSave.setToolTip ("Save JSON file")
        topButtonBox.addWidget(buttonSave)
        buttonSave.clicked.connect(self.buttonSaveClicked)

        buttonSaveOne = QtGui.QPushButton("Save One")
        buttonSaveOne.setToolTip ("Save current formula to a JSON file\n\
Overwrites any existing content in the file\n")
        bottomButtonBox.addWidget(buttonSaveOne)
        buttonSaveOne.clicked.connect(self.buttonSaveOneClicked)

        buttonAppend = QtGui.QPushButton("Append One")
        buttonAppend.setToolTip ("Append current formula to a JSON file")
        bottomButtonBox.addWidget(buttonAppend)
        buttonAppend.clicked.connect(self.buttonAppendClicked)

        buttonAppendAll = QtGui.QPushButton("Append")
        buttonAppendAll.setToolTip ("Append one or more formulas to a JSON file")
        topButtonBox.addWidget(buttonAppendAll)
        buttonAppendAll.clicked.connect(self.buttonAppendAllClicked)

        bottomButtonBox.addStretch()

        formulaBox.addWidget(QtGui.QLabel("a:"),0,0,QtCore.Qt.AlignRight)
        self.a_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.a_Line,0,1)

        formulaBox.addWidget(QtGui.QLabel("b:"),1,0,QtCore.Qt.AlignRight)
        self.b_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.b_Line,1,1)

        formulaBox.addWidget(QtGui.QLabel("c:"),2,0,QtCore.Qt.AlignRight)
        self.c_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.c_Line,2,1)

        dsize = 5
        formulaBox.addWidget(QtGui.QLabel("d1:\nd2:\nd3:\ndN:\n..."),3,0,dsize,1,QtCore.Qt.AlignRight)
        self.d_Lines = QtGui.QPlainTextEdit()
        formulaBox.addWidget(self.d_Lines,3,1,dsize,1)

        formulaBox.addWidget(QtGui.QLabel("X:"),4+dsize,0,QtCore.Qt.AlignRight)
        self.X_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.X_Line,4+dsize,1)

        formulaBox.addWidget(QtGui.QLabel("Y:"),5+dsize,0,QtCore.Qt.AlignRight)
        self.Y_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.Y_Line,5+dsize,1)

        formulaBox.addWidget(QtGui.QLabel("Z:"),6+dsize,0,QtCore.Qt.AlignRight)
        self.Z_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.Z_Line,6+dsize,1)

        formulaBox.addWidget(QtGui.QLabel("t_min:"),7+dsize,0,QtCore.Qt.AlignRight)
        self.t_min_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.t_min_Line,7+dsize,1)

        formulaBox.addWidget(QtGui.QLabel("interval:"),8+dsize,0,QtCore.Qt.AlignRight)
        self.interval_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.interval_Line,8+dsize,1)

        formulaBox.addWidget(QtGui.QLabel("t_max:"),9+dsize,0,QtCore.Qt.AlignRight)
        self.t_max_Line = QtGui.QLineEdit()
        formulaBox.addWidget(self.t_max_Line,9+dsize,1)

        self.form.setWindowTitle(f"Formula editor v{__version__}")
        self.fp.Proxy.editingMode = True
        self.blockSignals = False
        self.json = self.shallowCopy(self.fp.Proxy.JSON_Data)
        self.updateFormulaList()
        self.populateLines(self.formulaList.itemAt(0,0).text())

    def shallowCopy(self,fromdict):
        """make shallow copy of dictionary of dictionaries"""
        todict = {}
        for k,v in fromdict.items():
            formula = {}
            for kk,vv in v.items():
                formula[kk] = vv
            todict[k] = formula
        return todict

    def updateFormulaList(self):
        self.blockSignals = True
        self.formulaList.clear()
        keys = self.json.keys() if not self.sorted else sorted(self.json.keys())
        for key in keys:
            self.formulaList.addItem(key)
        self.blockSignals = False
        self.formulaList.setCurrentItem(self.formulaList.itemAt(0,0))

    def formulaListCurrentItemChanged(self,current,prev):
        if self.blockSignals:
            return
        #FreeCAD.Console.PrintMessage(f"current = {current.text() if current else None}, prev = {prev.text() if prev else None}\n")
        if prev:
            self.saveLinesToJson(prev.text())
        if current:
            #FreeCAD.Console.PrintMessage(f"populating lines with {current.text()}\n")
            self.populateLines(current.text())

    def importFormula(self, fromDict, formulaName):
        '''adds fromDict[formulaName] to self.json'''
        current = self.formulaList.currentItem().text()
        self.saveLinesToJson(current)
        if not formulaName in self.json:
            self.json[formulaName] = fromDict[formulaName]
        else: #name conflict
            newName = formulaName
            while newName in self.json:
                newName,ok = QtGui.QInputDialog.getText(FreeCADGui.getMainWindow(), "Formula exists","Formula exists already, enter a new name:",text=formulaName)
                if not ok:
                    return False
            self.json[newName] = fromDict[formulaName]
        return True

    def buttonImportClicked(self,btn):
        current = self.formulaList.currentItem().text()
        self.saveLinesToJson(current)
        fname = QtGui.QFileDialog.getOpenFileName(FreeCADGui.getMainWindow(),"Open a JSON file",filter='*.*')[0]
        if not fname:
            return
        try:
            f = open(fname)
        except Exception as ex:
            FreeCAD.Console.PrintError(f"ParametricCurve::Exception {ex}\n")
            return
        try:
            jtemp = json.load(f)
        except Exception as ex:
            FreeCAD.Console.PrintError(f"ParametricCurve::Exception {ex}\nFile not opened.\n")
            f.close()
            return
        f.close()
    #now rename any "t" to "t_min"
        for k,v in jtemp.items():
            if "t" in v.keys():
                jtemp[k]["t_min"] = jtemp[k]["t"]
                jtemp[k].pop("t")
                FreeCAD.Console.PrintMessage(f"ParametricCurve: renaming 't' to 't_min' in {k}"+chr(10))
        items = [k for k in jtemp.keys()]
        if not items:
            return #nothing to import
        if len(items) == 1:
            self.importFormula(jtemp, items[0])
        else:
            dlg = SelectObjects(items,"Select formulas to import:")
            dlg.all.setCheckState(QtCore.Qt.Checked)
            ok = dlg.exec_()
            if not ok:
                return []
            selected = dlg.selected
            for key in jtemp.keys():
                if key in selected:
                    success = self.importFormula(jtemp,key)
                    if not success:
                        break
        self.updateFormulaList()

    def checkBoxSortedClicked(self,btn):
        self.sorted = not self.sorted
        self.checkBoxSorted.setChecked(self.sorted)
        self.updateFormulaList()

    def buttonOpenClicked(self,btn):
        fname = QtGui.QFileDialog.getOpenFileName(FreeCADGui.getMainWindow(),"Open a JSON file",filter='*.*')[0]
        if not fname:
            return
        try:
            f = open(fname)
        except Exception as ex:
            FreeCAD.Console.PrintError(f"ParametricCurve::Exception {ex}\n")
            return
        try:
            self.json = json.load(f)
        except Exception as ex:
            FreeCAD.Console.PrintError(f"ParametricCurve::Exception {ex}\nFile not opened.\n")
            f.close()
            return
        f.close()
    #now rename any "t" to "t_min"
        for k,v in self.json.items():
            if "t" in v.keys():
                self.json[k]["t_min"] = self.json[k]["t"]
                self.json[k].pop("t")
                FreeCAD.Console.PrintMessage(f"ParametricCurve: renaming 't' to 't_min' in {k}"+chr(10))
        self.updateFormulaList()

    def setupAppend(self,all=False):
        fname = QtGui.QFileDialog.getOpenFileName(FreeCADGui.getMainWindow(),"Append to a JSON file",filter='*.*')[0]
        if not fname:
            return
        try:
            f = open(fname)
        except Exception as ex:
            FreeCAD.Console.PrintError(f"ParametricCurve::Exception opening file: {ex}\n")
            return
        try:
            contents = f.read()
            jtemp = json.loads(contents) if contents else dict()
        except Exception as ex:
            FreeCAD.Console.PrintError(f"ParametricCurve::Exception {ex}\nFile not opened.\n")
            f.close()
            return
        f.close()
        if not all:
            current = self.formulaList.currentItem().text()
            self.appendFormula(fname, current, jtemp)
        else:
            items = []
            for ii in range(self.formulaList.count()):
                items.append(self.formulaList.item(ii).text())
            dlg = SelectObjects(items,"Select formulas to append:")
            dlg.all.setCheckState(QtCore.Qt.Checked)
            ok = dlg.exec_()
            if not ok:
                return []
            selected = dlg.selected
            for sel in selected:
                success = self.appendFormula(fname,sel,jtemp)
                if not success:
                    break #user canceled

    def appendFormula(self, fname, formulaName, jtemp):
        current = formulaName
        item = self.json[current]
        newName = current
        while newName in jtemp:
            newName,ok = QtGui.QInputDialog.getText(FreeCADGui.getMainWindow(), "Formula exists","Formula exists already, enter a new name:",text=current)
            if not ok:
                return False
        jtemp[newName] = item
        FreeCAD.Console.PrintMessage(f"Appending '{newName}': {jtemp[newName]} to {fname}\n")
        with open(fname,"w") as outfile:
            json.dump(jtemp,outfile)
        return True

    def buttonAppendClicked(self,btn):
        current = self.formulaList.currentItem().text()
        self.saveLinesToJson(current)
        self.setupAppend()

    def buttonAppendAllClicked(self,btn):
        current = self.formulaList.currentItem().text()
        self.saveLinesToJson(current)
        self.setupAppend(all=True)

    def buttonSaveClicked(self,btn):
        current = self.formulaList.currentItem().text()
        self.saveLinesToJson(current)
        fname = QtGui.QFileDialog.getSaveFileName(FreeCADGui.getMainWindow(),"Save all formulas to a JSON file",filter='*.*')[0]
        if not fname:
            return
        items = [key for key in self.json.keys()]
        dlg = SelectObjects(items,"Select formulas to save:")
        dlg.all.setCheckState(QtCore.Qt.Checked)
        ok = dlg.exec_()
        if not ok:
            return
        selected = dlg.selected
        if not selected:
            return
        new_dict = {}
        for sel in selected:
            new_dict[sel] = self.json[sel]
        with open(fname,"w") as outfile:
            json.dump(new_dict,outfile)

    def buttonSaveOneClicked(self,btn):
        current = self.formulaList.currentItem().text()
        self.saveLinesToJson(current)
        fname = QtGui.QFileDialog.getSaveFileName(FreeCADGui.getMainWindow(),"Save a formula to JSON file",dir=current)[0]
        if not fname:
            return
        jtemp = self.shallowCopy(self.json)
        pops = [key for key in jtemp.keys() if not key == current]
        for pop in pops:
            jtemp.pop(pop)
        with open(fname,"w") as outfile:
            json.dump(jtemp,outfile)
        for key in jtemp.keys():
            FreeCAD.Console.PrintMessage(f"saved '{key}': {jtemp[key]} to {fname}\n")

    def buttonClearAllClicked(self,btn):
        self.json = dict()
        self.updateFormulaList()
        self.buttonClearClicked(True)
        self.buttonPlusClicked(True)

    def buttonClearClicked(self,btn):
        current = self.formulaList.currentItem().text() if self.formulaList.currentItem() else ""
        lines = [self.a_Line, self.b_Line, self.c_Line,
                 self.X_Line, self.Y_Line, self.Z_Line, self.t_min_Line,
                 self.interval_Line, self.t_max_Line]
        for line in lines:
            line.setText("")
        self.d_Lines.setPlainText("")
        self.saveLinesToJson(current) if current else None

    def buttonPlusClicked(self, btn):
        ii = 1
        trialName = "formula1"
        while (trialName in self.json):
            ii += 1
            trialName = "formula"+str(ii)
        self.json[trialName] ={
                "a":self.a_Line.text(),
                "b":self.b_Line.text(),
                "c":self.c_Line.text(),
                "d":self.d_Lines.toPlainText().split("\n"),
                "X":self.X_Line.text(),
                "Y":self.Y_Line.text(),
                "Z":self.Z_Line.text(),
                "t_min":self.t_min_Line.text(),
                "t_max":self.t_max_Line.text(),
                "interval":self.interval_Line.text()
                }
        self.updateFormulaList()
        self.blockSignals = True
        self.formulaList.setCurrentItem(self.formulaList.findItems(trialName, QtCore.Qt.MatchExactly)[0])
        self.blockSignals = False

    def buttonRenameClicked(self, btn):
        current = self.formulaList.currentItem().text()
        newName,ok = QtGui.QInputDialog.getText(FreeCADGui.getMainWindow(), "Parametric Curve FP","Enter name:")
        if ok:
            if newName in self.json:
                FreeCAD.Console.PrintError(f"{newName} already exists\n")
                return
            else:
                self.json[newName] = self.json.pop(current,None)
                self.updateFormulaList()
                #FreeCAD.Console.PrintMessage(f"blocksignals = {self.blockSignals}\n")
                self.formulaList.setCurrentItem(self.formulaList.findItems(newName, QtCore.Qt.MatchExactly)[0])

    def buttonMinusClicked(self, btn):
        self.fp.Document.openTransaction("ParametricCurve::Delete Formula")
        self.blockSignals = True
        row = self.formulaList.currentRow()
        self.json.pop(self.formulaList.currentItem().text(),None)
        self.updateFormulaList()
        if len(self.json.keys()) == 0:
            self.buttonClearClicked(True)
            self.buttonPlusClicked(True)
        self.formulaList.setCurrentRow(row if row < self.formulaList.count() else self.formulaList.count()-1)
        self.populateLines(self.formulaList.item(0).text())
        self.blockSignals = False
        self.fp.Document.commitTransaction()

    def buttonCopyClicked(self, btn):
        current = self.formulaList.currentItem().text()
        tempDict = {current:self.json[current]}
        jsonstr = str(tempDict).replace('"','"""').replace("'",'"')
        self.clipboard.setText(jsonstr)
        FreeCAD.Console.PrintMessage(f"string in clipboard: {jsonstr}\n")

    def buttonPasteClicked(self, btn):
        cliptext = self.clipboard.text()
        #FreeCAD.Console.PrintMessage(f"cliptext = {cliptext}\n")
        if not cliptext:
            FreeCAD.Console.PrintError("No text in clipboard\n")
            return
        else:
            try:
                tempDict = json.loads(cliptext)
            except Exception as ex:
                FreeCAD.Console.PrintError(f"ParametricCurve::PasteException: {ex}\n")
                return
        self.buttonPlusClicked(True)
        current = self.formulaList.currentItem().text()
        keyName = [k for k in tempDict.keys()][0]
        if keyName in self.json:
            FreeCAD.Console.PrintWarning(f"{keyName} already exists, so using default formula name: {current}\n")
            newName = current
        else:
            newName = keyName
        self.json.pop(current,None)
        self.json[newName] = tempDict[keyName]
        self.updateFormulaList()
        self.formulaList.setCurrentRow(self.formulaList.count()-1)
        self.populateLines(newName)

    def saveLinesToJson(self,key=""):
#        FreeCAD.Console.PrintMessage(f"saveLinesToJson({key}), blockSignals = {self.blockSignals}\n")
        cur = self.json[key]
#        FreeCAD.Console.PrintMessage(f"key = {key}\n")
        cur["a"] = self.a_Line.text() if hasattr(self,"a_Line") else ""
        cur["b"] = self.b_Line.text() if hasattr(self,"b_Line") else ""
        cur["c"] = self.c_Line.text() if hasattr(self,"c_Line") else ""
        cur["d"] = self.d_Lines.toPlainText().split("\n")  if hasattr(self,"d_Lines") else ""
        cur["X"] = self.X_Line.text() if hasattr(self,"X_Line") else ""
        cur["Y"] = self.Y_Line.text() if hasattr(self,"Y_Line") else ""
        cur["Z"] = self.Z_Line.text() if hasattr(self,"Z_Line") else ""
        cur["t_min"] = self.t_min_Line.text() if hasattr(self,"t_min_Line") else ""
        cur["interval"] = self.interval_Line.text() if hasattr(self,"interval_Line") else ""
        cur["t_max"] = self.t_max_Line.text() if hasattr(self,"t_max_Line") else ""

    def populateLines(self,key):
#        FreeCAD.Console.PrintMessage(f"populateLines({key})\n")
#        FreeCAD.Console.PrintMessage(f"self.json[{key}] = {self.json[key]}\n")
        self.blockSignals = True
        cur = self.json[key]
        self.a_Line.setText(cur["a"])
        self.b_Line.setText(cur["b"])
        self.c_Line.setText(cur["c"])
        self.d_Lines.setPlainText("\n".join(cur["d"]))
        self.X_Line.setText(cur["X"])
        self.Y_Line.setText(cur["Y"])
        self.Z_Line.setText(cur["Z"])
        self.t_min_Line.setText(cur["t_min"])
        self.interval_Line.setText(cur["interval"])
        self.t_max_Line.setText(cur["t_max"])
        self.blockSignals = False

    def reject(self):
        if not FreeCAD.ActiveDocument:
            FreeCADGui.Control.closeDialog()
            return
        self.fp.Proxy.editingMode = False
        FreeCADGui.Control.closeDialog()
        FreeCADGui.activeDocument().resetEdit()
        FreeCAD.ActiveDocument.recompute()

    def accept(self):
        if not FreeCAD.ActiveDocument:
            FreeCADGui.Control.closeDialog()
            return
        self.fp.Document.openTransaction("ParametricCurve::Accept")
        if hasattr(self.fp,"Sorted"):
            self.fp.Sorted = self.sorted
        self.saveLinesToJson(self.formulaList.currentItem().text())
        jsonstr = str(self.json).replace('"','"""').replace("'",'"')
        self.fp.Proxy.readJSONFile(self.fp,jsonstr)
        if not self.fp: #user deleted or closed document perhaps
            self.fp.Document.abortTransaction()
            return
        self.fp.Proxy.JSON_Data = self.shallowCopy(self.json)
        if hasattr(self.fp.Proxy,"editingMode"):
            self.fp.Proxy.editingMode = False
        self.fp.Document.commitTransaction()
        FreeCADGui.Control.closeDialog()
        FreeCADGui.ActiveDocument.resetEdit()
        FreeCAD.ActiveDocument.recompute()

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok) | int(QtGui.QDialogButtonBox.Cancel) | int(QtGui.QDialogButtonBox.Reset) | int(QtGui.QDialogButtonBox.Apply)

    def clicked(self, button):
        if not FreeCAD.ActiveDocument:
            FreeCAD.Console.PrintError("No document.\n")
            return
        if button == QtGui.QDialogButtonBox.Reset:
            self.sorted = self.fp.Sorted if hasattr(self.fp,"Sorted") else False
            self.json =self.shallowCopy(self.fp.Proxy.JSON_Data)
            self.updateFormulaList()
            self.formulaList.setCurrentRow(0)
            self.populateLines(next(iter(self.json))) #first key
        elif button == QtGui.QDialogButtonBox.Apply:
            self.fp.Document.openTransaction("ParametricCurve::Apply")
            if hasattr(self.fp,"Sorted"):
                self.fp.Sorted = self.sorted
            FreeCAD.Console.PrintMessage("Applying... Can be undone\n")
            self.saveLinesToJson(self.formulaList.currentItem().text())
            jsonstr = str(self.json).replace('"','"""').replace("'",'"')
            self.fp.Proxy.readJSONFile(self.fp,jsonstr)
            self.fp.Formulas = self.formulaList.currentItem().text()
            self.fp.Document.commitTransaction()
            self.fp.Document.recompute()

#select objects dialog class
class SelectObjects(QtGui.QDialog):
    def __init__(self, objects, label=""):
        QtGui.QDialog.__init__(self)
        scrollContents = QtGui.QWidget()
        scrollingLayout = QtGui.QVBoxLayout(self)
        scrollContents.setLayout(scrollingLayout)
        scrollArea = QtGui.QScrollArea()
        scrollArea.setVerticalScrollBarPolicy(QtGui.Qt.ScrollBarAlwaysOn)
        scrollArea.setHorizontalScrollBarPolicy(QtGui.Qt.ScrollBarAlwaysOff)
        scrollArea.setWidgetResizable(True)
        scrollArea.setWidget(scrollContents)
        vBoxLayout = QtGui.QVBoxLayout(self)
        vBoxLayout.addWidget(QtGui.QLabel(label))
        self.all = QtGui.QCheckBox("All")
        #self.all.setCheckState(QtCore.Qt.Checked) #set by caller
        self.all.stateChanged.connect(self.allStateChanged)
        vBoxLayout.addWidget(self.all)
        vBoxLayout.addWidget(scrollArea)
        self.setLayout(vBoxLayout)
        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok.__or__(QtGui.QDialogButtonBox.Cancel),
            QtCore.Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.checkBoxes = []
        self.selected = []
        for ii,object in enumerate(objects):
            self.checkBoxes.append(QtGui.QCheckBox(object))
            self.checkBoxes[-1].setCheckState(self.all.checkState())
            scrollingLayout.addWidget(self.checkBoxes[-1])
        vBoxLayout.addWidget(buttons)
    def allStateChanged(self, arg):
        self.checkAll(self.all.checkState())
    def checkAll(self, state):
        for cb in self.checkBoxes:
            cb.setCheckState(state)
    def accept(self):
        self.selected = []
        for cb in self.checkBoxes:
            if cb.checkState():
                self.selected.append(cb.text())
        super().accept()
class CurveVP:
    '''Creates a 3D parametric curve'''
    def __init__(self, obj):
        '''Set this object to the proxy object of the actual view provider'''
        obj.Proxy = self

    def onDelete(self, vobj, subelements):
       if vobj.Object.Proxy.editingMode:
           FreeCADGui.Control.closeDialog()
       return True

    def attach(self, obj):
        '''Setup the scene sub-graph of the view provider, this method is mandatory'''
        self.Object = obj.Object

    def updateData(self, fp, prop):
        '''If a property of the handled feature has changed we have the chance to handle this here'''
        # fp is the handled feature, prop is the name of the property that has changed
        pass

    def canDropObject(self, incoming):
        return incoming.isDerivedFrom("App::TextDocument")

    def dropObject(self,vobj, incoming):
        if incoming.isDerivedFrom("App::TextDocument"):
            if incoming.Text:
                FreeCAD.Console.PrintWarning("Parametric_Curve_FP: Ensure document has been saved since last edit of Text document.\n")
                vobj.Object.Document.openTransaction("Drop Text Document")
                vobj.Object.Proxy.readJSONFile(vobj.Object,incoming.Text)
                vobj.Object.Document.commitTransaction()
            else:
                FreeCAD.Console.PrintError("Empty text document.  Save file and try again.\n")

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

    def setupContextMenu(self, vobj, menu):
        if vobj.Object.Proxy.editingMode == False:
            text = "Edit Formulas..."
            mode = 0
        else:
            text = "Accept Formulas"
            mode = 6
        action = menu.addAction(text)
        action.triggered.connect(lambda: self.setEdit(vobj,mode))
        attachAction = menu.addAction("Edit Attachment...")
        attachAction.triggered.connect(lambda: self.setEdit(vobj,8))

    def setEdit(self,vp,modNum):
        FreeCAD.Console.PrintLog(f"ParametricCurve::setEdit: modNum = {modNum}\n")
        if modNum == 0:
            vp.Object.Proxy.showEditor()
        elif modNum == 1:
            FreeCADGui.runCommand("Std_TransformManip",0)
            return True
        elif modNum == 3:
            FreeCADGui.runCommand('Part_ColorPerFace',0)
        elif modNum == 6: #accept changes and end edit mode
            FreeCADGui.getMainWindow().findChild(QtGui.QWidget,"formulaEditor").editor.accept()
        elif modNum == 8:
            FreeCADGui.runCommand("Part_EditAttachment",0)
        else:
            FreeCAD.Console.PrintMessage(f"modNum = {modNum}\n")
        return False

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

# end of CurveVP

def makeCurve(Parametric_Curve_FP):
    sheet = None
    textDoc = None
    txt = """
{
"helix": {"a": "1  #pitch", "b": "5 #height", "c": "1 #base radius",
"d": [
"{d1} 20 #angle deg",
"{d2} 1  # 1= RH  0 = LH",
"{d3} t*b/a",
"{d4} c + b*t*sin(rad(d1))/(2*pi)",
"{d5} ternary(d2, 1, -1)"],
"X": "d4*cos(d3*d5)", "Y": "d4*sin(d3*d5)", "Z": "b*t/(2*pi)",
"t_min": "0", "t_max": "2*pi", "interval": "0.1"},

"ellipse": {"a": "20 #major radius", "b": "10 #minor radius (ignored if c != 0)",
"c": "0.5 #eccentricity (0 to ignore and use a and b, else b^2 = a^2*(1 - c^2)",
"d": [
"{d1} 0 # x center",
"{d2} 0 # y center",
"{d3} 20 # angle from x-axis to major axis (deg)",
"{d4} ternary(c, a*(1-c*c)^0.5, b)",
"{d5} a * cos(t) # x -unrotated ellipse",
"{d6} d4 * sin(t) # y- unrotated ellipse",
"{d7} radians(d3) # angle in radians"
],
"X": "d1 + d5 * cos(d7) - d6 * sin(d7)", "Y": "d2 + d5 * sin(d7) + d6 * cos(d7)", "Z": "0",
"t_min": "0.0", "t_max": "2*pi", "interval": "0.1"},

"amoeba": {"a": "36.3", "b": "12", "c": "1.5", "d": ["(a+c*sin(b*t))"],
"X": "cos(t)*d1", "Y": "sin(t)*d1", "Z": "0",
"t_min": "0.0", "t_max": "2*pi", "interval": "0.1"},

"coil": {"a": "6", "b": "1", "c": "20", "d": [],
"X": "(a + b * cos(c*t))*cos(t)", "Y": "(a + b * cos(c*t))*sin(t)", "Z": "b*sin(c*t)",
"t_min": "0.0", "t_max": "2*pi", "interval": "0.02"},

"holesaw": {"a": "12  # radius", "b": "6 #no of teeth", "c": "5.000000 #sine amplitude",
"d": [""], "X": "cos(t)*a", "Y": "sin(t)*a", "Z": "c*sin(b*t)",
"t_min": "0.0", "t_max": "2*pi", "interval": "0.1"},

"sawtooth": {"a": "40 #radius", "b": "5 #number teeth", "c": "0.8 # tooth parameter between 0 and 1",
"d": ["10 #amplitude", "mod(b*t, 1)", "# best with polygon"],
"X": "a*cos(2*pi*t)", "Y": "a*sin(2*pi*t)", "Z": "d1*(lt(d2,c)*d2/c + gte(d2,c)*(1-d2)/(1-c))",
"t_min": "0.0", "t_max": "1.0", "interval": "0.01"},

"sinbraid_round_3": {"a": "10", "b": "sin(t*10/3) #radial amplitude", "c": "cos(t*5/3)*5 #vertical amplitude", "d": [],
"X": "a*sin(t)+b*sin(t)", "Y": "a*cos(t)+b*cos(t)", "Z": "c",
"t_min": "0.0", "t_max": "6*pi", "interval": "0.02"},

"sinbraid_round_4_3": {"a": "10  #radius", "b": "sin(t*9/4)   # radial amplitude", "c": "cos(t*3/4)*4  # vertical amplitude", "d": [],
"X": "a*sin(t)+b*sin(t)", "Y": "a*cos(t)+b*cos(t)", "Z": "c",
"t_min": "0.0", "t_max": "8*pi", "interval": "0.1"},

"para_curve": {"a": "10 #radius plane", "b": "4 #period", "c": "3 #amplitude", "d": ["(a+c*sin(b*t+pi/2)) #formula"],
"X": "cos(t)*d1 #polar X", "Y": "sin(t)*d1  #polarY", "Z": "0",
"t_min": "0.0", "t_max": "2*pi", "interval": "0.1"}
}
"""
    sel = FreeCADGui.Selection.getSelection()
    if sel and sel[0].isDerivedFrom("Spreadsheet::Sheet"):
        sheet = sel[0]
    elif sel and sel[0].isDerivedFrom("App::TextDocument"):
        textDoc = sel[0]
    if not FreeCAD.ActiveDocument:
        FreeCAD.newDocument()
    pc=FreeCAD.ActiveDocument.addObject("Part::FeaturePython","ParametricCurve")
    if Parametric_Curve_FP:
        Parametric_Curve_FP.Curve(pc)
        Parametric_Curve_FP.CurveVP(pc.ViewObject)
    else: #for debugging/testing only
        Curve(pc)
        CurveVP(pc.ViewObject)
    FreeCAD.ActiveDocument.recompute()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(FreeCAD.ActiveDocument.Name,pc.Name)
    if sheet:
        pc.Spreadsheet = sheet
    elif textDoc:
        FreeCAD.Console.PrintWarning("Parametric_Curve_FP: Ensure the document has been saved since the last edit of the Text document\n")
        FreeCAD.Console.PrintMessage(f"Attempting to import:\n{textDoc.Text}\n")
        pc.Proxy.readJSONFile(pc,textDoc.Text)
    else:
        pc.Proxy.readJSONFile(pc,txt)
        FreeCADGui.SendMsgToActiveView("ViewSelection",True)


if __name__ == "__main__":
    import importlib
    import Parametric_Curve_FP
    importlib.reload(Parametric_Curve_FP)
    makeCurve(Parametric_Curve_FP)

