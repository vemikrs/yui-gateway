---
doc_type: appendix
status: draft
owner: vemikrs
created: 2025-09-20
updated: 2025-09-22
since: v0.2.0
related:
  - meta/MANIFESTO.md
  - notes/manifesto.personal.md
  - meta/FOCUS.md
  - meta/ETHICS.md
  - meta/appendix/abstract.terms.md
---

# YuiHub Lexicon v0.2.0

この辞書は、YuiHubにおける用語を正規化し、思想の膨張や比喩の乱立を防ぐための**ガードレール**である。  
用語は **Core / Principles / Extended / Background** の四区分で整理する。  
抽象語（思想源泉）は `meta/appendix/abstract.terms.md` に分離し、本書から参照する。  

---

## Core Terms（必須）

### Fragment（断片）
即興的に生まれる気づきやアイデアの最小単位。  
保存されることで後にKnotへ発展する。

### Knot（結節）
意思決定や根拠をまとめた最小のまとまり。  
Fragmentを選び取り、再訪や共有の起点になる。

### Thread（筋）
複数のKnotが連なった意図の流れ。  
思想の「筋道」を表す。

### Context Packet
Fragment / Knot / Thread を実装に橋渡しする翻訳層。  
Intent, Prior Decisions, Constraints, Evidence, Open Questions, Next Action で構成される。

### Modes（旗）
- **Shelter Mode（避難所）**: 思想を守り、安心と連続性を優先する旗。  
- **Signal Mode（発信）**: 思想を翻訳し、他者に共有・協働する旗。  
  - Mode ＝ 安心のための「振る舞いの旗」。  

---

## Principles（原則）
思想と実装をつなぐ基盤。Contractを導き、Specの調整に影響する。  

- **Continuity over Velocity**: 速度よりも連続性を優先する。  
- **Traceability by Design**: 辿れる形で記録を設計に組み込む。  
- **Small-to-Stable**: 小さく残し、安定させてから広げる。  
- **Intent > Implementation**: 実装は意図の従属物。  
- **Revisit is a Feature**: 見返せることを機能価値とみなす。  

### Invariants（不変条件）
Lexiconでは概要のみ記載し、具体は meta/ETHICS.md にて定義する。  

### Anti-Goals（アンチゴール）
Lexiconでは参照のみとし、具体は meta/FOCUS.md にて定義する。  

---

## Extended Terms（拡張）

### Spec（仕様）
- システムやAPI全体の設計図。  
- 要件・機能・非機能・制約などを含む広い概念。  
- 可変性が高く、開発の過程で更新される。  

### Contract（コントラクト）
- Specの中から「相互に守るべき最小単位」を抜き出したもの。  
- API入出力形式や必須フィールド、返却ルールなどを含む。  
- 不変性が高く、変更にはバージョニングが必要。  
- Principlesに基づいて定義され、Specを導く基盤になる。  

### Idea-First（思想ファースト）
成果物よりも、思想の痕跡を外部に残すことを優先する方針。  

### Intent Thread（意図の筋）
Threadの中でも、選択理由が鎖のように連なり、意図が継続する状態を強調した表現。  

### DoD（Definition of Done／受け渡し規格）
思想を成果物に確実に結びつけるための最低限のルール。  
Context Packetを付与し、成果物と照合し、重要判断はKnot化する。  

### YuiFlow Framework（YuiFlow）
思想を「型」として翻訳する枠組み。  
Hub（具象の場）に対する Flow（思想の型）の関係を明示する。  

---

## Background Terms（背景）

### 結（Yui）
「結ぶ／共同する／命をつなぐ」の日本語的由来。  
YuiHubの象徴的モチーフであり、KnotやThreadの背景にある世界観を支える。

### 思想の翻訳層
会話（設計意図）と実装（成果物）の間に必要な媒介層。  
Context Packetという仕組みで実現される。

### 創造一般（General Creativity）
プログラミングに限らず、絵・音楽・言葉など人間のあらゆる創造行為に拡張できるという視点。  
YuiHubの思想の射程を広げるキーワード。  
