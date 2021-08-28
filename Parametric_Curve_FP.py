# -*- coding: utf-8 -*-

__title__ = "3DParametricCurveFP"
__author__ = "<TheMarkster> 2021.08.27, based on macro 3D Parametric Curve by Gomez Lucio,  Modified by Laurent Despeyroux on 9th feb 2015"
__license__ = "LGPL 2.1"
__doc__ = "Parametric curve from formula"
__usage__ = """Activate the tool and modify properties as desired"""
__version__ = "2021.08.27"


import FreeCAD, FreeCADGui
from pivy import coin
from math import *
import Part

#In order to avoid using eval() and the security implications therefrom, I have borrowed and modified
#some code for using pyparsing
#https://github.com/pyparsing/pyparsing/blob/master/examples/fourFn.py
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
)
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
    """
    expop   :: '^'
    multop  :: '*' | '/'
    addop   :: '+' | '-'
    integer :: ['+' | '-'] '0'..'9'+
    atom    :: PI | E | real | fn '(' expr ')' | '(' expr ')'
    factor  :: atom [ expop factor ]*
    term    :: factor [ multop factor ]*
    expr    :: term [ addop term ]*
    """
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
        fnumber = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
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


def evaluate_stack(s,d):
    op, num_args = s.pop(), 0
    if isinstance(op, tuple):
        op, num_args = op
    if op == "unary -":
        return -evaluate_stack(s,d)
    if op in "+-*/^":
        # note: operands are pushed onto the stack in reverse order
        op2 = evaluate_stack(s,d)
        op1 = evaluate_stack(s,d)
        return opn[op](op1, op2)
    elif op == "PI":
        return math.pi  # 3.1415926535
    elif op == "E":
        return math.e  # 2.718281828
    elif op == "t":
        return d["t"]
    elif op == "a":
        return d["a"]
    elif op == "b":
        return d["b"]
    elif op == "c":
        return d["c"]
    elif op == "X":
        return d["X"]
    elif op == "Y":
        return d["Y"]
    elif op == "Z":
        return d["Z"]
    elif op in fn:
        # note: args are pushed onto the stack in reverse order
        args = reversed([evaluate_stack(s,d) for _ in range(num_args)])
        return fn[op](*args)
    elif op[0].isalpha():
        raise Exception("invalid identifier '%s'" % op)
    else:
        # try to evaluate as int first, then as float if int fails
        try:
            return int(op)
        except ValueError:
            return float(op)

def evaluate(s, d):
    exprStack[:] = []
    try:
        results = BNF().parseString(s, parseAll=True)
        val = evaluate_stack(exprStack[:],d)
    except ParseException as pe:
        raise Exception(s, "failed parse:", str(pe))
    except Exception as e:
        raise Exception (s, "failed eval:", str(e), exprStack)
    else:
        return val


