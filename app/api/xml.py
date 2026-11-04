from xml.etree.ElementTree import Element, SubElement, tostring
from quart import Response

NS="http://s3.amazonaws.com/doc/2006-03-01/"
def xml(tag, data=None):
    root=Element(tag, xmlns=NS)
    for k,v in (data or {}).items():
        if v is not None: SubElement(root,k).text=str(v)
    return Response(tostring(root,encoding="utf-8",xml_declaration=True),status=200,content_type="application/xml")
def error(code,message,status,resource=""):
    root=Element("Error");
    for k,v in (("Code",code),("Message",message),("Resource",resource)): SubElement(root,k).text=v
    return Response(tostring(root,encoding="utf-8",xml_declaration=True),status=status,content_type="application/xml")
def response(tag, root_data=None):
    root=Element(tag,xmlns=NS)
    def add(parent,k,v):
        if isinstance(v,dict):
            child=SubElement(parent,k)
            for ck,cv in v.items(): add(child,ck,cv)
        elif v is not None: SubElement(parent,k).text=str(v)
    for k,v in (root_data or {}).items():
        if isinstance(v,list):
            wrapper = SubElement(root,k) if k == "Buckets" else root
            item_tag = "Bucket" if k == "Buckets" else k
            for item in v:
                child=SubElement(wrapper,item_tag)
                for ck,cv in item.items(): add(child,ck,cv)
        else: add(root,k,v)
    return Response(tostring(root,encoding="utf-8",xml_declaration=True),content_type="application/xml")
