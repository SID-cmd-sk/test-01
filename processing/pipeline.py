from __future__ import annotations
import hashlib, json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
import cv2, numpy as np
from PIL import Image
from pypdf import PdfReader
import ezdxf

class Stage(str, Enum):
    INGEST="ingest"; PREPROCESS="preprocess"; GEOMETRY="geometry_detection"; OCR="ocr_dimension_parsing"; RECONSTRUCT="vector_reconstruction"; EXPORT="export"
STAGE_ORDER=[Stage.INGEST,Stage.PREPROCESS,Stage.GEOMETRY,Stage.OCR,Stage.RECONSTRUCT,Stage.EXPORT]

@dataclass(frozen=True)
class JobConfig:
    input_pdf:str; output_dir:str; dpi:int=300; denoise_strength:int=2; adaptive_threshold_block:int=31; adaptive_threshold_bias:int=7; snap_tolerance:float=1.25; collinearity_angle_tolerance:float=1.0
@dataclass
class StageResult: stage:Stage; payload:dict[str,Any]
@dataclass
class JobState: config_hash:str; completed_stages:list[str]=field(default_factory=list)

class ProcessingPipeline:
    def __init__(self, config: JobConfig):
        self.config=config; self.out_dir=Path(config.output_dir); self.state_file=self.out_dir/"state.json"; self.stage_dir=self.out_dir/"stages"
    def run(self)->None:
        self.out_dir.mkdir(parents=True,exist_ok=True); self.stage_dir.mkdir(parents=True,exist_ok=True); st=self._load_state()
        for stage in STAGE_ORDER:
            if stage.value in st.completed_stages: continue
            res=self._run_stage(stage); (self.stage_dir/f"{stage.value}.json").write_text(json.dumps(res.payload,indent=2)); st.completed_stages.append(stage.value); self._save_state(st)
    def _config_hash(self)->str: return hashlib.sha256(json.dumps(asdict(self.config),sort_keys=True).encode()).hexdigest()
    def _load_state(self)->JobState:
        if not self.state_file.exists(): return JobState(self._config_hash())
        p=json.loads(self.state_file.read_text()); return JobState(**p) if p.get("config_hash")==self._config_hash() else JobState(self._config_hash())
    def _save_state(self,s:JobState): self.state_file.write_text(json.dumps(asdict(s),indent=2))
    def _read(self, stage:Stage): return json.loads((self.stage_dir/f"{stage.value}.json").read_text())
    def _run_stage(self,stage): return StageResult(stage, getattr(self,f"_run_{stage.value.replace('geometry_detection','geometry').replace('ocr_dimension_parsing','ocr').replace('vector_reconstruction','reconstruct')}")())
    def _run_ingest(self):
        p=Path(self.config.input_pdf); ext=p.suffix.lower();
        if ext==".pdf":
            reader=PdfReader(str(p)); vector=any(bool(pg.get('/Contents')) for pg in reader.pages)
            pages=[{"page_index":i,"is_vector":vector} for i,_ in enumerate(reader.pages)]
        else: pages=[{"page_index":0,"is_vector":False}]
        return {"input":str(p),"pages":pages}
    def _run_preprocess(self):
        p=Path(self.config.input_pdf); img=cv2.imread(str(p),cv2.IMREAD_GRAYSCALE) if p.suffix.lower()!=".pdf" else np.full((1200,1600),255,np.uint8)
        blur=cv2.medianBlur(img,3); bw=cv2.adaptiveThreshold(blur,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,7)
        out=self.out_dir/"preprocessed.png"; cv2.imwrite(str(out),bw); return {"preprocessed":str(out)}
    def _run_geometry(self):
        img=cv2.imread(str(self.out_dir/"preprocessed.png"),cv2.IMREAD_GRAYSCALE)
        lines=cv2.HoughLinesP(255-img,1,np.pi/180,60,minLineLength=20,maxLineGap=5)
        entities=[]
        if lines is not None:
            for i,l in enumerate(lines[:500]): x1,y1,x2,y2=l[0]; entities.append({"id":f"L{i}","type":"line","p1":[int(x1),int(y1)],"p2":[int(x2),int(y2)],"confidence":0.8})
        return {"entities":entities}
    def _run_ocr(self): return {"recognized":[]}
    def _run_reconstruct(self): return {"entities":self._read(Stage.GEOMETRY)["entities"],"uncertain":[e for e in self._read(Stage.GEOMETRY)["entities"] if e["confidence"]<0.7]}
    def _run_export(self):
        rec=self._read(Stage.RECONSTRUCT); doc=ezdxf.new('R2010');
        for name in ["GEOMETRY","TEXT","DIMENSIONS","UNCERTAIN"]:
            if name not in doc.layers: doc.layers.add(name)
        msp=doc.modelspace()
        for e in rec["entities"]: msp.add_line(tuple(e["p1"]),(e["p2"]),dxfattribs={"layer":"GEOMETRY"})
        out=self.out_dir/"output.dxf"; doc.saveas(out); return {"dxf":str(out),"layers":["GEOMETRY","TEXT","DIMENSIONS","UNCERTAIN"]}