class Curve:
    def __init__(self, obj):
        obj.addExtension("Part::AttachExtensionPython")
        obj.addProperty("App::PropertyString","a","Equation1(a,b,c)","a(t)").a = "37"
        obj.addProperty("App::PropertyString","b","Equation1(a,b,c)","b(a,t)").b = "1"
        obj.addProperty("App::PropertyString","c","Equation1(a,b,c)","c(a,b,t)").c = "(a+cos(a*t)*2)*b"
        obj.addProperty("App::PropertyString","X","Equation2(X,Y,Z)","X(a,b,c,t)").X = "cos(t)*c"
        obj.addProperty("App::PropertyString","Y","Equation2(X,Y,Z)","Y(a,b,c,t)").Y = "sin(t)*c"
        obj.addProperty("App::PropertyString","Z","Equation2(X,Y,Z)","Z(a,b,c,t)").Z = "0"
        obj.addProperty("App::PropertyFloat","t","T Parameters","start value for t").t = 0.0
        obj.addProperty("App::PropertyFloat","t_max","T Parameters","Max t").t_max = 2*pi
        obj.addProperty("App::PropertyFloat","Interval","T Parameters","Interval").Interval = 0.01
        obj.addProperty("App::PropertyBool","Closed","Curve","Whether curve is closed").Closed=True
        obj.addProperty("App::PropertyString","Version", "Base", "Version this object was created with").Version = __version__
        obj.addProperty("App::PropertyBool","MakeBSpline","Curve","Make BSPline if True or Polygon if False").MakeBSpline=True
        obj.addProperty("App::PropertyLink","Spreadsheet","Data","Link a spreadsheet to populate the values")
        obj.addProperty("App::PropertyBool","UpdateSpreadsheet","Data","If True data gets saved to spreadsheet, aliases created, if necessary, then this gets set back to False\nIf no spreadsheet is linked a new one is created.").UpdateSpreadsheet=False
        obj.addProperty("App::PropertyBool","UseSpreadsheet","Data","If True, poperties are readonly and must come from spreadsheet.  If false, spreadsheet is ignored and properties are set to read/write.").UseSpreadsheet=False
        obj.addProperty("App::PropertyFloat","d","Data","hidden variable used during evaluation loop").d=0
        obj.setEditorMode('d',3) #hidden
        obj.Proxy = self

    def setReadOnly(self,fp,bReadOnly):
        """if bReadOnly = True, we set the properties linked to the spreadsheet readonly, else set them normal mode"""
        if bReadOnly:
            mode = 1
        else:
            mode = 0
        if not hasattr(fp,"a"):
            return
        fp.setEditorMode('a',mode)
        fp.setEditorMode('b',mode)
        fp.setEditorMode('c',mode)
        fp.setEditorMode('X',mode)
        fp.setEditorMode('Y',mode)
        fp.setEditorMode('Z',mode)
        fp.setEditorMode('t',mode)
        fp.setEditorMode('t_max',mode)
        fp.setEditorMode('Interval',mode)

    def updateToSpreadsheet(self,fp):
        sheet = None
        if fp.Spreadsheet == None:
            sheet = FreeCAD.ActiveDocument.addObject("Spreadsheet::Sheet","PC_Sheet")
            fp.Spreadsheet = sheet

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
                fp.Spreadsheet.set('A7',"min_t")
                fp.Spreadsheet.setAlias('B7',"min_t")
                fp.Spreadsheet.set('A8',"max_t")
                fp.Spreadsheet.setAlias('B8',"max_t")
                fp.Spreadsheet.set('A9',"interval")
                fp.Spreadsheet.setAlias('B9',"interval")

        fp.Spreadsheet.set('a_cell',fp.a)
        fp.Spreadsheet.set('b_cell',fp.b)
        fp.Spreadsheet.set('c_cell',fp.c)
        fp.Spreadsheet.set('X',fp.X)
        fp.Spreadsheet.set('Y',fp.Y)
        fp.Spreadsheet.set('Z',fp.Z)
        fp.Spreadsheet.set('min_t',str(fp.t))
        fp.Spreadsheet.set('max_t',str(fp.t_max))
        fp.Spreadsheet.set('interval',str(fp.Interval))


    def updateFromSpreadsheet(self,fp):
            if not hasattr(fp.Spreadsheet,"a_cell"):
                return
            if fp.UseSpreadsheet == False:
                self.setReadOnly(fp,False)
                return
            else:
                self.setReadOnly(fp,True)

            fp.a=str(fp.Spreadsheet.a_cell)
            fp.b=str(fp.Spreadsheet.b_cell)
            fp.c=str(fp.Spreadsheet.c_cell)
            fp.X=str(fp.Spreadsheet.X)
            fp.Y=str(fp.Spreadsheet.Y)
            fp.Z=str(fp.Spreadsheet.Z)
            fp.t=fp.Spreadsheet.min_t 
            fp.t_max=fp.Spreadsheet.max_t
            fp.Interval=fp.Spreadsheet.interval 
    def onChanged(self, fp, prop):
        '''Do something when a property has changed'''
        #FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        if prop == "Spreadsheet" and fp.Spreadsheet != None:
            self.updateFromSpreadsheet(fp)
            self.setReadOnly(fp,True)
            if hasattr(fp,"UseSpreadsheet"):
                fp.UseSpreadsheet = True
        elif prop == "Spreadsheet" and fp.Spreadsheet == None:
            self.setReadOnly(fp,False)

        if prop == "UpdateSpreadsheet" and fp.UpdateSpreadsheet == True:
            self.updateToSpreadsheet(fp)
            fp.UpdateSpreadsheet = False


    def makeCurve(self, fp):
        self.updateFromSpreadsheet(fp)
        d = {"a":0,"b":0,"c":0,"X":0,"Y":0,"Z":0,"t":0}
        fa = fp.a
        fb = fp.b
        fc = fp.c
        fx = fp.X
        fy = fp.Y
        fz = fp.Z
        t = fp.t
        tf = fp.t_max
        intv = fp.Interval
        dd=(tf-t)/intv
        matriz = []
        for i in range(int(dd)):

            try:
                d["t"] = t
                value="a ->"+str(fa)
                a=evaluate(fa,d)
                d["a"]=a
                value="b ->"+str(fb)
                b=evaluate(fb,d)
                d["b"] = b
                value="c ->"+str(fc)
                c=evaluate(fc,d)
                d["c"]=c
                value="X ->"+str(fx)
                fxx=evaluate(fx,d)
                d["X"]=fxx
                value="Y ->"+str(fy)
                fyy=evaluate(fy,d)
                d["Y"]=fyy
                value="Z ->"+str(fz)
                fzz=evaluate(fz,d)
                d["Z"]=fzz
            except ZeroDivisionError:
                FreeCAD.Console.PrintError("Error division by zero in calculus of "+value+"() for t="+str(t)+" !")
            except:
                FreeCAD.Console.PrintError("Error in the formula of "+value+"() !")

            matriz.append(FreeCAD.Vector(fxx,fyy,fzz))
            t+=intv
        if fp.MakeBSpline == False and fp.Closed == True:
            matriz.append(matriz[0])
        curva = Part.makePolygon(matriz)
        if fp.MakeBSpline == True:
            #curve = Shape = Draft.makeBSpline(curva,closed=fp.Closed,face=False)
            curve = Part.BSplineCurve()
            curve.interpolate(matriz, PeriodicFlag=fp.Closed)
            curve = curve.toShape()
        else:
            curve = curva
        return curve

    def execute(self, fp):
        '''Do something when doing a recomputation, this method is mandatory'''
        fp.Shape = self.makeCurve(fp)
        #FreeCAD.Console.PrintMessage("Recompute Python Curve feature\n")

