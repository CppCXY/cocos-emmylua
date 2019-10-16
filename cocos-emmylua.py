import os
import sys
import re
import argparse
parser=argparse.ArgumentParser()
parser.description="trans cocos tolua++ lua api to emmylua api"
parser.add_argument("-i","--input",help="input dir path",type=str)
parser.add_argument("-o","--output",help="output file path",type=str)
args=parser.parse_args()

inputPath=args.input
outPath=args.output

EmptyRe=re.compile(r'^\s*$')
NormalRe=re.compile(r'^\s*--\s(?!@)(?P<comment>.*)')
SpeicalRe=re.compile(r'^\s*--\s@(?P<head>\S+)(?P<comment>.*)')
EndRe=re.compile(r'^----.+')
FunctionRe=re.compile(r'\s*\[parent=#(?P<parent>[^\]]+)\]\s*(?P<func>\w+)')
ParamRe=re.compile(r'\s*((#(?=unsigned)(?P<ptype_u>unsigned [\w.:]+))|(#)(?P<ptype>[\w.:]+))?\s*(?P<param>\w+)\s*(?P<subComment>.+)?')
returnRe=re.compile(r'.+\(return\s+value:\s*(?P<rtype>[^\)]+)\)')
commentTemplate="""

---@class {0}.{1} {2}
local {1}={{ }}
---@class {1} : {0}.{1}
{0}.{1}={1}

"""


transFunc={
    "end":"endToLua"
}
transParam={
    "repeat":"_repeat",
    "end" : "_end"
}
transType={
    "cc.experimental::TMXTiledMap":"ccexp.TMXTiledMap",
    "cc.experimental::TMXLayer":"ccexp.TMXLayer",
    "cc.experimental::ui::VideoPlayer":"ccexp.VideoPlayer",
    "cc.experimental::AudioEngine":"ccexp.AudioEngine",
    "cc.experimental::AudioProfile":"ccexp.AudioProfile",
    "cc.experimental::ui::WebView":"ccexp.WebView",
    "cc.RenderState::StateBlock":"cc.RenderState.StateBlock",
    "cc.experimental::Viewport":"ccexp.Viewport",
    "cc.experimental::FrameBuffer":"ccexp.FrameBuffer",
    "cc.TrianglesCommand::Triangles":"cc.TrianglesCommand.Triangles",
    "cc.Texture2D::_TexParam":"cc.Texture2D._TexParam",
    "cc.Terrain::DetailMap":"cc.Terrain.DetailMap",
    "cc.Terrain::TerrainData":"cc.Terrain.TerrainData",
    "unsigned int":"unsigned_int",
    "unsigned char":"unsigned_char",
    "bool":"boolean"
}
#空着
defineClass=set([
    "number",
    "table",
    "string",
    "boolean",
    "nil",
    "function",
    "userdata"
])
#自己写，也可以不写
#用来给未定义的类型比如int，提供alias或者class声明
unDefineClass={

}
#喜欢可以自己写，不写会自己推断
Namespace={

}

def transferDisableType(name):

    result=transType.get(name,None)
    result=result if result is not None else name

    if result not in defineClass:
        unDefineClass[result]="---@class {0}".format(result) 
    return result

def transferDisableParam(name):
    result=transParam.get(name,None)
    return result if result is not None else name

def transferDisableFuncName(name):
    result=transFunc.get(name,None)
    return result if result is not None else name



