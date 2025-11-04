---
doc_type: meta
status: stable
owner: vemikrs
created: 2025-09-21
updated: 2025-09-21
related:
  - meta/MANIFESTO.md
  - meta/ETHICS.md
---

# FOCUS — PoCにおける焦点とDoD

## 1. 焦点（Focus）
YuiHub PoCの焦点は、**思想の筋を途切れさせないこと**と、  
そのための仕組みとして **Context Packetを生成し、Agent AI（例: Copilot）へ伝搬できるUXを確認すること** にある。  

---

## 2. DoD（Definition of Done）
以下の3点を満たすことをもってPoCの成功とする。  

1. **Packet生成ができる**  
   - ChatGPT等の対話AIで、Fragment→Knot→Threadを整理し、  
     Context Packet（Intent / Prior Decisions / Constraints / Evidence / Open Questions / Next Action）が作成されること。  

2. **PacketをAgent AIに伝搬できる**  
   - Context PacketがAgent AI（Copilot等）に形式上渡され、受け渡しが成立すること。  

3. **Agent AIがPacketを認識して動作する**  
   - Agent AIがPacketを受領し、少なくとも解釈・実装の起点として扱えること。  

---

## 3. スコープ外（Out of Scope / Anti-Goals）
- **短期速度ハック**：速度最大化のために思想を省略する開発は対象外。  
- **完全自動化**：思想の翻訳・連続性が保証されない全自動ワークフローはPoCの範囲外。  
- **思想なき実装**：成果物だけが残り、根拠や判断過程が欠落する状態は避ける。  

---

## 4. 備考
- 本PoCは **Shelter Mode** を優先し、思想の筋を保全するための基盤確認に重きを置く。  
- Signal Mode（外部発信）は本フェーズの対象外とする。  
