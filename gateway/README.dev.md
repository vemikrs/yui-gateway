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

## 要件（MVP）

- [ ] FastAPI を使って `/v1/chat/completions` POST エンドポイントを定義する  
- [ ] `.env` ファイルから Azure AD の認証情報を読み込み、トークンを取得する  
  - `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`, `SCOPE`, `AZURE_OPENAI_ENDPOINT`
- [ ] リクエストを Azure OpenAI API に転送し、応答をクライアントに返す  
  - Authorization: Bearer トークンをヘッダに付けること  
  - OpenAI互換の JSON構造（model, messages, temperatureなど）で受け取る
- [ ] FastAPI `app` は `gateway.routes:app` に定義する（Uvicorn起動対象）

---

## 技術構成

- 言語：Python 3.10+
- フレームワーク：FastAPI
- 認証：Microsoft Authentication Library (MSAL)
- HTTP通信：httpx
- 起動方法：`scripts/start_local.sh` または Docker

---

## 今後の拡張予定（念頭に置いて）

- ログ出力（リクエスト／レスポンスのマスキング付き記録）
- モデルの切り替えルーティング（Azure以外のバックエンドを追加）
- `plugin/` ディレクトリでモデル切替やカスタム後処理をサポート
- `admin/` API で使用状況やトークンの管理
- OpenTelemetry or Prometheus でメトリクス計測

---

## 補足（思想ドキュメント）

このプロジェクトは思想を記録・保存するための YuiHub の設計原則に基づいています。  
実装の詳細よりも、「なぜそうしたか」「どう繋がるか」の説明が優先されます。  
判断の背景や選択肢の記録（Knot）を可能な限りコードコメントまたはコミットに残してください。

---
