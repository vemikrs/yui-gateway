---
doc_type: meta
status: stable
owner: vemikrs
created: 2025-09-20
updated: 2025-09-21
related:
  - meta/MANIFESTO.md
  - meta/appendix/lexicon.md
---

# Definition of Done（受け渡し規格）

> 実務寄りの参照はここに集約。Manifesto は理念を保つ。

## 最小DoD
- **Context Packetを付与**  
  - Intent / Prior Decisions / Constraints / Evidence / Open Questions / Next Action  
- **成果物とPacketの照合**  
  - 実装後に「意図との一致点」「差異と理由」を1行で記載  
- **重要な判断のKnot化**  
  - 判断理由・比較した選択肢・除外根拠を簡潔に  

## 運用リズム（軽量）
- **Before**：Packet準備 → Copilot等に渡す  
- **During**：Knotが増えたらThreadに編み込む  
- **After**：照合と差分Knot化（週次でさっと棚卸し）

## モード切替の目安
- **Shelter → Signal**  
  - 直近3サイクルで「照合差分が少・安定」  
  - 語彙がLexicon準拠でブレていない  
  - 公開時の要約・抽象化が完了  
