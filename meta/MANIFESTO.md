（YuiHubに準拠した思想マニフェスト、現状の写し）

---
doc_type: meta
status: stable
owner: vemikrs
created: 2025-09-20
updated: 2025-09-21
related:
  - meta/ETHICS.md
  - meta/FOCUS.md
  - meta/DOD.md
  - meta/appendix/lexicon.md
---

# YuiHub Manifesto

## Why
AIとの対話や開発の過程で、思考は一瞬で流れ去り、根拠や判断は散逸する。  
その結果、成果物は残っても思想は途切れ、物語は失われる――**思想の空洞化**。  
YuiHubは、この空洞を埋め、**「思想が一本の筋として続いている」**状態を守るために生まれた。

## How
YuiHubは「思想ファースト」の立場から、断片を結び直し、物語として残す。  
- **Fragment**（断片）をすくい、  
- **Knot**（結節）で判断を結び、  
- **Thread**（筋）として連続させる。  
さらに **Context Packet** によって、意図や根拠を外部化し、後から再訪・再利用できるようにする。  
（用語は *meta/appendix/lexicon.md* を参照）

## What
YuiHubは「**結（Yui）**」を核に据える。  
- **結ぶ**：断片を筋へ編み、思想を連続させる  
- **残す**：結び目を外に置き、再訪と再利用を可能にする  
- **ひらく**：必要に応じて他者と共有し、協働の物語を育てる

### Modes
- **Shelter Mode（避難所）**  
  自分の安心と安定を守るモード。  
  Fragment→Knot→Threadに集中し、筋を切らさない。  
  設計的には「内部に留める」ことを優先し、公開範囲は *internal* を既定とする。  
  （将来は *detail=minimal, external_io=blocked* を既定とする予定）

- **Signal Mode（発信）**  
  外に伝えるモード。  
  PacketやThreadを翻訳し、OSS貢献や協働へつなげる。  
  設計的には「外に出す」ことを優先し、公開範囲は *partner / public* を既定とする。  
  （将来は *detail=standard|rich, external_io=allowed* を既定とする予定）

---

YuiHubは、思想を守る **避難所（Shelter）** であると同時に、  
次の創造を開く **発信の場（Signal）** でもある。  

PoCでは Mode を“旗”として掲げつつ、制御は **公開範囲（visibility）** のみに絞る。  
将来的には「情報の粒度（detail）」や「外部送信方針（external_io）」も組み込み、  
安心のための二層的なモード設計へと拡張していく。

---

## Appendix（軽量・可変）
> Manifesto 本文は安定、Appendix は進化する領域とする。

### A. アンチゴール
- 速度だけを最大化する短期ハックは対象外。  
- 完全自動化は目的ではない。思想の翻訳と連続性を優先する。  

### B. 不変条件（Invariants）
- 判断は**根拠に即時参照**できること。  
- 再訪すれば**結論が再現**できること。  
（この二つが欠ければ、思想の筋は断絶したとみなす）

### C. 前提と依存
- 技術前提：LLM / MCP / VCS 等  
- 社会前提：OSSガバナンス / ライセンス  
※ 思想の枠組み（**結ぶ**）は前提に依存しない。

### D. 語彙の境界（概要）
- Fragment = 即興の断片（Issue/ログとは異なる）  
- Knot = 意思決定の結び目（軽量ADR）  
- Thread = 意図の連なり（PRDより流動的）  
→ 詳細は *meta/appendix/lexicon.md* を参照。