class ClassComment:
    def __init__(self):
        self.name=""
        self.parent=""
        self.extend=""
        self.stack=[]
        self.currentFunction=""
        self.params=[]
        self.paramTypes=[]
        self.results=[]
        self.overload=[]
        self.rtype="void"

    def append(self,head,comment):
        if head=="module":
            self.name=comment.strip()
        elif head=="extend":
            if comment.find(","):
                self.extend=": "+comment.replace(",","@",1)
            else:
                self.extend=": "+comment
        elif head=="parent_module":
            self.parent=comment.strip()
        elif head=="function":
            mc=FunctionRe.match(comment)
            parent=mc.group('parent')
            func=mc.group('func')
            func=transferDisableFuncName(func)
            self.currentFunction=parent+":"+func
        elif head=="param":
            mc=ParamRe.match(comment)
            param=mc.group('param')
            if param=="self":
                return
            ctype=mc.group('ptype_u')
            if ctype is None:
                ctype=mc.group('ptype')
                if ctype is None:
                    ctype="any"
            ctype=transferDisableType(ctype)
            param=transferDisableParam(param)
            subComment=mc.group('subComment')
            if subComment is None:
                subComment=comment
            self.params.append(param.strip())
            self.paramTypes.append(ctype.strip())
            self.stack.append("---@param {0} {1}@{2}".format(param,ctype,subComment))                
        elif head=="return":
            mc=returnRe.match(comment)
            rtype=mc.group('rtype')
            rtype=transferDisableType(rtype)
            subComment=comment
            self.rtype=rtype or "void"
            self.stack.append("---@return {0}@{1}".format(rtype,subComment))    
        elif head=="normal":
            self.stack.append("---* "+comment)
        elif head=="overload":
            self.overload.append(comment)

    def implement(self):
        if self.currentFunction!="":
            self.results.append("\n".join(self.stack))
            if len(self.overload)!=0:
                
                for comment in self.overload:
                    params=[]
                    index=0
                    for param in comment.split(","):
                        param=transferDisableType(param.strip())
                        if param=="self":
                            continue
                        if param==self.paramTypes[index]:
                            params.append(self.params[index]+":"+param)
                        else:
                            params.append("unkown"+str(index)+":"+param)
                        index=index+1
                    self.results.append("---@overload fun({0}):{1}".format(",".join(params),self.rtype))
                self.overload=[]
            self.results.append("function {0}({1}) end".format(self.currentFunction,",".join(self.params)))
            self.params=[]
            self.paramTypes=[]
            self.rtype="void"
            self.currentFunction=""
            self.stack=[]

    def dump(self,results):
        self.implement()

        if self.parent=="":
            return

        defineClass.add("{0}.{1}".format(self.parent,self.name))
        defineClass.add("{0}".format(self.name))
        unDefineClass.pop("{0}.{1}".format(self.parent,self.name),1)
        unDefineClass.pop("{0}".format(self.name),1)
        if self.parent not in Namespace:
            Namespace[self.parent]="---@class {0}\n{0}={{}}\n".format(self.parent)
        results.append(commentTemplate.format(self.parent,self.name,self.extend))
        results.append("\n".join(self.results))

def CheckLine(line):
    mc:re.Match=EmptyRe.match(line)
    if mc is not None:
        return "EMPTY_LINE",None
    mc=NormalRe.match(line)
    if mc is not None:
        return "NORMAL_LINE",mc
    mc=SpeicalRe.match(line)
    if mc is not None:
        return "SPECIAL_LINE",mc
    mc=EndRe.match(line)
    if mc is not None:
        return "END_LINE",None
    return None,None

def ParseLine(line,comment):
    szType,mc=CheckLine(line)
    if szType=="NORMAL_LINE":
        comment.append("normal",mc.group('comment'))
    elif szType=="SPECIAL_LINE":
        head=mc.group('head')
        comment.append(head,mc.group('comment'))
    elif szType=="END_LINE":
        comment.implement()

def ParseFile(filePath,results):
    #results=[]
    file=open(filePath,'r',encoding="utf8")
    cm=ClassComment()
    for line in file.readlines():
        ParseLine(line,cm)
    file.close()
    cm.dump(results)

    #file=open(outPath,'w',encoding="utf8")
    #cm.dump(file)
    #file.close()


def ParseDir(fileDirPath,outPath):
    results=[]
   
    for filePath in os.listdir(fileDirPath):
        ParseFile(fileDirPath+"/"+filePath,results)
    file=open(outPath+".lua",'w',encoding="utf8")
    for _,comment in Namespace.items():
        file.write(comment)
    file.write("\n".join(results))
    for _,value in unDefineClass.items():
        file.write(value+"\n\n")
    file.close()

ParseDir(inputPath,outPath)
