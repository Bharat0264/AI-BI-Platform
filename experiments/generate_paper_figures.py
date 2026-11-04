"""Render code-native AURA-BI diagrams from implemented contracts and measured artifacts."""
from __future__ import annotations
import json, os, textwrap
from pathlib import Path
os.environ.setdefault("MPLBACKEND","Agg"); os.environ.setdefault("MPLCONFIGDIR","/private/tmp/aura-mpl")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/paper_figures"; EVIDENCE=ROOT/"outputs/paper_evidence"
COLORS={"legacy":"#d9e2f3","research":"#d8ead3","verify":"#fff2cc","blocked":"#f4cccc","pending":"#e7e6e6","external":"#eadcf8"}

def diagram(name,title,nodes,edges,notes=(),size=(12,6)):
 fig,ax=plt.subplots(figsize=size);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis("off");ax.set_title(title,fontsize=14,fontweight="bold",pad=14)
 for key,label,x,y,kind in nodes:
  # A compact fixed grid keeps labels legible at IEEE column scale.  Explicit
  # newlines are retained; long labels get deterministic wrapping rather than
  # being allowed to run through a neighbouring component.
  w=.12;h=.12; rendered="\n".join(textwrap.fill(line, width=17, break_long_words=False, break_on_hyphens=False) for line in label.split("\n"))
  ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle="round,pad=0.012",fc=COLORS[kind],ec="#334155",lw=1))
  ax.text(x,y,rendered,ha="center",va="center",fontsize=6.4,linespacing=1.05)
 for a,b,caption in edges:
  start=next(n for n in nodes if n[0]==a);end=next(n for n in nodes if n[0]==b)
  dx,dy=end[2]-start[2],end[3]-start[3]
  # Stop arrows at the source/target rectangle boundary instead of drawing
  # through labels.  The same geometry is used for every rendered vector.
  t=min(.06/max(abs(dx),1e-9), .06/max(abs(dy),1e-9))
  source=(start[2]+dx*t,start[3]+dy*t); target=(end[2]-dx*t,end[3]-dy*t)
  ax.annotate("",xy=target,xytext=source,arrowprops=dict(arrowstyle="->",lw=1,color="#475569"))
  if caption: ax.text((start[2]+end[2])/2,(start[3]+end[3])/2+.025,caption,fontsize=6,ha="center",color="#475569")
 for i,note in enumerate(notes):ax.text(.01,.015+i*.025,note,fontsize=6.5,color="#475569",ha="left")
 for suffix in ("png","svg","pdf"):fig.savefig(OUT/f"{name}.{suffix}",dpi=300 if suffix=="png" else None,bbox_inches="tight")
 plt.close(fig)
 # Mermaid is an editable source description corresponding to the rendered diagram.
 lines=["flowchart LR"]+[f'  {k}["{label.replace(chr(10)," ")}"]' for k,label,*_ in nodes]+[f"  {a} -->|{c}| {b}" if c else f"  {a} --> {b}" for a,b,c in edges]
 (OUT/f"{name}.mmd").write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 diagram("fig01_system_architecture","AURA-BI system architecture",[("u","User / browser",.05,.55,"legacy"),("f","Flask + static UI",.19,.55,"legacy"),("a","Authentication + dataset context",.34,.55,"verify"),("m","MongoDB\naccounts/datasets/evidence",.49,.78,"external"),("c","Semantic schema + planner",.49,.48,"research"),("d","Deterministic analytics",.63,.48,"research"),("v","Evidence verifier",.77,.48,"verify"),("s","SIIE",.63,.25,"research"),("e","EVVE",.77,.25,"research"),("g","Dashboard consistency",.89,.25,"research"),("p","Selective publication",.89,.55,"verify"),("r","Research PDF + JSON manifest",.89,.78,"research")],[ ("u","f",""),("f","a",""),("a","m","persist"),("a","c","dataset"),("c","d","plan"),("d","v","evidence"),("v","s","ambiguity"),("v","e","values"),("s","e","conditional"),("e","g","contracts"),("g","p","gate"),("p","r","verified only")],("Blue: legacy application path. Green: additive research workflow.",))
 diagram("fig02_nlp_pipeline","Implemented question-processing pipeline",[("q","Natural-language question",.06,.5,"legacy"),("x","parse_question\nsupported grammar",.2,.5,"verify"),("s","SemanticSchemaEngine\ncolumns + corrections",.34,.5,"research"),("i","Metric candidates\n/ exact selection",.48,.5,"research"),("p","Analytics plan",.62,.5,"research"),("d","Pandas deterministic computation",.76,.5,"research"),("v","EvidenceClaim + verifier",.9,.5,"verify"),("l","Optional Gemini narrator\nNOT_VERIFIED",.76,.2,"pending")],[("q","x",""),("x","s","grounding"),("s","i","roles"),("i","p","ambiguous → alternatives"),("p","d",""),("d","v",""),("v","l","compact evidence only")],("No transformers, embeddings, learned intent classifier, or LLM-generated code/SQL are used in this path.",))
 diagram("fig03_research_methodology","Research methodology and current status",[("p","UCI procurement\nCOMPLETED",.08,.55,"research"),("v","Checksum/schema validation\nCOMPLETED",.23,.55,"verify"),("q","Developer task preparation\nCOMPLETED",.38,.55,"research"),("h","Independent human annotation\nPENDING",.53,.55,"pending"),("a","Adjudication + freeze\nPENDING",.68,.55,"pending"),("b","Matched B0–B4\nPENDING",.83,.55,"pending"),("m","Metrics + clustered statistics\nPENDING",.83,.25,"pending")],[("p","v",""),("v","q",""),("q","h",""),("h","a","two annotators"),("a","b","frozen corpus"),("b","m","")],("Developer-only measured checks are separate and cannot replace pending independent stages.",))
 diagram("fig04_siie_workflow","SIIE internal workflow",[("q","Ambiguous business question",.08,.5,"legacy"),("c","Candidate definitions\n≤32",.25,.5,"research"),("a","Independent deterministic computations",.43,.5,"research"),("n","Aggregate / grouped impact",.6,.68,"verify"),("r","Ranking impact",.6,.5,"verify"),("v","Chart-shape impact",.6,.32,"verify"),("g","Semantic impact graph",.78,.5,"research"),("k","Clarification required\nno selection",.92,.5,"blocked")],[("q","c",""),("c","a",""),("a","n",""),("a","r",""),("a","v",""),("n","g",""),("r","g",""),("v","g",""),("g","k","")])
 diagram("fig05_evidence_verification","Deterministic evidence verification",[("d","Dataset + version",.08,.5,"external"),("s","Selected columns\nfilters/scope",.25,.5,"research"),("o","Operation + result bindings",.42,.5,"research"),("e","AnalyticsEvidence\nID",.59,.5,"research"),("c","EvidenceClaim\npath/value/tolerance",.76,.5,"verify"),("r","SUPPORTED or\nUNSUPPORTED",.92,.5,"blocked")],[("d","s",""),("s","o",""),("o","e",""),("e","c",""),("c","r","exact binding")])
 diagram("fig06_evve_workflow","EVVE workflow",[("e","Computed evidence",.08,.5,"research"),("s","VisualizationSpecification",.25,.5,"research"),("a","Type, axes, metric, grouping",.43,.5,"research"),("n","Series oracle + alignment",.6,.5,"verify"),("p","Dataset/version/scope/provenance",.76,.5,"verify"),("r","VERIFIED / INVALID /\nAMBIGUOUS / UNSUPPORTED",.92,.5,"blocked")],[("e","s",""),("s","a",""),("a","n",""),("n","p",""),("p","r","")])
 diagram("fig07_dashboard_consistency","Dashboard semantic consistency",[("c","KPI/chart components",.08,.5,"legacy"),("d","Definition + aggregation",.25,.68,"research"),("s","Dataset/version\nscope/time",.25,.32,"research"),("u","Currency + unit",.43,.5,"research"),("i","Declared direct-comparison groups",.6,.5,"verify"),("g","Consistency issues\nsemantic graph",.77,.5,"research"),("p","Publish / clarify / reject",.92,.5,"blocked")],[("c","d",""),("c","s",""),("d","i",""),("s","i",""),("u","i",""),("i","g",""),("g","p","")],("Legitimate differences are not flagged unless components declare direct comparability.",))
 diagram("fig08_publication_gate","Selective publication decision tree",[("s","Start: pipeline output",.1,.5,"legacy"),("a","Any unresolved\nambiguity?",.32,.68,"verify"),("b","Any blocked / invalid\n/ insufficient evidence?",.55,.5,"verify"),("c","Consistency =\nPUBLISH_VERIFIED?",.75,.32,"verify"),("q","CLARIFICATION_REQUIRED",.55,.8,"blocked"),("x","BLOCKED",.75,.65,"blocked"),("p","PUBLISH_VERIFIED",.92,.32,"research")],[("s","a",""),("a","q","yes"),("a","b","no"),("b","x","yes"),("b","c","no"),("c","p","yes"),("c","x","no")],("Exact research-pipeline precedence: unresolved ambiguity → clarification; otherwise blocked/invalid evidence or non-publishable consistency → blocked.",))
 diagram("fig09_deployment_architecture","Deployment architecture (configured, not live-verified)",[("b","Browser",.08,.5,"legacy"),("f","Flask static frontend",.25,.5,"legacy"),("w","Waitress / start.py",.42,.5,"verify"),("a","Authentication + CSRF\nsecure cookies",.58,.68,"verify"),("m","MongoDB\nrequired",.75,.68,"external"),("r","PDF/JSON stream",.75,.32,"research"),("s","AURA_REPORT_DIR optional\nor ephemeral local disk",.92,.32,"pending")],[("b","f","HTTPS"),("f","w","API"),("w","a",""),("a","m","datasets/sessions"),("w","r","reports"),("r","s","storage")],("No live deployment URL or cloud storage service has been verified.",))
 diagram("fig10_experimental_comparison","Independent comparison design (pending)",[("d","Frozen external datasets\nPENDING",.08,.5,"pending"),("q","Human-authored cases\nPENDING",.25,.5,"pending"),("b","B0–B4 matched inputs\nPENDING",.45,.5,"pending"),("a","Ablations\nPENDING",.62,.5,"pending"),("m","Metrics + traces\nPENDING",.78,.5,"pending"),("s","Paired clustered analysis\nPENDING",.92,.5,"pending")],[("d","q",""),("q","b",""),("b","a",""),("a","m",""),("m","s","")],("Developer stress fixtures are excluded from this design's independent claims.",))
 diagram("fig11_report_provenance","Verified report provenance",[("q","Verified questions",.08,.5,"research"),("e","Analytical evidence records",.25,.5,"research"),("c","EVVE chart contracts",.43,.5,"research"),("g","Consistency + publication decision",.61,.5,"verify"),("p","PDF research report",.78,.65,"research"),("j","JSON manifest\nIDs/definitions/results",.78,.32,"research")],[("q","e",""),("e","c",""),("c","g",""),("g","p","PUBLISH_VERIFIED only"),("g","j","")])
 diagram("fig12_safety_case_study","Illustrative developer safety case",[("q","“What is sales by category?”",.1,.5,"legacy"),("g","Gross Sales\nsource-derived",.3,.68,"research"),("n","Net Sales proxy\nsource-derived",.3,.32,"research"),("i","Different values/ranks/\nchart shapes",.52,.5,"verify"),("c","SIIE: VALUE + RANKING +\nVISUALIZATION sensitive",.7,.5,"research"),("r","CLARIFICATION_REQUIRED\nno verified report",.9,.5,"blocked")],[("q","g","candidate"),("q","n","candidate"),("g","i",""),("n","i",""),("i","c",""),("c","r","")],("Illustrative developer-derived case; not independent evaluation or a real net-sales policy.",))
 # Measured developer-only result visualization: sources in outputs/paper_evidence.
 diagram("fig13_results","Measured developer-only results",[("n","Arithmetic: 4/4 correct\nSUPPORTED evidence",.16,.65,"research"),("a","Ambiguity: 1 clarification\n1 conditional chart",.4,.65,"verify"),("e","EVVE: verified 1\ninvalid rejected 1",.64,.65,"verify"),("d","Dashboard: publish 1\nreject 1",.86,.65,"verify"),("t","Median timing: pipeline 4.05 ms\nPDF 1.76 ms (10 runs)",.5,.3,"external")],[],("Developer-only measured fixture results. No independent baseline, ablation, or deployment-performance inference.",),size=(12,5))
 captions = '''# AURA-BI Figure Captions

All figures use a white background, accessible semantic colors, and code-native editable Mermaid sources. Figures 3, 9, 10, and 13 explicitly distinguish completed developer engineering evidence from pending independent evaluation and unverified deployment.

| Figure | IEEE-style caption | Suggested placement | Supporting implementation / records |
|---|---|---|---|
| 1 | **AURA-BI system architecture.** The legacy Flask application path is distinguished from the additive evidence-verified research workflow. | Double column; System Architecture | `server.py`, `aura/core.py`, `aura/research_pipeline.py`, `aura/visualization_engine.py`, `aura/dashboard_consistency.py`, `app/report_generator.py` |
| 2 | **Implemented question-processing pipeline.** Deterministic schema grounding, planning, computation, and evidence verification precede any optional non-authoritative narration. | Double column; Methodology | `aura/core.py`, `aura/verifier.py`, `aura/interpretations.py` |
| 3 | **Research methodology and evidence status.** Dataset preparation and developer checks are complete; independent annotation, freeze, and matched evaluation remain pending. | Double column; Experimental Setup | `benchmark/`, `docs/INDEPENDENT_EVALUATION_PROTOCOL.md`, `outputs/paper_evidence/` |
| 4 | **Semantic Interpretation Impact Engine (SIIE).** Each admissible definition is independently computed and compared before clarification is required. | Single column; Methodology | `aura/impact.py`, `aura/interpretations.py` |
| 5 | **Deterministic evidence-verification flow.** Evidence binds source data, scope, operation, result, and claim verification. | Single column; Methodology | `aura/verifier.py`, `aura/provenance.py` |
| 6 | **Evidence-Verified Visualization Engine (EVVE).** Chart contracts are validated against evidence, series, scope, and provenance. | Single column; Methodology | `aura/visualization_engine.py` |
| 7 | **Cross-dashboard semantic consistency verification.** Declared comparable components are checked for compatible semantics and scope. | Single column; Methodology | `aura/dashboard_consistency.py` |
| 8 | **Selective publication decision tree.** The unified pipeline gives unresolved ambiguity precedence, then blocks invalid evidence or non-publishable consistency. | Single column; Safety Methodology | `aura/research_pipeline.py`, `aura/dashboard_consistency.py` |
| 9 | **Configured deployment architecture.** This is an implementation diagram only; no live deployment is claimed. | Single column; Implementation | `start.py`, `server.py`, `docs/DEPLOYMENT_VALIDATION.md` |
| 10 | **Prespecified independent comparison design.** Frozen human-authored data and paired B0–B4 execution are pending. | Double column; Experimental Setup | `benchmark/freeze.py`, `experiments/independent_evaluation.py` |
| 11 | **Verified report provenance.** A publishable research report couples analytical evidence and chart contracts to a machine-readable manifest. | Single column; System Architecture | `aura/research_pipeline.py`, `app/report_generator.py`, `server.py` |
| 12 | **Illustrative developer safety case.** Alternative sales definitions can change values, rankings, and chart shapes, requiring clarification rather than selection. | Single column; Case Study | `outputs/paper_evidence/development/ambiguity_outcomes.json`, `aura/impact.py` |
| 13 | **Measured developer-only engineering checks.** Results come from reproducible development fixtures, not independent evaluation. | Double column; Engineering Validation | `outputs/paper_evidence/development/*.json`, `outputs/paper_evidence/provenance/experiment_metadata.json` |

## Technical notes

- Every `*.mmd` file is the editable structural source for its SVG/PDF/PNG counterpart. Re-run `python experiments/generate_paper_figures.py` with the supported environment to regenerate the collection.
- Figure 13 is sourced only from real development records: `deterministic_correctness.json`, `ambiguity_outcomes.json`, `evve_outcomes.json`, `dashboard_outcomes.json`, and `component_timings.json`. It intentionally excludes independent baseline, ablation, and live-deployment claims because those measurements do not exist.
- Figure 12 is illustrative and developer-derived; it is not evidence of human-annotated interpretation accuracy.
'''
 (OUT/"FIGURE_CAPTIONS.md").write_text(captions, encoding="utf-8")
if __name__=="__main__":main()