class CurveVP:
    """Creates a 3D parametric curve"""
    def __init__(self, obj):
        '''Set this object to the proxy object of the actual view provider'''
        obj.Proxy = self
 
    def attach(self, obj):
        '''Setup the scene sub-graph of the view provider, this method is mandatory'''
        self.Object = obj.Object
 
    def updateData(self, fp, prop):
        '''If a property of the handled feature has changed we have the chance to handle this here'''
        # fp is the handled feature, prop is the name of the property that has changed
        #l = fp.getPropertyByName("Length")
        #w = fp.getPropertyByName("Width")
        #h = fp.getPropertyByName("Height")
        #self.scale.scaleFactor.setValue(float(l),float(w),float(h))
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
        #FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")

 
    def getIcon(self):
        '''Return the icon in XPM format which will appear in the tree view. This method is\
                optional and if not defined a default icon is shown.'''
        return """
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

"""
 
    def __getstate__(self):
        '''When saving the document this object gets stored using Python's json module.\
                Since we have some un-serializable parts here -- the Coin stuff -- we must define this method\
                to return a tuple of all serializable objects or None.'''
        return None
 
    def __setstate__(self,state):
        '''When restoring the serialized object from document we have the chance to set some internals here.\
                Since no data were serialized nothing needs to be done here.'''
        return None



def makeCurve():
    sheet = None
    sel = FreeCADGui.Selection.getSelection()
    if sel and "Spreadsheet" in str(type(sel[0])):
        sheet = sel[0]
    if not FreeCAD.ActiveDocument:
        FreeCAD.newDocument()
    pc=FreeCAD.ActiveDocument.addObject("Part::FeaturePython","ParametricCurve")
    Curve(pc)
    CurveVP(pc.ViewObject)

    FreeCAD.ActiveDocument.recompute()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(FreeCAD.ActiveDocument.Name,pc.Name)
    if sheet:
        pc.Spreadsheet = sheet
    else:
        FreeCADGui.SendMsgToActiveView("ViewSelection")

