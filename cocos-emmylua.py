import os
import sys
import re
import argparse
parser=argparse.ArgumentParser()
parser.description="trans cocos tolua++ lua api to emmylua api"
parser.add_argument("-i","--input",help="input dir path",type=str)
parser.add_argument("-o","--output",help="output file path",type=str)
parser.add_argument("-p","--pakage",help="is out as one file",type=bool)
args=parser.parse_args()

inputPath=args.input or "api"
outPath=args.output or "out"
pk=args.pakage

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
{0}.{1}={1}

"""
#---@alias {1} {0}.{1}

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
    "bool":"boolean",
    "cc.backend::ProgramState":"cc.backend.ProgramState",
    "cc.backend::Buffer":"cc.backend.Buffer",
    "cc.backend::TextureBacken":"cc.backend.TextureBacken",
    "cc.backend::UniformLocation":"cc.backend.UniformLocation",
    "cc.backend::Program":"cc.backend.Program",
    "cc.backend::TextureBackend":"cc.backend.TextureBackend",
    "cc.backend::ShaderCache":"cc.backend.ShaderCache",
    "cc.backend::ShaderModule":"cc.backend.ShaderModule",
    "cc.backend::Texture2DBackend":"cc.backend.Texture2DBackend",
    "cc.backend::SamplerDescriptor":"cc.backend.SamplerDescriptor",
    "cc.backend::TextureDescriptor":"cc.backend.TextureDescriptor",
    "cc.backend::SamplerDescripto":"cc.backend.SamplerDescripto",
    "cc.backend::TextureCubemapBackend":"cc.backend.TextureCubemapBackend",
    "cc.backend::TextureCubemapBackend":"cc.backend.TextureCubemapBackend",
    "cc.backend::VertexLayout":"cc.backend.VertexLayout",


}
#空着
defineClass=set([
    "number",
    "table",
    "string",
    "boolean",
    "nil",
    "function",
    "userdata",
    "self"
])
#自己写，也可以不写
#用来给未定义的类型比如int，提供alias或者class声明
unDefineClass={

}
#喜欢可以自己写，不写会自己推断
Namespace={

}
#不要管
Alias={
    
}
FirstWrite="""
---require emmylua 0.3.36
"""

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

class FunctionComment:
    def __init__(self):
        self.name=""
        self.parent=""
        self.params=[]
        self.overload=[]
        self.rtype="void"
        self.comment=[]
        self.paramsTypes=[]

    def implement(self):
        if len(self.overload)!=0: 
            newOverload=[]   
            for comment in self.overload:
                params=[]
                index=0
                for param in comment.split(","):
                    param=transferDisableType(param.strip())
                    if param=="self":
                        continue
                    if param==self.paramsTypes[index]:
                        params.append(self.paramsTypes[index]+":"+param)
                    else:
                        params.append(self.paramsTypes[index]+str(index)+":"+param)
                    index=index+1
                rtype="self" if Alias.get(self.rtype)==Alias.get(self.parent) else self.rtype
                newOverload.append("---@overload fun({0}):{1}".format(",".join(params),rtype))

            self.overload=newOverload
    def dump(self):
        if self.name=="":
            return ""
        result=[]
        if len(self.comment)!=0:
            result.append("\n".join(self.comment))
        if len(self.overload)!=0:
            result.append("\n".join(self.overload))
        if len(self.params)!=0:
            result.append("\n".join(["---@param {0} {1}".format(param,paramType)  for param,paramType in zip(self.params,self.paramsTypes)   ]))
        rtype=self.rtype
        if Alias.get(rtype)==Alias.get(self.parent):
            result.append("---@return self")
        else:
            result.append("---@return {0}".format(rtype))
        result.append("function {0}:{1} ({2}) end".format(self.parent,self.name, ",".join(self.params)))
        return "\n".join(result)
class ClassComment:
    def __init__(self):
        self.name=""
        self.parent=""
        self.extend=""
        self.func=FunctionComment()
        self.results=[]

    def append(self,head,comment):
        if head=="module":
            self.name=comment.strip()
        elif head=="extend":
            self.extend=comment.strip()
        elif head=="parent_module":
            self.parent=comment.strip()
            if self.parent not in Namespace:
                Namespace[self.parent]="---@class {0}\n{0}={{}}\n".format(self.parent)
        elif head=="function":
            mc=FunctionRe.match(comment)
            parent=mc.group('parent')
            func=mc.group('func')
            func=transferDisableFuncName(func)
            self.func.name=func
            self.func.parent=parent
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
            self.func.params.append(param.strip())
            self.func.paramsTypes.append(ctype.strip())
            #self.stack.append("---@param {0} {1}@{2}".format(param,ctype,subComment))                
        elif head=="return":
            mc=returnRe.match(comment)
            rtype=mc.group('rtype')
            rtype=transferDisableType(rtype)
            subComment=comment
            self.func.rtype=rtype
            #self.stack.append("---@return {0}@{1}".format(rtype,subComment))    
        elif head=="normal":
            self.func.comment.append("---* "+comment)
        elif head=="overload":
            self.func.overload.append(comment)

    def implement(self):
        self.func.implement()
        self.results.append(self.func)
        self.func=FunctionComment()

    def dump(self):
        self.implement()
        if self.parent=="":
            return ""

        defineClass.add("{0}.{1}".format(self.parent,self.name))
        #defineClass.add("{0}".format(self.name))
        unDefineClass.pop("{0}.{1}".format(self.parent,self.name),1)
        #unDefineClass.pop("{0}".format(self.name),1)

        
        oldextend=self.extend
        extends=self.extend.split(",")
        #emmylua当前只支持单继承
        extend=extends[0]
        extend=Alias.get(extend,"")
        
        if extend !="" :
            extend=":"+extend
        if len(extends) !=1:
            extend=extend+"@all parent class: "+oldextend
        results=[]
        results.append(commentTemplate.format(self.parent,self.name,extend))
        for func in self.results:
            results.append(func.dump())
        return "\n".join(results)

def CheckLine(line):
    mc=EmptyRe.match(line)
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
    
    file=open(filePath,'r',encoding="utf8")
    cm=ClassComment()
    for line in file.readlines():
        ParseLine(line,cm)
    file.close()
    if cm.parent is not "":
        name="{0}.{1}".format(cm.parent,cm.name) 
        aliasName=cm.name
        Alias[name]=name
        Alias[aliasName]=name
    results.append(cm)

def outFile(outPath,results):
    if pk:
        file=open(outPath+".lua",'w',encoding="utf8")
        file.write(FirstWrite+"\n")
        for _,comment in Namespace.items():
            file.write(comment)
        file.write( "\n".join([ result.dump() for result in results]))
        for _,value in unDefineClass.items():
            file.write(value+"\n\n")
        file.close()
    else:
        if not os.path.exists(outPath):
            os.mkdir(outPath)
        gl=open(outPath+"/global.lua","w",encoding="utf8")
        gl.write(FirstWrite+"\n")
        for _,comment in Namespace.items():
            gl.write(comment)
        for result in results:
            resultStr=result.dump()
            if resultStr=="":
                continue
            file=open(outPath+"/{0}.{1}".format(result.parent,result.name)+".lua","w",encoding="utf8")
            file.write(resultStr)
            file.close()
        for _,value in unDefineClass.items():
            gl.write(value+"\n\n")
        gl.close()


def ParseDir(fileDirPath,outPath):
    results=[]
    for filePath in os.listdir(fileDirPath):
        ParseFile(fileDirPath+"/"+filePath,results)
    outFile(outPath,results)


ParseDir(inputPath,outPath)
