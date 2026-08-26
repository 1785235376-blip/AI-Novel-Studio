from __future__ import annotations
import re
from dataclasses import dataclass

def markdown_to_document(markdown:str)->dict:
    nodes=[]
    for block in re.split(r"\n\s*\n",markdown.strip()):
        if not block: continue
        match=re.match(r"^(#{1,6})\s+(.*)$",block,re.S)
        if match: nodes.append({"type":"heading","attrs":{"level":len(match.group(1))},"content":[{"type":"text","text":match.group(2).strip()}]}); continue
        if block.startswith("```"):
            lines=block.splitlines(); nodes.append({"type":"codeBlock","attrs":{"language":lines[0][3:] or None},"content":[{"type":"text","text":"\n".join(lines[1:-1])}]}); continue
        nodes.append({"type":"paragraph","content":[{"type":"text","text":block.replace("\n","\n")}]})
    return {"type":"doc","content":nodes}

def document_to_markdown(doc:dict)->str:
    blocks=[]
    for node in doc.get("content",[]):
        text="".join(x.get("text","") for x in node.get("content",[]))
        if node.get("type")=="heading": blocks.append("#"*int(node.get("attrs",{}).get("level",1))+" "+text)
        elif node.get("type")=="codeBlock": blocks.append("```"+(node.get("attrs",{}).get("language") or "")+"\n"+text+"\n```")
        else: blocks.append(text)
    if not blocks:return ""
    return "\n\n".join(blocks)+"\n\n"

def plain_text(doc:dict)->str:
    return "\n".join("".join(x.get("text","") for x in n.get("content",[])) for n in doc.get("content",[]))
