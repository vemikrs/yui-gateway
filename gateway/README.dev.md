# Copilot 開発コンテキスト：YuiGateway

## プロジェクト概要

YuiGateway は、Entra ID（Azure AD）認証を用いて安全に Azure OpenAI に接続する **ローカルAIプロキシ**です。
ユーザーのローカル環境または社内ネットワーク上で動作し、APIキーを直接渡さずに **トークンベース認証 + Azure OpenAI 推論** を可能にします。

このプロジェクトは、思想記録プラットフォーム [YuiHub](https://github.com/vemikrs/yuihub) における「モデル実行層」として設計されており、**AI推論の入口を安全に切り出す**ことを目的としています。

---

## 全体方針（思想に基づく開発原則）

- APIキーを露出せず、**Entra ID を通じてトークンを取得**する（MSALベース）
- OpenAI 互換の API を提供し、既存クライアント（A5M2等）がそのまま使えるようにする
- 将来的に他の LLM（ローカル／クラウド）にも切り替え可能なルーティング層を備える
- ログ・リクエストの記録は原則非公開とし、オプトインで分析可能にする
- YuiHub からの呼び出し時は Signal モード下の trigger 実行対象として動作する

---

## 実装状況（MVP達成済）

- [x] **FastAPIエンドポイント** - `/v1/chat/completions` POSTエンドポイント実装済
- [x] **設定管理** - `.env`ファイルからAzure AD認証情報を読み込み
- [x] **トークン管理** - MSALでトークン取得・キャッシュ・リフレッシュ
- [x] **Azure OpenAIプロキシ** - リクエスト転送、Bearerトークン付与
- [x] **OpenAI互換性** - model, messages, temperatureなどのパラメータサポート
- [x] **Uvicorn起動** - `gateway.routes:app`で定義、スクリプト対応

## 追加実装済機能

- [x] **自動プロビジョニング** - Azureリソース、アプリ登録、RBAC付与の全自動化
- [x] **マルチログイン** - Interactive/CLI/DeviceCode認証サポート
- [x] **デプロイメント検出** - Azure管理APIでモデル情報取得
- [x] **VS Code統合** - タスクでプロビジョニング・起動・テスト実行
- [x] **テストスイート** - 45ケースのpytestテスト、カバレッジ測定
- [x] **新旧モデル対応** - max_tokens vs max_completion_tokensの適切な使い分け

---

## 技術構成

### コア技術
- **言語**: Python 3.10+ (3.12推奨)
- **フレームワーク**: FastAPI (lifespanイベント対応)
- **認証**: Microsoft Authentication Library (MSAL)
- **HTTPクライアント**: httpx (async)
- **設定管理**: Pydantic Settings v2

### Azure SDK
- **azure-identity**: DefaultAzureCredential, InteractiveBrowserCredential
- **azure-mgmt-resource**: サブスクリプション管理
- **azure-mgmt-cognitiveservices**: Cognitive Services管理
- **azure-mgmt-authorization**: RBAC管理

### 開発ツール
- **テスト**: pytest + pytest-asyncio + pytest-mock
- **リンタ**: ruff + black
- **パッケージ管理**: Poetry
- **VS Code**: タスク統合, デバッグ設定

### 実行環境
- **ローカル**: `scripts/start_local.sh`, Uvicorn
- **Docker**: Dockerfile付属
- **CI/CD**: GitHub Actions対応

---

## 今後の拡張予定（優先度順）

### Phase 1: ストリーミング対応
- [ ] **ストリーミングレスポンス** - Server-Sent Eventsでリアルタイム応答
- [ ] **非同期処理改善** - ストリーミング用の非同期プロキシ

### Phase 2: モデルルーティング層
- [ ] **モデルスイッチャー** - 設定ベースのバックエンド切り替え
- [ ] **ローカルLLM対応** - Ollama, llama.cpp等へのルーティング
- [ ] **OpenAI API対応** - 直接OpenAIへのルーティング

### Phase 3: ログ・メトリクス
- [ ] **リクエストログ** - PIIマスキング付きログ出力
- [ ] **使用量メトリクス** - Prometheus/OpenTelemetry対応
- [ ] **コストトラッキング** - トークン使用量・料金計算

### Phase 4: 管理機能
- [ ] **Admin API** - 使用状況、トークン情報、設定管理
- [ ] **プラグインシステム** - カスタム前処理・後処理フック
- [ ] **Rate Limiting** - リクエスト频度制限機能

---

## 補足（思想ドキュメント）

このプロジェクトは思想を記録・保存するための YuiHub の設計原則に基づいています。
実装の詳細よりも、「なぜそうしたか」「どう繋がるか」の説明が優先されます。
判断の背景や選択肢の記録（Knot）を可能な限りコードコメントまたはコミットに残してください。

---
